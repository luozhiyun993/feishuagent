import json
import logging
import os
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
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


def on_message_receive(data: P2ImMessageReceiveV1) -> None:
    try:
        msg = data.event.message
        chat_id = msg.chat_id
        msg_type = msg.message_type

        if msg_type != "text":
            return

        content_str = msg.content
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


def main():
    APP_ID = os.environ["FEISHU_APP_ID"]
    APP_SECRET = os.environ["FEISHU_APP_SECRET"]

    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message_receive) \
        .build()

    cli = lark.ws.Client(
        APP_ID, APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    log.info("Starting Feishu AI Event Planner Bot...")
    cli.start()


if __name__ == "__main__":
    main()
