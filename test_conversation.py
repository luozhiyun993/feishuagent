import unittest

import conversation
from conversation import ConversationManager, State


class ConversationManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_chat = conversation.chat
        self.original_extract = getattr(conversation, "_extract_slots", None)
        self.original_reply = getattr(conversation, "_generate_reply", None)
        self.original_safe_chat = getattr(conversation, "_safe_chat", None)

    def tearDown(self) -> None:
        conversation.chat = self.original_chat
        if self.original_extract is not None:
            conversation._extract_slots = self.original_extract
        if self.original_reply is not None:
            conversation._generate_reply = self.original_reply
        if self.original_safe_chat is not None:
            conversation._safe_chat = self.original_safe_chat

    def test_collects_slots_across_out_of_order_messages(self) -> None:
        extraction_results = [
            {
                "activity_type": "羽毛球活动",
                "people": "",
                "time": "",
                "location": "",
                "is_confirmation": False,
            },
            {
                "activity_type": "",
                "people": "",
                "time": "下周六下午三点",
                "location": "静安体育中心",
                "is_confirmation": False,
            },
            {
                "activity_type": "",
                "people": "同事们一起",
                "time": "",
                "location": "",
                "is_confirmation": False,
            },
        ]
        replies = ["先问人", "继续确认", "请确认"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager()

        reply, card = manager.process("chat-1", "我想周末组织一次羽毛球活动")
        self.assertEqual("先问人", reply)
        self.assertIsNone(card)

        reply, card = manager.process("chat-1", "下周六下午三点，静安体育中心")
        self.assertEqual("继续确认", reply)
        self.assertIsNone(card)

        reply, card = manager.process("chat-1", "同事们一起")

        session = manager._sessions["chat-1"]
        self.assertEqual("请确认", reply)
        self.assertIsNone(card)
        self.assertEqual("羽毛球活动", session.activity_type)
        self.assertEqual("同事们一起", session.people)
        self.assertEqual("下周六下午三点", session.time)
        self.assertEqual("静安体育中心", session.location)
        self.assertEqual(State.CONFIRM, session.state)

    def test_single_message_can_fill_multiple_slots(self) -> None:
        conversation._extract_slots = lambda session, user_text: {
            "activity_type": "羽毛球活动",
            "people": "同事们一起",
            "time": "下周六下午三点",
            "location": "静安体育中心",
            "is_confirmation": False,
        }
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: "请确认完整信息"
        manager = ConversationManager()

        reply, card = manager.process("chat-2", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")

        session = manager._sessions["chat-2"]
        self.assertEqual("请确认完整信息", reply)
        self.assertIsNone(card)
        self.assertEqual(State.CONFIRM, session.state)
        self.assertEqual("羽毛球活动", session.activity_type)
        self.assertEqual("同事们一起", session.people)
        self.assertEqual("下周六下午三点", session.time)
        self.assertEqual("静安体育中心", session.location)

    def test_confirmation_generates_card_when_all_slots_present(self) -> None:
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
        replies = ["请确认完整信息", "活动卡片已生成"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager()

        manager.process("chat-3", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
        reply, card = manager.process("chat-3", "确认")

        self.assertEqual("活动卡片已生成", reply)
        self.assertIsNotNone(card)
        self.assertEqual("羽毛球活动", card["elements"][0]["fields"][0]["text"]["content"].split("\n", 1)[1])
        self.assertEqual("同事们一起", card["elements"][0]["fields"][1]["text"]["content"].split("\n", 1)[1])
        self.assertEqual(State.DONE, manager._sessions["chat-3"].state)

    def test_modification_during_confirmation_updates_slots_instead_of_resetting(self) -> None:
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
                "time": "下周日上午十点",
                "location": "",
                "is_confirmation": False,
            },
        ]
        replies = ["请确认完整信息", "已更新，请再次确认"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager()

        manager.process("chat-4", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
        reply, card = manager.process("chat-4", "时间改成下周日上午十点")

        session = manager._sessions["chat-4"]
        self.assertEqual("已更新，请再次确认", reply)
        self.assertIsNone(card)
        self.assertEqual("下周日上午十点", session.time)
        self.assertEqual("静安体育中心", session.location)
        self.assertEqual(State.CONFIRM, session.state)

    def test_extraction_failure_falls_back_safely(self) -> None:
        conversation._extract_slots = lambda session, user_text: {
            "activity_type": "",
            "people": "",
            "time": "",
            "location": "",
            "is_confirmation": False,
        }
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: "我先确认一下，你想办什么活动？"
        manager = ConversationManager()

        reply, card = manager.process("chat-5", "随便聊聊")

        self.assertEqual("我先确认一下，你想办什么活动？", reply)
        self.assertIsNone(card)
        self.assertEqual(State.COLLECTING, manager._sessions["chat-5"].state)

    def test_done_state_resets_for_new_request(self) -> None:
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
            {
                "activity_type": "烧烤活动",
                "people": "",
                "time": "",
                "location": "",
                "is_confirmation": False,
            },
        ]
        replies = ["请确认完整信息", "活动卡片已生成", "新的活动收到啦"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager()

        manager.process("chat-6", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
        manager.process("chat-6", "确认")
        reply, card = manager.process("chat-6", "我想再组织一次烧烤")

        session = manager._sessions["chat-6"]
        self.assertEqual("新的活动收到啦", reply)
        self.assertIsNone(card)
        self.assertEqual("烧烤活动", session.activity_type)
        self.assertEqual("", session.people)
        self.assertEqual(State.COLLECTING, session.state)

    def test_regenerate_request_after_done_reuses_existing_slots(self) -> None:
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
            {
                "activity_type": "",
                "people": "",
                "time": "",
                "location": "",
                "is_confirmation": False,
            },
        ]
        replies = ["请确认完整信息", "活动卡片已生成", "重新生成好了"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager()

        manager.process("chat-7", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
        manager.process("chat-7", "确认")
        reply, card = manager.process("chat-7", "帮我重新生成一次活动邀请")

        session = manager._sessions["chat-7"]
        self.assertEqual("重新生成好了", reply)
        self.assertIsNotNone(card)
        self.assertEqual("羽毛球活动", session.activity_type)
        self.assertEqual(State.DONE, session.state)

    def test_restart_with_new_activity_uses_new_message_as_context_without_intro_reset(self) -> None:
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
            {
                "activity_type": "团建",
                "people": "同事一起",
                "time": "",
                "location": "",
                "is_confirmation": False,
            },
        ]
        replies = ["请确认完整信息", "活动卡片已生成", "收到，这次是同事团建，我还差时间和地点"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager()

        manager.process("chat-8", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
        manager.process("chat-8", "确认")
        reply, card = manager.process("chat-8", "这次我想要邀请同事一起去参加一次团建")

        session = manager._sessions["chat-8"]
        self.assertEqual("收到，这次是同事团建，我还差时间和地点", reply)
        self.assertIsNone(card)
        self.assertEqual("团建", session.activity_type)
        self.assertEqual("同事一起", session.people)
        self.assertEqual(State.COLLECTING, session.state)

    def test_history_keeps_only_latest_ten_rounds_for_model_context(self) -> None:
        captured = {}

        def fake_safe_chat(messages):
            captured["messages"] = messages
            return '{"activity_type":"","people":"","time":"","location":"","is_confirmation":false}'

        conversation._safe_chat = fake_safe_chat
        manager = ConversationManager(store_path=":memory:")
        session = manager._get_session("chat-9")
        session.history = []
        for i in range(12):
            session.history.append({"role": "user", "content": f"user-{i}"})
            session.history.append({"role": "assistant", "content": f"assistant-{i}"})

        conversation._extract_slots(session, "最新消息")

        prompt = captured["messages"][0]["content"]
        self.assertIn("user-2", prompt)
        self.assertIn("assistant-11", prompt)
        self.assertNotIn("user-0", prompt)
        self.assertNotIn("assistant-0", prompt)

    def test_new_round_clears_old_history(self) -> None:
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
            {
                "activity_type": "烧烤活动",
                "people": "",
                "time": "",
                "location": "",
                "is_confirmation": False,
            },
        ]
        replies = ["请确认完整信息", "活动卡片已生成", "新的活动收到啦"]
        conversation._extract_slots = lambda session, user_text: extraction_results.pop(0)
        conversation._generate_reply = lambda session, user_text, missing_fields, is_confirmation: replies.pop(0)
        manager = ConversationManager(store_path=":memory:")

        manager.process("chat-10", "我想周末和同事在静安体育中心打羽毛球，下周六下午三点")
        manager.process("chat-10", "确认")
        manager.process("chat-10", "我想再组织一次烧烤")

        session = manager._sessions["chat-10"]
        self.assertEqual(2, len(session.history))
        self.assertEqual("我想再组织一次烧烤", session.history[0]["content"])
        self.assertEqual("新的活动收到啦", session.history[1]["content"])


if __name__ == "__main__":
    unittest.main()
