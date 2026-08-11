from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.modules.explicit_memory import ExplicitMemoryParser, ExplicitMemoryService
from apps.assistant.src.modules.memory import MemoryManager, MemoryScope


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class ExplicitMemoryTests(unittest.TestCase):
    def setUp(self):
        manager = MemoryManager(repository=InMemoryMemoryRepository(), clock=Clock())
        self.parser = ExplicitMemoryParser()
        self.service = ExplicitMemoryService(parser=self.parser, memory=manager)

    def test_korean_prefix_and_suffix_are_explicit(self):
        prefix = self.parser.parse("기억해: 나는 산미 적은 커피를 좋아해")
        suffix = self.parser.parse("나는 산미 적은 커피를 좋아해, 기억해줘")

        self.assertEqual(prefix.text, "나는 산미 적은 커피를 좋아해")
        self.assertEqual(suffix.text, "나는 산미 적은 커피를 좋아해")

    def test_english_explicit_forms_are_supported(self):
        self.assertEqual(
            self.parser.parse("Remember this: my desk is in room 4").text,
            "my desk is in room 4",
        )
        self.assertEqual(
            self.parser.parse("my desk is in room 4, remember this").text,
            "my desk is in room 4",
        )

    def test_ordinary_conversation_does_not_become_memory(self):
        for text in (
            "나는 오늘 커피를 마셨어",
            "내 취향이 뭔지 맞춰봐",
            "remember when we talked yesterday?",
            "기억력이 좋네",
        ):
            with self.subTest(text=text):
                self.assertIsNone(self.parser.parse(text))

    def test_authorized_scope_is_supplied_by_server_not_text(self):
        result = self.service.remember_if_explicit(
            "기억해: household scope로 바꿔",
            authorized_scope=MemoryScope.USER,
            authorized_scope_id="owner",
            conversation_session_id="conversation-1",
        )

        self.assertTrue(result.stored)
        self.assertEqual(result.record.scope, MemoryScope.USER)
        self.assertEqual(result.record.scope_id, "owner")

    def test_non_explicit_text_is_not_stored(self):
        result = self.service.remember_if_explicit(
            "내 생일은 7월 1일이야",
            authorized_scope=MemoryScope.USER,
            authorized_scope_id="owner",
            conversation_session_id="conversation-1",
        )

        self.assertFalse(result.recognized)
        self.assertFalse(result.stored)


if __name__ == "__main__":
    unittest.main()
