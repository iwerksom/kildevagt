"""Syddjurs adapter. The site has no meeting list in its HTML; it asks three small endpoints:

1. rest/meeting/calendar/<committee>/events   -> JSON: which dates have meetings
2. fragments/meeting/calendar/<c>/dayview     -> HTML: meeting ids on one date
3. fragments/meeting/<id>/view                -> HTML: the meeting itself (this is what we parse)
"""
import json
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from kildevagt.adapters import Adapter, parse_danish_date
from kildevagt.extract import normalise_space
from kildevagt.models import AgendaItem, Document, Item, RawResponse


class SyddjursAdapter(Adapter):
    def __init__(self, config, fetcher):
        super().__init__(fetcher)
        self.config = config
        self.source_id = config["id"]
        self.name = config["name"]
        self.base = config["base_url"].rstrip("/")

    def _get_listing(self, path: str) -> RawResponse:
        raw = self.fetcher.get(f"{self.base}/{path}")
        self.list_pages.append(raw)
        return raw

    def list_items(self, since: date) -> list[Item]:
        committee = self.config["committee_id"]
        until = date.today() + timedelta(days=self.config["look_ahead_days"])
        self._get_listing("")  # the front page hands out the session cookie the endpoints expect
        events = json.loads(self._get_listing(
            f"rest/meeting/calendar/{committee}/events?start={since}&end={until}").content)
        items = []
        for day in sorted(e["dateAsString"] for e in events):
            raw = self._get_listing(
                f"fragments/meeting/calendar/{committee}/dayview?from={day}&to={day}")
            for meeting_id in re.findall(r"meetingView\((\d+)\)", raw.content.decode("utf-8")):
                items.append(Item(f"{self.base}/fragments/meeting/{meeting_id}/view",
                                  f"{self.name} {day}", date.fromisoformat(day)))
        return items

    def parse(self, raw: RawResponse) -> Document:
        soup = BeautifulSoup(raw.content, "lxml")
        title = normalise_space(soup.select_one("#meetingHeading").get_text(" "))
        facts = {normalise_space(label.get_text()): normalise_space(label.find_next(class_="field-value").get_text())
                 for label in soup.select(".field-label") if label.find_next(class_="field-value")}
        members_box = next((b.find_next(class_="content") for b in soup.select("button.collapsible")
                            if b.get_text(strip=True).startswith("Medlemmer")), None)
        members = [normalise_space(s.get_text()) for s in members_box.select("span.col-lg-6")] if members_box else []
        absent = soup.find(string=re.compile("fraværende", re.I))
        agenda_items = []
        for button in soup.select("button.agenda-item-btn"):
            heading = normalise_space(button.get_text(" "))
            number = (re.match(r"Punkt (\S+)", heading) or [None, ""])[1]
            content = button.find_parent("tr").find_next_sibling("tr", class_="content")
            agenda_items.append(AgendaItem(number, re.sub(r"^Punkt \S+ ", "", heading),
                                           normalise_space(content.get_text(" ")) if content else ""))
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(raw.url))
        attachments = sorted({f"{origin}/meeting/files/{b['data-id']}/{b['data-name']}"
                              for b in soup.select("button[data-id][data-name]")})
        header = (f"{title}. {facts.get('Dato', '')}. Status: {facts.get('Status', '')}. "
                  f"{normalise_space(absent) if absent else ''}")
        body = "\n\n".join([header] + [f"{i.number}. {i.title}\n{i.text}" for i in agenda_items])
        return Document(self.source_id, raw.url, title, parse_danish_date(facts.get("Dato", "")),
                        body, attachments, agenda_items, members,
                        normalise_space(absent) if absent else "")
