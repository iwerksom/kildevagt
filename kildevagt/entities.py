"""Find companies, places and elected officials in text.

Privacy rules (see README/NOTES): only companies, places and *elected officials* become graph
nodes. Any other person spaCy finds is counted, never stored, and removed from snippets.
Public bodies (kommuner, udvalg, styrelser) are not companies and are skipped.
"""
import re
from dataclasses import dataclass

from .extract import normalise_space

from .orgclass import _FORM, LEGAL_FORM_AT_END, LEGAL_FORMS, PUBLIC_BODY, classify

COMPANY_WITH_FORM = re.compile(
    rf"((?:[A-ZÆØÅ][^\s,;:()\"]*\s+){{0,5}}[A-ZÆØÅ][^\s,;:()\"]*)\s+({_FORM})(?![\wæøå])")
FILE_NAME = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)\b", re.IGNORECASE)
CONFIDENCE = {"legal form": 0.95, "known business": 0.9, "known organisation": 0.9,
              "business word": 0.7}   # anything else with a kind: 0.7 (a word like 'forening'); Unclassified: 0.3


@dataclass
class Mention:
    kind: str            # Company | Organisation | Unclassified | Place | Person
    name: str            # as written (display)
    key: str             # normalised, used to merge
    method: str          # how it was found
    confidence: float
    snippet: str
    legal_form: str | None = None
    party: str | None = None


def normalise_company(name: str) -> tuple[str, str | None]:
    """'aarhus vand a/s ' -> ('aarhus vand', 'A/S'). Case, spacing, dots and legal form removed."""
    name = normalise_space(name).strip(" ,.;:")
    form = None
    match = LEGAL_FORM_AT_END.search(name)
    if match:
        form = LEGAL_FORMS.get(match.group(1).lower())
        name = name[:match.start()]
    key = re.sub(r"[^\w\s&æøå]", "", name.casefold())
    return normalise_space(key), form


def member_name(member: str) -> tuple[str, str | None]:
    """'Mette Foged (Å)' -> ('Mette Foged', 'Å')"""
    match = re.match(r"(.*?)\s*\(([^)]+)\)\s*$", member)
    return (match.group(1), match.group(2)) if match else (member, None)


def _snippet(text: str, start: int, end: int, person_spans: list[tuple[int, int]]) -> str:
    lo, hi = max(0, start - 110), min(len(text), end + 110)
    out, pos = [], lo
    for s, e in sorted(person_spans):          # redact private persons inside the window
        if e <= lo or s >= hi:
            continue
        out += [text[pos:max(pos, s)], "[navn fjernet]"]
        pos = min(hi, e)
    out.append(text[pos:hi])
    return ("…" if lo else "") + normalise_space("".join(out)) + ("…" if hi < len(text) else "")


def extract(nlp, text: str, members: dict[str, str]) -> tuple[list[Mention], dict]:
    """members maps lower-case full name -> 'Name (Party)'. Returns (mentions, stats)."""
    doc = nlp(text)
    stats = {"private_persons_dropped": 0, "public_bodies_skipped": 0, "noise_skipped": 0}
    elected_spans, person_spans = [], []
    for name_lower, member in members.items():
        for m in re.finditer(re.escape(name_lower), text.casefold()):
            elected_spans.append((m.start(), m.end(), member))
    for ent in doc.ents:
        if ent.label_ == "PER":
            if not any(s <= ent.start_char < e or s < ent.end_char <= e for s, e, _ in elected_spans):
                person_spans.append((ent.start_char, ent.end_char))
                stats["private_persons_dropped"] += 1

    mentions: list[Mention] = []
    for start, end, member in elected_spans:
        name, party = member_name(member)
        mentions.append(Mention("Person", name, name.casefold(), "member_list", 1.0,
                                _snippet(text, start, end, person_spans), party=party))

    candidates: dict[tuple[int, int], tuple[str, str]] = {}   # span -> (text, method)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            candidates[(ent.start_char, ent.end_char)] = (ent.text, "spacy_org")
    for m in COMPANY_WITH_FORM.finditer(text):
        span = (m.start(), m.end())
        overlapping = [s for s in candidates if s[0] < span[1] and span[0] < s[1]]
        if overlapping:                                    # spaCy saw it too: keep its boundaries
            for s in overlapping:
                candidates[s] = (candidates[s][0], "spacy_org")
        else:
            candidates[span] = (m.group(0), "legal_form_regex")

    for (start, end), (surface, method) in sorted(candidates.items()):
        if FILE_NAME.search(surface):
            stats["noise_skipped"] += 1
            continue
        result = classify(surface)
        if result.label == "Skip":
            stats["public_bodies_skipped" if "public" in result.reason or "committee" in result.reason
                  or "party" in result.reason else "noise_skipped"] += 1
            continue
        confidence = 0.3 if result.label == "Unclassified" else CONFIDENCE.get(result.reason, 0.7)
        if result.legal_form and method == "spacy_org":
            confidence = 0.95
        elif result.legal_form:
            confidence = 0.9
        mentions.append(Mention(result.label, result.name, result.key, f"{method}: {result.reason}",
                                confidence, _snippet(text, start, end, person_spans), result.legal_form))

    for ent in doc.ents:
        if ent.label_ == "LOC" and len(ent.text) >= 3 and not PUBLIC_BODY.search(ent.text):
            mentions.append(Mention("Place", normalise_space(ent.text), normalise_space(ent.text).casefold(),
                                    "spacy_loc", 0.5,
                                    _snippet(text, ent.start_char, ent.end_char, person_spans)))
    return mentions, stats
