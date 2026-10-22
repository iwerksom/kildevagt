"""FirstAgenda adapter: honest about what it cannot do.

The FirstAgenda front page is allowed by robots.txt, but it contains no meetings. They are loaded
from /api, which robots.txt disallows. So this adapter fetches the allowed shell, confirms the list
is empty, and raises SourceBlocked, making the source show up red. It never touches /api.
Once Horsens or FirstAgenda gives written permission, list_items/parse are what to write here.
"""
from datetime import date

from bs4 import BeautifulSoup

from kildevagt.adapters import Adapter, SourceBlocked
from kildevagt.models import Document, Item, RawResponse


class FirstAgendaAdapter(Adapter):
    def __init__(self, config, fetcher):
        super().__init__(fetcher)
        self.source_id = config["id"]
        self.name = config["name"]
        self.base = config["base_url"].rstrip("/")

    def list_items(self, since: date) -> list[Item]:
        raw = self.fetcher.get(self.base + "/")
        self.list_pages.append(raw)
        soup = BeautifulSoup(raw.content, "lxml")
        placeholder = soup.select_one("#resultaterplaceholder")
        if placeholder is None:
            raise RuntimeError("FirstAgenda page layout changed: no #resultaterplaceholder")
        if placeholder.find(True) is None:  # empty: the list is filled in by JavaScript
            raise SourceBlocked(
                f"{self.base} loads its meetings from /api, which robots.txt disallows. "
                "Needs permission from the municipality or FirstAgenda.")
        raise NotImplementedError("Meetings were found in the HTML; write a parser for them")

    def parse(self, raw: RawResponse) -> Document:
        raise NotImplementedError("No FirstAgenda parser until access is agreed")
