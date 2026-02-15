"""桌面工具包（Playwright 方案）"""
from task_engine.executors.desktop_executor.tools.shell_run import shell_run
from task_engine.executors.desktop_executor.tools.app_open import app_open
from task_engine.executors.desktop_executor.tools.click import click
from task_engine.executors.desktop_executor.tools.type_text import type_text
from task_engine.executors.desktop_executor.tools.key_press import key_press
from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze

# 工具注册表：名称 → 函数
TOOL_REGISTRY = {
    "shell_run": shell_run,
    "app_open": app_open,
    "page_analyze": page_analyze,
    "click": click,
    "type_text": type_text,
    "key_press": key_press,
}

# 工具描述，供 LLM tool-call 使用
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "app_open",
            "description": "使用 Playwright 打开浏览器并访问指定 URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "page_analyze",
            "description": (
                "通过 Playwright 分析页面可交互元素（搜索框、输入框、按钮），"
                "返回元素描述和可用于 click/type_text 的 CSS 选择器。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "element_type": {
                        "type": "string",
                        "description": "要查找的元素类型：search（搜索框）、input（输入框）、button（按钮）",
                        "enum": ["search", "input", "button"],
                    },
                },
                "required": ["element_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "通过 CSS 选择器点击页面元素",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS 选择器，如 #search-input, button.play"},
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "通过 CSS 选择器在指定输入框中填入文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "输入框的 CSS 选择器"},
                    "text": {"type": "string", "description": "要输入的文本"},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "key_press",
            "description": "按下键盘按键（如 Enter、Tab 等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "按键名称，如 Enter、Tab"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_run",
            "description": "执行轻量 shell 命令（安全过滤）",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"},
                },
                "required": ["command"],
            },
        },
    },
]

__all__ = [
    "TOOL_REGISTRY",
    "TOOL_DEFINITIONS",
    "shell_run",
    "app_open",
    "page_analyze",
    "click",
    "type_text",
    "key_press",
]
