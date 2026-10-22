"""Measure the organisation classifier against names labelled by hand.

Two labelled sets, both made by reading names from the real graph:
  org_gold.csv        the first audit; the rules were written while looking at it (optimistic)
  org_gold_fresh.csv  names from meetings fetched afterwards. Rules were first measured on it, THEN
                      generalisable fixes were made, so it is also no longer fully untouched.
name_cleaning.csv holds strings that are an organisation plus a technical municipal word
('Glud Museum Samarbejdsaftale') with the name they must be cleaned to; they are not in the labelled sets.
expected = Company (a business), Organisation (not a business) or Other (anything else, including
'cannot tell'). What matters is PRECISION: a wrong 'Company' is worse than a name left Unclassified.
Recall is lower on purpose: a name with no word saying what it is stays Unclassified.
"""
import csv
from collections import Counter
from pathlib import Path

import pytest

from kildevagt.graph import _resolve_by_legal_form
from kildevagt.entities import Mention
from kildevagt.orgclass import classify

FIXTURES = Path(__file__).parent / "fixtures"
SETS = {name: list(csv.DictReader((FIXTURES / f"{name}.csv").open(encoding="utf-8")))
        for name in ("org_gold", "org_gold_fresh")}


def predicted(surface):
    label = classify(surface).label
    return label if label in ("Company", "Organisation") else "Other"


def scores(rows):
    counts = Counter((r["expected"], predicted(r["surface"])) for r in rows)
    out = {}
    for kind in ("Company", "Organisation"):
        said = sum(n for (e, p), n in counts.items() if p == kind)
        wanted = sum(n for (e, p), n in counts.items() if e == kind)
        out[kind] = (counts[(kind, kind)] / said if said else 1.0, counts[(kind, kind)] / wanted if wanted else 1.0)
    return out


@pytest.mark.parametrize("name,min_recall", [("org_gold", 0.9), ("org_gold_fresh", 0.65)])
def test_precision_and_recall(name, min_recall):
    rows = SETS[name]
    out = scores(rows)
    wrong = [(r["surface"], r["expected"], predicted(r["surface"])) for r in rows
             if predicted(r["surface"]) != "Other" and r["expected"] != predicted(r["surface"])]
    for kind in ("Company", "Organisation"):
        assert out[kind][0] >= 0.95, (kind, out, wrong)
        assert out[kind][1] >= min_recall, (kind, out)


def test_the_names_that_prompted_this():
    for surface in ("Borgerforslag", "Social Omsorg", "Miljøbeskyttelsesloven", "Natur & Miljø"):
        assert predicted(surface) == "Other", surface
    assert classify("Biltema").label == "Company" and classify("Landsbyggefonden").label == "Organisation"


def test_spellings_merge():
    assert classify("Sønderby Vandværks").key == classify("Sønderby Vandværker").key == classify("Sønderby Vandværk").key
    assert classify("Handelsstandsforeningen").key == classify("Handelsstandsforening").key
    assert classify("Danmarks Naturfredningsforenings").key == classify("Danmarks Naturfredningsforening").key
    assert classify("Energinets").key == classify("Energinet").key


def test_bare_name_is_merged_into_the_company_with_a_legal_form():
    def mention(name, kind):
        c = classify(name)
        return Mention(kind, c.name, c.key, "x", 0.5, "s", c.legal_form)
    mentions = [mention("Hedensted Spildevand A/S", "Company"), mention("Hedensted Spildevand", "Organisation"),
                mention("Biltema", "Company")]
    resolved = _resolve_by_legal_form(mentions)
    assert [m.kind for m in mentions] == ["Company", "Company", "Company"]
    assert resolved == {"hedensted spildevand": {"Hedensted Spildevand"}}


def test_a_match_across_a_sentence_boundary_keeps_only_the_company():
    result = classify("Hedensted Kommune. Sæsonens Madleverandør ApS")
    assert result.label == "Company" and result.name == "Sæsonens Madleverandør ApS"
    assert result.key == "sæsonens madleverandør"


def test_technical_words_are_removed_from_the_name():
    """'Glud Museum Samarbejdsaftale' is the organisation 'Glud Museum' plus a document type.
    These strings are not in the labelled sets (they are not organisations); they are checked here."""
    rows = list(csv.DictReader((FIXTURES / "name_cleaning.csv").open(encoding="utf-8")))
    assert len(rows) >= 8
    for r in rows:
        assert classify(r["surface"]).name == r["clean_name"], r["surface"]
    glued = {r["surface"] for rows_ in SETS.values() for r in rows_}
    assert not glued & {r["surface"] for r in rows}, "glued strings must not be in the labelled sets"
