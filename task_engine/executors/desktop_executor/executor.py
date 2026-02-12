"""
桌面操控执行器 - 核心 LLM tool-call 循环

⭐ 这是整个 task_engine 中最关键的模块。

执行流程：
1. 构建 system prompt（桌面操控策略）
2. 注册 DesktopToolRegistry
3. while 循环（max 15 次）：
   - LLM 返回 tool_call
   - 执行 tool
   - TaskGuard 校验
   - 将 tool result 回填 messages
4. LLM 不再调用工具 → 任务完成

tool_call 通过 aiohttp 调 vLLM /v1/chat/completions
（VLLMProvider 本身不支持 tools）
"""
import json
import os
from typing import Any, Dict, List, Optional

from task_engine.models import Step, StepResult
from task_engine.executors.base import BaseExecutor
from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
from task_engine.executors.desktop_executor.tools import TOOL_DEFINITIONS, TOOL_REGISTRY

# 最大循环次数
_MAX_ITERATIONS: int = 15

# vLLM 服务地址（从环境变量读取，无需新配置文件）
_VLLM_BASE_URL: str = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")
_VLLM_MODEL: str = os.environ.get("VLLM_MODEL", "default")

# 桌面操控 system prompt
_SYSTEM_PROMPT: str = """你是一个桌面操控助手。你的任务是通过调用工具来完成用户的桌面操作请求。

可用工具：
- app_open: 打开浏览器/URL
- screenshot: 屏幕截图
- vision_analyze: 视觉分析截图，识别 UI 元素坐标
- click: 鼠标点击指定坐标
- type_text: 在当前焦点位置输入文本
- key_press: 按下键盘按键
- shell_run: 执行 shell 命令

操作策略：
1. 先打开目标应用/网页
2. 截图查看当前屏幕状态
3. 用视觉分析找到目标 UI 元素
4. 点击/输入/按键完成操作
5. 再次截图验证结果
6. 重复直到任务完成

注意事项：
- 不要尝试登录、支付、输入密码等敏感操作
- 如果某个网站需要登录才能使用，尝试其他网站
- 每次操作后都应截图确认状态
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

        # 构建初始消息
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"请完成以下桌面操作任务：{task_text}"},
        ]

        for iteration in range(1, _MAX_ITERATIONS + 1):
            # 调用 LLM 获取下一步操作
            llm_response = await self._call_llm(messages)

            if llm_response is None:
                return StepResult(
                    success=False,
                    message=f"LLM 调用失败（第 {iteration} 轮）",
                )

            # 检查是否有 tool_call
            tool_calls = llm_response.get("tool_calls")
            assistant_content = llm_response.get("content", "")

            if not tool_calls:
                # LLM 不再调用工具，任务完成
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

            # 依次执行每个 tool_call
            for tc in tool_calls:
                func_name: str = tc.get("function", {}).get("name", "")
                func_args_raw: str = tc.get("function", {}).get("arguments", "{}")
                tc_id: str = tc.get("id", "")

                try:
                    func_args: Dict[str, Any] = json.loads(func_args_raw)
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                # 执行工具
                tool_fn = TOOL_REGISTRY.get(func_name)
                if tool_fn is None:
                    tool_result = f"未知工具: {func_name}"
                else:
                    try:
                        tool_result = await tool_fn(**func_args)
                    except Exception as e:
                        tool_result = f"工具执行异常: {e}"

                # 守卫检查
                action = self._guard.check(func_name, func_args, str(tool_result))
                if action == GuardAction.ABORT:
                    return StepResult(
                        success=False,
                        message=f"安全守卫终止：检测到危险操作或过多偏离",
                        data={"iterations": iteration, "last_tool": func_name},
                    )
                elif action == GuardAction.SWITCH:
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

        url = f"{_VLLM_BASE_URL}/v1/chat/completions"
        payload = {
            "model": _VLLM_MODEL,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    return {
                        "content": msg.get("content", ""),
                        "tool_calls": msg.get("tool_calls"),
                    }
        except Exception:
            return None
