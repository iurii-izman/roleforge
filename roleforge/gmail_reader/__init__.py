"""Gmail API reader: list message IDs by intake label, hydrate new messages only."""

from roleforge.gmail_reader.reader import GmailReader
from roleforge.gmail_reader.store import message_to_row, persist_messages

__all__ = ["GmailReader", "message_to_row", "persist_messages"]
