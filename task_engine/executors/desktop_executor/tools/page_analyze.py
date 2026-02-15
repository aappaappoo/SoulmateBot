"""
页面元素分析工具 - 基于浏览器 DOM 识别可交互元素

当视觉模型 (VLM) 无法识别页面中的搜索框等 UI 元素时，
通过浏览器的 DOM 和可访问性 API 来定位可交互元素的坐标。
使用 xdotool（Linux）或 osascript（macOS）配合浏览器 DevTools 协议。
"""
import asyncio
import json
from typing import Optional

from loguru import logger

from config import settings

# DOM 元素检测的默认置信度（低于 VLM 视觉分析的典型置信度，
# 因为 DOM 分析不涉及视觉匹配，而是基于元素属性和选择器推断）
_DOM_ELEMENT_CONFIDENCE = 0.85

# Chrome DevTools Protocol 调试端口
_CDP_PORT = int(getattr(settings, "cdp_port", 9222))

# 用于在浏览器中执行的 JavaScript，查找页面可交互元素
# 返回的坐标 (x, y) 为元素的中心点位置，与 vision_analyze 一致
_FIND_ELEMENTS_JS = r"""
(function() {
    var results = [];
    var selectors = {
        "search": 'input[type="search"], input[type="text"][placeholder*="搜索"], '
                  + 'input[type="text"][placeholder*="search" i], '
                  + 'input[name*="search" i], input[name*="query" i], '
                  + 'input[id*="search" i], input[class*="search" i], '
                  + 'input[aria-label*="搜索"], input[aria-label*="search" i], '
                  + '[role="searchbox"], [role="search"] input',
        "input": 'input[type="text"], input:not([type]), textarea',
        "button": 'button, [role="button"], input[type="submit"], input[type="button"]'
    };
    for (var type in selectors) {
        var elems = document.querySelectorAll(selectors[type]);
        for (var i = 0; i < elems.length; i++) {
            var el = elems[i];
            var rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                results.push({
                    type: type,
                    tag: el.tagName.toLowerCase(),
                    id: el.id || "",
                    name: el.name || "",
                    className: el.className || "",
                    placeholder: el.placeholder || "",
                    ariaLabel: el.getAttribute("aria-label") || "",
                    x: Math.round(rect.x + rect.width / 2),
                    y: Math.round(rect.y + rect.height / 2),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                });
            }
        }
    }
    return JSON.stringify(results);
})();
"""


async def page_analyze(element_type: str = "search") -> str:
    """
    通过浏览器 DOM 分析页面可交互元素

    当视觉分析无法识别 UI 元素时，通过浏览器 JavaScript 注入
    来查找搜索框、输入框、按钮等可交互元素的位置坐标。

    返回的坐标 (x, y) 为元素的中心点位置，与 vision_analyze 的坐标格式一致，
    可直接传递给 click 工具使用。

    Args:
        element_type: 要查找的元素类型，支持 "search"（搜索框）、
                     "input"（输入框）、"button"（按钮）

    Returns:
        str: JSON 格式的分析结果，包含元素描述和坐标
    """
    valid_types = ("search", "input", "button")
    if element_type not in valid_types:
        element_type = "search"

    logger.info(f"🔍 [page_analyze] 通过 DOM 分析查找 {element_type} 元素")

    # 尝试通过 xdotool + xdg-open / browser console 执行 JS
    js_result = await _run_browser_js(_FIND_ELEMENTS_JS)

    if js_result is None:
        logger.warning("🔍 [page_analyze] 无法通过浏览器执行 JS 分析")
        return json.dumps(
            {
                "found": False,
                "query": element_type,
                "elements": [],
                "error": "无法连接浏览器执行 DOM 分析",
            },
            ensure_ascii=False,
        )

    # 解析结果
    try:
        elements = json.loads(js_result)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"🔍 [page_analyze] JS 返回结果解析失败: {js_result}")
        return json.dumps(
            {"found": False, "query": element_type, "elements": [], "error": "DOM 分析结果解析失败"},
            ensure_ascii=False,
        )

    # 根据 element_type 过滤
    filtered = [e for e in elements if e.get("type") == element_type]
    if not filtered and element_type == "search":
        # 搜索框未找到时，回退到所有 input
        filtered = [e for e in elements if e.get("type") == "input"]

    result_elements = []
    for elem in filtered:
        desc_parts = []
        if elem.get("placeholder"):
            desc_parts.append(f'placeholder="{elem["placeholder"]}"')
        if elem.get("ariaLabel"):
            desc_parts.append(f'aria-label="{elem["ariaLabel"]}"')
        if elem.get("id"):
            desc_parts.append(f'id="{elem["id"]}"')
        desc = f"{elem.get('tag', 'input')}({', '.join(desc_parts)})" if desc_parts else elem.get("tag", "input")

        result_elements.append(
            {
                "description": desc,
                "x": elem.get("x", 0),
                "y": elem.get("y", 0),
                "width": elem.get("width", 0),
                "height": elem.get("height", 0),
                "confidence": _DOM_ELEMENT_CONFIDENCE,
            }
        )

    found = len(result_elements) > 0
    logger.info(f"🔍 [page_analyze] DOM 分析完成: 找到 {len(result_elements)} 个 {element_type} 元素")

    return json.dumps(
        {"found": found, "query": element_type, "elements": result_elements},
        ensure_ascii=False,
    )


async def _run_browser_js(js_code: str) -> Optional[str]:
    """
    尝试通过浏览器执行 JavaScript 代码

    使用 xdotool 配合 Ctrl+Shift+J 打开 DevTools 或
    通过 Chrome DevTools Protocol 远程调试来执行 JS。

    Args:
        js_code: 要执行的 JavaScript 代码

    Returns:
        str: JS 执行结果，或 None 表示失败
    """
    # 尝试方式：通过 Chrome/Chromium 的远程调试端口执行 JS
    # 常见调试端口: 9222
    result = await _try_cdp_evaluate(js_code)
    if result is not None:
        return result

    # 尝试方式2：通过 xdotool 模拟控制台输入（备选）
    logger.debug("🔍 [page_analyze] CDP 连接失败，跳过 DOM 分析")
    return None


async def _try_cdp_evaluate(js_code: str) -> Optional[str]:
    """
    通过 Chrome DevTools Protocol (CDP) 执行 JavaScript

    Args:
        js_code: 要执行的 JavaScript 代码

    Returns:
        str: 执行结果，或 None 表示失败
    """
    try:
        import aiohttp
    except ImportError:
        return None

    cdp_url = f"http://127.0.0.1:{_CDP_PORT}"

    try:
        async with aiohttp.ClientSession() as session:
            # 获取可调试的页面列表
            async with session.get(
                f"{cdp_url}/json",
                timeout=aiohttp.ClientTimeout(total=3),
            ) as resp:
                if resp.status != 200:
                    return None
                pages = await resp.json()

            if not pages:
                return None

            # 使用第一个页面的 WebSocket 调试 URL
            ws_url = pages[0].get("webSocketDebuggerUrl")
            if not ws_url:
                return None

            # 通过 WebSocket 发送 CDP 命令
            async with session.ws_connect(ws_url) as ws:
                cmd = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": js_code, "returnByValue": True},
                }
                await ws.send_json(cmd)

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("id") == 1:
                            result = data.get("result", {}).get("result", {})
                            return result.get("value")
                    elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                        break

    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
        logger.debug(f"🔍 [page_analyze] CDP 连接失败: {e}")

    return None
