import json
import logging
import os
import ssl
import time

import lark_oapi as lark
import lark_oapi.ws.client as _ws_client
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from dotenv import load_dotenv

# Patch SSL for corporate network proxy
_orig_ws_kwargs = _ws_client._ws_connect_kwargs


def _patched_ws_kwargs():
    kwargs = _orig_ws_kwargs()
    kwargs["ssl"] = ssl._create_unverified_context()
    return kwargs


_ws_client._ws_connect_kwargs = _patched_ws_kwargs

load_dotenv()

from feishu_client import FeishuClient
from conversation import ConversationManager
from runtime_state import MessageDeduper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)
PROCESS_STARTED_AT_MS = int(time.time() * 1000)

feishu = FeishuClient()
conv_mgr = ConversationManager()
message_deduper = MessageDeduper()


def on_message_receive(data: P2ImMessageReceiveV1) -> None:
    log.info(f"!!! EVENT RECEIVED !!!")
    try:
        msg = data.event.message
        chat_id = msg.chat_id
        msg_type = msg.message_type
        message_id = msg.message_id
        message_create_time = int(msg.create_time) if msg.create_time else 0
        event_age_ms = PROCESS_STARTED_AT_MS - message_create_time if message_create_time else -1

        log.info(
            "MSG id=%s type=%s chat_id=%s create_time=%s event_age_ms=%s content=%s",
            message_id,
            msg_type,
            chat_id,
            message_create_time,
            event_age_ms,
            msg.content[:100] if msg.content else "None",
        )

        if msg_type != "text":
            log.warning(f"Ignoring non-text message type: {msg_type}")
            return

        if message_id and message_deduper.seen(message_id):
            log.warning("Duplicate message ignored: id=%s chat_id=%s", message_id, chat_id)
            return

        log.info("Message accepted: id=%s chat_id=%s", message_id, chat_id)

        content_str = msg.content
        content = json.loads(content_str)
        user_text = content.get("text", "")
        if not user_text or not chat_id:
            log.warning("Empty user_text or chat_id, skipping")
            return

        log.info(f"[{chat_id}] User: {user_text}")

        reply_text, card = conv_mgr.process(chat_id, user_text)
        log.info(f"[{chat_id}] Bot reply: {reply_text}")
        resp = feishu.send_text(chat_id, reply_text)
        log.info(f"[{chat_id}] Bot replied, success={resp.success()}, code={resp.code}")

        if card:
            resp2 = feishu.send_card(chat_id, card)
            log.info(f"[{chat_id}] Card sent, success={resp2.success()}, code={resp2.code}")

    except Exception as e:
        log.error(f"Error processing message: {e}", exc_info=True)


def main():
    APP_ID = os.environ["FEISHU_APP_ID"]
    APP_SECRET = os.environ["FEISHU_APP_SECRET"]

    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message_receive) \
        .build()

    cli = lark.ws.Client(
        APP_ID, APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG,
    )
    log.info(
        "Starting Feishu AI Event Planner Bot... process_started_at_ms=%s session_store=%s",
        PROCESS_STARTED_AT_MS,
        conv_mgr._store_path,
    )
    cli.start()


if __name__ == "__main__":
    main()
