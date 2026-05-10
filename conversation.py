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
            "title": {"tag": "plain_text", "content": "🎉 活动邀请"},
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
