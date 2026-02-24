"""
Agent 浏览器工具 - 通过自建 browser control server 控制浏览器

所有浏览器操作通过 HTTP API 调用 browser control server 完成。
工具定义供 LLM tool-call 使用，LLM 自主决定何时调用哪个工具。

支持的 action：
- start: 启动浏览器实例
- navigate: 导航到指定 URL
- snapshot: 获取页面 UI 树快照（aria/accessibility format）
- act: 执行页面操作（click, type, scroll, hover, press, select, fill, drag）
- wait: 等待页面状态变化（加载完成、文本出现/消失、元素可见、URL 变化等）
- close: 关闭浏览器实例
"""
import json
import re
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger

from config import settings

# browser control server 配置
_BROWSER_SERVER_URL = (getattr(settings, "browser_server_url", None) or "http://localhost:9222")


# ============================================================
# 错误转义层 - 将 Playwright 原始错误转为 AI 可理解的提示
# ============================================================

def to_ai_friendly_error(error_msg: str, ref: Optional[str] = None, action: str = "") -> str:
    """
    将 Playwright / browser server 原始错误转为 AI 可理解的提示。

    参考 openclaw 的 toAIFriendlyError 实现，覆盖以下典型场景：
    1. strict mode violation - 选择器匹配到多个元素
    2. timeout / not visible - 元素不可见或不存在
    3. intercepts pointer events - 元素被遮挡
    4. Operation timeout - 操作超时
    5. detached from DOM - 元素已从 DOM 移除

    Args:
        error_msg: browser server 返回的原始错误字符串
        ref: 当前操作的元素 ref ID
        action: 当前执行的 action 类型

    Returns:
        str: AI 可理解的错误提示，包含建议的下一步操作
    """
    ref_hint = f' (ref="{ref}")' if ref else ""

    # 1. strict mode violation: 选择器匹配到多个元素
    if "strict mode violation" in error_msg:
        count_match = re.search(r"resolved to (\d+) elements", error_msg)
        count = count_match.group(1) if count_match else "多个"
        return (
            f"元素{ref_hint}匹配到了 {count} 个元素，无法确定操作目标。"
            f"【建议】请执行 snapshot 获取最新页面快照，使用更精确的 ref；"
            f"或者尝试用 selector 参数（CSS 选择器）精确定位目标元素。"
        )

    # 2. 元素不可见 / 超时等待可见
    if ("Timeout" in error_msg or "waiting for" in error_msg) and \
       ("to be visible" in error_msg or "not visible" in error_msg):
        return (
            f"元素{ref_hint}未找到或不可见（可能页面尚未加载完成，或元素被隐藏）。"
            f"【建议】先执行 wait(wait_type=\"loadState\", value=\"networkidle\") 等待页面加载，"
            f"然后重新 snapshot 获取最新元素列表。"
        )

    # 3. 元素被遮挡
    if "intercepts pointer events" in error_msg or \
       "not receive pointer events" in error_msg:
        return (
            f"元素{ref_hint}被其他元素遮挡，无法点击。"
            f"【建议】尝试先执行 act(act_kind=\"scroll\", ref=\"...\") 将目标滚动到视口中，"
            f"或关闭弹窗/遮罩层后重试。也可以用 coordinate 坐标方式直接点击。"
        )

    # 4. Operation timeout（通用操作超时）
    if "Operation timeout" in error_msg or "timeout" in error_msg.lower():
        return (
            f"操作{ref_hint}超时。元素可能不可交互或页面状态已变化。"
            f"【建议】执行 snapshot 查看当前页面最新状态，确认目标元素是否仍然存在；"
            f"如果页面正在加载，请先用 wait(wait_type=\"loadState\") 等待。"
        )

    # 5. 元素已从 DOM 移除
    if "detached" in error_msg.lower() or "no longer attached" in error_msg.lower():
        return (
            f"元素{ref_hint}已从页面 DOM 中移除（页面发生了导航或动态更新）。"
            f"【建议】执行 snapshot 获取最新页面快照，使用新的 ref ID 重试。"
        )

    # 6. 元素不可见（通用）
    if "not visible" in error_msg:
        return (
            f"元素{ref_hint}当前不可见。"
            f"【建议】尝试滚动页面使其可见，或执行 snapshot 确认元素状态。"
        )

    # 兜底：返回原始错误 + 通用建议
    return (
        f"操作失败{ref_hint}: {error_msg[:300]}。"
        f"【建议】执行 snapshot 查看当前页面状态后重试。"
    )


async def browser_tool(
    action: str,
    url: Optional[str] = None,
    ref: Optional[str] = None,
    act_kind: Optional[str] = None,
    value: Optional[str] = None,
    coordinate: Optional[str] = None,
    # --- 新增：多层定位参数 ---
    selector: Optional[str] = None,
    frame: Optional[str] = None,
    target_id: Optional[str] = None,
    # --- 新增：snapshot 模式参数 ---
    snapshot_format: Optional[str] = None,
    refs_mode: Optional[str] = None,
    interactive: Optional[bool] = None,
    # --- 新增：wait 参数 ---
    wait_type: Optional[str] = None,
    timeout_ms: Optional[int] = None,
    # --- 新增：act 扩展参数 ---
    start_ref: Optional[str] = None,
    end_ref: Optional[str] = None,
    values: Optional[List[str]] = None,
    submit: Optional[bool] = None,
) -> str:
    """
    统一的浏览器控制工具，通过 HTTP 调用自建 browser control server

    Args:
        action: 操作类型 (start / navigate / snapshot / act / wait / close)
        url: 目标 URL（navigate 时使用）
        ref: 元素引用 ID（act 时使用，来自 snapshot 返回的 ref ID）
        act_kind: 操作类型（act 时必填：click / type / scroll / hover / press / select / fill / drag）
        value: 输入值（type 时为输入文本，press 时为按键名称如 "Enter"）
        coordinate: 坐标定位（备选方式，格式 "x,y"，当没有 ref 时使用）
        selector: CSS 选择器（精确定位，当 ref 不可用或匹配多个元素时使用）
        frame: iframe 名称或 URL（当目标元素在 iframe 中时使用）
        target_id: 浏览器 Tab 的 CDP target ID（多 Tab 场景下指定操作目标）
        snapshot_format: 快照格式 "aria" 或 "ai"（默认 "ai"）
        refs_mode: ref 模式 "role" 或 "aria"（"aria" 模式的 ref 跨快照更稳定）
        interactive: snapshot 时是否只返回可交互元素
        wait_type: 等待类型 (time / text / textGone / selector / url / loadState / fn)
        timeout_ms: 等待超时时间（毫秒）
        start_ref: drag 操作的起始元素 ref
        end_ref: drag 操作的结束元素 ref
        values: select 操作的选项值列表
        submit: type 操作后是否自动按 Enter 提交

    Returns:
        str: JSON 格式的操作结果
    """
    server_url = _BROWSER_SERVER_URL.rstrip("/")

    payload: Dict[str, Any] = {"action": action}

    # 基础参数
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

    # 多层定位参数
    if selector is not None:
        payload["selector"] = selector
    if frame is not None:
        payload["frame"] = frame
    if target_id is not None:
        payload["targetId"] = target_id

    # snapshot 模式参数
    if snapshot_format is not None:
        payload["snapshotFormat"] = snapshot_format
    if refs_mode is not None:
        payload["refsMode"] = refs_mode
    if interactive is not None:
        payload["interactive"] = interactive

    # wait 参数
    if wait_type is not None:
        payload["waitType"] = wait_type
    if timeout_ms is not None:
        payload["timeoutMs"] = timeout_ms

    # act 扩展参数
    if start_ref is not None:
        payload["startRef"] = start_ref
    if end_ref is not None:
        payload["endRef"] = end_ref
    if values is not None:
        payload["values"] = values
    if submit is not None:
        payload["submit"] = submit

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{server_url}/browser",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    # ★ 关键改动：错误转义层
                    friendly_error = to_ai_friendly_error(
                        error_text, ref=ref, action=action
                    )
                    logger.error(f"❌ [BrowserTool] payload={payload} {friendly_error}")
                    return json.dumps(
                        {"success": False, "error": friendly_error},
                        ensure_ascii=False,
                    )

                result = await resp.json()

                # ★ 对返回结果中的错误也做转义
                if not result.get("success", True) and "error" in result:
                    result["error"] = to_ai_friendly_error(
                        result["error"], ref=ref, action=action
                    )

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
        logger.error(f"❌ [BrowserTool] payload={payload} {error_msg}")
        return json.dumps({"success": False, "error": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"浏览器工具执行异常: {e}"
        friendly_error = to_ai_friendly_error(str(e), ref=ref, action=action)
        logger.error(f"❌ [BrowserTool] payload={payload} {friendly_error}")
        return json.dumps({"success": False, "error": friendly_error}, ensure_ascii=False)


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
                '- "start": 启动浏览器实例\n'
                '- "navigate": 导航到指定 URL（需提供 url 参数）\n'
                '- "snapshot": 获取当前页面的 UI 树快照，返回页面元素列表及其 ref ID\n'
                '  - snapshot_format: "ai"（默认，简洁）或 "aria"（完整无障碍树）\n'
                '  - refs_mode: "role"（默认）或 "aria"（aria 模式的 ref 跨快照更稳定）\n'
                '  - interactive: true 时只返回可交互元素，减少噪音\n'
                '- "act": 执行页面操作（需提供 act_kind）\n'
                '  - act_kind="click": 点击元素\n'
                '  - act_kind="type": 输入文本（需提供 value，可选 submit=true 自动回车）\n'
                '  - act_kind="press": 按键（需提供 value，如 "Enter"）\n'
                '  - act_kind="scroll": 滚动页面或元素\n'
                '  - act_kind="hover": 悬停在元素上\n'
                '  - act_kind="select": 选择下拉选项（需提供 values 列表）\n'
                '  - act_kind="fill": 清空后填入文本（需提供 value）\n'
                '  - act_kind="drag": 拖拽（需提供 start_ref 和 end_ref）\n'
                '- "wait": 等待页面状态变化\n'
                '  - wait_type="time": 等待指定毫秒（value 为毫秒数字符串）\n'
                '  - wait_type="text": 等待页面出现指定文本（value 为文本内容）\n'
                '  - wait_type="textGone": 等待页面指定文本消失（value 为文本内容）\n'
                '  - wait_type="selector": 等待 CSS 选择器匹配的元素出现（value 为选择器）\n'
                '  - wait_type="url": 等待 URL 变化包含指定字符串（value 为 URL 片段）\n'
                '  - wait_type="loadState": 等待页面加载状态（value 可选 "load" / "domcontentloaded" / "networkidle"）\n'
                '- "close": 关闭浏览器实例\n\n'
                "【元素定位优先级】（从高到低）：\n"
                "1. ref: 来自 snapshot 的元素 ID（如 'e1', 'e5'），最常用\n"
                "2. selector: CSS 选择器，当 ref 匹配多个元素时用于精确定位\n"
                "3. coordinate: 坐标 'x,y'，当以上方式都不可用时的兜底方案\n"
                "4. frame: 目标元素在 iframe 中时，指定 iframe 名称或 URL\n"
                "5. target_id: 多 Tab 场景下指定操作的浏览器 Tab\n\n"
                "【错误处理】：\n"
                "- 如果操作返回 success=false，error 字段包含 AI 可读的错误描述和建议\n"
                "- 遇到'匹配到多个元素'错误 → 执行 snapshot 获取最新 ref，或用 selector 精确定位\n"
                "- 遇到'元素不可见'错误 → 先 wait(wait_type=\"loadState\") 等待加载，再 snapshot\n"
                "- 遇到'元素被遮挡'错误 → 尝试 scroll 或关闭弹窗后重试\n"
                "- 遇到'操作超时'错误 → snapshot 查看最新页面状态\n\n"
                "典型使用流程：\n"
                '1. browser(action="start") 启动浏览器\n'
                '2. browser(action="navigate", url="...") 打开网页\n'
                '3. browser(action="wait", wait_type="loadState", value="networkidle") 等待加载\n'
                '4. browser(action="snapshot") 获取页面快照\n'
                '5. browser(action="act", act_kind="click", ref="e1") 操作元素\n'
                '6. browser(action="snapshot") 再次快照确认结果\n'
                '7. browser(action="close") 任务完成后关闭浏览器'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "操作类型",
                        "enum": ["start", "navigate", "snapshot", "act", "wait", "close"],
                    },
                    "url": {
                        "type": "string",
                        "description": "目标 URL（navigate 时必填）",
                    },
                    "ref": {
                        "type": "string",
                        "description": "元素引用 ID（来自 snapshot 返回的 ref，如 'e1', 'e5'）",
                    },
                    "act_kind": {
                        "type": "string",
                        "description": "操作类型（act 时必填）",
                        "enum": ["click", "type", "scroll", "hover", "press", "select", "fill", "drag"],
                    },
                    "value": {
                        "type": "string",
                        "description": (
                            "输入值，根据上下文含义不同：\n"
                            "- type/fill: 输入文本内容\n"
                            "- press: 按键名称（如 'Enter', 'Tab', 'Escape'）\n"
                            "- wait(time): 等待毫秒数\n"
                            "- wait(text/textGone): 等待的文本内容\n"
                            "- wait(selector): CSS 选择器\n"
                            "- wait(url): URL 片段\n"
                            "- wait(loadState): 'load' / 'domcontentloaded' / 'networkidle'"
                        ),
                    },
                    "coordinate": {
                        "type": "string",
                        "description": "坐标定位（格式 'x,y'，当 ref/selector 不可用时的兜底方案）",
                    },
                    # --- 多层定位参数 ---
                    "selector": {
                        "type": "string",
                        "description": (
                            "CSS 选择器，用于精确定位元素。当 ref 匹配多个元素时使用。"
                            "例如: '#search-input', '.btn-primary', 'input[name=\"q\"]'"
                        ),
                    },
                    "frame": {
                        "type": "string",
                        "description": "iframe 名称或 URL 片段（当目标元素在 iframe 中时指定）",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "浏览器 Tab 的 CDP target ID（多 Tab 场景下指定操作目标 Tab）",
                    },
                    # --- snapshot 参数 ---
                    "snapshot_format": {
                        "type": "string",
                        "description": "快照格式：'ai'（简洁，默认）或 'aria'（完整无障碍树）",
                        "enum": ["ai", "aria"],
                    },
                    "refs_mode": {
                        "type": "string",
                        "description": "ref 模式：'role'（默认）或 'aria'（跨快照更稳定的 ref ID）",
                        "enum": ["role", "aria"],
                    },
                    "interactive": {
                        "type": "boolean",
                        "description": "snapshot 时为 true 则只返回可交互元素，减少结果噪音",
                    },
                    # --- wait 参数 ---
                    "wait_type": {
                        "type": "string",
                        "description": "等待类型（action=\"wait\" 时必填）",
                        "enum": ["time", "text", "textGone", "selector", "url", "loadState"],
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "等待超时时间（毫秒，默认 30000）",
                    },
                    # --- act 扩展参数 ---
                    "start_ref": {
                        "type": "string",
                        "description": "drag 操作的起始元素 ref",
                    },
                    "end_ref": {
                        "type": "string",
                        "description": "drag 操作的结束元素 ref",
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "select 操作的选项值列表",
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "type 操作后是否自动按 Enter 提交（默认 false）",
                    },
                },
                "required": ["action"],
            },
        },
    },
]