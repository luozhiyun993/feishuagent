import tempfile
import unittest
from pathlib import Path

import conversation
from conversation import ConversationManager, State
from runtime_state import MessageDeduper


class PersistenceAndDedupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_extract = conversation._extract_slots
        self.original_reply = conversation._generate_reply

    def tearDown(self) -> None:
        conversation._extract_slots = self.original_extract
        conversation._generate_reply = self.original_reply

    def test_persisted_done_session_can_regenerate_after_restart(self) -> None:
        extraction_results = [
            {
                "activity_type": "羽毛球活动",
                "people": "同事们一起",
                "time": "下周六下午三点",
                "location": "静安体育中心",
                "is_confirmation": False,
            },
            {
                "activity_type": "",
                "people": "",
                "time": "",
                "location": "",
                "is_confirmation": True,
            },
        ]
        replies = ["请确认完整信息", "活动卡片已生成", "重新生成好了"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            store_path = Path(tmp_dir) / "sessions.json"

            manager = ConversationManager(store_path=store_path)
            manager.process("chat-1", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
            manager.process("chat-1", "确认")

            restarted = ConversationManager(store_path=store_path)
            reply, card = restarted.process("chat-1", "帮我重新生成一次活动邀请")

            self.assertEqual("重新生成好了", reply)
            self.assertIsNotNone(card)
            self.assertEqual(State.DONE, restarted._sessions["chat-1"].state)

    def test_message_deduper_rejects_duplicate_message_id(self) -> None:
        deduper = MessageDeduper(max_ids=3)

        self.assertFalse(deduper.seen("msg-1"))
        self.assertTrue(deduper.seen("msg-1"))
        self.assertFalse(deduper.seen("msg-2"))


if __name__ == "__main__":
    unittest.main()
