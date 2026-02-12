"""
视觉分析工具 - VLM 识别 UI 元素坐标

通过视觉语言模型分析截图，识别指定 UI 元素的位置。
当前为占位实现，实际需对接 VLM (如 vLLM 的视觉模型)。
"""
import json
import os
from typing import Optional


async def vision_analyze(image_path: str, query: str) -> str:
    """
    使用视觉模型分析截图，识别 UI 元素

    Args:
        image_path: 截图文件路径
        query: 要查找的 UI 元素描述

    Returns:
        str: JSON 格式的分析结果，包含元素描述和坐标
    """
    if not os.path.exists(image_path):
        return json.dumps({"error": f"截图文件不存在: {image_path}"}, ensure_ascii=False)

    # 占位实现：实际应调用 VLM API
    # 例如通过 aiohttp 调 vLLM /v1/chat/completions 并传入图片
    result = {
        "found": False,
        "query": query,
        "message": "视觉模型未配置，请对接 VLM 服务（如 vLLM）",
        "elements": [],
    }

    return json.dumps(result, ensure_ascii=False)
