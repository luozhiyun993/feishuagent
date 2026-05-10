import json
import logging
import websocket
from dotenv import load_dotenv

load_dotenv()

from feishu_client import FeishuClient
from conversation import ConversationManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

feishu = FeishuClient()
conv_mgr = ConversationManager()

FEISHU_WS_URL = "wss://open.feishu.cn/open-apis/event/v1"


def on_message(ws, raw):
    log.info(f"WS message received (first 500 chars): {raw[:500]}")
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
        log.info(f"[{chat_id}] Bot replied")

        if card:
            feishu.send_card(chat_id, card)
            log.info(f"[{chat_id}] Card sent")

    except Exception as e:
        log.error(f"Error processing message: {e}", exc_info=True)


def on_error(ws, error):
    log.error(f"WebSocket error: {error}")


def on_close(ws, code, msg):
    log.info(f"WebSocket closed: code={code} msg={msg}")


def on_open(ws):
    log.info("WebSocket connected to Feishu")


def main():
    token = feishu.get_token()
    log.info("Got tenant access token, connecting to WebSocket...")

    ws = websocket.WebSocketApp(
        FEISHU_WS_URL,
        header={"Authorization": f"Bearer {token}"},
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    ws.run_forever()


if __name__ == "__main__":
    main()
