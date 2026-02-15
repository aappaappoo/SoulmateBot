"""
桌面操控执行器 - 核心 LLM tool-call 循环（Playwright 方案）

⭐ 这是整个 task_engine 中最关键的模块。

执行流程：
1. 构建 system prompt（Playwright 操控策略）
2. 注册 DesktopToolRegistry
3. while 循环（max 15 次）：
   - LLM 返回 tool_call
   - 执行 tool
   - TaskGuard 校验
   - 将 tool result 回填 messages
4. LLM 不再调用工具 → 任务完成

每一步都输出详细日志：
  🌐 打开页面 → 🔍 分析元素 → 🖱️ 点击/输入 → ✅/❌ 验证

tool_call 通过 aiohttp 调 vLLM /v1/chat/completions
"""
import json
import time
from typing import Any, Dict, List, Optional
from loguru import logger

from task_engine.models import Step, StepResult
from task_engine.executors.base import BaseExecutor
from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
from task_engine.executors.desktop_executor.tools import TOOL_DEFINITIONS, TOOL_REGISTRY
from config import settings


# 执行的LLM配置（从环境变量读取）
EXECUTOR_LLM_URL = getattr(settings, 'executor_llm_url', "http://localhost:8000")
EXECUTOR_LLM_MODEL = getattr(settings, 'executor_llm_model', "default")
EXECUTOR_LLM_TOKEN = getattr(settings, 'executor_llm_token', "")
_MAX_ITERATIONS = getattr(settings, 'max_iterations', "")



# 桌面操控 system prompt（Playwright 方案）
_SYSTEM_PROMPT: str = """你是一个网页操控助手。你的任务是通过调用工具来完成用户的网页操作请求。
所有操作基于 Playwright 浏览器自动化，通过 CSS 选择器定位元素。

可用工具：
- app_open: 使用 Playwright 打开浏览器并访问 URL
- page_analyze: 分析页面可交互元素（搜索框、输入框、按钮），返回元素描述和 CSS 选择器
- click: 通过 CSS 选择器点击页面元素
- type_text: 通过 CSS 选择器在输入框中填入文本
- key_press: 按下键盘按键（如 Enter、Tab）
- shell_run: 执行 shell 命令

操作策略（请严格按照以下步骤执行）：
1. 先用 app_open 打开目标网页
2. 用 page_analyze 分析页面，获取可交互元素的 CSS 选择器
3. 用 type_text 在搜索框中输入文本（需提供选择器和文本）
4. 用 key_press 按下 Enter 键执行搜索
5. 等待搜索结果后，再次用 page_analyze 查找播放相关按钮
6. 用 click 点击播放按钮
7. 任务完成后，用自然语言描述操作结果

重要规则：
- page_analyze 返回的 selector 可直接用于 click 和 type_text
- 先 page_analyze 获取选择器，再用选择器操作
- 不要尝试登录、支付、输入密码等敏感操作
- 如果某个网站需要登录才能使用，尝试其他网站
- 任务完成后，用自然语言描述操作结果
"""


class DesktopExecutor(BaseExecutor):
    """
    桌面操控执行器

    通过 LLM tool-call 循环实现自主桌面操控。
    """

    def __init__(self) -> None:
        self._guard = TaskGuard()

    async def execute(self, step: Step) -> StepResult:
        """
        执行桌面操控任务

        Args:
            step: 包含 params["task"] 的步骤

        Returns:
            StepResult: 执行结果
        """
        task_text: str = step.params.get("task", "")
        if not task_text:
            return StepResult(success=False, message="缺少 task 参数")

        self._guard.reset()
        logger.info(f"🚀 [DesktopExecutor] 开始桌面操控任务: {task_text}")

        # 构建初始消息
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"请完成以下桌面操作任务：{task_text}"},
        ]

        for iteration in range(1, _MAX_ITERATIONS + 1):
            logger.info(f"🔄 [DesktopExecutor] === 第 {iteration}/{_MAX_ITERATIONS} 轮 ===")

            # 调用 LLM 获取下一步操作
            llm_response = await self._call_llm(messages)

            if llm_response is None:
                logger.error(f"❌ [DesktopExecutor] LLM 调用失败（第 {iteration} 轮）")
                return StepResult(
                    success=False,
                    message=f"LLM 调用失败（第 {iteration} 轮）",
                )

            # 检查是否有 tool_call
            tool_calls = llm_response.get("tool_calls")
            assistant_content = llm_response.get("content", "")

            if assistant_content:
                logger.info(f"💬 [DesktopExecutor] LLM 回复: {assistant_content[:200]}")

            if not tool_calls:
                # LLM 不再调用工具，任务完成
                logger.info(f"✅ [DesktopExecutor] 任务完成（第 {iteration} 轮），LLM 无更多工具调用")
                return StepResult(
                    success=True,
                    message=assistant_content or "桌面操控任务已完成",
                    data={"iterations": iteration},
                )

            # 将 assistant 消息加入历史
            messages.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": tool_calls,
            })

            logger.info(
                f"🛠️ [DesktopExecutor] 第 {iteration} 轮共 {len(tool_calls)} 个工具调用: "
                f"{[tc.get('function', {}).get('name', '?') for tc in tool_calls]}"
            )

            # 依次执行每个 tool_call
            for tc_idx, tc in enumerate(tool_calls, 1):
                func_name: str = tc.get("function", {}).get("name", "")
                func_args_raw: str = tc.get("function", {}).get("arguments", "{}")
                tc_id: str = tc.get("id", "")

                try:
                    func_args: Dict[str, Any] = json.loads(func_args_raw)
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                # 根据工具类型记录不同的日志图标
                tool_icon = _get_tool_icon(func_name)
                logger.info(
                    f"{tool_icon} [DesktopExecutor] 执行工具 [{tc_idx}/{len(tool_calls)}]: "
                    f"{func_name}({_summarize_args(func_name, func_args)})"
                )

                # 执行工具
                tool_fn = TOOL_REGISTRY.get(func_name)
                if tool_fn is None:
                    tool_result = f"未知工具: {func_name}"
                    logger.warning(f"⚠️ [DesktopExecutor] 未知工具: {func_name}")
                else:
                    try:
                        start_time = time.time()
                        tool_result = await tool_fn(**func_args)
                        elapsed = time.time() - start_time
                        logger.info(
                            f"✅ [DesktopExecutor] 工具 {func_name} 执行成功 "
                            f"({elapsed:.1f}s): {_summarize_result(func_name, str(tool_result))}"
                        )
                    except Exception as e:
                        tool_result = f"工具执行异常: {e}"
                        logger.error(f"❌ [DesktopExecutor] 工具 {func_name} 执行异常: {e}")

                # 守卫检查
                action = self._guard.check(func_name, func_args, str(tool_result))
                if action == GuardAction.ABORT:
                    logger.warning(
                        f"🛑 [DesktopExecutor] 安全守卫终止: "
                        f"tool={func_name}, iteration={iteration}"
                    )
                    return StepResult(
                        success=False,
                        message=f"安全守卫终止：检测到危险操作或过多偏离",
                        data={"iterations": iteration, "last_tool": func_name},
                    )
                elif action == GuardAction.SWITCH:
                    logger.warning(
                        f"🔀 [DesktopExecutor] 守卫建议切换: "
                        f"tool={func_name}, iteration={iteration}"
                    )
                    # 提示 LLM 切换目标
                    tool_result = (
                        f"{tool_result}\n"
                        f"[守卫提示] 当前应用/网站多次失败，请切换到其他替代方案。"
                    )

                # 将 tool 结果回填消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": str(tool_result),
                })

        logger.warning(
            f"⏰ [DesktopExecutor] 达到最大迭代次数 ({_MAX_ITERATIONS})，任务未完成"
        )
        return StepResult(
            success=False,
            message=f"达到最大迭代次数 ({_MAX_ITERATIONS})，任务未完成",
            data={"iterations": _MAX_ITERATIONS},
        )

    async def _call_llm(self, messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        调用 vLLM /v1/chat/completions 获取 LLM 响应

        通过 aiohttp 直接调用，支持 tool_call。

        Args:
            messages: 对话消息列表

        Returns:
            Dict 包含 content 和 tool_calls，或 None 表示失败
        """
        try:
            import aiohttp
        except ImportError:
            # aiohttp 已在 requirements.txt 中，不应发生
            return None

        url = f"{EXECUTOR_LLM_URL}/v1/chat/completions"
        payload = {
            "model": EXECUTOR_LLM_MODEL,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
        }
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {EXECUTOR_LLM_TOKEN}"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.warning(
                            f"⚠️ [DesktopExecutor] LLM API 返回 HTTP {resp.status}: "
                            f"{error_text[:200]}"
                        )
                        return None
                    data = await resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    logger.info(f"🪛 [DesktopExecutor] LLM 响应: {msg}")

                    return {
                        "content": msg.get("content", ""),
                        "tool_calls": msg.get("tool_calls"),
                    }
        except Exception as exc:
            logger.error(f"❌ [DesktopExecutor] LLM 调用异常: {exc}")
            return None


def _get_tool_icon(tool_name: str) -> str:
    """根据工具名称返回对应的日志图标"""
    icons = {
        "page_analyze": "🔍",
        "click": "🖱️",
        "type_text": "⌨️",
        "key_press": "⌨️",
        "app_open": "🌐",
        "shell_run": "💻",
    }
    return icons.get(tool_name, "🔧")


def _summarize_args(func_name: str, func_args: Dict[str, Any]) -> str:
    """简要描述工具参数，避免日志过长"""
    if func_name == "click":
        return f'selector="{func_args.get("selector", "")}"'
    if func_name == "type_text":
        return f'selector="{func_args.get("selector", "")}", text="{func_args.get("text", "")}"'
    if func_name == "key_press":
        return f'key="{func_args.get("key", "")}"'
    if func_name == "app_open":
        return f'url="{func_args.get("url", "")}"'
    if func_name == "page_analyze":
        return f'element_type="{func_args.get("element_type", "search")}"'
    if func_name == "shell_run":
        cmd = func_args.get("command", "")
        return f'command="{cmd[:50]}"' if len(cmd) > 50 else f'command="{cmd}"'
    return str(func_args)[:100]


def _summarize_result(func_name: str, result: str) -> str:
    """简要描述工具执行结果，避免日志过长"""
    if func_name == "page_analyze":
        try:
            data = json.loads(result)
            found = data.get("found", False)
            elements = data.get("elements", [])
            if found and elements:
                descs = [e.get("description", "?") for e in elements[:3]]
                return f"找到 {len(elements)} 个元素: {descs}"
            return f"未找到目标元素"
        except (json.JSONDecodeError, TypeError):
            pass
    # 默认截断
    return result[:200] if len(result) > 200 else result
