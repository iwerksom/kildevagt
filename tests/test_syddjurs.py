"""Offline tests for the Syddjurs adapter (three-step listing, then a meeting fragment)."""
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from kildevagt.models import RawResponse
from sources.syddjurs import SyddjursAdapter

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = yaml.safe_load((Path(__file__).parent.parent / "sources" / "syddjurs.yaml").read_text())


def raw(url, name):
    return RawResponse(url, (FIXTURES / name).read_bytes(), "text/html", 200, datetime.now(timezone.utc))


class FakeFetcher:
    """Answers each of the adapter's three endpoints from saved files."""
    def get(self, url):
        if "/events" in url:
            return raw(url, "syddjurs_events.json")
        if "dayview" in url:
            return raw(url, "syddjurs_dayview.html")
        return raw(url, "syddjurs_dayview.html")  # front page: content is not used


def test_listing_follows_calendar_to_meeting_ids():
    items = SyddjursAdapter(CONFIG, FakeFetcher()).list_items(since=date(2026, 7, 24))
    assert items and all(i.url.endswith("/view") for i in items)
    assert {i.date for i in items} >= {date(2026, 10, 28)}


def test_meeting_is_parsed():
    adapter = SyddjursAdapter(CONFIG, FakeFetcher())
    doc = adapter.parse(raw("https://aabendagsorden.syddjurs.dk/fragments/meeting/3033/view",
                            "syddjurs_meeting.html"))
    assert doc.date == date(2026, 10, 7)
    assert len(doc.agenda_items) == 2
    assert doc.agenda_items[0].number == "202" and "Budget 2027" in doc.agenda_items[0].title
    assert len(doc.members) == 27 and "Michael Harregaard Stegger (A)" in doc.members
    assert doc.attachments == ["https://aabendagsorden.syddjurs.dk/meeting/files/Files_7051_10565540/10565540.pdf"]
