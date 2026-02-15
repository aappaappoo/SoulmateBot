"""
Browser Control Server - Python implementation inspired by openclaw

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
    "action": "start" | "navigate" | "snapshot" | "act" | "close",
    "url": "...",           # navigate 时使用
    "ref": "e1",            # act 时元素引用
    "actKind": "click",     # act 时操作类型
    "value": "...",         # type 时输入值
    "coordinate": "x,y"     # 备选坐标定位
}

### 独立路由（openclaw 风格）
POST /start              - 启动浏览器
POST /navigate           - 导航到 URL，Body: {"url": "..."}
GET  /snapshot           - 获取页面快照（accessibility tree with ref IDs）
POST /act                - 执行操作，Body: {"kind": "click", "ref": "e1", ...}
POST /stop               - 关闭浏览器
POST /close              - 关闭浏览器（别名）
GET  /health             - 健康检查
GET  /                   - 服务状态

## 测试命令

# 启动服务器
python browser_server.py

# 在另一个终端测试
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "start"}'
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "navigate", "url": "https://www.baidu.com"}'
curl -X GET http://localhost:9222/snapshot
curl -X POST http://localhost:9222/browser -H "Content-Type: application/json" -d '{"action": "close"}'

## 架构设计

借鉴 openclaw 的关键设计：
1. 独立 HTTP 服务 - aiohttp server 监听指定端口
2. 分离式路由 - 按功能分组的路由处理器
3. Playwright 驱动 - 使用 Playwright 控制浏览器
4. ref 引用系统 - snapshot 返回带 ref ID 的元素列表，act 通过 ref 定位
5. 健康检查端点 - 返回服务状态

## 实现细节

- 浏览器实例在首次 start 时创建，保持单例
- snapshot 使用 Playwright 的 accessibility snapshot API
- 每个可交互元素分配唯一的 ref ID (e1, e2, e3...)
- act 操作通过 ref ID 定位元素并执行相应操作
"""

import asyncio
import json
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
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        # 稳定性参数（不用 --single-process）
                        "--disable-software-rasterizer",
                        "--disable-extensions",
                        "--disable-background-networking",
                        "--disable-sync",
                        "--disable-translate",
                        "--no-first-run",
                        "--disable-renderer-backgrounding",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-ipc-flooding-protection",
                        # 内存优化
                        "--js-flags=--max-old-space-size=256",
                        "--renderer-process-limit=1",
                        "--disable-features=TranslateUI",
                        "--disable-component-update",
                    ],
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    locale="zh-CN",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                self._page = await self._context.new_page()

                # 监听页面崩溃事件，自动标记
                self._page.on("crash", lambda: logger.error("💥 [Browser] 页面崩溃事件触发！"))

                logger.info("✅ [Browser] 浏览器启动成功")
                return {"success": True, "message": "Browser started successfully"}
            except Exception as e:
                logger.error(f"❌ [Browser] 启动失败: {e}")
                return {"success": False, "error": str(e)}

    async def _ensure_page(self) -> bool:
        """确保 page 对象可用，如果崩溃则自动恢复"""
        if not self._page:
            return False
        try:
            # 尝试一个轻量操作来检查 page 是否存活
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
                self._page.on("crash", lambda: logger.error("💥 [Browser] 页面崩溃事件触发！"))
                logger.info("✅ [Browser] 页面恢复成功")
                return True
            except Exception as e:
                logger.error(f"❌ [Browser] 页面恢复失败: {e}")
                return False

    async def navigate(self, url: str) -> Dict[str, Any]:
        """导航到指定 URL"""
        if not self._page:
            return {"success": False, "error": "Browser not started"}

        # 导航前检查并恢复页面
        if not await self._ensure_page():
            return {"success": False, "error": "Page is not available and recovery failed"}

        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 [Browser] 导航到: {url} (尝试 {attempt + 1}/{max_retries})")
                await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # 短暂等待页面渲染
                await self._page.wait_for_timeout(2000)
                logger.info(f"✅ [Browser] 导航成功: {url}")
                return {"success": True, "url": url, "title": await self._page.title()}
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ [Browser] 导航失败 (尝试 {attempt + 1}): {error_msg}")

                # 如果是页面崩溃/关闭，尝试恢复后重试
                if "crash" in error_msg.lower() or "closed" in error_msg.lower():
                    if attempt < max_retries - 1:
                        logger.warning("🔄 [Browser] 检测到页面崩溃/关闭，恢复中...")
                        if await self._ensure_page():
                            continue  # 恢复成功，重试导航
                        else:
                            return {"success": False, "error": f"Page crashed and recovery failed: {error_msg}"}

                return {"success": False, "error": error_msg}

        return {"success": False, "error": "Navigation failed after all retries"}


    async def snapshot(self) -> Dict[str, Any]:
        """
        获取页面 accessibility tree 快照

        返回扁平化的元素列表，每个元素包含：
        - ref: 引用 ID (e1, e2, e3...)
        - role: ARIA role (button, link, textbox...)
        - name: 可访问名称
        - value: 当前值（输入框等）
        - description: 描述信息
        """
        if not self._page:
            return {"success": False, "error": "Browser not started"}
        # 先确保 page 可用
        if not await self._ensure_page():
            return {"success": False, "error": "Page is not available and recovery failed"}
        try:
            logger.info("📸 [Browser] 获取页面快照...")

            # 使用 JavaScript 获取页面可交互元素
            # 获取常见的可交互元素和它们的属性
            js_code = """
            () => {
                const elements = [];
                const selectors = [
                    'button', 'a', 'input', 'textarea', 'select',
                    '[role="button"]', '[role="link"]', '[role="textbox"]',
                    '[onclick]', '[role="tab"]', '[role="menuitem"]'
                ];
                
                const allElements = document.querySelectorAll(selectors.join(','));
                
                allElements.forEach((el, index) => {
                    // 跳过不可见元素
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        return;
                    }
                    
                    const tagName = el.tagName.toLowerCase();
                    let role = el.getAttribute('role') || tagName;
                    
                    // 映射标签名到 ARIA role
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
                    
                    elements.push({
                        role: role,
                        name: name,
                        value: value,
                        tagName: tagName,
                        id: el.id || '',
                        className: el.className || '',
                    });
                });
                
                return elements;
            }
            """

            raw_elements = await self._page.evaluate(js_code)

            # 分配 ref ID
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

                # 保存到 ref 映射表（用于后续 act 操作定位）
                self._ref_map[ref_id] = {
                    "role": elem["role"],
                    "name": elem["name"],
                    "tagName": elem["tagName"],
                    "id": elem.get("id", ""),
                    "className": elem.get("className", ""),
                }

            logger.info(f"✅ [Browser] 快照完成，共 {len(elements)} 个元素")
            return {
                "success": True,
                "elements": elements,
                "count": len(elements),
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [Browser] 快照失败: {error_msg}")
            # 崩溃时自动恢复
            if "crash" in error_msg.lower() or "closed" in error_msg.lower():
                await self._ensure_page()
            return {"success": False, "error": error_msg}

    async def act(
            self,
            kind: Optional[str] = None,
            ref: Optional[str] = None,
            value: Optional[str] = None,
            coordinate: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._page:
            return {"success": False, "error": "Browser not started"}
        # 先确保 page 可用
        if not await self._ensure_page():
            return {"success": False, "error": "Page is not available and recovery failed"}

        if not kind:
            return {"success": False, "error": "Missing 'kind' parameter"}

        try:
            logger.info(f"🎯 [Browser] 执行操作: kind={kind}, ref={ref}, value={value}")

            # ===== 全局操作（不需要 ref 或 coordinate） =====
            if not ref and not coordinate:
                if kind == "scroll":
                    # 全局向下滚动页面
                    await self._page.evaluate("window.scrollBy(0, 500)")
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
                    logger.info(f"✅ [Browser] 全局输入成功: {value}")
                    return {"success": True, "action": "type", "value": value}

                else:
                    return {"success": False,
                            "error": f"Action '{kind}' requires 'ref' or 'coordinate' parameter"}
            # 通过坐标定位（fallback）
            if coordinate and not ref:
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
            if not ref:
                return {"success": False, "error": "Missing 'ref' or 'coordinate' parameter"}

            ref_info = self._ref_map.get(ref)
            if not ref_info:
                return {"success": False, "error": f"Invalid ref: {ref}"}

            role = ref_info["role"]
            name = ref_info["name"]
            tag_name = ref_info.get("tagName", "")
            elem_id = ref_info.get("id", "")
            class_name = ref_info.get("className", "")

            # 根据元素信息定位元素
            # 优先使用 ID，然后尝试其他方式
            locator = None
            try:
                # 1. 优先使用 ID
                if elem_id:
                    locator = self._page.locator(f"#{elem_id}")
                # 2. 尝试根据 role 和 name
                elif name and role in ["button", "link", "textbox", "combobox"]:
                    try:
                        candidate = self._page.get_by_role(role, name=name)
                        # 检查是否匹配多个元素，如果是则取第一个
                        count = await candidate.count()
                        if count == 1:
                            locator = candidate
                        elif count > 1:
                            logger.warning(f"⚠️ [Browser] get_by_role 匹配到 {count} 个元素，使用第一个")
                            locator = candidate.first
                    except Exception:
                        pass
                # 3. 尝试根据文本内容
                if locator is None and name:
                    if tag_name == "button":
                        candidate = self._page.get_by_role("button", name=name)
                        locator = candidate.first if await candidate.count() > 1 else candidate
                    elif tag_name == "a":
                        candidate = self._page.get_by_role("link", name=name)
                        locator = candidate.first if await candidate.count() > 1 else candidate
                    elif tag_name in ["input", "textarea"]:
                        # 使用 Playwright 的内置方法而不是 CSS 选择器
                        locator = self._page.get_by_placeholder(name)
                        if await locator.count() == 0:
                            locator = self._page.locator(tag_name).first
                # 4. 最后尝试标签名
                if locator is None:
                    locator = self._page.locator(tag_name).first

                if locator is None or await locator.count() == 0:
                    return {"success": False, "error": f"Cannot locate element with ref={ref}"}
            except Exception as e:
                logger.warning(f"⚠️ [Browser] 定位器创建失败: {e}")
                return {"success": False, "error": f"Failed to create locator: {e}"}

            # 执行操作
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
                    logger.info(f"✅ [Browser] 输入成功: ref={ref}, value={value}")
                    return {"success": True, "action": "type", "ref": ref, "value": value}

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


# 全局浏览器控制器实例
browser_controller = BrowserControlServer()


# ==================== HTTP 路由处理器 ====================

async def health_handler(request: web.Request) -> web.Response:
    """健康检查端点"""
    return web.json_response({
        "status": "ok",
        "browser_connected": browser_controller.is_connected(),
    })


async def start_handler(request: web.Request) -> web.Response:
    """启动浏览器"""
    result = await browser_controller.start_browser()
    status = 200 if result["success"] else 500
    return web.json_response(result, status=status)


async def navigate_handler(request: web.Request) -> web.Response:
    """导航到指定 URL"""
    try:
        data = await request.json()
        url = data.get("url")
        if not url:
            return web.json_response(
                {"success": False, "error": "Missing 'url' parameter"},
                status=400
            )
        result = await browser_controller.navigate(url)
        status = 200 if result["success"] else 500
        return web.json_response(result, status=status)
    except Exception as e:
        return web.json_response(
            {"success": False, "error": str(e)},
            status=400
        )


async def snapshot_handler(request: web.Request) -> web.Response:
    """获取页面快照"""
    result = await browser_controller.snapshot()
    status = 200 if result["success"] else 500
    return web.json_response(result, status=status)


async def act_handler(request: web.Request) -> web.Response:
    """执行页面操作"""
    try:
        data = await request.json()
        kind = data.get("kind") or data.get("actKind")
        ref = data.get("ref")
        value = data.get("value")
        coordinate = data.get("coordinate")

        result = await browser_controller.act(
            kind=kind,
            ref=ref,
            value=value,
            coordinate=coordinate,
        )
        status = 200 if result["success"] else 500
        return web.json_response(result, status=status)
    except Exception as e:
        return web.json_response(
            {"success": False, "error": str(e)},
            status=400
        )


async def stop_handler(request: web.Request) -> web.Response:
    """关闭浏览器"""
    result = await browser_controller.close_browser()
    status = 200 if result["success"] else 500
    return web.json_response(result, status=status)


async def unified_browser_handler(request: web.Request) -> web.Response:
    """
    统一浏览器操作入口（兼容现有 tools.py）

    根据 action 字段分发到对应的处理器
    """
    try:
        data = await request.json()
        action = data.get("action")

        if not action:
            return web.json_response(
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
                return web.json_response(
                    {"success": False, "error": "Missing 'url' parameter"},
                    status=400
                )
            result = await browser_controller.navigate(url)
        elif action == "snapshot":
            result = await browser_controller.snapshot()
        elif action == "act":
            kind = data.get("actKind") or data.get("kind")
            ref = data.get("ref")
            value = data.get("value")
            coordinate = data.get("coordinate")
            result = await browser_controller.act(
                kind=kind,
                ref=ref,
                value=value,
                coordinate=coordinate,
            )
        elif action == "close" or action == "stop":
            result = await browser_controller.close_browser()
        else:
            return web.json_response(
                {"success": False, "error": f"Unknown action: {action}"},
                status=400
            )

        status = 200 if result["success"] else 500
        return web.json_response(result, status=status)

    except json.JSONDecodeError:
        return web.json_response(
            {"success": False, "error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        logger.error(f"❌ [Unified] 处理失败: {e}")
        return web.json_response(
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
    logger.info(f"   - POST /stop             - 关闭浏览器")
    logger.info(f"   - GET  /health           - 健康检查")

    web.run_app(app, host="0.0.0.0", port=port, access_log=None)


if __name__ == "__main__":
    main()
