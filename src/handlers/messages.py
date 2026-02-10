"""
Message handlers for conversations - Async Version
异步消息处理器
"""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos"""
    message = update.message or update.channel_post

    if not message:
        return

    logger.info("Received photo")

    await message.reply_text(
        "📷 谢谢你分享的照片！\n\n"
        "我看到了你的照片。虽然我还在学习如何更好地理解图片，"
        "但我能感受到你想要分享的心情。\n\n"
        "如果你想聊聊这张照片，或者告诉我你的感受，我很乐意倾听！"
    )


async def handle_sticker(update: Update, context:  ContextTypes.DEFAULT_TYPE):
    """Handle incoming stickers"""
    message = update.message or update.channel_post

    if not message:
        return

    logger.info("Received sticker")

    await message.reply_text(
        "😊 收到了你的表情包！\n\n"
        "我能感受到你想表达的情绪。继续和我聊天吧！"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    import traceback

    error_traceback = ''.join(traceback.format_exception(
        type(context.error),
        context.error,
        context.error.__traceback__
    ))

    logger.error(f"❌ Error occurred: {context.error}")
    logger.error(f"Full traceback:\n{error_traceback}")
    logger.error(f"Update that caused error: {update}")

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "抱歉，发生了一个错误。请稍后再试。"
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")