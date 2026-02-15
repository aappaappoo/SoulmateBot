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
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
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
        expected_tools = [
            "shell_run", "app_open", "screenshot",
            "vision_analyze", "page_analyze", "click", "type_text", "key_press",
        ]
        for tool_name in expected_tools:
            assert tool_name in TOOL_REGISTRY, f"工具 {tool_name} 未注册"

    def test_tool_definitions_completeness(self):
        from task_engine.executors.desktop_executor.tools import TOOL_DEFINITIONS
        names = [td["function"]["name"] for td in TOOL_DEFINITIONS]
        expected = ["app_open", "screenshot", "vision_analyze", "click", "type_text", "key_press", "shell_run", "page_analyze"]
        for name in expected:
            assert name in names, f"工具定义 {name} 缺失"

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

    @pytest.mark.asyncio
    async def test_vision_analyze_missing_file(self):
        from task_engine.executors.desktop_executor.tools.vision_analyze import vision_analyze
        result = await vision_analyze("/nonexistent/file.png", "搜索框")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_vision_analyze_encode_image(self):
        """测试图片 base64 编码"""
        import tempfile
        from task_engine.executors.desktop_executor.tools.vision_analyze import _encode_image
        # 创建临时测试图片
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            tmp_path = f.name
        try:
            encoded = _encode_image(tmp_path)
            assert isinstance(encoded, str)
            assert len(encoded) > 0
            # 验证 base64 可解码
            import base64
            decoded = base64.b64decode(encoded)
            assert decoded[:4] == b"\x89PNG"
        finally:
            os.remove(tmp_path)

    def test_vision_analyze_get_mime_type(self):
        """测试 MIME 类型识别"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _get_mime_type
        assert _get_mime_type("test.png") == "image/png"
        assert _get_mime_type("test.jpg") == "image/jpeg"
        assert _get_mime_type("test.jpeg") == "image/jpeg"
        assert _get_mime_type("test.gif") == "image/gif"
        assert _get_mime_type("test.webp") == "image/webp"
        assert _get_mime_type("test.bmp") == "image/bmp"
        assert _get_mime_type("test.unknown") == "image/png"  # 默认值

    def test_parse_vlm_response_valid_json(self):
        """测试 VLM 响应解析 - 有效 JSON"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = json.dumps({
            "found": True,
            "elements": [
                {"description": "搜索框", "x": 500, "y": 100, "width": 200, "height": 30, "confidence": 0.95}
            ],
        })
        result = _parse_vlm_response(content, "搜索框")
        assert result["found"] is True
        assert result["query"] == "搜索框"
        assert len(result["elements"]) == 1
        assert result["elements"][0]["x"] == 500
        assert result["elements"][0]["y"] == 100
        assert result["elements"][0]["confidence"] == 0.95

    def test_parse_vlm_response_json_in_code_block(self):
        """测试 VLM 响应解析 - JSON 被代码块包裹"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = '```json\n{"found": true, "elements": [{"description": "按钮", "x": 200, "y": 300, "width": 80, "height": 40, "confidence": 0.9}]}\n```'
        result = _parse_vlm_response(content, "按钮")
        assert result["found"] is True
        assert len(result["elements"]) == 1
        assert result["elements"][0]["x"] == 200

    def test_parse_vlm_response_not_found(self):
        """测试 VLM 响应解析 - 未找到元素"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = json.dumps({"found": False, "elements": []})
        result = _parse_vlm_response(content, "搜索框")
        assert result["found"] is False
        assert result["elements"] == []

    def test_parse_vlm_response_invalid_json(self):
        """测试 VLM 响应解析 - 无效 JSON 回退"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = "这不是 JSON 格式的回复"
        result = _parse_vlm_response(content, "搜索框")
        assert result["found"] is False
        assert "message" in result

    def test_parse_vlm_response_multiple_elements(self):
        """测试 VLM 响应解析 - 多个元素"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = json.dumps({
            "found": True,
            "elements": [
                {"description": "搜索框1", "x": 100, "y": 200, "width": 300, "height": 30, "confidence": 0.9},
                {"description": "搜索框2", "x": 400, "y": 500, "width": 300, "height": 30, "confidence": 0.7},
            ],
        })
        result = _parse_vlm_response(content, "搜索框")
        assert result["found"] is True
        assert len(result["elements"]) == 2

    def test_parse_vlm_response_invalid_element(self):
        """测试 VLM 响应解析 - 无效元素被过滤"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = json.dumps({
            "found": True,
            "elements": [
                {"description": "有效", "x": 100, "y": 200},
                {"description": "无效-缺少坐标"},
            ],
        })
        result = _parse_vlm_response(content, "测试")
        assert len(result["elements"]) == 1

    def test_parse_vlm_response_unclosed_code_block(self):
        """测试 VLM 响应解析 - 未闭合代码块不崩溃"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _parse_vlm_response
        content = '```json\n{"found": false, "elements": []}'
        result = _parse_vlm_response(content, "测试")
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_vision_analyze_vlm_api_success(self):
        """测试 VLM API 调用成功场景（mock）"""
        import tempfile
        from task_engine.executors.desktop_executor.tools.vision_analyze import vision_analyze

        # 创建临时测试图片
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            tmp_path = f.name

        vlm_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "found": True,
                        "elements": [
                            {"description": "搜索框", "x": 500, "y": 100, "width": 200, "height": 30, "confidence": 0.95}
                        ],
                    })
                }
            }]
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=vlm_response)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("aiohttp.ClientSession", return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=False),
        )):
            try:
                result_str = await vision_analyze(tmp_path, "搜索框")
                result = json.loads(result_str)
                assert result["found"] is True
                assert len(result["elements"]) == 1
                assert result["elements"][0]["x"] == 500
            finally:
                os.remove(tmp_path)

    @pytest.mark.asyncio
    async def test_vision_analyze_vlm_api_connection_error(self):
        """测试 VLM API 连接失败场景"""
        import tempfile
        from task_engine.executors.desktop_executor.tools.vision_analyze import vision_analyze

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            tmp_path = f.name

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_session = AsyncMock()
            mock_session.post = MagicMock(side_effect=aiohttp.ClientError("连接失败"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            try:
                result_str = await vision_analyze(tmp_path, "搜索框")
                result = json.loads(result_str)
                assert result["found"] is False
                assert "error" in result
            finally:
                os.remove(tmp_path)

    def test_draw_bounding_boxes_single_element(self):
        """测试绘制单个元素边框标注"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import draw_bounding_boxes

        # 创建临时测试图片 (200x200 白色图片)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        img = Image.new("RGB", (200, 200), "white")
        img.save(tmp_path)

        elements = [
            {"description": "搜索框", "x": 100, "y": 50, "width": 120, "height": 30, "confidence": 0.95}
        ]
        try:
            annotated_path = draw_bounding_boxes(tmp_path, elements)
            assert annotated_path is not None
            assert os.path.exists(annotated_path)
            assert "_annotated" in annotated_path
            # 验证标注图片可以正常打开
            annotated_img = Image.open(annotated_path)
            assert annotated_img.size == (200, 200)
        finally:
            os.remove(tmp_path)
            if annotated_path and os.path.exists(annotated_path):
                os.remove(annotated_path)

    def test_draw_bounding_boxes_multiple_elements(self):
        """测试绘制多个元素边框标注"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import draw_bounding_boxes

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        img = Image.new("RGB", (400, 300), "white")
        img.save(tmp_path)

        elements = [
            {"description": "搜索框", "x": 200, "y": 50, "width": 200, "height": 30, "confidence": 0.95},
            {"description": "播放按钮", "x": 100, "y": 200, "width": 60, "height": 40, "confidence": 0.8},
        ]
        try:
            annotated_path = draw_bounding_boxes(tmp_path, elements)
            assert annotated_path is not None
            assert os.path.exists(annotated_path)
        finally:
            os.remove(tmp_path)
            if annotated_path and os.path.exists(annotated_path):
                os.remove(annotated_path)

    def test_draw_bounding_boxes_no_width_height(self):
        """测试元素无宽高时使用默认大小"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import draw_bounding_boxes

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        img = Image.new("RGB", (200, 200), "white")
        img.save(tmp_path)

        elements = [
            {"description": "按钮", "x": 100, "y": 100, "width": 0, "height": 0, "confidence": 0.7}
        ]
        try:
            annotated_path = draw_bounding_boxes(tmp_path, elements)
            assert annotated_path is not None
        finally:
            os.remove(tmp_path)
            if annotated_path and os.path.exists(annotated_path):
                os.remove(annotated_path)

    def test_draw_bounding_boxes_empty_elements(self):
        """测试空元素列表返回 None"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import draw_bounding_boxes
        result = draw_bounding_boxes("/some/path.png", [])
        assert result is None

    def test_draw_bounding_boxes_missing_file(self):
        """测试不存在的文件返回 None"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import draw_bounding_boxes
        result = draw_bounding_boxes("/nonexistent/file.png", [{"x": 100, "y": 100}])
        assert result is None

    @pytest.mark.asyncio
    async def test_page_analyze_no_cdp(self):
        """测试 page_analyze 在无 CDP 连接时返回合理结果"""
        from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze
        result_str = await page_analyze("search")
        result = json.loads(result_str)
        assert result["found"] is False
        assert result["query"] == "search"

    @pytest.mark.asyncio
    async def test_page_analyze_invalid_type_defaults_to_search(self):
        """测试 page_analyze 无效类型默认回退为 search"""
        from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze
        result_str = await page_analyze("invalid_type")
        result = json.loads(result_str)
        assert result["query"] == "search"

    @pytest.mark.asyncio
    async def test_page_analyze_with_mock_cdp(self):
        """测试 page_analyze 通过 mock CDP 返回元素"""
        from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze

        mock_js_result = json.dumps([
            {
                "type": "search",
                "tag": "input",
                "id": "srch",
                "name": "query",
                "className": "search-input",
                "placeholder": "搜索音乐",
                "ariaLabel": "搜索",
                "x": 600,
                "y": 35,
                "width": 200,
                "height": 30,
            }
        ])

        with patch(
            "task_engine.executors.desktop_executor.tools.page_analyze._run_browser_js",
            new_callable=AsyncMock,
            return_value=mock_js_result,
        ):
            result_str = await page_analyze("search")
            result = json.loads(result_str)
            assert result["found"] is True
            assert len(result["elements"]) == 1
            assert result["elements"][0]["x"] == 600
            assert result["elements"][0]["y"] == 35
            assert "搜索音乐" in result["elements"][0]["description"]

    @pytest.mark.asyncio
    async def test_page_analyze_search_fallback_to_input(self):
        """测试 page_analyze search 未找到时回退到 input 类型"""
        from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze

        mock_js_result = json.dumps([
            {
                "type": "input",
                "tag": "input",
                "id": "text-field",
                "name": "",
                "className": "text-input",
                "placeholder": "输入内容",
                "ariaLabel": "",
                "x": 400,
                "y": 50,
                "width": 150,
                "height": 25,
            }
        ])

        with patch(
            "task_engine.executors.desktop_executor.tools.page_analyze._run_browser_js",
            new_callable=AsyncMock,
            return_value=mock_js_result,
        ):
            result_str = await page_analyze("search")
            result = json.loads(result_str)
            assert result["found"] is True
            assert len(result["elements"]) == 1
            assert result["elements"][0]["x"] == 400

    @pytest.mark.asyncio
    async def test_page_analyze_invalid_js_result(self):
        """测试 page_analyze JS 返回无效结果"""
        from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze

        with patch(
            "task_engine.executors.desktop_executor.tools.page_analyze._run_browser_js",
            new_callable=AsyncMock,
            return_value="not-valid-json",
        ):
            result_str = await page_analyze("search")
            result = json.loads(result_str)
            assert result["found"] is False
            assert "error" in result

    def test_vision_analyze_system_prompt_has_search_hints(self):
        """测试 VLM system prompt 包含搜索框视觉特征描述"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _VISION_SYSTEM_PROMPT
        assert "搜索框" in _VISION_SYSTEM_PROMPT
        assert "放大镜" in _VISION_SYSTEM_PROMPT
        assert "导航栏" in _VISION_SYSTEM_PROMPT
        assert "music.163.com" in _VISION_SYSTEM_PROMPT

    def test_scale_elements_retina_2x(self):
        """测试 Retina 2x 缩放因子下的坐标转换"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _scale_elements
        elements = [
            {"description": "搜索框", "x": 810, "y": 334, "width": 400, "height": 60, "confidence": 0.95}
        ]
        scaled = _scale_elements(elements, 2.0)
        assert len(scaled) == 1
        assert scaled[0]["x"] == 405
        assert scaled[0]["y"] == 167
        assert scaled[0]["width"] == 200
        assert scaled[0]["height"] == 30
        assert scaled[0]["confidence"] == 0.95
        assert scaled[0]["description"] == "搜索框"

    def test_scale_elements_no_scaling(self):
        """测试缩放因子为 1.0 时不修改坐标"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _scale_elements
        elements = [
            {"description": "按钮", "x": 400, "y": 200, "width": 100, "height": 40, "confidence": 0.9}
        ]
        scaled = _scale_elements(elements, 1.0)
        assert scaled[0]["x"] == 400
        assert scaled[0]["y"] == 200

    def test_scale_elements_near_one(self):
        """测试接近 1.0 的缩放因子（差异 < 0.01）不修改坐标"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _scale_elements
        elements = [
            {"description": "按钮", "x": 400, "y": 200, "width": 100, "height": 40, "confidence": 0.9}
        ]
        scaled = _scale_elements(elements, 1.005)
        # Should return unchanged values since diff < 0.01
        assert scaled[0]["x"] == 400
        assert scaled[0]["y"] == 200
        assert scaled[0]["width"] == 100
        assert scaled[0]["height"] == 40

    def test_scale_elements_multiple(self):
        """测试多个元素的坐标缩放"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _scale_elements
        elements = [
            {"description": "搜索框", "x": 800, "y": 300, "width": 400, "height": 60, "confidence": 0.9},
            {"description": "播放按钮", "x": 600, "y": 500, "width": 80, "height": 80, "confidence": 0.8},
        ]
        scaled = _scale_elements(elements, 2.0)
        assert len(scaled) == 2
        assert scaled[0]["x"] == 400
        assert scaled[0]["y"] == 150
        assert scaled[1]["x"] == 300
        assert scaled[1]["y"] == 250

    def test_scale_elements_preserves_original(self):
        """测试坐标缩放不修改原始元素"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _scale_elements
        elements = [
            {"description": "搜索框", "x": 800, "y": 300, "width": 400, "height": 60, "confidence": 0.9},
        ]
        scaled = _scale_elements(elements, 2.0)
        # 原始元素不应被修改
        assert elements[0]["x"] == 800
        assert elements[0]["y"] == 300
        # 缩放后的元素应该是新列表
        assert scaled[0]["x"] == 400
        assert scaled[0]["y"] == 150

    def test_get_image_size(self):
        """测试获取图片尺寸"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import _get_image_size
        # 创建测试图片
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (2880, 1800), color="white")
            img.save(f, format="PNG")
            tmp_path = f.name
        try:
            w, h = _get_image_size(tmp_path)
            assert w == 2880
            assert h == 1800
        finally:
            os.remove(tmp_path)

    def test_get_image_size_nonexistent(self):
        """测试获取不存在文件的尺寸"""
        from task_engine.executors.desktop_executor.tools.vision_analyze import _get_image_size
        w, h = _get_image_size("/nonexistent/file.png")
        assert w is None
        assert h is None

    @pytest.mark.asyncio
    async def test_get_scale_factor_retina(self):
        """测试 Retina 屏幕下的缩放因子计算"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import _get_scale_factor
        # 创建 2880x1800 的测试图片（模拟 Retina 截图）
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (2880, 1800), color="white")
            img.save(f, format="PNG")
            tmp_path = f.name
        try:
            # Mock 屏幕分辨率为 1440x900
            with patch(
                "task_engine.executors.desktop_executor.tools.vision_analyze.get_screen_resolution",
                return_value=(1440, 900),
            ):
                scale = await _get_scale_factor(tmp_path)
                assert scale == 2.0
        finally:
            os.remove(tmp_path)

    @pytest.mark.asyncio
    async def test_get_scale_factor_no_scaling(self):
        """测试非 HiDPI 屏幕下缩放因子为 1.0"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import _get_scale_factor
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (1920, 1080), color="white")
            img.save(f, format="PNG")
            tmp_path = f.name
        try:
            with patch(
                "task_engine.executors.desktop_executor.tools.vision_analyze.get_screen_resolution",
                return_value=(1920, 1080),
            ):
                scale = await _get_scale_factor(tmp_path)
                assert scale == 1.0
        finally:
            os.remove(tmp_path)

    @pytest.mark.asyncio
    async def test_get_scale_factor_no_screen_resolution(self):
        """测试无法获取屏幕分辨率时返回 None"""
        import tempfile
        from PIL import Image
        from task_engine.executors.desktop_executor.tools.vision_analyze import _get_scale_factor
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (1920, 1080), color="white")
            img.save(f, format="PNG")
            tmp_path = f.name
        try:
            with patch(
                "task_engine.executors.desktop_executor.tools.vision_analyze.get_screen_resolution",
                return_value=None,
            ):
                scale = await _get_scale_factor(tmp_path)
                assert scale is None
        finally:
            os.remove(tmp_path)


# ============================================================
# 工具日志辅助函数测试
# ============================================================

class TestToolLogHelpers:
    """测试工具日志辅助函数"""

    def test_get_tool_icon(self):
        from task_engine.executors.desktop_executor.executor import _get_tool_icon
        assert _get_tool_icon("screenshot") == "📸"
        assert _get_tool_icon("vision_analyze") == "👁️"
        assert _get_tool_icon("page_analyze") == "🔍"
        assert _get_tool_icon("click") == "🖱️"
        assert _get_tool_icon("type_text") == "⌨️"
        assert _get_tool_icon("key_press") == "⌨️"
        assert _get_tool_icon("app_open") == "🌐"
        assert _get_tool_icon("shell_run") == "💻"
        assert _get_tool_icon("unknown_tool") == "🔧"

    def test_summarize_args_screenshot(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        assert _summarize_args("screenshot", {}) == ""

    def test_summarize_args_click(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        result = _summarize_args("click", {"x": 100, "y": 200})
        assert "x=100" in result
        assert "y=200" in result

    def test_summarize_args_type_text(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        result = _summarize_args("type_text", {"text": "周杰伦"})
        assert "周杰伦" in result

    def test_summarize_args_key_press(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        result = _summarize_args("key_press", {"key": "Return"})
        assert "Return" in result

    def test_summarize_args_app_open(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        result = _summarize_args("app_open", {"url": "https://music.163.com"})
        assert "music.163.com" in result

    def test_summarize_args_vision_analyze(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        result = _summarize_args("vision_analyze", {"query": "搜索框", "image_path": "/tmp/test.png"})
        assert "搜索框" in result

    def test_summarize_args_page_analyze(self):
        from task_engine.executors.desktop_executor.executor import _summarize_args
        result = _summarize_args("page_analyze", {"element_type": "search"})
        assert "search" in result

    def test_summarize_result_vision_found(self):
        from task_engine.executors.desktop_executor.executor import _summarize_result
        result_json = json.dumps({
            "found": True,
            "elements": [{"description": "搜索框", "x": 100, "y": 50}]
        })
        summary = _summarize_result("vision_analyze", result_json)
        assert "找到" in summary
        assert "搜索框" in summary

    def test_summarize_result_vision_not_found(self):
        from task_engine.executors.desktop_executor.executor import _summarize_result
        result_json = json.dumps({"found": False, "elements": []})
        summary = _summarize_result("vision_analyze", result_json)
        assert "未找到" in summary

    def test_summarize_result_page_analyze_found(self):
        from task_engine.executors.desktop_executor.executor import _summarize_result
        result_json = json.dumps({
            "found": True,
            "elements": [{"description": "input(placeholder=\"搜索\")", "x": 500, "y": 35}]
        })
        summary = _summarize_result("page_analyze", result_json)
        assert "DOM 找到" in summary

    def test_summarize_result_page_analyze_not_found(self):
        from task_engine.executors.desktop_executor.executor import _summarize_result
        result_json = json.dumps({"found": False, "elements": []})
        summary = _summarize_result("page_analyze", result_json)
        assert "DOM 未找到" in summary

    def test_summarize_result_truncation(self):
        from task_engine.executors.desktop_executor.executor import _summarize_result
        long_result = "a" * 300
        summary = _summarize_result("click", long_result)
        assert len(summary) <= 200

    def test_summarize_result_screenshot_json(self):
        """测试 screenshot JSON 结果的摘要"""
        from task_engine.executors.desktop_executor.executor import _summarize_result
        result_json = json.dumps({
            "file_path": "/tmp/desktop_screenshot_123.png",
            "image_width": 2880,
            "image_height": 1800,
            "screen_width": 1440,
            "screen_height": 900,
            "scale_factor": 2.0,
        })
        summary = _summarize_result("screenshot", result_json)
        assert "/tmp/desktop_screenshot_123.png" in summary
        assert "scale=2.0" in summary

    def test_summarize_result_screenshot_json_no_scale(self):
        """测试无缩放的 screenshot JSON 结果的摘要"""
        from task_engine.executors.desktop_executor.executor import _summarize_result
        result_json = json.dumps({
            "file_path": "/tmp/desktop_screenshot_123.png",
            "image_width": 1920,
            "image_height": 1080,
        })
        summary = _summarize_result("screenshot", result_json)
        assert "/tmp/desktop_screenshot_123.png" in summary
        assert "scale" not in summary

    def test_summarize_result_screenshot_plain_string(self):
        """测试旧格式的 screenshot 结果兼容性"""
        from task_engine.executors.desktop_executor.executor import _summarize_result
        summary = _summarize_result("screenshot", "/tmp/screenshot.png")
        assert "/tmp/screenshot.png" in summary


# ============================================================
# DesktopExecutor 测试
# ============================================================

class TestDesktopExecutor:
    """测试桌面操控执行器"""

    @pytest.mark.asyncio
    async def test_missing_task_param(self):
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step
        executor = DesktopExecutor()
        step = Step(executor_type=ExecutorType.DESKTOP, description="test", params={})
        result = await executor.execute(step)
        assert result.success is False
        assert "缺少" in result.message

    @pytest.mark.asyncio
    async def test_llm_call_failure_returns_error(self):
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step
        executor = DesktopExecutor()
        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="test",
            params={"task": "打开浏览器播放音乐"},
        )
        # vLLM 未运行，_call_llm 会返回 None
        result = await executor.execute(step)
        assert result.success is False
        assert "LLM 调用失败" in result.message

    @pytest.mark.asyncio
    async def test_tool_call_loop_completion(self):
        """测试 LLM 返回无 tool_calls 时正常完成"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step

        executor = DesktopExecutor()

        # Mock _call_llm 返回无 tool_calls（任务完成）
        async def mock_call_llm(messages):
            return {"content": "已完成播放周杰伦的晴天", "tool_calls": None}

        executor._call_llm = mock_call_llm
        step = Step(
            executor_type=ExecutorType.DESKTOP,
            description="test",
            params={"task": "播放音乐"},
        )
        result = await executor.execute(step)
        assert result.success is True
        assert "周杰伦" in result.message

    @pytest.mark.asyncio
    async def test_guard_abort_during_loop(self):
        """测试守卫在循环中检测到危险操作时终止"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step

        executor = DesktopExecutor()
        call_count = 0

        async def mock_call_llm(messages):
            nonlocal call_count
            call_count += 1
            return {
                "content": "",
                "tool_calls": [{
                    "id": f"call_{call_count}",
                    "function": {
                        "name": "click",
                        "arguments": json.dumps({"x": 100, "y": 200}),
                    },
                }],
            }

        # Mock click 工具，通过 TOOL_REGISTRY 替换
        async def mock_click(**kwargs):
            return "点击了支付按钮"

        with patch.dict(
            "task_engine.executors.desktop_executor.tools.TOOL_REGISTRY",
            {"click": mock_click},
        ):
            executor._call_llm = mock_call_llm
            step = Step(
                executor_type=ExecutorType.DESKTOP,
                description="test",
                params={"task": "测试"},
            )
            result = await executor.execute(step)
            assert result.success is False
            assert "安全守卫终止" in result.message

    @pytest.mark.asyncio
    async def test_multi_step_tool_call_flow(self):
        """测试多步骤工具调用流程（截图→分析→点击→输入→回车）并验证日志输出"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step

        executor = DesktopExecutor()
        call_count = 0

        async def mock_call_llm(messages):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一轮：打开网页
                return {
                    "content": "我来打开音乐网站",
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {
                            "name": "app_open",
                            "arguments": json.dumps({"url": "https://music.163.com"}),
                        },
                    }],
                }
            elif call_count == 2:
                # 第二轮：截图
                return {
                    "content": "网页已打开，我来截图",
                    "tool_calls": [{
                        "id": "call_2",
                        "function": {
                            "name": "screenshot",
                            "arguments": "{}",
                        },
                    }],
                }
            elif call_count == 3:
                # 第三轮：视觉分析 + 点击 + 输入 + 回车
                return {
                    "content": "我来搜索周杰伦",
                    "tool_calls": [
                        {
                            "id": "call_3a",
                            "function": {
                                "name": "click",
                                "arguments": json.dumps({"x": 500, "y": 100}),
                            },
                        },
                        {
                            "id": "call_3b",
                            "function": {
                                "name": "type_text",
                                "arguments": json.dumps({"text": "周杰伦"}),
                            },
                        },
                        {
                            "id": "call_3c",
                            "function": {
                                "name": "key_press",
                                "arguments": json.dumps({"key": "Return"}),
                            },
                        },
                    ],
                }
            else:
                # 第四轮：完成
                return {
                    "content": "已成功搜索并播放周杰伦的音乐",
                    "tool_calls": None,
                }

        # Mock 所有工具
        async def mock_app_open(**kwargs):
            return f"已打开: {kwargs.get('url', '')}"

        async def mock_screenshot(**kwargs):
            return "/tmp/test_screenshot.png"

        async def mock_click(**kwargs):
            return f"已点击坐标 ({kwargs.get('x')}, {kwargs.get('y')})"

        async def mock_type_text(**kwargs):
            return f"已输入文本: {kwargs.get('text', '')}"

        async def mock_key_press(**kwargs):
            return f"已按下: {kwargs.get('key', '')}"

        with patch.dict(
            "task_engine.executors.desktop_executor.tools.TOOL_REGISTRY",
            {
                "app_open": mock_app_open,
                "screenshot": mock_screenshot,
                "click": mock_click,
                "type_text": mock_type_text,
                "key_press": mock_key_press,
            },
        ):
            executor._call_llm = mock_call_llm
            step = Step(
                executor_type=ExecutorType.DESKTOP,
                description="test",
                params={"task": "打开网页里的音乐输入周杰伦播放音乐"},
            )
            result = await executor.execute(step)
            assert result.success is True
            assert "周杰伦" in result.message
            assert result.data["iterations"] == 4
            assert call_count == 4

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self):
        """测试达到最大迭代次数时返回失败"""
        from task_engine.executors.desktop_executor.executor import DesktopExecutor
        from task_engine.models import ExecutorType, Step

        executor = DesktopExecutor()

        async def mock_call_llm(messages):
            return {
                "content": "继续截图",
                "tool_calls": [{
                    "id": "call_loop",
                    "function": {
                        "name": "screenshot",
                        "arguments": "{}",
                    },
                }],
            }

        async def mock_screenshot(**kwargs):
            return "/tmp/loop_screenshot.png"

        with patch.dict(
            "task_engine.executors.desktop_executor.tools.TOOL_REGISTRY",
            {"screenshot": mock_screenshot},
        ):
            executor._call_llm = mock_call_llm
            step = Step(
                executor_type=ExecutorType.DESKTOP,
                description="test",
                params={"task": "无限循环任务"},
            )
            result = await executor.execute(step)
            assert result.success is False
            assert "最大迭代次数" in result.message


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
    async def test_desktop_flow_without_vllm(self):
        """桌面任务在无 vLLM 时应返回失败"""
        from task_engine.engine import TaskEngine
        engine = TaskEngine()
        result = await engine.run("打开网页里的音乐输入周杰伦播放音乐")
        assert "❌" in result or "LLM 调用失败" in result


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
