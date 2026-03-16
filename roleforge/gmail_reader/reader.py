"""
Gmail reader: fetch message IDs from an intake label and hydrate messages.

Uses Gmail API messages.list (label-scoped) and messages.get (full format).
Idempotency: caller passes already-seen IDs; only new IDs are returned/hydrated.
See docs/specs/gmail-intake-spec.md.
"""

from __future__ import annotations

from typing import Any


# Type for Gmail API service (googleapiclient.discovery.Resource)
# Caller builds with build("gmail", "v1", credentials=...)
class GmailReader:
    """Read Gmail messages by intake label; filter by already-seen IDs."""

    def __init__(self, service: Any) -> None:
        """Initialize with a Gmail API service object (from googleapiclient.discovery.build)."""
        self._service = service

    def list_message_ids(
        self,
        label_id: str,
        *,
        max_results: int = 500,
        page_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """
        List all message IDs for a label (one page).

        Returns (message_ids, next_page_token). next_page_token is None when no more pages.
        """
        request: dict[str, Any] = {
            "userId": "me",
            "labelIds": [label_id],
            "maxResults": min(max_results, 500),
        }
        if page_token:
            request["pageToken"] = page_token
        response = self._service.users().messages().list(**request).execute()
        messages = response.get("messages") or []
        ids = [m["id"] for m in messages]
        return ids, response.get("nextPageToken")

    def list_all_message_ids(
        self,
        label_id: str,
        *,
        max_per_page: int = 500,
    ) -> list[str]:
        """List all message IDs for the label, following pagination."""
        all_ids: list[str] = []
        page_token: str | None = None
        while True:
            ids, page_token = self.list_message_ids(
                label_id,
                max_results=max_per_page,
                page_token=page_token,
            )
            all_ids.extend(ids)
            if not page_token:
                break
        return all_ids

    def get_new_message_ids(
        self,
        label_id: str,
        seen_ids: set[str] | None = None,
        *,
        max_per_page: int = 500,
    ) -> list[str]:
        """
        Return message IDs from the intake label that are not in seen_ids.

        If seen_ids is None, returns all IDs (no filtering).
        Order: same as API (newest first by default).
        """
        all_ids = self.list_all_message_ids(label_id, max_per_page=max_per_page)
        if seen_ids is None:
            return all_ids
        return [mid for mid in all_ids if mid not in seen_ids]

    def get_message(self, message_id: str, format: str = "full") -> dict[str, Any]:
        """Fetch a single message by ID (full format: headers + body)."""
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format=format)
            .execute()
        )

    def fetch_messages(
        self,
        message_ids: list[str],
        *,
        format: str = "full",
    ) -> list[dict[str, Any]]:
        """
        Fetch full message payloads for the given IDs.

        Deterministic: same ID order yields same result order. No retry logic here
        (caller handles retries); each get is independent.
        """
        out: list[dict[str, Any]] = []
        for mid in message_ids:
            msg = self.get_message(mid, format=format)
            out.append(msg)
        return out

    def resolve_label_id(self, label_name: str) -> str | None:
        """Resolve label name to ID via users.labels.list. Returns None if not found."""
        response = self._service.users().labels().list(userId="me").execute()
        for label in response.get("labels") or []:
            if label.get("name") == label_name:
                return label["id"]
        return None
