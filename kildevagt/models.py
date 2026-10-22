"""Plain data classes passed between adapter and core."""
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Item:
    """Something an adapter found on a listing page (a meeting, a document)."""
    url: str
    title: str
    date: date | None
    kind: str = "meeting"


@dataclass
class RawResponse:
    """Bytes exactly as the server sent them, plus where and when."""
    url: str
    content: bytes
    content_type: str
    status: int
    fetched_at: datetime


@dataclass
class AgendaItem:
    number: str
    title: str
    text: str


@dataclass
class Document:
    """The normalised form every source is turned into."""
    source_id: str
    url: str
    title: str
    date: date | None
    body: str
    attachments: list[str] = field(default_factory=list)
    agenda_items: list[AgendaItem] = field(default_factory=list)
    members: list[str] = field(default_factory=list)  # who the meeting body consists of
    absent_note: str = ""  # raw text about absentees; "Ingen fraværende" means all members attended
