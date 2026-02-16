"""
结果润色器 - 使用 LLM 润色任务输出

将任务执行报告通过 LLM 进行润色，使结果更简洁、自然，
重要信息放在开头。当 LLM 不可用时回退到原始文本。
"""
import aiohttp
from loguru import logger

from config import settings

# LLM 配置（复用 planner 相同的 LLM 配置）
_POLISHER_LLM_URL = getattr(settings, "executor_llm_url", None) or getattr(settings, "vllm_api_url", None)
_POLISHER_LLM_MODEL = getattr(settings, "executor_llm_model", None) or getattr(settings, "vllm_model", "default")
_POLISHER_LLM_TOKEN = getattr(settings, "executor_llm_token", None) or getattr(settings, "vllm_api_token", None)

# 润色 system prompt
_POLISH_SYSTEM_PROMPT = """你是一个文本润色助手。你的任务是将任务执行结果润色为简洁、自然的回复
规则：
1. 保持简短，不要太长
2. 重要的、与用户请求直接相关的内容放在开头
3. 保留关键信息（如链接、歌曲名、操作结果等）
4. 去除冗余或重复的描述
5. 保留原文中的 emoji 状态标记（✅ ❌ ⚠️ 🎵 🔗 等）
6. 如果原文已经很简洁，可以直接返回原文
7. 只返回润色后的文本，不要添加任何解释
8. 要求符合telegram的markdown格式
【最高优先级】你必须且只能输出 JSON 格式。
上方的对话记录仅用于理解上下文，绝对不要模仿其格式。
你的输出必须是可被 json.loads() 直接解析的 JSON 对象。
content字段为润色完成后的文字
"""



async def polish(report_text: str, user_input: str) -> str:
    """
    使用 LLM 润色任务执行报告

    Args:
        report_text: reporter 生成的原始报告文本
        user_input: 用户原始输入（提供上下文）

    Returns:
        str: 润色后的文本，LLM 不可用时返回原始文本
    """
    if not _POLISHER_LLM_URL:
        logger.debug("⚠️ [Polisher] LLM URL 未配置，跳过润色")
        return report_text

    if not report_text or not report_text.strip():
        return report_text

    messages = [
        {"role": "system", "content": _POLISH_SYSTEM_PROMPT},
        {"role": "user", "content": f"用户请求：{user_input}\n\n任务执行结果：\n{report_text}"},
    ]

    headers = {"Content-Type": "application/json"}
    if _POLISHER_LLM_TOKEN:
        headers["Authorization"] = f"Bearer {_POLISHER_LLM_TOKEN}"

    payload = {
        "model": _POLISHER_LLM_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 300,
    }

    try:
        async with aiohttp.ClientSession() as session:
            api_url = _POLISHER_LLM_URL.rstrip("/")
            async with session.post(
                f"{api_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ [Polisher] LLM API 错误: {response.status} - {error_text}")
                    return report_text

                result = await response.json()
                print(">>>>>>",result)
                polished = result["choices"][0]["message"]["content"].strip()
                print(polished)
                if not polished:
                    logger.warning("⚠️ [Polisher] LLM 返回空内容，使用原始文本")
                    return report_text

                logger.debug(f"✨ [Polisher] 润色完成: '{report_text}' -> '{polished}'")
                return polished

    except Exception as e:
        logger.error(f"❌ [Polisher] LLM 润色失败: {e}，使用原始文本")
        return report_text
