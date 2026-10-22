"""Offline tests: saved Hedensted pages, no network."""
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from kildevagt.adapters import ConfigAdapter, parse_danish_date
from kildevagt.archive import classify_change
from kildevagt.fetch import Fetcher, RobotsDisallowed
from kildevagt.models import RawResponse
import yaml

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = yaml.safe_load((Path(__file__).parent.parent / "sources" / "hedensted.yaml").read_text())
LIST_URL = CONFIG["list_pages"][0]


def raw(name, url):
    return RawResponse(url, (FIXTURES / name).read_bytes(), "text/html", 200,
                       datetime.now(timezone.utc))


class FakeFetcher:
    def get(self, url):
        return raw("hedensted_list.html", url)


def test_danish_dates():
    assert parse_danish_date("8. oktober 2026 16:00") == date(2026, 10, 8)
    assert parse_danish_date("Spørgsmål til spørgetiden") is None


def test_listing_finds_expected_meetings():
    adapter = ConfigAdapter(CONFIG, FakeFetcher())
    items = adapter.list_items(since=date(2026, 7, 1))
    assert [i.date for i in items] == [date(2026, 10, 28), date(2026, 10, 8), date(2026, 9, 30),
                                        date(2026, 9, 17), date(2026, 8, 26)]
    assert all("agenda=" in i.url for i in items)


def test_listing_respects_since():
    items = ConfigAdapter(CONFIG, FakeFetcher()).list_items(since=date(2026, 10, 1))
    assert len(items) == 2


def test_listing_that_returns_nothing_is_visible_to_caller():
    """If a selector breaks, the item count drops to 0; health checks (milestone 5) key off this."""
    broken = {**CONFIG, "item_link": "a.does-not-exist"}
    assert ConfigAdapter(broken, FakeFetcher()).list_items(date(2026, 1, 1)) == []


def test_meeting_is_parsed():
    adapter = ConfigAdapter(CONFIG, FakeFetcher())
    doc = adapter.parse(raw("hedensted_meeting.html", "https://www.hedensted.dk/x"))
    assert doc.date == date(2026, 10, 8)
    assert len(doc.agenda_items) == 3
    assert all(i.title and i.text for i in doc.agenda_items)
    assert doc.attachments and doc.attachments[0].endswith("Dagsorden.pdf")
    assert "Kommunalbestyrelsen" in doc.body


def test_change_classification():
    assert classify_change(None, "a") == "new"
    assert classify_change("a", "a") == "unchanged"
    assert classify_change("a", "b") == "changed"


def test_robots_disallow_is_enforced():
    fetcher = Fetcher()
    robots = RawResponse("https://x.test/robots.txt", b"User-agent: *\nDisallow: /api\n",
                         "text/plain", 200, datetime.now(timezone.utc))
    fetcher._request = lambda url, allow_error=False: robots
    with pytest.raises(RobotsDisallowed):
        fetcher.get("https://x.test/api/meetings")
