"""FirstAgenda is reported as blocked, and the fetcher refuses /api."""
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml

from kildevagt.adapters import SourceBlocked
from kildevagt.fetch import Fetcher, RobotsDisallowed
from kildevagt.models import RawResponse
from sources.firstagenda import FirstAgendaAdapter

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG = yaml.safe_load((Path(__file__).parent.parent / "sources" / "horsens_firstagenda.yaml").read_text())
ROBOTS = b"user-agent: *\ndisallow: /api\nallow: /\n"  # as served by dagsordener.horsens.dk


class ShellFetcher:
    def get(self, url):
        return RawResponse(url, (FIXTURES / "horsens_firstagenda_shell.html").read_bytes(),
                           "text/html", 200, datetime.now(timezone.utc))


def test_empty_shell_is_reported_as_blocked_not_as_zero_items():
    with pytest.raises(SourceBlocked, match="robots.txt"):
        FirstAgendaAdapter(CONFIG, ShellFetcher()).list_items(date(2026, 7, 1))


def test_api_path_is_refused_by_the_fetcher():
    fetcher = Fetcher()
    fetcher._request = lambda url, allow_error=False: RawResponse(
        url, ROBOTS, "text/plain", 200, datetime.now(timezone.utc))
    with pytest.raises(RobotsDisallowed):
        fetcher.get("https://dagsordener.horsens.dk/api/anything")
    assert fetcher._allowed("https://dagsordener.horsens.dk/")
