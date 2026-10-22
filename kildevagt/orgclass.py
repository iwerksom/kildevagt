"""Decide what a name spaCy called ORG really is. Positive evidence is required.

spaCy's ORG label means "looks like a name". In council agendas that includes departments,
committees, laws, projects and capitalised common nouns ("Borgerforslag"). So a name only becomes
a node of a kind when there is *evidence* for that kind, and the reason is stored with it:

  Company        a legal form (A/S, ApS ...), a known business, or a business word (Advokater, Holding ...)
  Organisation   not a business: association, foundation, waterworks, museum, public-owned company ...
  Unclassified   spaCy said ORG, nothing says what it is. Kept, hidden by default, never counted as a company.
  (skipped)      public bodies, committees, parties, lower-case fragments, numbers. Counted, not stored.

The two lists below are curated by hand and deliberately small. They are the stand-in for a CVR lookup.
"""
import re
from dataclasses import dataclass

LEGAL_FORMS = {
    "a/s": "A/S", "aps": "ApS", "i/s": "I/S", "k/s": "K/S", "p/s": "P/S", "ivs": "IVS",
    "amba": "A.m.b.a.", "a.m.b.a.": "A.m.b.a.", "a.m.b.a": "A.m.b.a.",
    "fmba": "F.m.b.a.", "f.m.b.a.": "F.m.b.a.", "f.m.b.a": "F.m.b.a.",
}
_FORM = r"(?:A/S|ApS|I/S|K/S|P/S|IVS|A\.m\.b\.a\.?|amba|F\.m\.b\.a\.?|fmba)"
LEGAL_FORM_AT_END = re.compile(rf"\s+({_FORM})\s*$", re.IGNORECASE)

# Known names (lower case). Extend these when a name is wrong, or replace with CVR data.
KNOWN_BUSINESSES = {
    "biltema", "bdo", "netto", "rema", "rema 1000", "aldi", "lidl", "føtex", "bilka", "fakta", "meny", "spar",
    "brugsforeningen", "nykredit", "seb", "nordea", "danske bank", "jyske bank", "codex", "cip",
    "copenhagen infrastructure partners", "e-boks", "first agenda", "firstagenda",
}
KNOWN_ORGANISATIONS = {  # public-owned companies, NGOs, associations
    "energinet", "banedanmark", "midttrafik", "visit aarhus", "concito", "dbu", "dgi", "kl", "danske regioner",
}

PARTIES = {
    "venstre", "socialdemokratiet", "dansk folkeparti", "liberal alliance", "enhedslisten", "sf",
    "socialistisk folkeparti", "konservative", "det konservative folkeparti", "radikale venstre",
    "alternativet", "nye borgerlige", "danmarksdemokraterne", "moderaterne", "borgernes parti",
    "frie grønne", "kristendemokraterne",
}
COMMITTEES = {"fbl", "kfl", "ntm", "ep", "øk", "sb", "sæ", "uøe", "puk", "eb", "kbu", "sou"}

PUBLIC_BODY = re.compile(
    r"kommune|region|byråd|kommunalbestyrelse|udvalg|forvaltning|styrelse|ministeri|ministeren|politi|"
    r"folketing|regering|landsforening|statens|danmarks statistik|domstol|beredskab|brandvæsen|"
    r"^center for|^sekretariatet|^borgerråd|^borgerteam|^socialcentret|^specialrådgivning|^forsvaret|"
    r"^skats?$|^råd$|rådet$|rådets$|nævn|direktorat|tilsyn|administration|afdeling|^kls?$",
    re.IGNORECASE)
DEPARTMENT = re.compile(r"^[A-ZÆØÅ][\wæøå-]+ & [A-ZÆØÅ][\wæøå-]+s?$")   # "Natur & Miljø", "Børn & Unge"

# Words that sit next to a name in the page layout and are not part of it ("Sagsfremstilling Visit Aarhus").
SECTION_WORDS = {"dagsorden", "sagsfremstilling", "beslutning", "indstilling", "resumé", "lovgrundlag", "bekendtgørelse",
                 "samarbejdsaftale", "bilag", "beslutningstema", "baggrund"}

# Non-business cues: the LAST word of a multi-word name, in any common form (-en, -et, -s, -ets ...)
ORG_CUE = re.compile(r"^(forening|fond|fonde|vandværk|vandværker|museum|museer|boligselskab|boligforening|"
                     r"fjernvarme|spildevand|forsyning|andelsselskab|højskole|efterskole|skole|børnehave|"
                     r"klub|kirke|hospital|plejehjem|samfund|fællesråd|kollegium)(en|et|s|ets|ens)?$", re.IGNORECASE)
# One-word compounds: Landsbyggefonden, Handelsstandsforeningen, Klimaskovfonden. Needs a prefix before the cue.
ORG_COMPOUND = re.compile(r"^[\w-]{4,}(fonden|fond|foreningen|forening|boligforeningen|boligselskab|"
                          r"vandværket|vandværk|museet|museum|højskolen|højskole|efterskolen|efterskole|"
                          r"friskolen|friskole|privatskolen|privatskole|komitéen|komité|komiteen)s?$", re.IGNORECASE)
ORG_FIRST_CUE = re.compile(r"^(foreningen|fonden|kollegiet|stiftelsen)$", re.IGNORECASE)
# Business cues, last word
BUSINESS_CUE = re.compile(r"^(lufthavn|advokater|advokatfirma|rådgivere|consulting|group|holding|partners|invest|"
                          r"entreprise|bank|forsikring|transport|maskinfabrik|ejendomme)$", re.IGNORECASE)


@dataclass
class Classification:
    label: str          # Company | Organisation | Unclassified | Skip
    name: str           # cleaned name, genitive and layout words removed
    key: str            # for merging spellings
    reason: str
    legal_form: str | None = None


def clean_name(surface: str) -> str:
    """Remove layout words at either end ("Sagsfremstilling Visit Aarhus"), and 's / ’s."""
    surface = re.sub(r"\s+", " ", surface).strip(" ,.;:")
    surface = re.split(r"(?<=[a-zæøå])\. ", surface)[-1]        # a match that ran over a sentence boundary
    words = surface.split(" ")
    while words and words[0].lower() in SECTION_WORDS:
        words = words[1:]
    while words and words[-1].lower() in SECTION_WORDS:
        words = words[:-1]
    name = " ".join(words)
    return re.sub(r"[’']s$", "", name)


def _stem_cue_word(word: str) -> str:
    """'Vandværker' / 'Vandværks' / 'Foreningen' -> 'vandværk' / 'forening' (for merging spellings)."""
    w = word.lower()
    if w.endswith("værker") or w.endswith("værks"):
        return w[: w.index("værk")] + "værk"
    for suffix in ("ens", "ets", "en", "et", "s"):
        if w.endswith(suffix) and ORG_CUE.match(w):
            candidate = w[: -len(suffix)]
            if ORG_CUE.match(candidate + ""):
                return candidate
    return w


def _key(name: str) -> str:
    words = [w for w in re.sub(r"[^\w\s&æøå-]", "", name.casefold()).split()]
    if words and ORG_COMPOUND.match(words[-1]):                 # ...foreningen / ...foreningens -> ...forening
        for suffix in ("ens", "en", "et", "s"):
            if words[-1].endswith(suffix) and ORG_COMPOUND.match(words[-1][: -len(suffix)]):
                words[-1] = words[-1][: -len(suffix)]
                break
    elif len(words) > 1 and ORG_CUE.match(words[-1]):
        words[-1] = _stem_cue_word(words[-1])
    return " ".join(words)


def _known(name: str, table: set[str]) -> bool:
    low = name.lower()
    return low in table or (low.endswith("s") and low[:-1] in table)


def classify(surface: str) -> Classification:
    name = clean_name(surface)
    low = name.lower()
    words = name.split()

    def skip(reason):
        return Classification("Skip", name, low, reason)

    if len(name) < 3:
        return skip("too short")
    if (match := LEGAL_FORM_AT_END.search(name)):
        form = LEGAL_FORMS.get(match.group(1).lower())
        base = name[: match.start()]
        return Classification("Company", name, _key(base), "legal form", form)
    if not name[0].isupper() and not name[0].isdigit() and not name[0] == "e":      # "klager Udvikling", "miljøscreeninger"
        return skip("starts lower case")
    if name.endswith("-") or re.search(r"\d|§|₂", name):
        return skip("fragment or contains digits")
    if low in PARTIES or any(low.startswith(p) and ("gruppe" in low or low.endswith("s")) for p in PARTIES):
        return skip("political party")
    if low in COMMITTEES or DEPARTMENT.match(name):
        return skip("committee or department")
    if _known(name, KNOWN_BUSINESSES):
        return Classification("Company", name, _key(name.rstrip("s") if low.rstrip("s") in KNOWN_BUSINESSES else name),
                              "known business")
    if _known(name, KNOWN_ORGANISATIONS):
        base = low[:-1] if low not in KNOWN_ORGANISATIONS else low
        return Classification("Organisation", name, base, "known organisation")
    if PUBLIC_BODY.search(low):
        return skip("public body")
    if words and BUSINESS_CUE.match(words[-1]) and len(words) > 1:
        return Classification("Company", name, _key(name), "business word")
    if words and ORG_COMPOUND.match(words[-1]) or \
            (len(words) > 1 and (ORG_CUE.match(words[-1]) or ORG_FIRST_CUE.match(words[0]))):
        return Classification("Organisation", name, _key(name), "non-business word (forening, fond, vandværk ...)")
    return Classification("Unclassified", name, _key(name), "no evidence for any kind")
