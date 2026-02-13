"""
视觉分析工具 - VLM 识别 UI 元素坐标

通过视觉语言模型分析截图，识别指定 UI 元素的位置。
使用 vLLM 的 OpenAI 兼容 API，支持视觉模型（如 Qwen-VL, LLaVA 等）。
"""
import base64
import json
import os
from typing import Optional

import aiohttp
from loguru import logger

from config import settings

# VLM 配置（优先使用 VLM 专用配置，回退到 executor LLM 配置）
_VLM_URL = (
    getattr(settings, "vlm_api_url", None)
    or getattr(settings, "executor_llm_url", None)
    or "http://localhost:8000"
)
_VLM_MODEL = (
    getattr(settings, "vlm_model", None)
    or getattr(settings, "executor_llm_model", None)
    or "default"
)
_VLM_TOKEN = (
    getattr(settings, "vlm_api_token", None)
    or getattr(settings, "executor_llm_token", None)
    or ""
)

# VLM 视觉分析 system prompt
_VISION_SYSTEM_PROMPT = (
    "你是一个视觉 UI 分析助手。分析给定的屏幕截图，找到用户描述的 UI 元素。\n\n"
    "请返回 JSON 格式的结果：\n"
    "{\n"
    '  "found": true,\n'
    '  "elements": [\n'
    "    {\n"
    '      "description": "元素描述",\n'
    '      "x": 中心X坐标,\n'
    '      "y": 中心Y坐标,\n'
    '      "width": 元素宽度,\n'
    '      "height": 元素高度,\n'
    '      "confidence": 置信度\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "注意：\n"
    "- 坐标为截图中的像素坐标（整数）\n"
    "- 如果找到多个匹配元素，全部列出\n"
    '- 如果未找到，返回 {"found": false, "elements": []}\n'
    "- 只返回 JSON，不要有其他文字"
)


def _encode_image(image_path: str) -> str:
    """将图片文件编码为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_mime_type(image_path: str) -> str:
    """根据文件扩展名获取 MIME 类型"""
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


def _parse_vlm_response(content: str, query: str) -> dict:
    """
    解析 VLM 返回的内容为结构化结果

    Args:
        content: VLM 返回的文本内容
        query: 原始查询

    Returns:
        dict: 结构化的分析结果
    """
    content = content.strip()

    # 处理 JSON 被代码块包裹的情况
    try:
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            content = content[start:end].strip()
    except ValueError:
        pass  # 代码块格式不完整，使用原始内容继续解析

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            found = parsed.get("found", False)
            elements = parsed.get("elements", [])
            valid_elements = []
            for elem in elements:
                if isinstance(elem, dict) and "x" in elem and "y" in elem:
                    valid_elements.append(
                        {
                            "description": elem.get("description", query),
                            "x": int(elem.get("x", 0)),
                            "y": int(elem.get("y", 0)),
                            "width": int(elem.get("width", 0)),
                            "height": int(elem.get("height", 0)),
                            "confidence": float(elem.get("confidence", 0.0)),
                        }
                    )
            return {
                "found": bool(found and valid_elements),
                "query": query,
                "elements": valid_elements,
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # JSON 解析失败时返回原始内容
    return {
        "found": False,
        "query": query,
        "message": content,
        "elements": [],
    }


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

    # 编码图片为 base64
    try:
        image_base64 = _encode_image(image_path)
    except Exception as e:
        return json.dumps({"error": f"图片读取失败: {e}"}, ensure_ascii=False)

    mime_type = _get_mime_type(image_path)

    # 构建 VLM 请求消息（OpenAI 兼容的视觉格式）
    messages = [
        {"role": "system", "content": _VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
                {
                    "type": "text",
                    "text": f"请在截图中找到以下 UI 元素：{query}",
                },
            ],
        },
    ]

    # 调用 VLM API
    url = f"{_VLM_URL}/v1/chat/completions"
    payload = {
        "model": _VLM_MODEL,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_VLM_TOKEN}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.warning(f"VLM API 返回 {resp.status}: {error_text}")
                    return json.dumps(
                        {
                            "found": False,
                            "query": query,
                            "error": f"VLM API 错误 (HTTP {resp.status})",
                            "elements": [],
                        },
                        ensure_ascii=False,
                    )
                data = await resp.json()
    except aiohttp.ClientError as e:
        logger.warning(f"VLM API 连接失败: {e}")
        return json.dumps(
            {
                "found": False,
                "query": query,
                "error": f"VLM 服务连接失败: {e}",
                "elements": [],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.warning(f"VLM 调用异常: {e}")
        return json.dumps(
            {
                "found": False,
                "query": query,
                "error": f"VLM 调用异常: {e}",
                "elements": [],
            },
            ensure_ascii=False,
        )

    # 解析 VLM 返回内容
    try:
        content = data["choices"][0]["message"]["content"]
        logger.info(f"👁️ VLM 分析完成: query={query}")
        result = _parse_vlm_response(content, query)
        return json.dumps(result, ensure_ascii=False)
    except (KeyError, IndexError) as e:
        logger.warning(f"VLM 响应格式异常: {e}, data={data}")
        return json.dumps(
            {
                "found": False,
                "query": query,
                "error": "VLM 响应格式异常",
                "elements": [],
            },
            ensure_ascii=False,
        )
