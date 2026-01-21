"""初始化测试数据"""
from src. database import get_db_session
from src.models.database import Bot, Channel, ChannelBotMapping, User

db = get_db_session()

try:
    # 1. 创建用户（如果需要）
    user = User(
        telegram_id=7224312427,  # 你的 Telegram ID
        username="Rasojuh",
        first_name="poo",
        last_name="Apa"
    )
    db.add(user)
    db.commit()
    print(f"✅ 创建用户: {user.id}")

    # 2. 创建 Bot
    bot = Bot(
        bot_token="YOUR_BOT_TOKEN",  # 替换为你的 token
        bot_name="Solin AI Bot",
        bot_username="Solin_AI_Bot",
        system_prompt="你是一个温柔的情感陪伴助手",
        created_by=user.id
    )
    db.add(bot)
    db.commit()
    print(f"✅ 创建 Bot: {bot.id}")

    # 3. 创建 Channel（私聊）
    channel = Channel(
        telegram_chat_id=7224312427,  # 私聊的 chat_id 就是用户 ID
        chat_type="private",
        owner_id=user.id
    )
    db.add(channel)
    db.commit()
    print(f"✅ 创建 Channel: {channel.id}")

    # 4. 绑定 Bot 到 Channel
    mapping = ChannelBotMapping(
        channel_id=channel. id,
        bot_id=bot.id,
        is_active=True,
        routing_mode="auto"  # 自动回复所有消息
    )
    db.add(mapping)
    db.commit()
    print(f"✅ 绑定完成!")

    print("\n🎉 初始化完成！现在可以测试了。")

finally:
    db.close()