import pytest
import spacy

from kildevagt.entities import extract, normalise_company

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("da_core_news_lg")


def test_company_names_are_normalised():
    assert normalise_company("Aarhus Vand A/S") == ("aarhus vand", "A/S")
    assert normalise_company("  AARHUS  vand a/s.") == ("aarhus vand", "A/S")
    assert normalise_company("Aarhus Vand") == ("aarhus vand", None)
    assert normalise_company("Nordic Fix ApS")[1] == "ApS"


def test_company_found_with_legal_form(nlp):
    mentions, _ = extract(nlp, "Byrådet godkender en aftale med Nordic Fix ApS om vejarbejde.", {})
    company = [m for m in mentions if m.kind == "Company"]
    assert company and company[0].key == "nordic fix" and company[0].confidence >= 0.9


def test_public_bodies_are_not_companies(nlp):
    mentions, stats = extract(nlp, "Sagen sendes til Økonomiudvalget og Region Midtjylland.", {})
    assert not [m for m in mentions if m.kind == "Company"]


def test_private_persons_are_dropped_and_redacted(nlp):
    text = "Ansøgning fra Jens Hansen Larsen om dispensation. Aftalen er med Nordic Fix ApS."
    mentions, stats = extract(nlp, text, {})
    assert not [m for m in mentions if m.kind == "Person"]
    assert all("Jens Hansen" not in m.snippet for m in mentions)


def test_elected_officials_are_kept(nlp):
    members = {"mette foged": "Mette Foged (Å)"}
    mentions, _ = extract(nlp, "Mette Foged stillede et forslag om budgettet.", members)
    person = [m for m in mentions if m.kind == "Person"]
    assert person and person[0].party == "Å"


def test_file_names_and_parties_are_noise(nlp):
    text = "Bilag 1 - Fælles ejerstrategi for Reno Djurs.pdf. Venstre og Socialdemokratiet stemte for."
    mentions, stats = extract(nlp, text, {})
    assert not [m for m in mentions if m.kind in ("Company", "Organisation") and
                ("pdf" in m.key or m.key in ("venstre", "socialdemokratiet"))]


def test_file_name_pattern_matches_the_surface_form_not_the_stripped_key():
    from kildevagt.entities import FILE_NAME
    assert FILE_NAME.search("Reno Djurs.pdf")
    assert not FILE_NAME.search("Reno Djurs I/S")
