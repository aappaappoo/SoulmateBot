"""
屏幕截图工具
"""
import asyncio
import json
import os
import tempfile
import time

from loguru import logger

from task_engine.executors.desktop_executor.platform import get_screenshot_command, get_screen_resolution


async def screenshot() -> str:
    """
    执行屏幕截图

    Returns:
        str: JSON 格式结果，包含截图文件路径、图片像素尺寸和屏幕逻辑分辨率。
             当图片像素尺寸大于屏幕逻辑分辨率时（如 macOS Retina），
             说明存在缩放因子，vision_analyze 返回的坐标需要按比例缩放后才能用于点击。
    """
    # 使用临时目录存储截图
    tmp_dir = tempfile.gettempdir()
    filename = f"desktop_screenshot_{int(time.time())}.png"
    filepath = os.path.join(tmp_dir, filename)

    cmd_template = get_screenshot_command()
    command = cmd_template.format(path=filepath)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0 and os.path.exists(filepath):
            # 获取截图的实际像素尺寸
            image_width, image_height = _get_image_size(filepath)
            # 获取屏幕逻辑分辨率
            screen_res = await get_screen_resolution()

            result = {"file_path": filepath}
            if image_width and image_height:
                result["image_width"] = image_width
                result["image_height"] = image_height
            if screen_res:
                result["screen_width"] = screen_res[0]
                result["screen_height"] = screen_res[1]

            # 计算并记录缩放因子
            if image_width and screen_res and screen_res[0] > 0:
                scale = image_width / screen_res[0]
                if abs(scale - 1.0) > 0.01:
                    result["scale_factor"] = round(scale, 2)
                    logger.info(
                        f"📐 [screenshot] Retina/HiDPI 检测: "
                        f"图片 {image_width}x{image_height}, "
                        f"屏幕 {screen_res[0]}x{screen_res[1]}, "
                        f"缩放因子 {scale:.2f}"
                    )

            return json.dumps(result, ensure_ascii=False)
        err = stderr.decode(errors="replace") if stderr else "截图命令失败"
        return f"截图失败: {err}"
    except asyncio.TimeoutError:
        return "截图超时（10秒）"
    except Exception as e:
        return f"截图异常: {e}"


def _get_image_size(filepath: str):
    """
    获取图片的像素尺寸

    Returns:
        (width, height) 或 (None, None)
    """
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        pass
    return None, None
