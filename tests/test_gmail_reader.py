"""
Tests for gmail_reader: list IDs by label, filter by seen, hydrate messages.

Uses fixture JSON; no live Gmail API. Service is mocked.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from roleforge.gmail_reader import GmailReader

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def make_mock_service(
    list_responses: list[dict] | None = None,
    get_responses: dict[str, dict] | None = None,
) -> MagicMock:
    """Build a mock Gmail API service that returns fixture data."""
    list_responses = list_responses or [_load_fixture("gmail_list_response.json")]
    get_responses = get_responses or {
        "msg-001": _load_fixture("gmail_message_full.json"),
        "msg-002": _load_fixture("gmail_message_full.json"),  # reuse shape
        "msg-003": _load_fixture("gmail_message_full.json"),
    }

    def list_call(**kwargs):
        resp = list_responses.pop(0) if list_responses else {"messages": [], "nextPageToken": None}
        mock = MagicMock()
        mock.execute.return_value = resp
        return mock

    def get_call(userId: str, id: str, format: str = "full"):
        mock = MagicMock()
        payload = get_responses.get(id)
        if payload is None:
            payload = {"id": id, "threadId": "thread-1", "labelIds": [], "payload": {}}
        else:
            payload = dict(payload)
            payload["id"] = id
        mock.execute.return_value = payload
        return mock

    service = MagicMock()
    service.users.return_value.messages.return_value.list.side_effect = list_call
    service.users.return_value.messages.return_value.get.side_effect = get_call
    return service


class TestGmailReaderListIds(unittest.TestCase):
    """Test list_message_ids and get_new_message_ids."""

    def test_list_message_ids_returns_ids_and_next_token(self) -> None:
        service = make_mock_service()
        reader = GmailReader(service)
        ids, next_token = reader.list_message_ids("Label_123")
        self.assertEqual(ids, ["msg-001", "msg-002", "msg-003"])
        self.assertIsNone(next_token)

    def test_list_message_ids_pagination(self) -> None:
        service = make_mock_service(
            list_responses=[
                _load_fixture("gmail_list_response_paged.json"),
                _load_fixture("gmail_list_response_page2.json"),
            ]
        )
        reader = GmailReader(service)
        all_ids = reader.list_all_message_ids("Label_123")
        self.assertEqual(all_ids, ["msg-001", "msg-002", "msg-003"])

    def test_get_new_message_ids_filters_seen(self) -> None:
        service = make_mock_service()
        reader = GmailReader(service)
        seen = {"msg-001", "msg-003"}
        new_ids = reader.get_new_message_ids("Label_123", seen_ids=seen)
        self.assertEqual(new_ids, ["msg-002"])

    def test_get_new_message_ids_no_seen_returns_all(self) -> None:
        service = make_mock_service()
        reader = GmailReader(service)
        new_ids = reader.get_new_message_ids("Label_123", seen_ids=None)
        self.assertEqual(new_ids, ["msg-001", "msg-002", "msg-003"])

    def test_get_new_message_ids_empty_seen_returns_all(self) -> None:
        service = make_mock_service()
        reader = GmailReader(service)
        new_ids = reader.get_new_message_ids("Label_123", seen_ids=set())
        self.assertEqual(new_ids, ["msg-001", "msg-002", "msg-003"])


class TestGmailReaderFetch(unittest.TestCase):
    """Test fetch_messages and get_message."""

    def test_fetch_messages_deterministic_order(self) -> None:
        service = make_mock_service()
        reader = GmailReader(service)
        messages = reader.fetch_messages(["msg-001", "msg-002"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["id"], "msg-001")
        self.assertEqual(messages[1]["id"], "msg-002")

    def test_get_message_returns_full_payload(self) -> None:
        service = make_mock_service()
        reader = GmailReader(service)
        msg = reader.get_message("msg-001")
        self.assertEqual(msg["id"], "msg-001")
        self.assertIn("payload", msg)
        self.assertIn("headers", msg["payload"])


if __name__ == "__main__":
    unittest.main()
