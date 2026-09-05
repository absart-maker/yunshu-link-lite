import time
import unittest

from engine.session import Conversation, SessionRegistry


class ConversationTest(unittest.TestCase):
    def test_append_and_snapshot(self) -> None:
        conv = Conversation(system_prompt="系统")
        conv.append("user", "你好")
        conv.append("assistant", "你好呀")
        snapshot = conv.snapshot()
        self.assertEqual(snapshot[0].content, "系统")
        self.assertEqual(len(snapshot), 3)

    def test_trim_exceeding_limit(self) -> None:
        conv = Conversation(max_messages=4)
        for index in range(6):
            conv.append("user", f"msg-{index}")
        self.assertEqual(len(conv.messages), 4)
        self.assertEqual(conv.messages[0].content, "msg-2")

    def test_estimated_tokens_non_negative(self) -> None:
        conv = Conversation()
        conv.append("user", "你好 world")
        self.assertGreater(conv.estimated_tokens(), 0)


class SessionRegistryTest(unittest.TestCase):
    def test_create_get_close(self) -> None:
        registry = SessionRegistry()
        session = registry.create(device_id="dev-1")
        self.assertEqual(registry.get(session.id).device_id, "dev-1")
        self.assertTrue(registry.close(session.id))
        self.assertIsNone(registry.get(session.id))

    def test_max_sessions_limit(self) -> None:
        registry = SessionRegistry(max_sessions=2)
        registry.create(device_id="a")
        registry.create(device_id="b")
        with self.assertRaises(RuntimeError):
            registry.create(device_id="c")

    def test_evict_idle(self) -> None:
        registry = SessionRegistry(idle_timeout=0.01)
        session = registry.create(device_id="old")
        time.sleep(0.03)
        self.assertEqual(registry.evict_idle(), 1)
        self.assertEqual(registry.count(), 0)


if __name__ == "__main__":
    unittest.main()
