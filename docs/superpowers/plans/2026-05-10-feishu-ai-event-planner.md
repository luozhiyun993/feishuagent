# Feishu AI Event Planner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Feishu Bot that helps users plan events through multi-turn conversation using DeepSeek LLM, and generates invitation cards.

**Architecture:** 4-file Python app. A WebSocket client listens for Feishu messages, routes through a conversation state machine backed by DeepSeek for natural responses, and sends replies + cards via Feishu Open API.

**Tech Stack:** Python 3, openai SDK, websocket-client, httpx, python-dotenv

---

## File Plan

| File | Responsibility |
|------|---------------|
| `.env` | API keys and config |
| `requirements.txt` | Python dependencies |
| `main.py` | Entry: WebSocket connection, event loop, message routing |
| `feishu_client.py` | Feishu Open API: get token, send text/card messages |
| `deepseek_client.py` | DeepSeek API wrapper via OpenAI SDK |
| `conversation.py` | State machine, session storage, card builder |

---

### Task 1: Project Setup

**Files:**
- Create: `.env`
- Create: `requirements.txt`

- [ ] **Step 1: Create `.env` file**

```bash
cat > /Users/bearluo/Documents/learn/feishu/.env << 'EOF'
DEEPSEEK_API_KEY=sk-dfc11cb79f9f4dea819f95a6423cf731
DEEPSEEK_BASE_URL=https://api.deepseek.com
FEISHU_APP_ID=cli_a951d9e61c79dbdb
FEISHU_APP_SECRET=9RiQLGlPScnn0rtsTP9AifPl4vcywYSg
FEISHU_ADMIN_OPEN_ID=ou_0a67bd02b58f63ce9743107090dba2f0
EOF
```

- [ ] **Step 2: Create `requirements.txt`**

```
openai>=1.0.0
websocket-client>=1.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
```

- [ ] **Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All 4 packages install successfully.

---

### Task 2: Feishu Client (`feishu_client.py`)

**Files:**
- Create: `feishu_client.py`

- [ ] **Step 1: Write `feishu_client.py`**

```python
import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]
FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    def __init__(self):
        self._token: str | None = None

    def get_token(self) -> str:
        if self._token:
            return self._token
        resp = httpx.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["tenant_access_token"]
        return self._token

    def refresh_token(self) -> str:
        self._token = None
        return self.get_token()

    def send_text(self, chat_id: str, text: str) -> dict:
        token = self.get_token()
        content = json.dumps({"text": text})
        resp = httpx.post(
            f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}"},
            json={"receive_id": chat_id, "msg_type": "text", "content": content},
        )
        resp.raise_for_status()
        return resp.json()

    def send_card(self, chat_id: str, card: dict) -> dict:
        token = self.get_token()
        resp = httpx.post(
            f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from feishu_client import FeishuClient; print('OK')"`
Expected: `OK`

---

### Task 3: DeepSeek Client (`deepseek_client.py`)

**Files:**
- Create: `deepseek_client.py`

- [ ] **Step 1: Write `deepseek_client.py`**

```python
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
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from deepseek_client import chat; print('OK')"`
Expected: `OK`

---

### Task 4: Conversation State Machine (`conversation.py`)

**Files:**
- Create: `conversation.py`

- [ ] **Step 1: Write `conversation.py`**

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from deepseek_client import chat


class State(Enum):
    IDLE = "idle"
    INTRO = "intro"
    ASK_TYPE = "ask_type"
    ASK_PEOPLE = "ask_people"
    ASK_TIME = "ask_time"
    ASK_LOCATION = "ask_location"
    CONFIRM = "confirm"
    DONE = "done"


RESET_KEYWORDS = ["重新开始", "算了", "新活动", "不做了", "取消"]


@dataclass
class Session:
    state: State = State.IDLE
    activity_type: str = ""
    people: str = ""
    time: str = ""
    location: str = ""
    history: list[dict] = field(default_factory=list)

    def reset(self):
        self.state = State.IDLE
        self.activity_type = ""
        self.people = ""
        self.time = ""
        self.location = ""
        self.history = []


class ConversationManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def _get_session(self, chat_id: str) -> Session:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = Session()
        return self._sessions[chat_id]

    def process(self, chat_id: str, user_text: str) -> tuple[str, dict | None]:
        """Return (reply_text, card_dict_or_None)."""
        session = self._get_session(chat_id)

        # Check reset keywords
        if any(kw in user_text for kw in RESET_KEYWORDS):
            session.reset()
            reply = chat([{"role": "user", "content": "用户说想重新开始，请简单回复，然后重新自我介绍并询问想策划什么活动。"}])
            session.state = State.ASK_TYPE
            session.history = [{"role": "assistant", "content": reply}]
            return reply, None

        # IDLE -> INTRO: user starts a conversation
        if session.state == State.IDLE:
            session.state = State.INTRO

        if session.state == State.INTRO:
            reply = chat([{"role": "user", "content": "请向用户做自我介绍，告诉他们你可以帮他们策划聚会活动、生成邀请卡片，然后询问他们想策划什么样的活动。回复要热情友好。"}])
            session.state = State.ASK_TYPE
            session.history.append({"role": "assistant", "content": reply})
            return reply, None

        # Collecting info states
        if session.state == State.ASK_TYPE:
            session.activity_type = user_text
            session.history.append({"role": "user", "content": user_text})
            reply = chat(session.history + [
                {"role": "user", "content": f"用户说想策划的是：{user_text}。请确认这个活动类型，然后询问用户想和谁一起参加（朋友、同事、家人等）。"}
            ])
            session.state = State.ASK_PEOPLE
            session.history.append({"role": "assistant", "content": reply})
            return reply, None

        if session.state == State.ASK_PEOPLE:
            session.people = user_text
            session.history.append({"role": "user", "content": user_text})
            reply = chat(session.history + [
                {"role": "user", "content": f"用户想邀请的人是：{user_text}。请确认，然后询问活动时间。"}
            ])
            session.state = State.ASK_TIME
            session.history.append({"role": "assistant", "content": reply})
            return reply, None

        if session.state == State.ASK_TIME:
            session.time = user_text
            session.history.append({"role": "user", "content": user_text})
            reply = chat(session.history + [
                {"role": "user", "content": f"用户说的活动时间是：{user_text}。请确认，然后询问活动地点。"}
            ])
            session.state = State.ASK_LOCATION
            session.history.append({"role": "assistant", "content": reply})
            return reply, None

        if session.state == State.ASK_LOCATION:
            session.location = user_text
            session.history.append({"role": "user", "content": user_text})
            reply = chat(session.history + [
                {"role": "user", "content": f"活动信息收集完毕：\n- 活动类型：{session.activity_type}\n- 参与人员：{session.people}\n- 时间：{session.time}\n- 地点：{session.location}\n\n请整理这些信息，用清晰友好的方式呈现给用户，请用户确认是否正确。"}
            ])
            session.state = State.CONFIRM
            session.history.append({"role": "assistant", "content": reply})
            return reply, None

        if session.state == State.CONFIRM:
            positive = any(w in user_text for w in ["好的", "可以", "确认", "对的", "是的", "没错", "没问题", "行", "ok", "OK", "好", "嗯", "对", "生成", "创建"])
            if positive:
                card = build_card(
                    activity_type=session.activity_type,
                    people=session.people,
                    time=session.time,
                    location=session.location,
                )
                reply = chat(session.history + [
                    {"role": "user", "content": "用户已确认活动信息。请告诉用户活动卡片已生成，可以查看并转发给朋友了。回复简短。"}
                ])
                session.state = State.DONE
                session.history.append({"role": "assistant", "content": reply})
                return reply, card
            else:
                reply = chat(session.history + [
                    {"role": "user", "content": "用户似乎想修改信息。请询问用户想修改什么内容。"}
                ])
                session.state = State.ASK_TYPE  # restart collection
                session.history.append({"role": "assistant", "content": reply})
                return reply, None

        if session.state == State.DONE:
            session.reset()
            reply = chat([{"role": "user", "content": "上一轮活动策划已完成，用户又发来新消息。请简短问候，重新自我介绍，询问想策划什么新活动。"}])
            session.state = State.ASK_TYPE
            session.history = [{"role": "assistant", "content": reply}]
            return reply, None

        # fallback
        session.reset()
        return "抱歉，出了点问题，请重新开始吧。你可以直接告诉我你想策划什么活动～", None


def build_card(activity_type: str, people: str, time: str, location: str) -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🎉 活动邀请"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": False, "text": {"tag": "lark_md", "content": f"**📌 活动**\n{activity_type}"}},
                    {"is_short": False, "text": {"tag": "lark_md", "content": f"**👥 参与人员**\n{people}"}},
                    {"is_short": False, "text": {"tag": "lark_md", "content": f"**🕐 时间**\n{time}"}},
                    {"is_short": False, "text": {"tag": "lark_md", "content": f"**📍 地点**\n{location}"}},
                ],
            },
            {
                "tag": "hr",
            },
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"由 AI 活动助手生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                ],
            },
        ],
    }
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from conversation import ConversationManager; print('OK')"`
Expected: `OK`

---

### Task 5: Main Entry (`main.py`)

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write `main.py`**

```python
import json
import logging
import websocket
from dotenv import load_dotenv

load_dotenv()

from feishu_client import FeishuClient
from conversation import ConversationManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

feishu = FeishuClient()
conv_mgr = ConversationManager()

FEISHU_WS_URL = "wss://open.feishu.cn/open-apis/ws/event/v1"


def on_message(ws, raw):
    log.info(f"Received: {raw}")
    try:
        event = json.loads(raw)
        event_type = event.get("header", {}).get("event_type", "")
        if event_type != "im.message.receive_v1":
            return
        msg = event.get("event", {}).get("message", {})
        chat_id = msg.get("chat_id", "")
        msg_type = msg.get("message_type", "")
        if msg_type != "text":
            return
        content_str = msg.get("content", "{}")
        content = json.loads(content_str)
        user_text = content.get("text", "")
        if not user_text or not chat_id:
            return

        log.info(f"[{chat_id}] User: {user_text}")

        reply_text, card = conv_mgr.process(chat_id, user_text)
        feishu.send_text(chat_id, reply_text)
        log.info(f"[{chat_id}] Bot: {reply_text}")

        if card:
            feishu.send_card(chat_id, card)
            log.info(f"[{chat_id}] Card sent")

    except Exception as e:
        log.error(f"Error processing message: {e}", exc_info=True)


def on_error(ws, error):
    log.error(f"WebSocket error: {error}")


def on_close(ws, code, msg):
    log.info(f"WebSocket closed: {code} {msg}")


def on_open(ws):
    log.info("Connected to Feishu WebSocket")


def main():
    token = feishu.get_token()
    log.info("Got tenant access token")

    ws = websocket.WebSocketApp(
        FEISHU_WS_URL,
        header={"Authorization": f"Bearer {token}"},
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    log.info("Starting WebSocket connection...")
    ws.run_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import main; print('OK')"`
Expected: `OK`

---

### Task 6: Integration Verification

- [ ] **Step 1: Verify all modules import cleanly**

Run: `cd /Users/bearluo/Documents/learn/feishu && .venv/bin/python -c "
from feishu_client import FeishuClient
from deepseek_client import chat
from conversation import ConversationManager, build_card, State
import main
print('All imports OK')
"`

- [ ] **Step 2: Test conversation state machine locally**

Run: `.venv/bin/python -c "
from conversation import ConversationManager
mgr = ConversationManager()
chat_id = 'test_123'

# Simulate full conversation flow
reply, card = mgr.process(chat_id, '嗨')
print(f'INTRO: {reply}')
assert card is None

reply, card = mgr.process(chat_id, '想搞个烧烤聚会')
print(f'ASK_PEOPLE: {reply}')
assert card is None

reply, card = mgr.process(chat_id, '和大学同学一起')
print(f'ASK_TIME: {reply}')
assert card is None

reply, card = mgr.process(chat_id, '周六下午3点')
print(f'ASK_LOCATION: {reply}')
assert card is None

reply, card = mgr.process(chat_id, '朝阳公园')
print(f'CONFIRM: {reply}')
assert card is None

reply, card = mgr.process(chat_id, '好的，确认')
print(f'DONE card: {card}')
assert card is not None
assert '烧烤聚会' in str(card)
assert '大学同学' in str(card)
assert '朝阳公园' in str(card)

# Test new round
reply, card = mgr.process(chat_id, '嗨，再帮我策划一个')
print(f'NEW ROUND: {reply}')
assert card is None

print('All state machine tests passed!')
"`

Expected: All assertions pass, `All state machine tests passed!`

- [ ] **Step 3: Start the bot**

Run: `python main.py`

Manual test in Feishu:
1. Send "嗨" to the bot
2. Follow the conversation flow
3. Verify the card is generated and displayed
