"""桌面工具包"""
from task_engine.executors.desktop_executor.tools.shell_run import shell_run
from task_engine.executors.desktop_executor.tools.app_open import app_open
from task_engine.executors.desktop_executor.tools.screenshot import screenshot
from task_engine.executors.desktop_executor.tools.vision_analyze import vision_analyze
from task_engine.executors.desktop_executor.tools.click import click
from task_engine.executors.desktop_executor.tools.type_text import type_text
from task_engine.executors.desktop_executor.tools.key_press import key_press
from task_engine.executors.desktop_executor.tools.page_analyze import page_analyze

# 工具注册表：名称 → 函数
TOOL_REGISTRY = {
    "shell_run": shell_run,
    "app_open": app_open,
    "screenshot": screenshot,
    "vision_analyze": vision_analyze,
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
            "description": "打开浏览器或指定 URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的 URL 或应用名称"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "屏幕截图，返回截图文件路径",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vision_analyze",
            "description": "使用视觉模型分析截图，识别 UI 元素坐标。返回元素描述和坐标。",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "截图文件路径"},
                    "query": {"type": "string", "description": "要查找的 UI 元素描述，如：搜索框、带放大镜搜索框、播放按钮"},
                },
                "required": ["image_path", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "鼠标点击屏幕指定坐标",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "点击的 X 坐标"},
                    "y": {"type": "integer", "description": "点击的 Y 坐标"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "在当前焦点位置输入文本（支持中文）",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要输入的文本"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "key_press",
            "description": "按下键盘按键（如 Enter、Tab、cmd+v 等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "按键名称，如 Return、Tab、cmd+v"},
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
    {
        "type": "function",
        "function": {
            "name": "page_analyze",
            "description": (
                "通过浏览器 DOM 分析页面可交互元素（搜索框、输入框、按钮）的坐标。"
                "当 vision_analyze 无法识别搜索框等元素时，使用此工具作为备选方案。"
                "通过 JavaScript 注入查找页面中的 input、button 等元素并返回坐标。"
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
]

__all__ = [
    "TOOL_REGISTRY",
    "TOOL_DEFINITIONS",
    "shell_run",
    "app_open",
    "screenshot",
    "vision_analyze",
    "page_analyze",
    "click",
    "type_text",
    "key_press",
]
