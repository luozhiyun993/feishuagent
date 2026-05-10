import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.environ["DEEPSEEK_BASE_URL"],
)

SYSTEM_PROMPT = """你是飞书里的"小聚"，一个热情友好的AI活动策划助手。你的风格：
- 回复自然、口语化，像朋友聊天一样
- 每次只引导一个话题，不要一次问太多问题
- 善用 emoji 让对话更生动
- 当收集完所有信息后，整理出来请用户确认"""


def chat(messages: list[dict], model: str = "deepseek-v4-flash") -> str:
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    resp = client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=0.8,
        max_tokens=1024,
    )
    return resp.choices[0].message.content
