from datetime import date

from kildevagt.health import BLOCKED, GREEN, RED, YELLOW, baseline, document_problems, evaluate
from kildevagt.models import AgendaItem, Document


def doc(**kw):
    base = dict(source_id="x", url="u", title="Byrådet", date=date(2026, 9, 1), body="b",
                agenda_items=[AgendaItem("1", "t", "x")])
    return Document(**{**base, **kw})


def test_normal_run_is_green():
    assert evaluate(5, 5, 5, 0).status == GREEN


def test_zero_items_is_red_even_without_history():
    assert evaluate(0, None, 0, 0).status == RED
    assert "0 items" in evaluate(0, 5, 0, 0).reasons[0]


def test_far_fewer_items_than_usual_is_red_and_somewhat_fewer_is_yellow():
    assert evaluate(2, 6, 2, 0).status == RED
    assert evaluate(4, 6, 4, 0).status == YELLOW


def test_most_pages_missing_fields_is_red():
    assert evaluate(5, 5, 5, 3).status == RED
    assert evaluate(5, 5, 5, 1).status == YELLOW


def test_blocked_is_not_the_same_as_broken():
    assert evaluate(0, None, 0, 0, "SourceBlocked: robots").status == BLOCKED
    assert evaluate(0, None, 0, 0, "HTTPError: 500").status == RED


def test_past_meeting_without_agenda_items_is_a_problem_but_a_future_one_is_not():
    assert document_problems(doc(agenda_items=[]), today=date(2026, 10, 1))
    assert not document_problems(doc(agenda_items=[], date=date(2026, 12, 1)), today=date(2026, 10, 1))
    assert not document_problems(doc(), today=date(2026, 10, 1))
    assert document_problems(doc(title=""), today=date(2026, 10, 1))


def test_baseline_is_the_median():
    assert baseline([5, 5, 6]) == 5 and baseline([]) is None


def test_page_that_once_had_items_must_not_suddenly_have_none_even_if_in_the_future():
    future = doc(agenda_items=[], date=date(2026, 12, 1))
    assert document_problems(future, today=date(2026, 10, 1), previously_had_items=22)
    assert not document_problems(future, today=date(2026, 10, 1), previously_had_items=0)
