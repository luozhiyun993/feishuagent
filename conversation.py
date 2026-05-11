import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from deepseek_client import chat

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = "idle"
    COLLECTING = "collecting"
    CONFIRM = "confirm"
    DONE = "done"


RESET_KEYWORDS = ["重新开始", "算了", "新活动", "不做了", "取消"]
REQUIRED_FIELDS = ("activity_type", "people", "time", "location")
REGENERATE_KEYWORDS = ("重新生成", "再生成", "重发", "再发", "重新发", "活动邀请", "邀请卡")
MAX_HISTORY_MESSAGES = 20


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
    def __init__(self, store_path: str | Path = "session_store.json"):
        self._sessions: dict[str, Session] = {}
        self._store_path = Path(store_path)
        self._load_sessions()

    def _get_session(self, chat_id: str) -> Session:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = Session()
        return self._sessions[chat_id]

    def process(self, chat_id: str, user_text: str) -> tuple[str, dict | None]:
        session = self._get_session(chat_id)
        log.info("Process start: chat_id=%s state=%s slots=%s", chat_id, session.state.value, _slot_snapshot(session))
        user_text = user_text.strip()
        if not user_text:
            return "请发送文字消息来开始策划活动吧～", None

        if any(kw in user_text for kw in RESET_KEYWORDS):
            log.info("Reset keyword matched: chat_id=%s user_text=%s", chat_id, user_text)
            session.reset()
            self._save_sessions()

        if session.state == State.DONE and _is_regenerate_request(user_text) and not _missing_fields(session):
            log.info("Branch regenerate: chat_id=%s", chat_id)
            _append_history(session, "user", user_text)
            reply = _generate_reply(session, user_text, [], True)
            card = build_card(
                activity_type=session.activity_type,
                people=session.people,
                time=session.time,
                location=session.location,
            )
            _append_history(session, "assistant", reply)
            self._save_sessions()
            log.info("Session slots: %s", _slot_snapshot(session))
            return reply, card

        if session.state == State.DONE:
            log.info("Branch done-reset-for-new-request: chat_id=%s", chat_id)
            session.reset()

        _append_history(session, "user", user_text)

        extracted = _extract_slots(session, user_text)
        log.info("Extracted slots: %s", extracted)
        _merge_slots(session, extracted)
        missing_fields = _missing_fields(session)

        if session.state == State.IDLE:
            session.state = State.COLLECTING

        if not missing_fields:
            if extracted["is_confirmation"]:
                log.info("Branch confirmation-complete: chat_id=%s", chat_id)
                card = build_card(
                    activity_type=session.activity_type,
                    people=session.people,
                    time=session.time,
                    location=session.location,
                )
                reply = _generate_reply(session, user_text, missing_fields, True)
                session.state = State.DONE
                _append_history(session, "assistant", reply)
                self._save_sessions()
                log.info("Session slots: %s", _slot_snapshot(session))
                return reply, card

            session.state = State.CONFIRM
            log.info("Branch ready-for-confirm: chat_id=%s", chat_id)
            reply = _generate_reply(session, user_text, missing_fields, False)
            _append_history(session, "assistant", reply)
            self._save_sessions()
            log.info("Session slots: %s", _slot_snapshot(session))
            return reply, None

        session.state = State.COLLECTING
        log.info("Branch collecting-missing-fields: chat_id=%s missing_fields=%s", chat_id, missing_fields)
        reply = _generate_reply(session, user_text, missing_fields, False)
        _append_history(session, "assistant", reply)
        self._save_sessions()
        log.info("Session slots: %s", _slot_snapshot(session))
        return reply, None

    def _load_sessions(self) -> None:
        if not self._store_path.exists():
            log.info("Session store missing, starting fresh: %s", self._store_path)
            return
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to load sessions from %s: %s", self._store_path, e)
            return
        for chat_id, payload in raw.items():
            self._sessions[chat_id] = Session(
                state=State(payload.get("state", State.IDLE.value)),
                activity_type=payload.get("activity_type", ""),
                people=payload.get("people", ""),
                time=payload.get("time", ""),
                location=payload.get("location", ""),
                history=payload.get("history", [])[-MAX_HISTORY_MESSAGES:],
            )
        log.info("Loaded sessions from %s count=%s", self._store_path, len(self._sessions))

    def _save_sessions(self) -> None:
        payload = {}
        for chat_id, session in self._sessions.items():
            payload[chat_id] = {
                "state": session.state.value,
                "activity_type": session.activity_type,
                "people": session.people,
                "time": session.time,
                "location": session.location,
                "history": session.history[-MAX_HISTORY_MESSAGES:],
            }
        try:
            self._store_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("Saved sessions to %s count=%s", self._store_path, len(payload))
        except Exception as e:
            log.warning("Failed to save sessions to %s: %s", self._store_path, e)


def _extract_slots(session: Session, user_text: str) -> dict:
    history_text = _recent_history_text(session)
    prompt = f"""你是信息抽取器。请从用户消息中提取活动信息，严格只返回 JSON，不要加 markdown。

当前已知信息：
- activity_type: {session.activity_type or ""}
- people: {session.people or ""}
- time: {session.time or ""}
- location: {session.location or ""}

最近对话历史：
{history_text}

用户消息：
{user_text}

返回格式：
{{
  "activity_type": "",
  "people": "",
  "time": "",
  "location": "",
  "is_confirmation": false
}}

规则：
- 没提到的字段返回空字符串
- 只有用户明确确认全部信息时，is_confirmation 才返回 true
- 如果用户是在修改已有信息，只返回修改的字段
- 输出必须是合法 JSON
"""
    try:
        raw = _safe_chat([{"role": "user", "content": prompt}])
        parsed = _parse_extraction_json(raw)
        return {
            "activity_type": str(parsed.get("activity_type", "") or ""),
            "people": str(parsed.get("people", "") or ""),
            "time": str(parsed.get("time", "") or ""),
            "location": str(parsed.get("location", "") or ""),
            "is_confirmation": bool(parsed.get("is_confirmation", False)),
        }
    except Exception as e:
        log.error("Slot extraction error: %s", e)
        return _heuristic_extract_slots(session, user_text)


def _generate_reply(session: Session, user_text: str, missing_fields: list[str], is_confirmation: bool) -> str:
    history_text = _recent_history_text(session)
    slot_summary = (
        f"活动类型：{session.activity_type or '未提供'}\n"
        f"参与人员：{session.people or '未提供'}\n"
        f"时间：{session.time or '未提供'}\n"
        f"地点：{session.location or '未提供'}"
    )
    if is_confirmation:
        prompt = f"""用户已经确认活动信息，请简短告诉用户活动卡片已生成，可以查看和转发。

当前活动信息：
{slot_summary}

最近对话历史：
{history_text}
"""
        return _safe_chat([{"role": "user", "content": prompt}])

    if missing_fields:
        prompt = f"""你是飞书里的"小聚"，一个热情友好的AI活动策划助手。

当前已收集信息：
{slot_summary}

最近对话历史：
{history_text}

仍缺少的信息字段：{", ".join(missing_fields)}
用户刚说：{user_text}

请自然回复用户：
- 先简短承接用户刚才的话
- 只追问缺失的信息
- 语气自然、简洁、友好
- 不要机械地罗列字段名
- 不要重新自我介绍，不要说“好久不见”
"""
        return _safe_chat([{"role": "user", "content": prompt}])

    prompt = f"""你是飞书里的"小聚"，一个热情友好的AI活动策划助手。

当前活动信息已经齐全：
{slot_summary}

最近对话历史：
{history_text}

用户刚说：{user_text}

请整理这些活动信息并请用户确认是否正确，语气自然友好。
- 不要重新自我介绍
"""
    return _safe_chat([{"role": "user", "content": prompt}])


def _merge_slots(session: Session, extracted: dict) -> None:
    for field_name in REQUIRED_FIELDS:
        value = extracted.get(field_name, "")
        if value:
            setattr(session, field_name, value.strip())


def _missing_fields(session: Session) -> list[str]:
    return [field_name for field_name in REQUIRED_FIELDS if not getattr(session, field_name)]


def _slot_snapshot(session: Session) -> dict:
    return {
        "state": session.state.value,
        "activity_type": session.activity_type,
        "people": session.people,
        "time": session.time,
        "location": session.location,
    }


def _append_history(session: Session, role: str, content: str) -> None:
    session.history.append({"role": role, "content": content})
    if len(session.history) > MAX_HISTORY_MESSAGES:
        session.history = session.history[-MAX_HISTORY_MESSAGES:]


def _recent_history_text(session: Session) -> str:
    if not session.history:
        return "无"
    return "\n".join(
        f"{item.get('role', 'unknown')}: {item.get('content', '')}"
        for item in session.history[-MAX_HISTORY_MESSAGES:]
    )


def _empty_extraction() -> dict:
    return {
        "activity_type": "",
        "people": "",
        "time": "",
        "location": "",
        "is_confirmation": False,
    }


def _parse_extraction_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        text = text[start:end]
    return json.loads(text)


def _heuristic_extract_slots(session: Session, user_text: str) -> dict:
    extracted = _empty_extraction()
    text = user_text.strip()

    if text in {"确认", "好的", "可以", "没问题", "行", "ok", "OK"}:
        extracted["is_confirmation"] = True

    if any(word in text for word in ("同事", "朋友", "家人", "同学", "我们", "大家")):
        extracted["people"] = text.replace("一起", "").strip("，。 ")

    if any(word in text for word in ("今天", "明天", "后天", "周", "星期", "下午", "上午", "晚上", "点")):
        extracted["time"] = text

    if any(word in text for word in ("在", "地点", "体育中心", "公园", "餐厅", "公司", "会议室", "KTV")):
        extracted["location"] = text.replace("地点是", "").replace("地点在", "").strip("，。 ")

    if any(word in text for word in ("活动", "聚会", "羽毛球", "烧烤", "露营", "聚餐", "生日")):
        extracted["activity_type"] = text

    if session.activity_type and extracted["activity_type"] == text and len(text) < 8:
        extracted["activity_type"] = ""

    return extracted


def _is_regenerate_request(user_text: str) -> bool:
    return any(word in user_text for word in REGENERATE_KEYWORDS) and any(
        word in user_text for word in ("重新", "再", "重")
    )


def _safe_chat(messages: list[dict]) -> str:
    try:
        return chat(messages)
    except Exception as e:
        log.error("Chat API error: %s", e)
        raise


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
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"由 AI 活动助手生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                ],
            },
        ],
    }
