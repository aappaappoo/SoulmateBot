"""
这是一个基于 aiohttp 的 HTTP 服务器，用于控制 Playwright 浏览器实例。
它提供了与 openclaw 项目类似的 API 架构，支持页面导航、快照和操作。

## 依赖安装

pip install aiohttp playwright loguru
python -m playwright install chromium

## 启动方式

python browser_server.py
# 或
python -m browser_server

服务器将监听在 http://localhost:9222

## API 端点

### 统一入口（兼容现有 tools.py）
POST /browser
Body: {
    "action": "start" | "navigate" | "snapshot" | "act" | "wait" | "close",
    "url": "...",              # navigate 时使用
    "ref": "e1",               # act 时元素引用
    "actKind": "click",        # act 时操作类型
    "value": "...",            # type 时输入值
    "coordinate": "x,y",       # 备选坐标定位
    "selector": "#id",         # ★ 新增: CSS 选择器精确定位
    "frame": "iframe-name",    # ★ 新增: iframe 定位
    "targetId": "...",         # ★ 新增: 多 Tab 场景
    "waitType": "loadState",   # ★ 新增: wait 操作类型
    "timeoutMs": 30000,        # ★ 新增: 超时时间
    "submit": true,            # ★ 新增: type 后自动回车
    "values": ["opt1"],        # ★ 新增: select 选项
    "startRef": "e1",          # ★ 新增: drag 起始
    "endRef": "e5"             # ★ 新增: drag 结束
}

### 独立路由（openclaw 风格）
POST /start              - 启动浏览器
POST /navigate           - 导航到 URL，Body: {"url": "..."}
GET  /snapshot           - 获取页面快照（accessibility tree with ref IDs）
POST /act                - 执行操作，Body: {"kind": "click", "ref": "e1", ...}
POST /wait               - ★ 新增: 等待操作
POST /stop               - 关闭浏览器
POST /close              - 关闭浏览器（别名）
GET  /health             - 健康检查
GET  /                   - 服务状态

## 测试命令

# 启动服务器
python browser_server.py

# 在另一个终端测试
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "start"}'| jq
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "navigate", "url": "https://www.baidu.com"}'| jq
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "wait", "waitType": "loadState", "value": "networkidle"}'| jq
curl -X GET http://localhost:9222/snapshot
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "close"}'| jq

## 架构设计

借鉴 openclaw 的关键设计：
1. 独立 HTTP 服务 - aiohttp server 监听指定端口
2. 分离式路由 - 按功能分组的路由处理器
3. Playwright 驱动 - 使用 Playwright 控制浏览器
4. ref 引用系统 - snapshot 返回带 ref ID 的元素列表，act 通过 ref 定位
5. 健康检查端点 - 返回服务状态
6. ★ 多层定位 - ref / selector / frame / coordinate 四级降级
7. ★ wait 操作 - 支持 loadState / text / selector / url 等多种等待模式

## 实现细节

- 浏览器实例在首次 start 时创建，保持单例
- snapshot 使用 Playwright 的 accessibility snapshot API
- 每个可交互元素分配唯一的 ref ID (e1, e2, e3...)
- act 操作通过 ref ID 定位元素并执行相应操作
"""

import asyncio
import json
import re
import sys
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import web
from loguru import logger

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        async_playwright,
    )
except ImportError:
    logger.error("❌ Playwright 未安装，请运行: pip install playwright && python -m playwright install chromium")
    sys.exit(1)


def safe_json_response(data, status=200):
    return web.json_response(
        data,
        status=status,
        dumps=lambda x: json.dumps(x, ensure_ascii=False)
    )


class BrowserControlServer:
    """浏览器控制服务器 - 管理 Playwright 浏览器实例和操作"""

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        # ref ID 映射表: ref -> locator 信息
        self._ref_map: Dict[str, Dict[str, Any]] = {}

    async def _ensure_page(self) -> bool:
        """确保 page 对象可用，崩溃时自动恢复"""
        if not self._page or not self._context:
            return False
        try:
            await self._page.evaluate("() => true")
            return True
        except Exception:
            logger.warning("🔄 [Browser] 页面不可用，尝试恢复...")
            try:
                try:
                    await self._page.close()
                except Exception:
                    pass
                self._page = await self._context.new_page()
                logger.info("✅ [Browser] 新页面创建成功")
                return True
            except Exception as e:
                logger.error(f"❌ [Browser] 页面恢复失败: {e}")
                return False

    # ★ 新增: 获取操作目标 page（支持 frame 切换）
    async def _get_target_frame(self, frame: Optional[str] = None):
        """
        获取操作目标：如果指定了 frame 则返回对应的 FrameLocator / Frame，
        否则返回当前 page。

        Args:
            frame: iframe 名称、URL 片段、或 CSS 选择器

        Returns:
            可以执行 locator / evaluate 的对象
        """
        if not frame or not self._page:
            return self._page

        # 尝试按 name 匹配
        for f in self._page.frames:
            if f.name == frame:
                logger.info(f"🖼️ [Browser] 切换到 iframe (name={frame})")
                return f

        # 尝试按 URL 片段匹配
        for f in self._page.frames:
            if frame in (f.url or ""):
                logger.info(f"🖼️ [Browser] 切换到 iframe (url contains '{frame}')")
                return f

        # 尝试按 CSS 选择器定位 iframe
        try:
            frame_locator = self._page.frame_locator(frame)
            # frame_locator 不能直接当 page 用，但可以返回用于 locator 链式调用
            logger.info(f"🖼️ [Browser] 使用 frame_locator: {frame}")
            return frame_locator
        except Exception:
            logger.warning(f"⚠️ [Browser] 未找到 iframe: {frame}，使用主页面")
            return self._page

    # ★ 新增: 通过 selector 参数创建 locator
    def _locator_from_selector(self, page_or_frame, selector: str):
        """
        通过 CSS 选择器创建 Playwright locator。
        支持 page 和 frame_locator 两种上下文。
        """
        return page_or_frame.locator(selector)

    async def start_browser(self) -> Dict[str, Any]:
        """启动浏览器实例"""
        async with self._lock:
            try:
                if self._browser and self._browser.is_connected():
                    logger.info("✅ [Browser] 浏览器已经在运行")
                    return {"success": True, "message": "Browser already running"}

                logger.info("🚀 [Browser] 启动 Chromium 浏览器...")
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    # proxy={"server": "direct://"},  # 不使用VPN链接
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        # 稳定性与内存优化
                        "--disable-software-rasterizer",
                        "--disable-extensions",
                        "--disable-background-networking",
                        "--disable-sync",
                        "--disable-translate",
                        "--no-first-run",
                        "--disable-renderer-backgrounding",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-ipc-flooding-protection",
                        "--renderer-process-limit=1",
                        "--js-flags=--max-old-space-size=256",
                    ],
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    locale="zh-CN",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                self._page = await self._context.new_page()
                logger.info("✅ [Browser] 浏览器启动成功")
                return {"success": True, "message": "Browser started successfully"}
            except Exception as e:
                logger.error(f"❌ [Browser] 启动失败: {e}")
                return {"success": False, "error": str(e)}

    async def navigate(self, url: str) -> Dict[str, Any]:
        """导航到指定 URL"""
        if not self._page:
            return {"success": False, "error": "Browser not started"}

        if not await self._ensure_page():
            return {"success": False, "error": "Page is not available and recovery failed"}

        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 [Browser] 导航到: {url} (尝试 {attempt + 1}/{max_retries})")
                await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # 短暂等待页面渲染，不用 networkidle 避免超时
                await self._page.wait_for_timeout(2000)
                logger.info(f"✅ [Browser] 导航成功: {url}")
                return {"success": True, "url": url, "title": await self._page.title()}
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ [Browser] 导航失败 (尝试 {attempt + 1}): {error_msg}")
                if ("crash" in error_msg.lower() or "closed" in error_msg.lower()) and attempt < max_retries - 1:
                    logger.warning("🔄 [Browser] 页面崩溃，恢复中...")
                    if await self._ensure_page():
                        continue
                return {"success": False, "error": error_msg}
        return {"success": False, "error": "Navigation failed after all retries"}

    async def snapshot(
        self,
        # ★ 新增参数
        interactive: bool = False,
        frame: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取页面 accessibility tree 快照

        Args:
            interactive: 为 True 时只返回可交互元素（减少噪音）
            frame: 指定 iframe 名称/URL，在该 iframe 中取快照
        """
        if not self._page:
            return {"success": False, "error": "Browser not started"}

        if not await self._ensure_page():
            return {"success": False,
                    "error": "Page crashed, recovered but needs re-navigation. Please navigate first."}

        try:
            logger.info("📸 [Browser] 获取页面快照...")

            # ★ 改动: 支持在 iframe 中取快照
            target = await self._get_target_frame(frame)
            # frame_locator 没有 evaluate，所以如果是 frame_locator 则回退到 page
            eval_target = target if hasattr(target, 'evaluate') else self._page

            # ★ 改动: interactive 模式的选择器更精简
            if interactive:
                selectors_js = """
                'button', 'a[href]', 'input:not([type="hidden"])', 'textarea', 'select',
                '[role="button"]', '[role="link"]', '[role="textbox"]',
                '[role="combobox"]', '[role="tab"]', '[role="menuitem"]',
                '[contenteditable="true"]'
                """
            else:
                selectors_js = """
                'button', 'a', 'input', 'textarea', 'select',
                '[role="button"]', '[role="link"]', '[role="textbox"]',
                '[onclick]', '[role="tab"]', '[role="menuitem"]',
                '[contenteditable="true"]', '[role="combobox"]',
                '[role="checkbox"]', '[role="radio"]', '[role="slider"]',
                '[role="switch"]', '[role="option"]'
                """

            js_code = f"""
            () => {{
                const elements = [];
                const selectors = [{selectors_js}];

                const allElements = document.querySelectorAll(selectors.join(','));

                allElements.forEach((el, index) => {{
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') {{
                        return;
                    }}

                    // ★ 新增: interactive 模式下过滤掉禁用元素
                    if ({'true' if interactive else 'false'} && el.disabled) {{
                        return;
                    }}

                    const tagName = el.tagName.toLowerCase();
                    let role = el.getAttribute('role') || tagName;

                    if (tagName === 'a') role = 'link';
                    if (tagName === 'button') role = 'button';
                    if (tagName === 'input') role = el.type === 'text' ? 'textbox' : el.type;
                    if (tagName === 'textarea') role = 'textbox';
                    if (tagName === 'select') role = 'combobox';

                    const innerText = el.innerText ? el.innerText.trim().substring(0, 100) : '';
                    const name = el.getAttribute('aria-label') ||
                                el.getAttribute('title') ||
                                el.getAttribute('placeholder') ||
                                innerText ||
                                el.value ||
                                '';

                    const value = el.value || '';

                    const rect = el.getBoundingClientRect();

                    // ★ 新增: 收集 CSS 选择器信息，便于 selector 定位
                    let cssSelector = '';
                    if (el.id) {{
                        cssSelector = '#' + el.id;
                    }} else if (el.className && typeof el.className === 'string') {{
                        const cls = el.className.trim().split(/\\s+/).slice(0, 2).join('.');
                        if (cls) cssSelector = tagName + '.' + cls;
                    }}

                    elements.push({{
                        role: role,
                        name: name,
                        value: value,
                        tagName: tagName,
                        id: el.id || '',
                        className: typeof el.className === 'string' ? el.className : '',
                        cssSelector: cssSelector,
                        x: Math.round(rect.x + rect.width / 2),
                        y: Math.round(rect.y + rect.height / 2),
                    }});
                }});

                return elements;
            }}
            """

            raw_elements = await eval_target.evaluate(js_code)

            elements = []
            self._ref_map = {}

            for index, elem in enumerate(raw_elements):
                ref_id = f"e{index + 1}"

                element = {
                    "ref": ref_id,
                    "role": elem["role"],
                    "name": elem["name"],
                }

                if elem.get("value"):
                    element["value"] = elem["value"]

                elements.append(element)

                self._ref_map[ref_id] = {
                    "role": elem["role"],
                    "name": elem["name"],
                    "tagName": elem["tagName"],
                    "id": elem.get("id", ""),
                    "className": elem.get("className", ""),
                    "cssSelector": elem.get("cssSelector", ""),
                    "x": elem.get("x", 0),
                    "y": elem.get("y", 0),
                }

            logger.info(f"✅ [Browser] 快照完成，共 {len(elements)} 个元素"
                        f"{' (仅可交互)' if interactive else ''}")
            return {
                "success": True,
                "elements": elements,
                "count": len(elements),
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [Browser] 快照失败: {error_msg}")
            if "crash" in error_msg.lower() or "closed" in error_msg.lower():
                await self._ensure_page()
            return {"success": False, "error": error_msg}

    # ================================================================
    # ★ 新增: wait 方法 — 等待页面状态变化
    # ================================================================
    async def wait(
        self,
        wait_type: str = "loadState",
        value: Optional[str] = None,
        timeout_ms: int = 30000,
        frame: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        等待页面状态变化。

        Args:
            wait_type: 等待类型
                - "time": 固定等待 value 毫秒
                - "text": 等待页面出现指定文本
                - "textGone": 等待页面指定文本消失
                - "selector": 等待 CSS 选择器匹配的元素出现
                - "url": 等待 URL 包含指定字符串
                - "loadState": 等待页面加载状态（load / domcontentloaded / networkidle）
            value: 等待的目标值
            timeout_ms: 超时时间（毫秒），默认 30000
            frame: 可选，指定 iframe

        Returns:
            Dict 操作结果
        """
        if not self._page:
            return {"success": False, "error": "Browser not started"}

        if not await self._ensure_page():
            return {"success": False, "error": "Page is not available"}

        # 安全限制超时范围
        timeout_ms = max(500, min(120_000, timeout_ms))

        try:
            target = await self._get_target_frame(frame)
            # frame_locator 没有 wait_for_* 方法，回退到 page
            wait_target = target if hasattr(target, 'wait_for_timeout') else self._page

            logger.info(f"⏳ [Browser] 等待: type={wait_type}, value={value}, timeout={timeout_ms}ms")

            if wait_type == "time":
                # 固定等待
                ms = int(value) if value and value.isdigit() else 1000
                ms = max(100, min(60_000, ms))  # 限制 100ms ~ 60s
                await self._page.wait_for_timeout(ms)
                logger.info(f"✅ [Browser] 固定等待 {ms}ms 完成")
                return {"success": True, "waitType": "time", "waited_ms": ms}

            elif wait_type == "text":
                # 等待页面出现指定文本
                if not value:
                    return {"success": False, "error": "Missing 'value' for wait(text)"}
                # 使用 text= 选择器等待文本出现
                await wait_target.locator(f"text={value}").first.wait_for(
                    state="visible", timeout=timeout_ms
                )
                logger.info(f"✅ [Browser] 文本 '{value}' 已出现")
                return {"success": True, "waitType": "text", "text": value}

            elif wait_type == "textGone":
                # 等待页面指定文本消失
                if not value:
                    return {"success": False, "error": "Missing 'value' for wait(textGone)"}
                await wait_target.locator(f"text={value}").first.wait_for(
                    state="hidden", timeout=timeout_ms
                )
                logger.info(f"✅ [Browser] 文本 '{value}' 已消失")
                return {"success": True, "waitType": "textGone", "text": value}

            elif wait_type == "selector":
                # 等待 CSS 选择器匹配的元素出现
                if not value:
                    return {"success": False, "error": "Missing 'value' for wait(selector)"}
                await wait_target.locator(value).first.wait_for(
                    state="visible", timeout=timeout_ms
                )
                logger.info(f"✅ [Browser] 选择器 '{value}' 匹配的元素已出现")
                return {"success": True, "waitType": "selector", "selector": value}

            elif wait_type == "url":
                # 等待 URL 变化包含指定字符串
                if not value:
                    return {"success": False, "error": "Missing 'value' for wait(url)"}
                await self._page.wait_for_url(
                    f"**{value}**", timeout=timeout_ms
                )
                current_url = self._page.url
                logger.info(f"✅ [Browser] URL 已变化包含 '{value}'，当前: {current_url}")
                return {"success": True, "waitType": "url", "url": current_url}

            elif wait_type == "loadState":
                # 等待页面加载状态
                state = value if value in ("load", "domcontentloaded", "networkidle") else "load"
                await wait_target.wait_for_load_state(state, timeout=timeout_ms)
                logger.info(f"✅ [Browser] 页面加载状态 '{state}' 已达成")
                return {"success": True, "waitType": "loadState", "state": state}

            else:
                return {"success": False, "error": f"Unknown wait_type: {wait_type}"}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [Browser] 等待失败: {error_msg}")
            # 超时不算致命错误，返回明确提示
            if "timeout" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"等待 '{wait_type}' 超时（{timeout_ms}ms）。页面可能仍在加载，"
                             f"可以尝试增加 timeout_ms 或执行 snapshot 查看当前状态。"
                }
            return {"success": False, "error": error_msg}

    # ================================================================
    # ★ 改动: act 方法 — 扩展多层定位 + 新操作类型
    # ================================================================
    async def act(
            self,
            kind: Optional[str] = None,
            ref: Optional[str] = None,
            value: Optional[str] = None,
            coordinate: Optional[str] = None,
            # ★ 新增参数
            selector: Optional[str] = None,
            frame: Optional[str] = None,
            submit: Optional[bool] = None,
            start_ref: Optional[str] = None,
            end_ref: Optional[str] = None,
            values: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not self._page:
            return {"success": False, "error": "Browser not started"}

        if not kind:
            return {"success": False, "error": "Missing 'kind' parameter"}

        # 操作前检查页面是否存活
        if not await self._ensure_page():
            return {"success": False, "error": "Page crashed and recovery failed"}

        try:
            logger.info(
                f"🎯 [Browser] 执行操作: kind={kind}, ref={ref}, "
                f"selector={selector}, value={value}"
            )

            # ★ 新增: 获取操作目标（支持 frame 切换）
            target = await self._get_target_frame(frame)

            # ===== 全局操作（不需要 ref 也不需要 coordinate 也不需要 selector） =====
            if not ref and not coordinate and not selector:
                if kind == "scroll":
                    eval_target = target if hasattr(target, 'evaluate') else self._page
                    await eval_target.evaluate("window.scrollBy(0, 500)")
                    logger.info("✅ [Browser] 全局页面向下滚动成功")
                    return {"success": True, "action": "scroll", "detail": "scrolled down 500px"}

                elif kind == "press":
                    if not value:
                        return {"success": False, "error": "Missing 'value' for press action"}
                    await self._page.keyboard.press(value)
                    logger.info(f"✅ [Browser] 全局按键成功: {value}")
                    return {"success": True, "action": "press", "key": value}

                elif kind == "type":
                    if not value:
                        return {"success": False, "error": "Missing 'value' for type action"}
                    await self._page.keyboard.type(value)
                    # ★ 新增: submit 参数支持
                    if submit:
                        await self._page.keyboard.press("Enter")
                    logger.info(f"✅ [Browser] 全局输入成功: {value}")
                    return {"success": True, "action": "type", "value": value}

                # ★ 新增: drag 操作（全局，通过 start_ref + end_ref）
                elif kind == "drag":
                    return await self._handle_drag(start_ref, end_ref)

                else:
                    return {"success": False, "error": f"Action '{kind}' requires 'ref', 'selector', or 'coordinate' parameter"}

            # ===== ★ 新增: 通过 selector 定位（优先级高于 coordinate，低于 ref） =====
            locator = None

            if selector and not ref:
                try:
                    locator = self._locator_from_selector(target, selector)
                    count = await locator.count()
                    if count == 0:
                        return {"success": False, "error": f"Selector '{selector}' matched 0 elements"}
                    if count > 1:
                        logger.warning(f"⚠️ [Browser] Selector '{selector}' 匹配到 {count} 个元素，使用 .first")
                        locator = locator.first
                    logger.info(f"✅ [Browser] 通过 selector 定位成功: {selector}")
                except Exception as e:
                    logger.warning(f"⚠️ [Browser] Selector 定位失败: {e}")
                    locator = None

            # 通过坐标定位（fallback）
            if not locator and coordinate and not ref:
                try:
                    x, y = map(float, coordinate.split(","))
                    if kind == "click":
                        await self._page.mouse.click(x, y)
                        logger.info(f"✅ [Browser] 坐标点击成功: ({x}, {y})")
                        return {"success": True, "action": "click", "coordinate": coordinate}
                except Exception as e:
                    logger.error(f"❌ [Browser] 坐标操作失败: {e}")
                    return {"success": False, "error": str(e)}

            # 通过 ref 定位元素
            if not locator and ref:
                ref_info = self._ref_map.get(ref)
                if not ref_info:
                    return {"success": False, "error": f"Invalid ref: {ref}. Run snapshot to get current refs."}

                role = ref_info["role"]
                name = ref_info["name"]
                tag_name = ref_info.get("tagName", "")
                elem_id = ref_info.get("id", "")
                class_name = ref_info.get("className", "")
                center_x = ref_info.get("x", 0)
                center_y = ref_info.get("y", 0)

                # 元素定位逻辑 — 处理多匹配 + 坐标兜底
                try:
                    # 1. 优先使用 ID
                    if elem_id:
                        candidate = self._page.locator(f"#{elem_id}")
                        count = await candidate.count()
                        if count == 1:
                            locator = candidate
                        elif count > 1:
                            # ★ 改动: ID 重复时也用 .first，而不是直接失败
                            logger.warning(f"⚠️ [Browser] ID '{elem_id}' 匹配到 {count} 个元素，使用 .first")
                            locator = candidate.first
                    # 2. 尝试根据 role 和 name
                    if locator is None and name and role in ["button", "link", "textbox", "combobox"]:
                        try:
                            candidate = self._page.get_by_role(role, name=name)
                            count = await candidate.count()
                            if count == 1:
                                locator = candidate
                            elif count > 1:
                                logger.warning(f"⚠️ [Browser] get_by_role 匹配到 {count} 个元素，使用 .first")
                                locator = candidate.first
                        except Exception:
                            pass
                    # 3. 尝试根据文本内容
                    if locator is None and name:
                        if tag_name == "button":
                            candidate = self._page.get_by_role("button", name=name)
                            count = await candidate.count()
                            locator = candidate.first if count > 1 else (candidate if count == 1 else None)
                        elif tag_name == "a":
                            candidate = self._page.get_by_role("link", name=name)
                            count = await candidate.count()
                            locator = candidate.first if count > 1 else (candidate if count == 1 else None)
                        elif tag_name in ["input", "textarea"]:
                            locator = self._page.get_by_placeholder(name)
                            if await locator.count() == 0:
                                locator = self._page.locator(tag_name).first
                    # 4. ★ 新增: 尝试用 snapshot 时记录的 cssSelector
                    if locator is None and ref_info.get("cssSelector"):
                        try:
                            candidate = self._page.locator(ref_info["cssSelector"])
                            if await candidate.count() > 0:
                                locator = candidate.first
                                logger.info(f"✅ [Browser] 通过 cssSelector 兜底定位: {ref_info['cssSelector']}")
                        except Exception:
                            pass
                    # 5. 最后尝试标签名
                    if locator is None:
                        locator = self._page.locator(tag_name).first

                    if locator is None or await locator.count() == 0:
                        # 6. 终极兜底：使用 snapshot 时记录的坐标点击
                        if center_x and center_y and kind == "click":
                            await self._page.mouse.click(center_x, center_y)
                            logger.info(f"✅ [Browser] 坐标兜底点击成功: ({center_x}, {center_y})")
                            return {"success": True, "action": "click", "ref": ref, "fallback": "coordinate"}
                        return {"success": False, "error": f"Cannot locate element with ref={ref}. Run snapshot to refresh."}
                except Exception as e:
                    logger.warning(f"⚠️ [Browser] 定位器创建失败: {e}")
                    # 兜底坐标点击
                    if center_x and center_y and kind == "click":
                        try:
                            await self._page.mouse.click(center_x, center_y)
                            logger.info(f"✅ [Browser] 定位失败后坐标兜底点击: ({center_x}, {center_y})")
                            return {"success": True, "action": "click", "ref": ref, "fallback": "coordinate"}
                        except Exception:
                            pass
                    return {"success": False, "error": f"Failed to create locator: {e}"}

            if locator is None:
                return {"success": False, "error": "No valid locator found. Provide ref, selector, or coordinate."}

            # ===== 执行操作 =====
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError

            try:
                if kind == "click":
                    await locator.click(timeout=5000)
                    logger.info(f"✅ [Browser] 点击成功: ref={ref}")
                    return {"success": True, "action": "click", "ref": ref}

                elif kind == "type":
                    if not value:
                        return {"success": False, "error": "Missing 'value' for type action"}
                    await locator.fill(value, timeout=5000)
                    # ★ 新增: submit 参数 — type 后自动回车
                    if submit:
                        await locator.press("Enter", timeout=3000)
                    logger.info(f"✅ [Browser] 输入成功: ref={ref}, value={value}, submit={submit}")
                    return {"success": True, "action": "type", "ref": ref, "value": value}

                # ★ 新增: fill 操作（清空后填入，与 type 区分）
                elif kind == "fill":
                    if not value:
                        return {"success": False, "error": "Missing 'value' for fill action"}
                    await locator.clear(timeout=3000)
                    await locator.fill(value, timeout=5000)
                    if submit:
                        await locator.press("Enter", timeout=3000)
                    logger.info(f"✅ [Browser] 填充成功: ref={ref}, value={value}")
                    return {"success": True, "action": "fill", "ref": ref, "value": value}

                elif kind == "hover":
                    await locator.hover(timeout=5000)
                    logger.info(f"✅ [Browser] 悬停成功: ref={ref}")
                    return {"success": True, "action": "hover", "ref": ref}

                elif kind == "scroll" or kind == "scrollIntoView":
                    await locator.scroll_into_view_if_needed(timeout=5000)
                    logger.info(f"✅ [Browser] 滚动成功: ref={ref}")
                    return {"success": True, "action": "scroll", "ref": ref}

                elif kind == "press":
                    if not value:
                        return {"success": False, "error": "Missing 'value' for press action"}
                    await locator.press(value, timeout=5000)
                    logger.info(f"✅ [Browser] 按键成功: ref={ref}, key={value}")
                    return {"success": True, "action": "press", "ref": ref, "key": value}

                # ★ 新增: select 操作
                elif kind == "select":
                    if not values:
                        return {"success": False, "error": "Missing 'values' for select action"}
                    await locator.select_option(values, timeout=5000)
                    logger.info(f"✅ [Browser] 选择成功: ref={ref}, values={values}")
                    return {"success": True, "action": "select", "ref": ref, "values": values}

                # ★ 新增: drag 操作
                elif kind == "drag":
                    return await self._handle_drag(start_ref or ref, end_ref)

                else:
                    return {"success": False, "error": f"Unknown action kind: {kind}"}

            except PlaywrightTimeoutError:
                logger.error(f"❌ [Browser] 操作超时: kind={kind}, ref={ref}")
                return {"success": False, "error": f"Operation timeout for ref={ref}"}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [Browser] 操作失败: {error_msg}")
            if "crash" in error_msg.lower() or "closed" in error_msg.lower():
                await self._ensure_page()
            return {"success": False, "error": error_msg}

    # ★ 新增: drag 辅助方法
    async def _handle_drag(
        self, start_ref: Optional[str], end_ref: Optional[str]
    ) -> Dict[str, Any]:
        """处理 drag 拖拽操作"""
        if not start_ref or not end_ref:
            return {"success": False, "error": "drag requires 'start_ref' and 'end_ref'"}

        start_info = self._ref_map.get(start_ref)
        end_info = self._ref_map.get(end_ref)

        if not start_info:
            return {"success": False, "error": f"Invalid start_ref: {start_ref}"}
        if not end_info:
            return {"success": False, "error": f"Invalid end_ref: {end_ref}"}

        sx, sy = start_info.get("x", 0), start_info.get("y", 0)
        ex, ey = end_info.get("x", 0), end_info.get("y", 0)

        if not (sx and sy and ex and ey):
            return {"success": False, "error": "Cannot determine coordinates for drag"}

        await self._page.mouse.move(sx, sy)
        await self._page.mouse.down()
        await self._page.mouse.move(ex, ey, steps=10)
        await self._page.mouse.up()

        logger.info(f"✅ [Browser] 拖拽成功: ({sx},{sy}) → ({ex},{ey})")
        return {
            "success": True,
            "action": "drag",
            "startRef": start_ref,
            "endRef": end_ref,
        }

    async def close_browser(self) -> Dict[str, Any]:
        """关闭浏览器"""
        async with self._lock:
            try:
                if self._page:
                    await self._page.close()
                    self._page = None
                if self._context:
                    await self._context.close()
                    self._context = None
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None

                self._ref_map = {}
                logger.info("✅ [Browser] 浏览器已关闭")
                return {"success": True, "message": "Browser closed successfully"}
            except Exception as e:
                logger.error(f"❌ [Browser] 关闭失败: {e}")
                return {"success": False, "error": str(e)}

    def is_connected(self) -> bool:
        """检查浏览器是否连接"""
        return self._browser is not None and self._browser.is_connected()

    async def debug_draw(self):
        js_code = """
        () => {
            const labels = document.querySelectorAll('.debug-label');
            labels.forEach(l => l.remove());

            const elements = document.querySelectorAll('input, button, a');
            elements.forEach((el, i) => {
                const rect = el.getBoundingClientRect();
                const div = document.createElement('div');
                div.className = 'debug-label';
                div.style.position = 'absolute';
                div.style.left = rect.left + window.scrollX + 'px';
                div.style.top = rect.top + window.scrollY + 'px';
                div.style.border = '2px solid red';
                div.style.color = 'red';
                div.style.fontWeight = 'bold';
                div.style.zIndex = '10000';
                div.style.pointerEvents = 'none';
                div.innerText = 'e' + (i + 1);
                document.body.appendChild(div);
            });
        }
        """
        await self._page.evaluate(js_code)
        return {"success": True}


# 全局浏览器控制器实例
browser_controller = BrowserControlServer()


# ==================== HTTP 路由处理器 ====================

async def health_handler(request: web.Request) -> web.Response:
    """健康检查端点"""
    return safe_json_response({
        "status": "ok",
        "browser_connected": browser_controller.is_connected(),
    })


async def start_handler(request: web.Request) -> web.Response:
    """启动浏览器"""
    result = await browser_controller.start_browser()
    status = 200 if result["success"] else 500
    return safe_json_response(result, status=status)


async def navigate_handler(request: web.Request) -> web.Response:
    """导航到指定 URL"""
    try:
        data = await request.json()
        url = data.get("url")
        if not url:
            return safe_json_response(
                {"success": False, "error": "Missing 'url' parameter"},
                status=400
            )
        result = await browser_controller.navigate(url)
        status = 200 if result["success"] else 500
        return safe_json_response(result, status=status)
    except Exception as e:
        return safe_json_response(
            {"success": False, "error": str(e)},
            status=400
        )


async def snapshot_handler(request: web.Request) -> web.Response:
    """获取页面快照"""
    # ★ 改动: 支持 query 参数
    interactive = request.query.get("interactive", "").lower() == "true"
    frame = request.query.get("frame")
    result = await browser_controller.snapshot(interactive=interactive, frame=frame)
    status = 200 if result["success"] else 500
    return safe_json_response(result, status=status)


async def act_handler(request: web.Request) -> web.Response:
    """执行页面操作"""
    try:
        data = await request.json()
        kind = data.get("kind") or data.get("actKind")
        ref = data.get("ref")
        value = data.get("value")
        coordinate = data.get("coordinate")
        # ★ 新增参数
        selector = data.get("selector")
        frame = data.get("frame")
        submit = data.get("submit")
        start_ref = data.get("startRef")
        end_ref = data.get("endRef")
        values = data.get("values")

        result = await browser_controller.act(
            kind=kind,
            ref=ref,
            value=value,
            coordinate=coordinate,
            selector=selector,
            frame=frame,
            submit=submit,
            start_ref=start_ref,
            end_ref=end_ref,
            values=values,
        )
        status = 200 if result["success"] else 500
        return safe_json_response(result, status=status)
    except Exception as e:
        return safe_json_response(
            {"success": False, "error": str(e)},
            status=400
        )


# ★ 新增: wait 路由处理器
async def wait_handler(request: web.Request) -> web.Response:
    """等待页面状态变化"""
    try:
        data = await request.json()
        wait_type = data.get("waitType", "loadState")
        value = data.get("value")
        timeout_ms = data.get("timeoutMs", 30000)
        frame = data.get("frame")

        if isinstance(timeout_ms, str) and timeout_ms.isdigit():
            timeout_ms = int(timeout_ms)
        elif not isinstance(timeout_ms, (int, float)):
            timeout_ms = 30000

        result = await browser_controller.wait(
            wait_type=wait_type,
            value=value,
            timeout_ms=int(timeout_ms),
            frame=frame,
        )
        status = 200 if result["success"] else 500
        return safe_json_response(result, status=status)
    except Exception as e:
        return safe_json_response(
            {"success": False, "error": str(e)},
            status=400
        )


async def stop_handler(request: web.Request) -> web.Response:
    """关闭浏览器"""
    result = await browser_controller.close_browser()
    status = 200 if result["success"] else 500
    return safe_json_response(result, status=status)


async def unified_browser_handler(request: web.Request) -> web.Response:
    """
    统一浏览器操作入口（兼容现有 tools.py）

    根据 action 字段分发到对应的处理器
    """
    try:
        data = await request.json()
        action = data.get("action")

        if not action:
            return safe_json_response(
                {"success": False, "error": "Missing 'action' parameter"},
                status=400
            )

        logger.info(f"📥 [Unified] 收到请求: action={action}")

        # 分发到对应的处理器
        if action == "start":
            result = await browser_controller.start_browser()

        elif action == "navigate":
            url = data.get("url")
            if not url:
                return safe_json_response(
                    {"success": False, "error": "Missing 'url' parameter"},
                    status=400
                )
            result = await browser_controller.navigate(url)

        elif action == "snapshot":
            # ★ 改动: 透传新参数
            interactive = data.get("interactive", False)
            frame = data.get("frame")
            result = await browser_controller.snapshot(
                interactive=bool(interactive),
                frame=frame,
            )

        elif action == "act":
            kind = data.get("actKind") or data.get("kind")
            ref = data.get("ref")
            value = data.get("value")
            coordinate = data.get("coordinate")
            # ★ 新增参数透传
            selector = data.get("selector")
            frame = data.get("frame")
            submit = data.get("submit")
            start_ref = data.get("startRef")
            end_ref = data.get("endRef")
            values = data.get("values")
            result = await browser_controller.act(
                kind=kind,
                ref=ref,
                value=value,
                coordinate=coordinate,
                selector=selector,
                frame=frame,
                submit=submit,
                start_ref=start_ref,
                end_ref=end_ref,
                values=values,
            )

        # ★ 新增: wait action 分发
        elif action == "wait":
            wait_type = data.get("waitType", "loadState")
            value = data.get("value")
            timeout_ms = data.get("timeoutMs", 30000)
            frame = data.get("frame")

            if isinstance(timeout_ms, str) and timeout_ms.isdigit():
                timeout_ms = int(timeout_ms)
            elif not isinstance(timeout_ms, (int, float)):
                timeout_ms = 30000

            result = await browser_controller.wait(
                wait_type=wait_type,
                value=value,
                timeout_ms=int(timeout_ms),
                frame=frame,
            )

        elif action == "close" or action == "stop":
            result = await browser_controller.close_browser()

        else:
            return safe_json_response(
                {"success": False, "error": f"Unknown action: {action}"},
                status=400
            )

        status = 200 if result["success"] else 500
        return safe_json_response(result, status=status)

    except json.JSONDecodeError:
        return safe_json_response(
            {"success": False, "error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        logger.error(f"❌ [Unified] 处理失败: {e}")
        return safe_json_response(
            {"success": False, "error": str(e)},
            status=500
        )


# ==================== 应用初始化 ====================

def create_app() -> web.Application:
    """创建 aiohttp 应用"""
    app = web.Application()

    # 注册路由
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    # 统一入口（兼容现有 tools.py）
    app.router.add_post("/browser", unified_browser_handler)

    # 独立路由（openclaw 风格）
    app.router.add_post("/start", start_handler)
    app.router.add_post("/navigate", navigate_handler)
    app.router.add_get("/snapshot", snapshot_handler)
    app.router.add_post("/act", act_handler)
    app.router.add_post("/wait", wait_handler)        # ★ 新增
    app.router.add_post("/stop", stop_handler)
    app.router.add_post("/close", stop_handler)

    return app


async def cleanup_on_shutdown(app: web.Application) -> None:
    """应用关闭时清理资源"""
    await browser_controller.close_browser()


def main() -> None:
    """启动服务器"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )

    # 创建应用
    app = create_app()
    app.on_cleanup.append(cleanup_on_shutdown)

    # 启动服务器
    port = 9222
    logger.info(f"🚀 Browser Control Server starting on http://localhost:{port}")
    logger.info(f"📖 API Documentation:")
    logger.info(f"   - POST /browser          - 统一入口（兼容现有 tools.py）")
    logger.info(f"   - POST /start            - 启动浏览器")
    logger.info(f"   - POST /navigate         - 导航到 URL")
    logger.info(f"   - GET  /snapshot         - 获取页面快照")
    logger.info(f"   - POST /act              - 执行页面操作")
    logger.info(f"   - POST /wait             - ★ 等待操作")
    logger.info(f"   - POST /stop             - 关闭浏览器")
    logger.info(f"   - GET  /health           - 健康检查")

    web.run_app(app, host="0.0.0.0", port=port, access_log=None)


if __name__ == "__main__":
    main()