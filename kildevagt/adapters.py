"""The adapter interface, and the config-driven adapter that covers simple HTML sources.

A new source is either a YAML file in sources/ (selectors only), or a Python class
that subclasses Adapter when the source needs logic. Both expose the same three methods.
"""
import importlib
import logging
import re
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from .extract import normalise_space
from .fetch import Fetcher
from .models import AgendaItem, Document, Item, RawResponse

log = logging.getLogger("kildevagt")

DANISH_MONTHS = {m: i + 1 for i, m in enumerate(
    ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
     "september", "oktober", "november", "december"])}


def parse_danish_date(text: str) -> date | None:
    match = re.search(r"(\d{1,2})\.\s*([a-zæøå]+)\s+(\d{4})", text.lower())
    if not match or match.group(2) not in DANISH_MONTHS:
        return None
    return date(int(match.group(3)), DANISH_MONTHS[match.group(2)], int(match.group(1)))


class SelectorMissing(Exception):
    """A CSS selector from the config matched nothing: the site probably changed its layout."""


class SourceBlocked(Exception):
    """The source can only be read in a way its owner has asked robots not to use."""


class Adapter(ABC):
    source_id: str
    name: str

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher
        self.list_pages: list[RawResponse] = []  # the core archives these too

    @abstractmethod
    def list_items(self, since: date) -> list[Item]: ...

    def fetch(self, item: Item) -> RawResponse:
        return self.fetcher.get(item.url)

    @abstractmethod
    def parse(self, raw: RawResponse) -> Document: ...


class ConfigAdapter(Adapter):
    """An HTML source described entirely by CSS selectors in a YAML file."""

    def __init__(self, config: dict, fetcher: Fetcher):
        super().__init__(fetcher)
        self.config = config
        self.source_id = config["id"]
        self.name = config["name"]

    def list_items(self, since: date) -> list[Item]:
        items = []
        for page_url in self.config["list_pages"]:
            raw = self.fetcher.get(page_url)
            self.list_pages.append(raw)
            soup = BeautifulSoup(raw.content, "lxml")
            links = soup.select(self.config["item_link"])
            if not links:
                log.warning("%s: selector %r matched no links on %s", self.source_id,
                            self.config["item_link"], page_url)
            for link in links:
                text = normalise_space(link.get_text(" "))
                when = parse_danish_date(text)
                if when is None:
                    # Not a meeting (e.g. a link to a sub-page); say so instead of dropping silently.
                    log.info("%s: skipping link without a date: %s", self.source_id, text[:60])
                    continue
                if when < since:
                    continue
                items.append(Item(urljoin(raw.url, link["href"]), text, when))
        return items

    def _required(self, scope, selector: str, what: str):
        element = scope.select_one(selector)
        if element is None:
            raise SelectorMissing(f"selector {selector!r} for {what} matched nothing")
        return element

    def parse(self, raw: RawResponse) -> Document:
        cfg = self.config["meeting"]
        soup = BeautifulSoup(raw.content, "lxml")
        title = normalise_space(self._required(soup, cfg["title"], "title").get_text(" "))
        facts = normalise_space(self._required(soup, cfg["facts"], "facts").get_text(" ")) if cfg.get("facts") else ""
        agenda_items = []
        for block in soup.select(cfg["agenda_item"]):
            heading = normalise_space(self._required(block, cfg["agenda_item_title"], "agenda item title").get_text(" "))
            number, _, name = heading.partition(". ")
            body = normalise_space(self._required(block, cfg["agenda_item_body"], "agenda item body").get_text(" "))
            agenda_items.append(AgendaItem(number, name, body))
        attachments = [urljoin(raw.url, a["href"]) for a in soup.select(cfg["attachment"])]
        body = "\n\n".join([facts] + [f"{i.number}. {i.title}\n{i.text}" for i in agenda_items])
        return Document(self.source_id, raw.url, title, parse_danish_date(facts), body,
                        attachments, agenda_items)


def load_adapter(path: Path, fetcher: Fetcher) -> Adapter:
    """YAML only -> ConfigAdapter. YAML with `python_adapter: package.module.Class` -> that class."""
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if "python_adapter" in config:
        module_name, _, class_name = config["python_adapter"].rpartition(".")
        adapter_class = getattr(importlib.import_module(module_name), class_name)
        return adapter_class(config, fetcher)
    return ConfigAdapter(config, fetcher)
