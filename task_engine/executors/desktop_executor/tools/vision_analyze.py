"""
视觉分析工具 - VLM 识别 UI 元素坐标

通过视觉语言模型分析截图，识别指定 UI 元素的位置。
使用 vLLM 的 OpenAI 兼容 API，支持视觉模型（如 Qwen-VL, LLaVA 等）。

当 VLM 识别到需要点击的具体元素时，会在截图上绘制红色边框标注。

坐标映射：
  VLM 返回的坐标基于截图的像素尺寸。在 macOS Retina/HiDPI 屏幕上，
  截图像素分辨率（如 2880x1800）通常是屏幕逻辑分辨率（如 1440x900）的 2 倍。
  而 click 工具使用的是屏幕逻辑坐标，因此需要将 VLM 坐标除以缩放因子。
"""
import base64
import json
import os
from typing import List, Optional

import aiohttp
from loguru import logger

from config import settings
from task_engine.executors.desktop_executor.platform import get_screen_resolution

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
    "常见 UI 元素的视觉特征：\n"
    "- 搜索框：通常位于页面顶部导航栏区域，是一个长条形的输入框，常带有放大镜图标🔍、"
    "\"搜索\"或\"Search\"文字提示，背景色通常与周围区域有对比（白色/浅灰色输入区域）。"
    "在音乐网站（如网易云音乐 music.163.com）中，搜索框通常在页面顶部黑色/深色导航栏内，"
    "是一个带有圆角的浅色输入区域。\n"
    "- 按钮：矩形或圆角矩形区域，通常有明显的背景色和文字标签。\n"
    "- 播放按钮：三角形▶图标或带有播放图标的圆形/矩形按钮。\n"
    "- 输入框：矩形区域，通常有边框线，内部可能有占位提示文字（灰色）。\n"
    "- 链接/标签：带有下划线或不同颜色的文字。\n"
    "- 导航栏：页面顶部的水平条状区域，包含多个菜单项和搜索框。\n\n"
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
    "- 只返回 JSON，不要有其他文字\n"
    "- 仔细观察页面的每个区域，特别是顶部导航栏中的搜索相关元素"
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


def _get_image_size(image_path: str):
    """
    获取图片的像素尺寸

    Returns:
        (width, height) 或 (None, None)
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        pass
    return None, None


def _scale_elements(elements: List[dict], scale_factor: float) -> List[dict]:
    """
    将 VLM 返回的图片像素坐标按缩放因子转换为屏幕逻辑坐标

    在 macOS Retina 等 HiDPI 屏幕上，截图像素尺寸是逻辑分辨率的 N 倍，
    VLM 返回的坐标基于图片像素，而 click 工具使用逻辑坐标。
    因此需要将坐标除以缩放因子。

    Args:
        elements: VLM 返回的元素列表，坐标为图片像素坐标
        scale_factor: 缩放因子（图片像素 / 屏幕逻辑），如 Retina 屏为 2.0

    Returns:
        坐标已转换为屏幕逻辑坐标的元素列表
    """
    if abs(scale_factor - 1.0) < 0.01:
        return elements

    scaled = []
    for elem in elements:
        e = dict(elem)
        e["x"] = int(round(e.get("x", 0) / scale_factor))
        e["y"] = int(round(e.get("y", 0) / scale_factor))
        e["width"] = int(round(e.get("width", 0) / scale_factor))
        e["height"] = int(round(e.get("height", 0) / scale_factor))
        scaled.append(e)
    return scaled


def draw_bounding_boxes(image_path: str, elements: List[dict]) -> Optional[str]:
    """
    在截图上绘制红色边框标注 VLM 识别到的 UI 元素

    Args:
        image_path: 原始截图文件路径
        elements: VLM 识别到的元素列表，每个元素包含 x, y, width, height, description

    Returns:
        str: 标注后的截图文件路径，失败返回 None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow 未安装，无法绘制边框标注")
        return None

    if not elements or not os.path.exists(image_path):
        return None

    try:
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        for elem in elements:
            cx = elem.get("x", 0)
            cy = elem.get("y", 0)
            w = elem.get("width", 0)
            h = elem.get("height", 0)
            desc = elem.get("description", "")
            confidence = elem.get("confidence", 0.0)

            # 如果没有宽高信息，使用默认大小
            if w <= 0:
                w = 60
            if h <= 0:
                h = 30

            # 计算矩形左上角和右下角坐标
            x1 = cx - w // 2
            y1 = cy - h // 2
            x2 = cx + w // 2
            y2 = cy + h // 2

            # 绘制红色矩形边框（3像素宽）
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)

            # 在矩形上方绘制标签文字
            label = f"{desc} ({confidence:.0%})"
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except (IOError, OSError):
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = x1
            text_y = max(0, y1 - text_h - 4)
            draw.rectangle([text_x, text_y, text_x + text_w + 4, text_y + text_h + 4], fill="red")
            draw.text((text_x + 2, text_y + 2), label, fill="white", font=font)

        # 保存标注后的截图
        base, ext = os.path.splitext(image_path)
        annotated_path = f"{base}_annotated{ext}"
        img.save(annotated_path)
        logger.info(f"🖼️ 已在截图上标注 {len(elements)} 个元素: {annotated_path}")
        return annotated_path

    except Exception as e:
        logger.warning(f"绘制边框标注失败: {e}")
        return None


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

        # 坐标缩放：将 VLM 的图片像素坐标映射到屏幕逻辑坐标
        if result.get("found") and result.get("elements"):
            scale_factor = await _get_scale_factor(image_path)
            if scale_factor and abs(scale_factor - 1.0) > 0.01:
                logger.info(
                    f"📐 [vision_analyze] 坐标缩放: "
                    f"scale_factor={scale_factor:.2f}, "
                    f"将图片像素坐标转换为屏幕逻辑坐标"
                )
                # 先在原始坐标上绘制标注
                draw_bounding_boxes(image_path, result["elements"])
                # 再缩放坐标
                result["elements"] = _scale_elements(
                    result["elements"], scale_factor
                )
                result["scale_factor"] = round(scale_factor, 2)
            else:
                # 无缩放，直接绘制标注
                annotated = draw_bounding_boxes(image_path, result["elements"])
                if annotated:
                    result["annotated_image"] = annotated
                    logger.info(f"🖼️ 元素标注截图已保存: {annotated}")

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


async def _get_scale_factor(image_path: str) -> Optional[float]:
    """
    计算截图像素坐标到屏幕逻辑坐标的缩放因子

    对比截图图片的实际像素宽度和屏幕的逻辑分辨率宽度，
    得出缩放因子。在 macOS Retina 屏上通常为 2.0。

    Args:
        image_path: 截图文件路径

    Returns:
        缩放因子（如 2.0），无法计算时返回 None
    """
    img_w, _ = _get_image_size(image_path)
    if not img_w:
        return None

    screen_res = await get_screen_resolution()
    if not screen_res or screen_res[0] <= 0:
        return None

    return img_w / screen_res[0]
