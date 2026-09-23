"""Synthetic model decisions exercise reconciliation gates, not model quality."""

from copy import deepcopy

import pytest

from ai.errors import PipelineError
from ai.extraction import extract, merge_tasks, reconcile_tasks

REQUEST = {
    "meeting_datetime": "2026-09-23T10:00:00+05:00",
    "timezone": "Asia/Almaty",
    "participants": [{"id": "p1", "name": "Айжан", "speaker_ids": []}],
}


def task(sid, due="2026-09-24", person="p1", text="Подготовить отчёт"):
    return {
        "id": "pending",
        "text": text,
        "assignee_id": person,
        "due_date": due,
        "source_segment_ids": [sid],
        "needs_review": True,
    }


def segment(sid, text):
    return {
        "id": sid,
        "start": int(sid[1:]) * 10,
        "end": int(sid[1:]) * 10 + 5,
        "speaker_id": "SPEAKER_0",
        "text": text,
    }


class Generator:
    format_repairs = 0

    def __init__(self, decision, fits=True):
        self.decision = decision
        self.can_fit = fits
        self.calls = []

    def fits(self, system, payload):
        return self.can_fit

    def generate(self, system, payload):
        self.calls.append(payload)
        return deepcopy(self.decision)


def replacement(
    sid="s2", quote="Срок отчёта переносим на послезавтра.", due="послезавтра"
):
    return {
        "decision": "replace_deadline",
        "source_segment_id": sid,
        "quote": quote,
        "due_text": due,
    }


def test_later_deadline_replaces_old_and_keeps_both_sources():
    segments = [
        segment("s1", "Айжан, подготовь отчёт завтра."),
        segment("s2", "Срок отчёта переносим на послезавтра."),
    ]
    source = [task("s1"), task("s2", "2026-09-25")]
    before = deepcopy(source)
    result, warnings = reconcile_tasks(
        source, segments, REQUEST, Generator(replacement())
    )
    assert len(result) == 1 and result[0]["due_date"] == "2026-09-25"
    assert result[0]["source_segment_ids"] == ["s1", "s2"]
    assert result[0]["needs_review"] and not warnings
    assert source == before


def test_kazakh_deadline_change():
    quote = "Есептің мерзімін бүрсігүні деп өзгертеміз."
    segments = [segment("s1", "Айжан, есепті ертең дайындаңыз."), segment("s2", quote)]
    result, _ = reconcile_tasks(
        [
            task("s1", text="Есепті дайындау"),
            task("s2", "2026-09-25", text="Есепті дайындау"),
        ],
        segments,
        REQUEST,
        Generator(replacement(quote=quote, due="бүрсігүні")),
    )
    assert len(result) == 1 and result[0]["due_date"] == "2026-09-25"


@pytest.mark.parametrize(
    "decision,source_text",
    [
        (replacement(sid="missing"), "Срок отчёта переносим на послезавтра."),
        (
            replacement(quote="Придуманный переносим на послезавтра."),
            "Срок отчёта переносим на послезавтра.",
        ),
        (replacement(due="завтра"), "Срок отчёта переносим на послезавтра."),
        (replacement(quote="Срок отчёта послезавтра."), "Срок отчёта послезавтра."),
        (
            replacement(quote="переносим на послезавтра"),
            "Срок отчёта не переносим на послезавтра.",
        ),
        (
            replacement(quote="Срок отчёта переносим на послезавтра?"),
            "Срок отчёта переносим на послезавтра?",
        ),
        (
            replacement(quote="Предлагаю срок отчёта перенести на послезавтра."),
            "Предлагаю срок отчёта перенести на послезавтра.",
        ),
    ],
)
def test_unproven_correction_keeps_both_with_warning(decision, source_text):
    result, warnings = reconcile_tasks(
        [task("s1"), task("s2", "2026-09-25")],
        [segment("s1", "Айжан, отчёт завтра."), segment("s2", source_text)],
        REQUEST,
        Generator(decision),
    )
    assert len(result) == 2 and warnings
    assert [t["due_date"] for t in result] == ["2026-09-24", "2026-09-25"]


def test_source_order_not_task_iteration_decides_what_is_later():
    result, _ = reconcile_tasks(
        [task("s2", "2026-09-25"), task("s1")],
        [segment("s1", "Айжан, отчёт завтра."), segment("s2", replacement()["quote"])],
        REQUEST,
        Generator(replacement()),
    )
    assert len(result) == 1 and result[0]["due_date"] == "2026-09-25"


def test_correction_cannot_use_an_earlier_or_already_shared_source():
    earlier = task("s1")
    earlier["source_segment_ids"].append("s2")
    result, warnings = reconcile_tasks(
        [earlier, task("s2", "2026-09-25")],
        [segment("s1", "Айжан, отчёт завтра."), segment("s2", replacement()["quote"])],
        REQUEST,
        Generator(replacement()),
    )
    assert len(result) == 2 and warnings


@pytest.mark.parametrize(
    "left,right",
    [
        (task("s1", person="p1"), task("s2", person="p2")),
        (task("s1", person=None), task("s2", person=None)),
        (
            task("s1", text="Проверить договор 101"),
            task("s2", text="Проверить договор 102"),
        ),
        (task("s1"), task("s2", text="Отправить смету")),
    ],
)
def test_separate_owners_objects_actions_are_not_merged(left, right):
    gen = Generator({"decision": "duplicate"})
    result, _ = reconcile_tasks(
        [left, right], [segment("s1", "a"), segment("s2", "b")], REQUEST, gen
    )
    assert len(result) == 2 and not gen.calls


def test_unknown_people_in_same_source_are_not_collapsed():
    assert len(merge_tasks([task("s1", person=None), task("s1", person=None)])) == 2


def test_periods_and_uncertain_repetitions_stay_separate_when_model_says_keep():
    gen = Generator({"decision": "keep"})
    result, warnings = reconcile_tasks(
        [
            task("s1", text="Подготовить отчёт за май"),
            task("s2", text="Подготовить отчёт за июнь"),
        ],
        [segment("s1", "Отчёт за май"), segment("s2", "Отчёт за июнь")],
        REQUEST,
        gen,
    )
    assert len(result) == 2 and warnings and gen.calls


def test_undated_recurring_assignments_are_not_collapsed_even_if_model_requests_it():
    result, warnings = reconcile_tasks(
        [task("s1", due=None), task("s2", due=None)],
        [segment("s1", "Отчёт"), segment("s2", "Отчёт ещё раз")],
        REQUEST,
        Generator({"decision": "duplicate"}),
    )
    assert len(result) == 2 and warnings


def test_confirmed_duplicate_across_distant_chunks_unions_sources():
    result, warnings = reconcile_tasks(
        [task("s1"), task("s100")],
        [
            segment("s1", "Айжан, отчёт завтра."),
            segment("s100", "Напоминаю: Айжан, тот же отчёт завтра."),
        ],
        REQUEST,
        Generator({"decision": "duplicate"}),
    )
    assert (
        len(result) == 1
        and result[0]["source_segment_ids"] == ["s1", "s100"]
        and not warnings
    )


def test_context_limit_preserves_all_tasks_with_warning():
    gen = Generator({"decision": "duplicate"}, fits=False)
    result, warnings = reconcile_tasks(
        [task("s1"), task("s2")], [segment("s1", "a"), segment("s2", "b")], REQUEST, gen
    )
    assert len(result) == 2 and warnings and not gen.calls


def test_model_comparison_count_is_bounded():
    source = [task(f"s{i}") for i in range(15)]
    segments = [segment(f"s{i}", "Поручение") for i in range(15)]
    gen = Generator({"decision": "keep"})
    result, warnings = reconcile_tasks(source, segments, REQUEST, gen)
    assert len(result) == 15 and len(gen.calls) == 64
    assert any("лимите" in warning for warning in warnings)


def test_invalid_reconciliation_response_is_not_accepted():
    with pytest.raises(PipelineError):
        reconcile_tasks(
            [task("s1"), task("s2")],
            [segment("s1", "a"), segment("s2", "b")],
            REQUEST,
            Generator({"decision": "invent_task"}),
        )


def test_extract_runs_final_reconciliation_over_chunk_outputs(monkeypatch):
    segments = [
        segment("s1", "Айжан, подготовь отчёт завтра."),
        segment("s2", "Айжан, срок отчёта переносим на послезавтра."),
    ]

    class ChunkGenerator(Generator):
        def fits(self, system, payload):
            return "participants" not in payload or len(payload["segments"]) == 1

        def generate(self, system, payload):
            if "earlier_task" in payload:
                return replacement(quote=segments[1]["text"])
            if "summaries" in payload:
                return {"summary": "Согласован отчёт."}
            sid = payload["segments"][0]["id"]
            return {
                "summary": "Отчёт",
                "tasks": [
                    {
                        "text": "Подготовить отчёт",
                        "owner": "Айжан",
                        "due_text": "завтра" if sid == "s1" else "послезавтра",
                        "source_segment_ids": [sid],
                    }
                ],
            }

    monkeypatch.setattr(
        "ai.extraction.LocalGenerator", lambda settings: ChunkGenerator({})
    )
    result = extract(segments, REQUEST, object())
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["due_date"] == "2026-09-25"
    assert result["tasks"][0]["source_segment_ids"] == ["s1", "s2"]
