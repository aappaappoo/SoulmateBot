"""
报告生成器 - 用户友好回复

将任务执行结果转换为自然语言回复。
"""
from .models import Task, TaskStatus


async def report(task: Task) -> str:
    """
    生成用户友好的任务执行报告

    Args:
        task: 已验证的任务

    Returns:
        str: 自然语言回复
    """
    if task.status == TaskStatus.SUCCESS:
        msg = task.result.message if task.result else "任务已完成"
        # 如果包含音乐播放数据，附加可点击的链接供用户在客户端播放
        music_link = _format_music_link(task)
        if music_link:
            return f"✅ {msg}\n\n{music_link}"
        return f"✅ {msg}"

    if task.status == TaskStatus.ABORTED:
        msg = task.result.message if task.result else "任务被终止"
        return f"⚠️ {msg}"

    if task.status == TaskStatus.FAILED:
        msg = task.result.message if task.result else "任务执行失败"
        return f"❌ {msg}"

    return "⏳ 任务仍在处理中..."


def _format_music_link(task: Task) -> str:
    """
    从任务结果中提取音乐链接，格式化为用户可点击的消息

    Args:
        task: 已完成的任务

    Returns:
        str: 格式化的音乐链接文本，无链接时返回空字符串
    """
    if not task.result or not task.result.data:
        return ""

    url = task.result.data.get("url", "")
    if not url:
        return ""

    song_title = task.result.data.get("song_title", "")
    artist = task.result.data.get("artist", "")

    title_display = song_title or "歌曲"
    if artist:
        title_display = f"{artist} - {title_display}"

    return f"🎵 点击播放：{title_display}\n🔗 {url}"
