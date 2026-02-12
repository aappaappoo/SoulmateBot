"""
task_engine 单元测试

测试内容：
- 数据模型（Task / Step / StepResult）
- Planner（桌面任务识别）
- Guard（三层安全守卫）
- Platform（平台检测）
- Verifier（结果验证）
- Reporter（报告生成）
- ShellExecutor（安全 shell 执行）
- LLMExecutor（LLM 兜底）
- ExecutorRouter（路由分发）
- TaskEngine（完整流程）
- TaskEngineAgent（Agent 桥接）
- Desktop Tools（工具注册）
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保项目根目录在 sys.path 中
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))


# ============================================================
# 数据模型测试
# ============================================================

class TestModels:
    """测试 Task / Step / StepResult 数据模型"""

    def test_executor_type_values(self):
        from task_engine.models import ExecutorType
        assert ExecutorType.SHELL == "shell"
        assert ExecutorType.LLM == "llm"
        assert ExecutorType.DESKTOP == "desktop"

    def test_task_status_values(self):
        from task_engine.models import TaskStatus
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.SUCCESS == "success"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.ABORTED == "aborted"

    def test_step_creation(self):
        from task_engine.models import ExecutorType, Step
        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="桌面操控",
            params={"task": "打开浏览器"},
        )
        assert step.executor_type == ExecutorType.DESKTOP
        assert step.description == "桌面操控"
        assert step.params["task"] == "打开浏览器"

    def test_step_default_params(self):
        from task_engine.models import ExecutorType, Step
        step = Step(executor_type=ExecutorType.LLM, description="test")
        assert step.params == {}

    def test_step_result_creation(self):
        from task_engine.models import StepResult
        result = StepResult(success=True, message="完成")
        assert result.success is True
        assert result.message == "完成"
        assert result.data == {}

    def test_task_creation(self):
        from task_engine.models import Task, TaskStatus
        task = Task(user_input="播放音乐")
        assert task.user_input == "播放音乐"
        assert task.steps == []
        assert task.status == TaskStatus.PENDING
        assert task.result is None


# ============================================================
# Planner 测试
# ============================================================

class TestPlanner:
    """测试任务规划器"""

    @pytest.mark.asyncio
    async def test_desktop_task_detection(self):
        from task_engine.models import ExecutorType
        from task_engine.planner import plan
        task = await plan("打开网页里的音乐输入周杰伦播放音乐")
        assert len(task.steps) == 1
        assert task.steps[0].executor_type == ExecutorType.DESKTOP

    @pytest.mark.asyncio
    async def test_desktop_keywords_multiple_hits(self):
        from task_engine.models import ExecutorType
        from task_engine.planner import plan
        task = await plan("打开浏览器播放视频")
        assert task.steps[0].executor_type == ExecutorType.DESKTOP

    @pytest.mark.asyncio
    async def test_non_desktop_task_fallback(self):
        from task_engine.models import ExecutorType
        from task_engine.planner import plan
        task = await plan("你好，今天心情不错")
        assert len(task.steps) == 1
        assert task.steps[0].executor_type == ExecutorType.LLM

    @pytest.mark.asyncio
    async def test_single_keyword_not_desktop(self):
        from task_engine.models import ExecutorType
        from task_engine.planner import plan
        # 只命中 1 个关键词，不应被识别为桌面任务
        task = await plan("音乐好听")
        assert task.steps[0].executor_type == ExecutorType.LLM

    @pytest.mark.asyncio
    async def test_task_params_contain_user_input(self):
        from task_engine.planner import plan
        user_input = "打开网页搜索周杰伦"
        task = await plan(user_input)
        assert task.steps[0].params["task"] == user_input


# ============================================================
# Guard 测试
# ============================================================

class TestTaskGuard:
    """测试三层安全守卫"""

    def test_allow_normal_operation(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        action = guard.check("click", {"x": 100, "y": 200}, "已点击坐标 (100, 200)")
        assert action == GuardAction.ALLOW

    def test_abort_on_login(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        action = guard.check("vision_analyze", {}, "页面显示登录框")
        assert action == GuardAction.ABORT

    def test_abort_on_payment(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        action = guard.check("click", {}, "支付确认按钮")
        assert action == GuardAction.ABORT

    def test_abort_on_password(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        action = guard.check("type_text", {"text": "abc"}, "密码输入框")
        assert action == GuardAction.ABORT

    def test_abort_on_sudo(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        action = guard.check("shell_run", {"command": "sudo apt install"}, "")
        assert action == GuardAction.ABORT

    def test_drift_accumulation(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        # 偏离信号不足阈值时仍然允许
        guard.check("vision_analyze", {}, "需要登录才能继续")
        assert guard.drift_count == 0  # 第一层先拦截

    def test_drift_threshold_abort(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        # 模拟多次偏离（使用不触发第一层的偏离信号）
        for _ in range(3):
            guard.check("screenshot", {}, "页面提示：会员专享")
        action = guard.check("screenshot", {}, "正常操作")
        assert action == GuardAction.ABORT

    def test_switch_on_repeated_failure(self):
        from task_engine.executors.desktop_executor.guard import GuardAction, TaskGuard
        guard = TaskGuard()
        # 同一 URL 多次失败
        for _ in range(3):
            action = guard.check("app_open", {"url": "https://music.example.com"}, "打开失败")
        assert action == GuardAction.SWITCH

    def test_reset(self):
        from task_engine.executors.desktop_executor.guard import TaskGuard
        guard = TaskGuard()
        guard.drift_count = 5
        guard.fail_counts["test"] = 3
        guard.reset()
        assert guard.drift_count == 0
        assert guard.fail_counts == {}


# ============================================================
# Platform 测试
# ============================================================

class TestPlatform:
    """测试平台检测"""

    def test_detect_platform_returns_valid_type(self):
        from task_engine.executors.desktop_executor.platform import PlatformType, detect_platform
        result = detect_platform()
        assert result in (PlatformType.MACOS, PlatformType.LINUX, PlatformType.UNKNOWN)

    def test_get_open_command(self):
        from task_engine.executors.desktop_executor.platform import get_open_command
        cmd = get_open_command()
        assert cmd in ("open", "xdg-open")

    def test_get_screenshot_command(self):
        from task_engine.executors.desktop_executor.platform import get_screenshot_command
        cmd = get_screenshot_command()
        assert "{path}" in cmd

    @patch("platform.system", return_value="Darwin")
    def test_macos_detection(self, mock_sys):
        from task_engine.executors.desktop_executor.platform import PlatformType, detect_platform
        assert detect_platform() == PlatformType.MACOS

    @patch("platform.system", return_value="Linux")
    def test_linux_detection(self, mock_sys):
        from task_engine.executors.desktop_executor.platform import PlatformType, detect_platform
        assert detect_platform() == PlatformType.LINUX

    @patch("platform.system", return_value="Windows")
    def test_unknown_detection(self, mock_sys):
        from task_engine.executors.desktop_executor.platform import PlatformType, detect_platform
        assert detect_platform() == PlatformType.UNKNOWN


# ============================================================
# Verifier 测试
# ============================================================

class TestVerifier:
    """测试结果验证器"""

    @pytest.mark.asyncio
    async def test_verify_success(self):
        from task_engine.models import StepResult, Task, TaskStatus
        from task_engine.verifier import verify
        task = Task(user_input="test")
        task.result = StepResult(success=True, message="完成")
        task = await verify(task)
        assert task.status == TaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_verify_failure(self):
        from task_engine.models import StepResult, Task, TaskStatus
        from task_engine.verifier import verify
        task = Task(user_input="test")
        task.result = StepResult(success=False, message="出错了")
        task = await verify(task)
        assert task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_verify_aborted(self):
        from task_engine.models import StepResult, Task, TaskStatus
        from task_engine.verifier import verify
        task = Task(user_input="test")
        task.result = StepResult(success=False, message="安全守卫终止：检测到危险")
        task = await verify(task)
        assert task.status == TaskStatus.ABORTED

    @pytest.mark.asyncio
    async def test_verify_no_result(self):
        from task_engine.models import Task, TaskStatus
        from task_engine.verifier import verify
        task = Task(user_input="test")
        task = await verify(task)
        assert task.status == TaskStatus.FAILED


# ============================================================
# Reporter 测试
# ============================================================

class TestReporter:
    """测试报告生成器"""

    @pytest.mark.asyncio
    async def test_report_success(self):
        from task_engine.models import StepResult, Task, TaskStatus
        from task_engine.reporter import report
        task = Task(user_input="test")
        task.status = TaskStatus.SUCCESS
        task.result = StepResult(success=True, message="播放了周杰伦的歌")
        text = await report(task)
        assert "✅" in text
        assert "周杰伦" in text

    @pytest.mark.asyncio
    async def test_report_failure(self):
        from task_engine.models import StepResult, Task, TaskStatus
        from task_engine.reporter import report
        task = Task(user_input="test")
        task.status = TaskStatus.FAILED
        task.result = StepResult(success=False, message="失败了")
        text = await report(task)
        assert "❌" in text

    @pytest.mark.asyncio
    async def test_report_aborted(self):
        from task_engine.models import StepResult, Task, TaskStatus
        from task_engine.reporter import report
        task = Task(user_input="test")
        task.status = TaskStatus.ABORTED
        task.result = StepResult(success=False, message="被终止")
        text = await report(task)
        assert "⚠️" in text

    @pytest.mark.asyncio
    async def test_report_pending(self):
        from task_engine.models import Task, TaskStatus
        from task_engine.reporter import report
        task = Task(user_input="test")
        task.status = TaskStatus.PENDING
        text = await report(task)
        assert "⏳" in text


# ============================================================
# ShellExecutor 测试
# ============================================================

class TestShellExecutor:
    """测试安全 Shell 执行器"""

    @pytest.mark.asyncio
    async def test_execute_safe_command(self):
        from task_engine.executors.shell_executor import ShellExecutor
        from task_engine.models import ExecutorType, Step
        executor = ShellExecutor()
        step = Step(
            executor_type=ExecutorType.SHELL,
            description="echo",
            params={"command": "echo hello"},
        )
        result = await executor.execute(step)
        assert result.success is True
        assert "hello" in result.message

    @pytest.mark.asyncio
    async def test_reject_rm_rf(self):
        from task_engine.executors.shell_executor import ShellExecutor
        from task_engine.models import ExecutorType, Step
        executor = ShellExecutor()
        step = Step(
            executor_type=ExecutorType.SHELL,
            description="rm",
            params={"command": "rm -rf /"},
        )
        result = await executor.execute(step)
        assert result.success is False
        assert "安全拒绝" in result.message

    @pytest.mark.asyncio
    async def test_reject_sudo(self):
        from task_engine.executors.shell_executor import ShellExecutor
        from task_engine.models import ExecutorType, Step
        executor = ShellExecutor()
        step = Step(
            executor_type=ExecutorType.SHELL,
            description="sudo",
            params={"command": "sudo apt-get install foo"},
        )
        result = await executor.execute(step)
        assert result.success is False
        assert "安全拒绝" in result.message

    @pytest.mark.asyncio
    async def test_missing_command(self):
        from task_engine.executors.shell_executor import ShellExecutor
        from task_engine.models import ExecutorType, Step
        executor = ShellExecutor()
        step = Step(
            executor_type=ExecutorType.SHELL,
            description="empty",
            params={},
        )
        result = await executor.execute(step)
        assert result.success is False
        assert "缺少" in result.message


# ============================================================
# LLMExecutor 测试
# ============================================================

class TestLLMExecutor:
    """测试 LLM 执行器"""

    @pytest.mark.asyncio
    async def test_execute_with_task(self):
        from task_engine.executors.llm_executor import LLMExecutor
        from task_engine.models import ExecutorType, Step
        executor = LLMExecutor()
        step = Step(
            executor_type=ExecutorType.LLM,
            description="llm",
            params={"task": "你好"},
        )
        result = await executor.execute(step)
        assert result.success is True
        assert "你好" in result.message

    @pytest.mark.asyncio
    async def test_execute_missing_task(self):
        from task_engine.executors.llm_executor import LLMExecutor
        from task_engine.models import ExecutorType, Step
        executor = LLMExecutor()
        step = Step(
            executor_type=ExecutorType.LLM,
            description="empty",
            params={},
        )
        result = await executor.execute(step)
        assert result.success is False


# ============================================================
# ExecutorRouter 测试
# ============================================================

class TestExecutorRouter:
    """测试执行器路由"""

    @pytest.mark.asyncio
    async def test_route_shell(self):
        from task_engine.executor_router import route_and_execute
        from task_engine.models import ExecutorType, Step
        step = Step(
            executor_type=ExecutorType.SHELL,
            description="echo",
            params={"command": "echo router_test"},
        )
        result = await route_and_execute(step)
        assert result.success is True
        assert "router_test" in result.message

    @pytest.mark.asyncio
    async def test_route_llm(self):
        from task_engine.executor_router import route_and_execute
        from task_engine.models import ExecutorType, Step
        step = Step(
            executor_type=ExecutorType.LLM,
            description="llm",
            params={"task": "test"},
        )
        result = await route_and_execute(step)
        assert result.success is True


# ============================================================
# Desktop Tools 测试
# ============================================================

class TestDesktopTools:
    """测试桌面工具注册表"""

    def test_tool_registry_completeness(self):
        from task_engine.executors.desktop_executor.tools import TOOL_REGISTRY
        # 视觉工具已移除（screenshot, vision_analyze, click），使用 Playwright 方案
        expected_tools = [
            "shell_run", "app_open", "type_text", "key_press",
        ]
        for tool_name in expected_tools:
            assert tool_name in TOOL_REGISTRY, f"工具 {tool_name} 未注册"
        # 确认视觉工具已移除
        for removed in ["screenshot", "vision_analyze", "click"]:
            assert removed not in TOOL_REGISTRY, f"视觉工具 {removed} 应已移除"

    def test_tool_definitions_completeness(self):
        from task_engine.executors.desktop_executor.tools import TOOL_DEFINITIONS
        names = [td["function"]["name"] for td in TOOL_DEFINITIONS]
        # 视觉工具已移除，使用 Playwright 方案
        expected = ["app_open", "type_text", "key_press", "shell_run"]
        for name in expected:
            assert name in names, f"工具定义 {name} 缺失"
        # 确认视觉工具已移除
        for removed in ["screenshot", "vision_analyze", "click"]:
            assert removed not in names, f"视觉工具定义 {removed} 应已移除"

    def test_tool_definitions_format(self):
        from task_engine.executors.desktop_executor.tools import TOOL_DEFINITIONS
        for td in TOOL_DEFINITIONS:
            assert td["type"] == "function"
            assert "name" in td["function"]
            assert "description" in td["function"]
            assert "parameters" in td["function"]

    @pytest.mark.asyncio
    async def test_shell_run_safe(self):
        from task_engine.executors.desktop_executor.tools.shell_run import shell_run
        result = await shell_run("echo tool_test")
        assert "tool_test" in result

    @pytest.mark.asyncio
    async def test_shell_run_reject_sudo(self):
        from task_engine.executors.desktop_executor.tools.shell_run import shell_run
        result = await shell_run("sudo rm -rf /")
        assert "安全拒绝" in result


# ============================================================
# DesktopExecutor 测试
# ============================================================

class TestDesktopExecutor:
    """测试桌面操控执行器（Playwright 方案）"""

    @pytest.mark.asyncio
    async def test_missing_task_param(self):
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step
        executor = DesktopExecutor()
        step = Step(executor_type=ExecutorType.DESKTOP, description="test", params={})
        result = await executor.execute(step)
        assert result.success is False
        assert "缺少" in result.message

    def test_extract_music_query_input_pattern(self):
        """测试从'输入XXX播放'模式提取关键词"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        assert DesktopExecutor._extract_music_query("打开网页里的音乐输入周杰伦播放音乐") == "周杰伦"

    def test_extract_music_query_search_pattern(self):
        """测试从'搜索XXX播放'模式提取关键词"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        assert DesktopExecutor._extract_music_query("搜索林俊杰播放") == "林俊杰"

    def test_extract_music_query_no_match(self):
        """测试无法匹配时返回 None"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        assert DesktopExecutor._extract_music_query("今天天气不错") is None

    @pytest.mark.asyncio
    async def test_no_query_returns_error(self):
        """测试无法识别关键词时返回错误"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step
        executor = DesktopExecutor()
        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="test",
            params={"task": "今天天气不错"},
        )
        result = await executor.execute(step)
        assert result.success is False
        assert "无法识别" in result.message

    @pytest.mark.asyncio
    async def test_playwright_play_music_mock(self):
        """测试 Playwright 播放音乐（mock Playwright）"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step

        executor = DesktopExecutor()

        # Mock _play_music 返回成功
        async def mock_play_music(query):
            return StepResult(
                success=True,
                message=f"已播放 {query} 的音乐: 晴天",
                data={"query": query, "song": "晴天"},
            )

        from task_engine.models import StepResult
        executor._play_music = mock_play_music

        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="test",
            params={"task": "打开网页里的音乐输入周杰伦播放音乐"},
        )
        result = await executor.execute(step)
        assert result.success is True
        assert "周杰伦" in result.message
        assert "晴天" in result.message

    @pytest.mark.asyncio
    async def test_playwright_import_error(self):
        """测试 Playwright 未安装时返回友好错误"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step

        executor = DesktopExecutor()

        # Mock _play_music 模拟 Playwright 未安装
        async def mock_play_music(query):
            return StepResult(
                success=False,
                message="Playwright 未安装，请运行: pip install playwright && playwright install chromium",
            )

        from task_engine.models import StepResult
        executor._play_music = mock_play_music

        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="test",
            params={"task": "打开网页里的音乐输入周杰伦播放音乐"},
        )
        result = await executor.execute(step)
        assert result.success is False
        assert "Playwright" in result.message


# ============================================================
# TaskEngine 完整流程测试
# ============================================================

class TestTaskEngine:
    """测试完整任务引擎流程"""

    @pytest.mark.asyncio
    async def test_llm_fallback_flow(self):
        """非桌面任务走 LLM 兜底"""
        from task_engine.engine import TaskEngine
        engine = TaskEngine()
        result = await engine.run("你好，今天天气真好")
        assert "✅" in result
        assert "LLM" in result

    @pytest.mark.asyncio
    async def test_desktop_flow_without_playwright(self):
        """桌面任务在无 Playwright 时应返回失败"""
        from task_engine.engine import TaskEngine
        engine = TaskEngine()
        result = await engine.run("打开网页里的音乐输入周杰伦播放音乐")
        # Playwright 未安装或执行失败时返回错误
        assert "❌" in result or "Playwright" in result or "播放失败" in result

    @pytest.mark.asyncio
    async def test_desktop_flow_with_mocked_playwright(self):
        """桌面任务使用 mocked Playwright 完整流程"""
        from task_engine.engine import TaskEngine
        from task_engine.models import StepResult

        # Mock DesktopExecutor._play_music 模拟成功播放
        async def mock_play_music(self, query):
            return StepResult(
                success=True,
                message=f"已播放 {query} 的音乐: 晴天",
                data={"query": query, "song": "晴天"},
            )

        with patch(
            "task_engine.executors.desktop_executor.executor.DesktopExecutor._play_music",
            mock_play_music,
        ):
            engine = TaskEngine()
            # 需要清除缓存的执行器实例
            from task_engine import executor_router
            executor_router._executors.clear()

            result = await engine.run("打开网页里的音乐输入周杰伦播放音乐")
            assert "✅" in result
            assert "周杰伦" in result
            assert "晴天" in result

            # 清理
            executor_router._executors.clear()


# ============================================================
# TaskEngineAgent 测试
# ============================================================

class TestTaskEngineAgent:
    """测试 TaskEngine Agent 桥接"""

    @pytest.fixture
    def agent(self):
        from src.agents.plugins.task_engine_agent import TaskEngineAgent
        return TaskEngineAgent()

    def test_agent_name(self, agent):
        assert agent.name == "TaskEngineAgent"

    def test_agent_description(self, agent):
        assert len(agent.description) > 0
        assert "桌面" in agent.description

    def test_skills(self, agent):
        assert "desktop_control" in agent.skills
        assert "music_play" in agent.skills
        assert "web_automation" in agent.skills

    def test_skill_keywords(self, agent):
        kw = agent.skill_keywords
        assert "desktop_control" in kw
        assert "打开" in kw["desktop_control"]

    def test_skill_description(self, agent):
        desc = agent.get_skill_description("desktop_control")
        assert desc is not None

    def test_can_handle_high_confidence(self, agent):
        from src.agents.models import ChatContext, Message
        msg = Message(content="打开网页播放音乐", user_id="u1", chat_id="c1")
        ctx = ChatContext(chat_id="c1")
        confidence = agent.can_handle(msg, ctx)
        assert confidence >= 0.75

    def test_can_handle_mention(self, agent):
        from src.agents.models import ChatContext, Message
        msg = Message(
            content="@TaskEngineAgent 帮我操作",
            user_id="u1",
            chat_id="c1",
            metadata={"mentions": ["@TaskEngineAgent"]},
        )
        ctx = ChatContext(chat_id="c1")
        assert agent.can_handle(msg, ctx) == 1.0

    def test_can_handle_no_match(self, agent):
        from src.agents.models import ChatContext, Message
        msg = Message(content="今天心情很好", user_id="u1", chat_id="c1")
        ctx = ChatContext(chat_id="c1")
        assert agent.can_handle(msg, ctx) == 0.0

    def test_can_handle_single_keyword_low(self, agent):
        from src.agents.models import ChatContext, Message
        msg = Message(content="音乐好听", user_id="u1", chat_id="c1")
        ctx = ChatContext(chat_id="c1")
        confidence = agent.can_handle(msg, ctx)
        assert confidence == 0.4

    def test_memory_read_write(self, agent):
        agent.memory_write("u1", {"count": 1})
        data = agent.memory_read("u1")
        assert data["count"] == 1

    def test_memory_read_empty(self, agent):
        data = agent.memory_read("nonexistent")
        assert data == {}

    def test_can_provide_skill(self, agent):
        assert agent.can_provide_skill("desktop_control") is True
        assert agent.can_provide_skill("nonexistent") is False

    def test_respond_non_desktop(self, agent):
        """测试非桌面任务的 respond"""
        from src.agents.models import AgentResponse, ChatContext, Message
        msg = Message(content="你好", user_id="u1", chat_id="c1")
        ctx = ChatContext(chat_id="c1")
        response = agent.respond(msg, ctx)
        assert isinstance(response, AgentResponse)
        assert response.agent_name == "TaskEngineAgent"
