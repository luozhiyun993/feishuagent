import os
import json
import uuid
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageResponse,
)
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]


class FeishuClient:
    def __init__(self):
        self._client = lark.Client.builder() \
            .app_id(APP_ID) \
            .app_secret(APP_SECRET) \
            .log_level(lark.LogLevel.INFO) \
            .build()

    def send_text(self, chat_id: str, text: str) -> CreateMessageResponse:
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .uuid(str(uuid.uuid4()))
                .build()
            ) \
            .build()
        response = self._client.im.v1.message.create(request)
        if not response.success():
            lark.logger.error(
                f"send_text failed, code: {response.code}, msg: {response.msg}"
            )
        return response

    def send_card(self, chat_id: str, card: dict) -> CreateMessageResponse:
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .uuid(str(uuid.uuid4()))
                .build()
            ) \
            .build()
        response = self._client.im.v1.message.create(request)
        if not response.success():
            lark.logger.error(
                f"send_card failed, code: {response.code}, msg: {response.msg}"
            )
        return response
