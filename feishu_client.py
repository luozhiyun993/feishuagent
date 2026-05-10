import os
import json
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]
FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    def __init__(self):
        self._token: str | None = None
        self._token_expires_at: float = 0

    def get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        resp = httpx.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise Exception(f"Feishu auth error: {data.get('code')} {data.get('msg')}")
        self._token = data["tenant_access_token"]
        # Refresh 60s before actual expiry
        self._token_expires_at = time.monotonic() + data.get("expire", 7200) - 60
        return self._token

    def refresh_token(self) -> str:
        self._token = None
        self._token_expires_at = 0
        return self.get_token()

    def _post(self, path: str, body: dict) -> dict:
        token = self.get_token()
        resp = httpx.post(
            f"{FEISHU_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise Exception(f"Feishu API error: {data.get('code')} {data.get('msg')}")
        return data

    def send_text(self, chat_id: str, text: str) -> dict:
        content = json.dumps({"text": text})
        return self._post(
            "/im/v1/messages?receive_id_type=chat_id",
            {"receive_id": chat_id, "msg_type": "text", "content": content},
        )

    def send_card(self, chat_id: str, card: dict) -> dict:
        return self._post(
            "/im/v1/messages?receive_id_type=chat_id",
            {
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
        )
