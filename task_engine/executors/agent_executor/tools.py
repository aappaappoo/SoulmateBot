"""
Agent 浏览器工具 - 通过自建 browser control server 控制浏览器

所有浏览器操作通过 HTTP API 调用 browser control server 完成。
工具定义供 LLM tool-call 使用，LLM 自主决定何时调用哪个工具。

支持的 action：
- start: 启动浏览器实例
- navigate: 导航到指定 URL
- snapshot: 获取页面 UI 树快照（aria/accessibility format）
- act: 执行页面操作（click, type, scroll, hover 等）
- close: 关闭浏览器实例
"""
import json
from typing import Any, Dict, Optional

import aiohttp
from loguru import logger

from config import settings

# browser control server 配置
_BROWSER_SERVER_URL = (getattr(settings, "browser_server_url", None) or "http://localhost:9222")


async def browser_tool(
    action: str,
    url: Optional[str] = None,
    ref: Optional[str] = None,
    act_kind: Optional[str] = None,
    value: Optional[str] = None,
    coordinate: Optional[str] = None,
) -> str:
    """
    统一的浏览器控制工具，通过 HTTP 调用自建 browser control server

    Args:
        action: 操作类型 (start / navigate / snapshot / act / close)
        url: 目标 URL（navigate 时使用）
        ref: 元素引用 ID（act 时使用，来自 snapshot 返回的 ref ID）
        act_kind: 操作类型（act 时使用：click / type / scroll / hover / press）
        value: 输入值（type 时使用）
        coordinate: 坐标（备选定位方式，格式 "x,y"）

    Returns:
        str: JSON 格式的操作结果
    """
    server_url = _BROWSER_SERVER_URL.rstrip("/")

    payload: Dict[str, Any] = {"action": action}

    if url is not None:
        payload["url"] = url
    if ref is not None:
        payload["ref"] = ref
    if act_kind is not None:
        payload["actKind"] = act_kind
    if value is not None:
        payload["value"] = value
    if coordinate is not None:
        payload["coordinate"] = coordinate
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{server_url}/browser",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    error_msg = f"Browser server 返回错误 HTTP {resp.status}: {error_text}"
                    logger.error(f"❌ [BrowserTool], payload={payload} {error_msg}")
                    return json.dumps({"success": False, "error": error_msg}, ensure_ascii=False)

                result = await resp.json()
                logger.info(
                    f"✅ [BrowserTool] action={action}, payload={payload} 完成: "
                    f"{json.dumps(result, ensure_ascii=False)[:300]}"
                )
                return json.dumps(result, ensure_ascii=False)

    except aiohttp.ClientConnectorError:
        error_msg = (
            f"无法连接到 browser control server ({server_url})。"
            f"请确保 browser control server 已启动。"
        )
        logger.error(f"❌ [BrowserTool], payload={payload}  {error_msg}")
        return json.dumps({"success": False, "error": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"浏览器工具执行异常: {e}"
        logger.error(f"❌ [BrowserTool], payload={payload}  {error_msg}")
        return json.dumps({"success": False, "error": error_msg}, ensure_ascii=False)


# 工具注册表：名称 → 函数
TOOL_REGISTRY = {
    "browser": browser_tool,
}

# 工具描述，供 LLM tool-call 使用
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "browser",
            "description": (
                "浏览器自动化控制工具。通过 browser control server 控制浏览器完成各种网页操作。\n"
                "支持的 action：\n"
                '- "start": 启动浏览器实例，开始新的浏览器会话\n'
                '- "navigate": 导航到指定 URL（需提供 url 参数）\n'
                '- "snapshot": 获取当前页面的 UI 树快照，返回页面元素列表及其 ref ID\n'
                '- "act": 执行页面操作（需提供 actKind 和 ref/coordinate）\n'
                '  - actKind="click": 点击元素\n'
                '  - actKind="type": 在元素中输入文本（需提供 value）\n'
                '  - actKind="scroll": 滚动页面\n'
                '  - actKind="hover": 悬停在元素上\n'
                '  - actKind="press": 按下键盘按键（需提供 value，如 "Enter"）\n'
                '- "close": 关闭浏览器实例\n\n'
                "典型使用流程：\n"
                "1. browser(action=\"start\") 启动浏览器\n"
                "2. browser(action=\"navigate\", url=\"...\") 打开网页\n"
                "3. browser(action=\"snapshot\") 获取页面快照，了解页面结构\n"
                "4. browser(action=\"act\", actKind=\"click\", ref=\"e1\") 点击元素\n"
                "5. browser(action=\"act\", actKind=\"type\", ref=\"e2\", value=\"...\") 输入文本\n"
                "6. browser(action=\"snapshot\") 再次快照确认操作结果\n"
                "7. browser(action=\"close\") 任务完成后关闭浏览器"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型",
                        "enum": ["start", "navigate", "snapshot", "act", "close"],
                    },
                    "url": {
                        "type": "string",
                        "description": "目标 URL（navigate 时必填）",
                    },
                    "ref": {
                        "type": "string",
                        "description": "元素引用 ID（act 时使用，来自 snapshot 返回的元素 ref ID，如 'e1', 'e5'）",
                    },
                    "act_kind": {
                        "type": "string",
                        "description": "操作类型（act 时必填）",
                        "enum": ["click", "type", "scroll", "hover", "press"],
                    },
                    "value": {
                        "type": "string",
                        "description": "输入值（type 时为输入文本，press 时为按键名称如 'Enter'）",
                    },
                    "coordinate": {
                        "type": "string",
                        "description": "坐标定位（备选方式，格式 'x,y'，当没有 ref 时使用）",
                    },
                },
                "required": ["action"],
            },
        },
    },
]
