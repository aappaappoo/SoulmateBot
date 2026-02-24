"""
Agent 执行器 - LLM 自主决策 + 浏览器工具循环

核心执行流程（AI 自主操控）：
1. 构建 system prompt（包含浏览器工具使用说明）
2. 注册 browser tool
3. while 循环（max N 次）：
   - LLM 分析当前状态，决定下一步操作
   - 执行 tool_call（浏览器操作）
   - TaskGuard 安全检查
   - 错误转义层将原始错误转为 AI 可理解的提示
   - 将 tool result 回填 messages，LLM 在下一轮能感知到执行状态
4. LLM 不再调用工具 → 任务完成，生成自然语言回复

所有决策由 LLM 自主完成：
- 意图识别：LLM 自然理解用户需求
- 目标网站选择：LLM 自主选择最合适的网站
- 关键词提取：LLM 自动从用户输入中理解和提取
- 操作步骤：LLM 根据 snapshot 结果自主决定点击/输入等操作
- 错误恢复：LLM 根据 AI 友好的错误提示自主决定恢复策略
"""
import json
import time
from typing import Any, Dict, List, Optional
import asyncio
import aiohttp
from loguru import logger

from config import settings
from task_engine.executors.base import BaseExecutor
from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
from task_engine.models import Step, StepResult
from task_engine.executors.agent_executor.tools import (
    TOOL_DEFINITIONS,
    TOOL_REGISTRY,
    to_ai_friendly_error,
)

# LLM 配置
_EXECUTOR_LLM_URL = getattr(settings, "executor_llm_url", None) or getattr(settings, "vllm_api_url",
                                                                           None) or "http://localhost:8000"
_EXECUTOR_LLM_MODEL = getattr(settings, "executor_llm_model", None) or getattr(settings, "vllm_model", "default")
_EXECUTOR_LLM_TOKEN = getattr(settings, "executor_llm_token", None) or getattr(settings, "vllm_api_token", None) or ""
_MAX_ITERATIONS = getattr(settings, "max_iterations", 15) or 15

# Agent system prompt - LLM 自主决策
_SYSTEM_PROMPT = """你是一个 AI 自主操控助手。你的任务是通过浏览器自动化工具完成用户的请求。

你有一个工具可用：browser —— 浏览器自动化控制。

你需要根据用户的请求，自主决定：
1. 自行判断用户请求所提供的信息是否充足，若不足则需要向用户追问缺失参数
2. 应该打开哪个网站（自主选择最合适的目标网站）
3. 应该搜索什么关键词（从用户请求中自动理解和提取）
4. 应该执行什么操作（点击、输入、滚动等）
5. 如何验证操作是否成功

标准操作流程：
1. 启动浏览器：browser(action="start")
2. 导航到目标网站：browser(action="navigate", url="...")
3. 等待页面加载完成：browser(action="wait", wait_type="loadState", value="networkidle")
4. 获取页面快照：browser(action="snapshot") — 返回页面 UI 树，包含每个可交互元素的 ref ID
5. 根据快照中的元素 ref 执行操作：
   - 点击：browser(action="act", act_kind="click", ref="e1")
   - 输入文本：browser(action="act", act_kind="type", ref="e2", value="搜索词")
   - 输入并提交：browser(action="act", act_kind="type", ref="e2", value="搜索词", submit=true)
   - 清空并填入：browser(action="act", act_kind="fill", ref="e2", value="新文本")
   - 按键：browser(action="act", act_kind="press", value="Enter")
   - 滚动：browser(action="act", act_kind="scroll")
   - 选择下拉项：browser(action="act", act_kind="select", ref="e3", values=["option1"])
   - 拖拽：browser(action="act", act_kind="drag", start_ref="e4", end_ref="e5")
6. 再次 snapshot 确认操作结果
7. 重复 5-6 直到任务完成
8. 任务完成后关闭浏览器：browser(action="close")

【元素定位策略】（按优先级从高到低）：
- ref: 来自 snapshot 的元素 ID（如 "e1"），最常用，但页面变化后可能失效
- selector: CSS 选择器（如 "#search-input", ".btn"），当 ref 匹配多个元素时使用
- coordinate: 坐标 "x,y"，当以上方式都不可用时的兜底方案
- frame: 当目标元素在 iframe 内时，需要指定 frame 参数
- target_id: 多 Tab 场景下指定操作的目标 Tab

【等待操作 wait 的使用场景】：
- 导航后等待页面加载：browser(action="wait", wait_type="loadState", value="networkidle")
- 点击后等待新内容出现：browser(action="wait", wait_type="text", value="搜索结果")
- 等待加载指示器消失：browser(action="wait", wait_type="textGone", value="加载中...")
- 等待特定元素出现：browser(action="wait", wait_type="selector", value=".result-item")
- 等待 URL 跳转：browser(action="wait", wait_type="url", value="/search?q=")
- 固定等待（不推荐，仅当无法判断加载状态时）：browser(action="wait", wait_type="time", value="2000")

【snapshot 高级用法】：
- 默认模式（推荐）：browser(action="snapshot")
- 只看可交互元素（页面复杂时推荐）：browser(action="snapshot", interactive=true)
- 使用稳定 ref（需要跨快照复用 ref 时）：browser(action="snapshot", refs_mode="aria")

【错误处理策略】（非常重要！）：
当工具返回 success=false 时，error 字段包含 AI 可读的错误描述和【建议】。请务必阅读建议并执行：
- "匹配到多个元素" → 执行 snapshot 获取最新 ref，或用 selector 精确定位
- "元素不可见" → 先 wait(wait_type="loadState") 等待加载，再 snapshot
- "元素被遮挡" → 尝试 scroll 或关闭弹窗后重试
- "操作超时" → snapshot 查看最新页面状态
- "已从 DOM 移除" → snapshot 获取最新 ref
- 如果同一个 ref 连续失败 2 次，不要继续重试，改用 snapshot + 新 ref 或 selector

重要规则：
- 每次操作后都应 snapshot 确认状态
- 导航后务必先 wait 再 snapshot，避免获取到空元素列表
- snapshot 返回的 ref ID 可直接用于后续 act 操作
- 如果某个网站不可用，自主切换到替代网站
- 不要尝试登录、支付、输入密码等敏感操作
- 如果某个网站需要登录才能使用，尝试其他网站
- 任务完成后，用自然语言描述操作结果（不再调用工具）
- 仅使用国内网址不使用需要梯子才能打开的网址
- 若判断用户请求所提供的信息存在不足则需要向用户追问缺失参数（不再调用工具）;不进行工具调用
"""

LLM_MAX_PER_MINUTE = 20  # 每分钟最多调用 LLM 的次数
_llm_semaphore = asyncio.Semaphore(LLM_MAX_PER_MINUTE)
_last_reset = time.time()


async def _throttle_llm():
    """每分钟限流，自动重置计数"""
    global _llm_semaphore, _last_reset
    now = time.time()
    if now - _last_reset >= 60:
        _llm_semaphore = asyncio.Semaphore(LLM_MAX_PER_MINUTE)
        _last_reset = now
    await _llm_semaphore.acquire()


class AgentExecutor(BaseExecutor):
    """
    AI 自主操控执行器

    通过 LLM + browser tool 循环实现全自主任务执行。
    LLM 自主决定目标网站、关键词提取、操作步骤，无需硬编码。
    错误转义层确保 LLM 能感知每次操作的执行状态，辅助下一轮决策。
    """

    def __init__(self) -> None:
        self._guard = TaskGuard()

    async def execute(self, step: Step) -> StepResult:
        """
        执行 AI 自主操控任务

        Args:
            step: 包含 params["task"] 的步骤

        Returns:
            StepResult: 执行结果
        """
        task_text: str = step.params.get("task", "")
        if not task_text:
            return StepResult(success=False, message="缺少 task 参数")

        self._guard.reset()
        logger.info(f"🤖 [AgentExecutor] 开始 AI 自主操控任务: {task_text}")

        # 构建初始消息
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"请完成以下任务：{task_text}"},
        ]
        accumulated_content = ""
        for iteration in range(1, _MAX_ITERATIONS + 1):
            logger.info(f"🔄 [AgentExecutor] === 第 {iteration}/{_MAX_ITERATIONS} 轮 ===")

            # 调用 LLM 获取下一步操作
            llm_response = await self._call_llm(messages)

            if llm_response is None:
                logger.error(f"❌ [AgentExecutor] LLM 调用失败（第 {iteration} 轮）")
                return StepResult(
                    success=False,
                    message=f"LLM 调用失败（第 {iteration} 轮）",
                )

            # 检查是否有 tool_call
            tool_calls = llm_response.get("tool_calls")
            assistant_content = llm_response.get("content", "")

            if assistant_content:
                assistant_content = assistant_content.strip() + "\n"
                logger.debug(f"💬 [AgentExecutor] LLM 回复: {assistant_content[:]}")

            if not tool_calls:
                # LLM 不再调用工具，任务完成
                logger.info(f"✅ [AgentExecutor] 任务完成（第 {iteration} 轮），LLM 无更多工具调用")
                return StepResult(
                    success=True,
                    message=assistant_content or "AI 自主操控任务已完成",
                    data={"iterations": iteration},
                )

            # 将 assistant 消息加入历史
            messages.append({
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": tool_calls,
            })

            logger.info(
                f"🛠️ [AgentExecutor] 第 {iteration} 轮共 {len(tool_calls)} 个工具调用"
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

                logger.info(
                    f"🌐 [AgentExecutor] 执行工具 [{tc_idx}/{len(tool_calls)}]: "
                    f"{func_name}({_summarize_args(func_args)})"
                )

                # TaskGuard 执行前安全检查
                pre_action = self._guard.pre_check(func_name, func_args)
                if pre_action == GuardAction.ABORT:
                    logger.warning(
                        f"🛑 [AgentExecutor] 安全守卫拒绝执行: "
                        f"tool={func_name}, iteration={iteration}"
                    )
                    return StepResult(
                        success=False,
                        message="安全守卫终止：检测到危险操作或过多偏离",
                        data={"iterations": iteration, "last_tool": func_name},
                    )

                # 执行工具
                tool_fn = TOOL_REGISTRY.get(func_name)
                if tool_fn is None:
                    tool_result = f"未知工具: {func_name}"
                    logger.warning(f"⚠️ [AgentExecutor] 未知工具: {func_name}")
                else:
                    try:
                        start_time = time.time()
                        tool_result = await tool_fn(**func_args)
                        elapsed = time.time() - start_time

                        # 解析结果判断成功/失败
                        try:
                            tool_result_json = json.loads(tool_result)
                        except (json.JSONDecodeError, TypeError):
                            tool_result_json = {}

                        is_success = tool_result_json.get("success", False) is True

                        if is_success:
                            logger.info(
                                f"✅ [AgentExecutor] 工具 {func_name} 执行成功 "
                                f"({elapsed:.1f}s): {str(tool_result)[:200]}"
                            )
                        else:
                            # ★ 错误转义：确保回填给 LLM 的是 AI 可理解的错误
                            # （browser_tool 内部已做过一次转义，这里做二次保障）
                            raw_error = tool_result_json.get("error", "")
                            if raw_error and "【建议】" not in raw_error:
                                # 如果 browser_tool 层没有转义过，这里补做
                                friendly_error = to_ai_friendly_error(
                                    raw_error,
                                    ref=func_args.get("ref"),
                                    action=func_args.get("action", ""),
                                )
                                tool_result_json["error"] = friendly_error
                                tool_result = json.dumps(
                                    tool_result_json, ensure_ascii=False
                                )

                            logger.warning(
                                f"❌ [AgentExecutor] 工具 {func_name} 执行失败 "
                                f"({elapsed:.1f}s): {str(tool_result)[:200]}"
                            )

                        logger.debug(
                            f"[AgentExecutor] 完整结果: {str(tool_result)[:]}"
                        )

                    except Exception as e:
                        # 异常也经过错误转义层
                        friendly_error = to_ai_friendly_error(
                            str(e),
                            ref=func_args.get("ref"),
                            action=func_args.get("action", ""),
                        )
                        tool_result = json.dumps(
                            {"success": False, "error": friendly_error},
                            ensure_ascii=False,
                        )
                        logger.error(
                            f"❌ [AgentExecutor] 工具 {func_name} 执行异常: {friendly_error}"
                        )

                # 将 tool 结果回填消息 — LLM 在下一轮能完整感知到本次操作的执行状态
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": str(tool_result),
                })

        logger.warning(
            f"⏰ [AgentExecutor] 达到最大迭代次数 ({_MAX_ITERATIONS})，任务未完成"
        )
        return StepResult(
            success=False,
            message=f"达到最大迭代次数 ({_MAX_ITERATIONS})，任务未完成",
            data={"iterations": _MAX_ITERATIONS},
        )

    async def _call_llm(self, messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        await _throttle_llm()
        try:
            return await self._call_llm_without_throttled(messages)
        finally:
            # 这里不立即释放，Semaphore 会在每分钟重置
            pass

    async def _call_llm_without_throttled(self, messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        调用 LLM /v1/chat/completions 获取响应

        Args:
            messages: 对话消息列表

        Returns:
            Dict 包含 content 和 tool_calls，或 None 表示失败
        """
        url = f"{_EXECUTOR_LLM_URL}/v1/chat/completions"
        payload = {
            "model": _EXECUTOR_LLM_MODEL,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
        }

        try:
            headers = {
                "Content-Type": "application/json",
            }
            if _EXECUTOR_LLM_TOKEN:
                headers["Authorization"] = f"Bearer {_EXECUTOR_LLM_TOKEN}"

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
                            f"⚠️ [AgentExecutor] LLM API 返回 HTTP {resp.status}: "
                            f"{error_text[:200]}"
                        )
                        return None

                    data = await resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    payload_str = json.dumps(payload, ensure_ascii=False)
                    logger.debug(f"📝 [AgentExecutor] LLM 输入: {payload_str}")
                    return {
                        "content": msg.get("content", ""),
                        "tool_calls": msg.get("tool_calls"),
                    }
        except Exception as exc:
            logger.error(f"❌ [AgentExecutor] LLM 调用异常: {exc}")
            return None


def _summarize_args(func_args: Dict[str, Any]) -> str:
    """简要描述工具参数，避免日志过长"""
    action = func_args.get("action", "")
    parts = [f"action={action}"]
    if func_args.get("url"):
        parts.append(f"url=\"{func_args['url']}\"")
    if func_args.get("act_kind"):
        parts.append(f"actKind={func_args['act_kind']}")
    if func_args.get("ref"):
        parts.append(f"ref={func_args['ref']}")
    if func_args.get("selector"):
        parts.append(f"selector=\"{func_args['selector']}\"")
    if func_args.get("wait_type"):
        parts.append(f"waitType={func_args['wait_type']}")
    if func_args.get("frame"):
        parts.append(f"frame=\"{func_args['frame']}\"")
    if func_args.get("target_id"):
        parts.append(f"targetId={func_args['target_id']}")
    if func_args.get("value"):
        val = func_args["value"]
        parts.append(f"value=\"{val[:50]}\"" if len(val) > 50 else f"value=\"{val}\"")
    return ", ".join(parts)
