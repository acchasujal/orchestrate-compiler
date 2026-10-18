from __future__ import annotations

import copy
import unittest
from datetime import datetime
from pathlib import Path

from code.loader import load_dataset
from code.resolver import ContextResolutionError, resolve_context


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tables, _ = load_dataset(Path(__file__).parents[2] / "dataset")
        cls.messages = list(cls.tables.messages)

    def row(self, conversation_type: str) -> dict[str, object]:
        return copy.deepcopy(next(row for row in self.messages if row["conversation_type"] == conversation_type))

    def test_personal_context_resolves_sender_and_optional_none(self) -> None:
        context = resolve_context(self.row("personal"), self.tables)
        self.assertEqual(context.conversation_type, "personal")
        self.assertIsNotNone(context.sender)
        self.assertIsNone(context.group)
        self.assertIsNone(context.group_membership)
        self.assertIsNone(context.business)
        self.assertIsNone(context.user_business_history)

    def test_personal_missing_sender_fails(self) -> None:
        row = self.row("personal")
        row["sender_user_id"] = None
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_group_context_resolves_group_sender_and_membership(self) -> None:
        context = resolve_context(self.row("group"), self.tables)
        self.assertIsNotNone(context.sender)
        self.assertIsNotNone(context.group)
        self.assertIsNotNone(context.group_membership)

    def test_group_missing_membership_fails(self) -> None:
        row = self.row("group")
        row["user_id"] = "user_missing_from_group"
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_group_missing_sender_fails(self) -> None:
        row = self.row("group")
        row["sender_user_id"] = None
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_business_context_allows_nullable_sender(self) -> None:
        row = self.row("business")
        row["sender_user_id"] = None
        context = resolve_context(row, self.tables)
        self.assertIsNone(context.sender)
        self.assertIsNotNone(context.business)

    def test_business_history_is_optional(self) -> None:
        row = next(
            copy.deepcopy(row)
            for row in self.messages
            if row["conversation_type"] == "business"
            and (row["user_id"], row["business_id"]) not in self.tables.user_business_history
        )
        context = resolve_context(row, self.tables)
        self.assertIsNone(context.user_business_history)

    def test_business_history_resolves_when_present(self) -> None:
        row = next(
            copy.deepcopy(row)
            for row in self.messages
            if row["conversation_type"] == "business"
            and (row["user_id"], row["business_id"]) in self.tables.user_business_history
        )
        context = resolve_context(row, self.tables)
        self.assertIsNotNone(context.user_business_history)

    def test_missing_required_foreign_keys_fail(self) -> None:
        cases = [("personal", "user_id", "missing"), ("group", "group_id", "missing"), ("business", "business_id", "missing")]
        for conversation_type, field, value in cases:
            with self.subTest(field=field):
                row = self.row(conversation_type)
                row[field] = value
                with self.assertRaises(ContextResolutionError):
                    resolve_context(row, self.tables)

    def test_invalid_conversation_type_fails(self) -> None:
        row = self.row("personal")
        row["conversation_type"] = "unknown"
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_corrupted_sender_foreign_key_fails(self) -> None:
        row = self.row("personal")
        row["sender_user_id"] = "missing_sender"
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_timestamp_is_preserved(self) -> None:
        row = self.row("personal")
        context = resolve_context(row, self.tables)
        self.assertEqual(context.created_at, datetime.fromisoformat(row["created_at"]))

    def test_invalid_timestamp_fails(self) -> None:
        row = self.row("personal")
        row["created_at"] = "not-a-timestamp"
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_incompatible_optional_join_fails(self) -> None:
        row = self.row("business")
        row["group_id"] = "group_001"
        with self.assertRaises(ContextResolutionError):
            resolve_context(row, self.tables)

    def test_source_order_is_preserved(self) -> None:
        resolved_ids = [resolve_context(row, self.tables).message_id for row in self.messages]
        source_ids = [row["message_id"] for row in self.messages]
        self.assertEqual(resolved_ids, source_ids)

    def test_all_target_rows_resolve(self) -> None:
        contexts = [resolve_context(row, self.tables) for row in self.messages]
        self.assertEqual(len(contexts), 110)


if __name__ == "__main__":
    unittest.main()
