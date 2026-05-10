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
