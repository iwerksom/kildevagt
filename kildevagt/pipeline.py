"""One run: list items, fetch, parse, archive, detect changes. Errors are collected, never hidden."""
import logging
from collections import Counter
from datetime import date

from .adapters import Adapter
from .archive import Archive, sha256
from .extract import pdf_text
from .fetch import BudgetExceeded
from .health import document_problems
from .models import RawResponse

log = logging.getLogger("kildevagt")


def run_source(adapter: Adapter, archive: Archive, run_id: int, since: date,
               force: bool = False, cache_hours: float = 12) -> tuple[int, Counter, list[str], int, list[str]]:
    """Returns (items found, counts of new/changed/unchanged/cached, error messages,
    pages checked, problems found in them)."""
    counts: Counter = Counter()
    errors: list[str] = []
    items = adapter.list_items(since)
    for raw in adapter.list_pages:
        archive.store(run_id, adapter.source_id, raw, kind="listing")
    log.info("%s: %d items on the listing", adapter.source_id, len(items))

    for item in items:
        # "Cache everything": do not re-fetch a page we already fetched a few hours ago.
        if not force and archive.fetched_recently(adapter.source_id, item.url, cache_hours):
            counts["cached"] += 1
            continue
        try:
            raw = adapter.fetch(item)
            doc = adapter.parse(raw)
            content_hash = sha256(f"{doc.title}\n{doc.body}\n{doc.attachments}".encode())
            unreadable = bool(document_problems(doc, previously_had_items=archive.best_item_count(
                adapter.source_id, item.url)))
            if unreadable:  # a broken selector must not look like the page changing
                content_hash = "bad:" + sha256(raw.content)
            change = archive.store(run_id, adapter.source_id, raw, "meeting", content_hash,
                                   doc.title, doc.date, len(doc.agenda_items))
            counts[change] += 1
            log.info("%s: %s [%s] %d agenda items", adapter.source_id, item.title[:40], change,
                     len(doc.agenda_items))
            for url in ([] if unreadable else doc.attachments):
                _archive_pdf(adapter, archive, run_id, url, doc.title, doc.date, change, errors)
        except BudgetExceeded:
            raise
        except Exception as error:  # one bad page must not stop the run, but it must be reported
            errors.append(f"{item.url}: {error}")
            log.warning("%s: FAILED %s: %s", adapter.source_id, item.url, error)
    checked, problems = check_archived_pages(adapter, archive, items)
    return len(items), counts, errors, checked, problems


def _archive_pdf(adapter, archive, run_id, url, title, doc_date, meeting_change, errors):
    if meeting_change == "unchanged" and archive.last_hash(adapter.source_id, url):
        return
    raw = adapter.fetcher.get(url)
    text, pages = pdf_text(raw.content)
    archive.store(run_id, adapter.source_id, raw, "pdf", title=title, doc_date=doc_date)
    if not text:
        errors.append(f"{url}: PDF has {pages} pages but no text layer (would need OCR)")
    log.info("%s: PDF %d pages, %d characters", adapter.source_id, pages, len(text))


def check_archived_pages(adapter, archive, items) -> tuple[int, list[str]]:
    """Parse the newest archived copy of every listed meeting and look for missing fields.

    This works offline and also covers pages served from the cache, so a broken selector shows up
    straight away instead of the next time a page happens to change.
    """
    checked, problems = 0, []
    for item in items:
        row = archive.latest_fetch(adapter.source_id, item.url)
        if row is None:
            continue
        checked += 1
        raw = RawResponse(row["url"], (archive.root / row["path"]).read_bytes(), "text/html", 200,
                          row["fetched_at"])
        try:
            found = document_problems(adapter.parse(raw),
                                      previously_had_items=archive.best_item_count(adapter.source_id, item.url))
        except Exception as error:
            found = [f"could not parse ({error})"]
        problems += [f"{item.url}: {p}" for p in found]
    return checked, problems
