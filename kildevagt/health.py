"""Health: does this run look like the usual run? The point is to fail loudly, never to return 0 quietly.

A source is
  RED      broken: listing failed, zero items, far fewer items than usual, or most pages unreadable
  YELLOW   suspicious: somewhat fewer items than usual, or some pages with missing fields
  BLOCKED  the owner does not allow robots, known and deliberate (not a failure of ours)
  GREEN    items found in a plausible number, and every checked page has its required fields
"""
import statistics
from dataclasses import dataclass, field
from datetime import date

RED, YELLOW, GREEN, BLOCKED = "RED", "YELLOW", "GREEN", "BLOCKED"


@dataclass
class Health:
    status: str
    reasons: list[str] = field(default_factory=list)


def document_problems(doc, today: date | None = None, previously_had_items: int = 0) -> list[str]:
    """Required fields for a meeting page. A past meeting must have agenda items, and a page that
    once had agenda items must not suddenly have none (a future meeting may be empty until published)."""
    today = today or date.today()
    problems = []
    if not doc.title:
        problems.append("empty title")
    if doc.date is None:
        problems.append("no date")
    elif doc.date < today and not doc.agenda_items:
        problems.append("meeting is in the past but has no agenda items")
    if previously_had_items and not doc.agenda_items:
        problems.append(f"agenda items dropped from {previously_had_items} to 0")
    return problems


def baseline(previous_counts: list[int]) -> float | None:
    """What a normal run finds: the median of the last few healthy runs."""
    return statistics.median(previous_counts) if previous_counts else None


def evaluate(items_found: int, usual: float | None, docs_checked: int, docs_bad: int,
             error: str | None = None) -> Health:
    if error:
        status = BLOCKED if error.startswith("SourceBlocked") else RED
        return Health(status, [error])
    reasons, status = [], GREEN
    if items_found == 0:
        return Health(RED, ["found 0 items" + (f" (usually about {usual:.0f})" if usual else "")])
    if usual:
        ratio = items_found / usual
        if ratio < 0.5:
            status = RED
            reasons.append(f"found {items_found} items, usually about {usual:.0f}")
        elif ratio < 0.8:
            status = YELLOW
            reasons.append(f"found {items_found} items, usually about {usual:.0f}")
    if docs_checked and docs_bad:
        share = docs_bad / docs_checked
        reasons.append(f"{docs_bad} of {docs_checked} pages are missing required fields")
        if share >= 0.5:
            status = RED
        elif status == GREEN:
            status = YELLOW
    return Health(status, reasons)
