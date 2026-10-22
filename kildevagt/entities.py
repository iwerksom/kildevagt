"""Find companies, places and elected officials in text.

Privacy rules (see README/NOTES): only companies, places and *elected officials* become graph
nodes. Any other person spaCy finds is counted, never stored, and removed from snippets.
Public bodies (kommuner, udvalg, styrelser) are not companies and are skipped.
"""
import re
from dataclasses import dataclass

from .extract import normalise_space

LEGAL_FORMS = {  # lower-case spelling -> canonical
    "a/s": "A/S", "aps": "ApS", "i/s": "I/S", "k/s": "K/S", "p/s": "P/S", "ivs": "IVS",
    "amba": "A.m.b.a.", "a.m.b.a.": "A.m.b.a.", "a.m.b.a": "A.m.b.a.",
    "fmba": "F.m.b.a.", "f.m.b.a.": "F.m.b.a.", "f.m.b.a": "F.m.b.a.",
}
_FORM = r"(?:A/S|ApS|I/S|K/S|P/S|IVS|A\.m\.b\.a\.?|amba|F\.m\.b\.a\.?|fmba)"
LEGAL_FORM_AT_END = re.compile(rf"\s+({_FORM})\s*$", re.IGNORECASE)
COMPANY_WITH_FORM = re.compile(
    rf"((?:[A-ZÆØÅ][^\s,;:()\"]*\s+){{0,5}}[A-ZÆØÅ][^\s,;:()\"]*)\s+({_FORM})(?![\wæøå])")
PUBLIC_BODY = re.compile(
    r"kommune|region|byråd|kommunalbestyrelse|udvalg|forvaltning|styrelse|ministeri|politi|"
    r"folketing|regering|landsforening|statens|danmarks statistik|domstol|beredskab|råd$|rådet$|nævn|"
    r"direktorat|tilsyn|administration|afdeling|^kls?$|^kl\b",
    re.IGNORECASE)
PARTIES = {"venstre", "socialdemokratiet", "dansk folkeparti", "liberal alliance", "enhedslisten",
           "sf", "socialistisk folkeparti", "konservative", "det konservative folkeparti",
           "radikale venstre", "alternativet", "nye borgerlige", "danmarksdemokraterne",
           "moderaterne", "borgernes parti", "frie grønne", "kristendemokraterne"}
FILE_NAME = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)\b", re.IGNORECASE)
GENERIC = {"teknik", "natur", "miljø", "social", "kultur", "erhverv", "børn", "sundhed", "ældre", "biler"}


@dataclass
class Mention:
    kind: str            # Company | Place | Person
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
        key, form = normalise_company(surface)
        if len(key) < 3 or re.fullmatch(r"[\d\s]+", key) or surface.rstrip().endswith("-") or key in GENERIC \
                or key in PARTIES or FILE_NAME.search(surface) or re.search(r"\d", key) and form is None:
            stats["noise_skipped"] += 1
            continue
        if PUBLIC_BODY.search(key):
            stats["public_bodies_skipped"] += 1
            continue
        confidence = 0.95 if (form and method == "spacy_org") else 0.9 if form else 0.5
        mentions.append(Mention("Company" if form else "Organisation", normalise_space(surface), key,
                                method if not form or method != "spacy_org" else "spacy_org+legal_form",
                                confidence, _snippet(text, start, end, person_spans), form))

    for ent in doc.ents:
        if ent.label_ == "LOC" and len(ent.text) >= 3 and not PUBLIC_BODY.search(ent.text):
            mentions.append(Mention("Place", normalise_space(ent.text), normalise_space(ent.text).casefold(),
                                    "spacy_loc", 0.5,
                                    _snippet(text, ent.start_char, ent.end_char, person_spans)))
    return mentions, stats
