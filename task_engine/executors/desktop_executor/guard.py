"""
三层任务守卫 - 保障桌面操控安全

三层守卫：
1. 禁止操作：登录 / 支付 / 密码 / sudo → 立即 ABORT
2. 偏离累计：需要登录 / 会员 / 下载客户端 → 超阈值 ABORT
3. 应用失败黑名单：同一网站多次失败 → SWITCH

执行模式（Nanobot tool-call loop）：
- pre_check: 在 tool_call 执行前检查安全性和任务偏离
- post_check: 在 tool_call 执行后检查结果（失败黑名单等）
- check: 兼容接口，同时检查参数和结果
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class GuardAction(str, Enum):
    """守卫动作"""
    ALLOW = "allow"       # 允许继续
    ABORT = "abort"       # 立即终止
    SWITCH = "switch"     # 切换应用/网站


# 第一层：禁止操作关键词
_FORBIDDEN_PATTERNS: List[re.Pattern] = [
    re.compile(r"(登录|登陆|注册|sign.?in|log.?in)", re.IGNORECASE),
    re.compile(r"(支付|付款|pay|payment|checkout)", re.IGNORECASE),
    re.compile(r"(密码|password|passwd)", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"(银行|bank|credit.?card)", re.IGNORECASE),
]

# 第二层：偏离信号关键词
_DRIFT_SIGNALS: List[str] = [
    "需要登录", "请登录", "会员", "VIP", "下载客户端",
    "下载APP", "安装应用", "requires login", "sign up",
]

# 偏离阈值：累计超过此值则终止
_DRIFT_THRESHOLD: int = 3


@dataclass
class TaskGuard:
    """
    三层任务守卫

    用于在桌面操控循环中检查每次操作的安全性，
    防止执行危险操作、偏离任务目标。

    Nanobot tool-call loop 模式：
    - 每次 tool_call 执行前必须经过 pre_check
    - 未通过检查的 tool_call 被拒绝并反馈给 LLM 重新决策
    """
    drift_count: int = 0
    fail_counts: Dict[str, int] = field(default_factory=dict)
    _fail_threshold: int = 3

    def pre_check(self, tool_name: str, tool_args: Dict) -> GuardAction:
        """
        tool_call 执行前的安全检查

        在工具实际执行之前，检查工具名称和参数是否存在安全风险
        或偏离当前任务目标。未通过的 tool_call 应被拒绝。

        Args:
            tool_name: 工具名称
            tool_args: 工具参数

        Returns:
            GuardAction: 允许 / 终止 / 切换
        """
        pre_text = f"{tool_name} {tool_args}"

        # 第一层：禁止操作
        for pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(pre_text):
                return GuardAction.ABORT

        # 第二层：偏离检查（基于参数中的信号）
        for signal in _DRIFT_SIGNALS:
            if signal in pre_text:
                self.drift_count += 1
                break
        if self.drift_count >= _DRIFT_THRESHOLD:
            return GuardAction.ABORT

        return GuardAction.ALLOW

    def post_check(self, tool_name: str, tool_args: Dict, tool_result: str) -> GuardAction:
        """
        tool_call 执行后的结果检查

        在工具执行完成后，检查返回结果中是否包含安全风险、
        偏离信号或重复失败模式。

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            tool_result: 工具返回结果

        Returns:
            GuardAction: 允许 / 终止 / 切换
        """
        # 第一层：检查结果中的禁止操作
        for pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(tool_result):
                return GuardAction.ABORT

        # 第二层：检查结果中的偏离信号
        for signal in _DRIFT_SIGNALS:
            if signal in tool_result:
                self.drift_count += 1
                break
        if self.drift_count >= _DRIFT_THRESHOLD:
            return GuardAction.ABORT

        # 第三层：应用失败黑名单
        if tool_name in ("app_open", "click") and "失败" in tool_result:
            app_key = str(tool_args.get("url", tool_args.get("target", "unknown")))
            self.fail_counts[app_key] = self.fail_counts.get(app_key, 0) + 1
            if self.fail_counts[app_key] >= self._fail_threshold:
                return GuardAction.SWITCH

        return GuardAction.ALLOW

    def check(self, tool_name: str, tool_args: Dict, tool_result: str) -> GuardAction:
        """
        检查工具调用是否安全（兼容接口）

        同时检查参数和结果，保持向后兼容。

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            tool_result: 工具返回结果

        Returns:
            GuardAction: 允许 / 终止 / 切换
        """
        combined_text = f"{tool_name} {tool_args} {tool_result}"

        # 第一层：禁止操作
        for pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(combined_text):
                return GuardAction.ABORT

        # 第二层：偏离累计
        for signal in _DRIFT_SIGNALS:
            if signal in combined_text:
                self.drift_count += 1
                break
        if self.drift_count >= _DRIFT_THRESHOLD:
            return GuardAction.ABORT

        # 第三层：应用失败黑名单
        if tool_name in ("app_open", "click") and "失败" in tool_result:
            app_key = str(tool_args.get("url", tool_args.get("target", "unknown")))
            self.fail_counts[app_key] = self.fail_counts.get(app_key, 0) + 1
            if self.fail_counts[app_key] >= self._fail_threshold:
                return GuardAction.SWITCH

        return GuardAction.ALLOW

    def reset(self) -> None:
        """重置守卫状态"""
        self.drift_count = 0
        self.fail_counts.clear()
