"""Synthetic grouping stubs exercise reconciliation guards, not LLM accuracy."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import text_segments, validate_analysis
from reconcile import apply_groups, reconcile_tasks, reconciliation_batches


def candidates():
    segments = text_segments('Алия подготовит отчёт до пятницы.\nЕрлан проверит договор.\n'
        'По отчёту: Алия, переносим срок до понедельника.')
    raw = {'tasks': [
        {'task': 'Подготовить отчёт', 'owner': 'Алия', 'due_text': 'до пятницы', 'source_ids': ['S0001']},
        {'task': 'Проверить договор', 'owner': 'Ерлан', 'source_ids': ['S0002']},
        {'task': 'Составить отчёт', 'owner': 'Алия', 'due_text': 'до понедельника', 'source_ids': ['S0003']} ]}
    return segments, validate_analysis(raw, segments, {}, '2026-09-23')['tasks']


def test_paraphrase_and_later_deadline_merge_with_all_evidence():
    segments, tasks = candidates()
    merged = apply_groups(tasks, [['T0', 'T2']], segments, {}, '2026-09-23')
    assert len(merged) == 2
    report = merged[0]
    assert report['due_date'] == '2026-09-28'
    assert report['source_ids'] == ['S0001', 'S0003']
    assert 'до пятницы' in report['quote'] and 'до понедельника' in report['quote']
    assert merged[1] == tasks[1]


def test_every_distant_candidate_pair_is_reconciled():
    _, tasks = candidates()
    expanded = [tasks[i % 3] for i in range(25)]
    batches = list(reconciliation_batches(expanded))
    covered = {frozenset((left['id'], right['id'])) for batch in batches
               for left in batch for right in batch if left != right}
    assert len(covered) == 25 * 24 // 2
    assert max(len(batch) for batch in batches) <= 12


def test_different_assignees_are_not_merged_even_if_model_groups_them():
    segments, tasks = candidates()
    assert len(apply_groups(tasks, [['T0', 'T1']], segments, {}, '2026-09-23')) == 3


def test_invalid_group_does_not_delete_or_fabricate_tasks():
    segments, tasks = candidates()
    merged, warnings = reconcile_tasks(tasks, segments, {}, '2026-09-23',
        lambda *_: '{"groups":[["T0","MADE_UP"]]}')
    assert merged == tasks
    assert warnings


def test_global_reconciliation_keeps_unmentioned_candidates():
    segments, tasks = candidates()
    def generate(system, content):
        assert 'T2' in content
        return json.dumps({'groups': [['T0', 'T2']]})
    merged, warnings = reconcile_tasks(tasks, segments, {}, '2026-09-23', generate)
    assert len(merged) == 2
    assert merged[1] == tasks[1]
    assert warnings == []


def test_different_deadline_without_explicit_correction_stays_for_review():
    segments, _ = candidates()
    segments[2]['text'] = 'Алия подготовит отчёт до понедельника.'
    raw = {'tasks': [
        {'task': 'Подготовить отчёт', 'owner': 'Алия', 'due_text': 'до пятницы', 'source_ids': ['S0001']},
        {'task': 'Составить отчёт', 'owner': 'Алия', 'due_text': 'до понедельника', 'source_ids': ['S0003']}]}
    tasks = validate_analysis(raw, segments, {}, '2026-09-23')['tasks']
    merged, warnings = reconcile_tasks(tasks, segments, {}, '2026-09-23',
        lambda *_: '{"groups":[["T0","T1"]]}')
    assert len(merged) == 2
    assert merged[0]['due_date'] == '2026-09-25'
    assert merged[1]['due_date'] == '2026-09-28'
    assert warnings
    assert all('Разные сроки без явного переноса' in task['review'] for task in merged)


def test_global_inference_work_is_bounded_and_unprocessed_tasks_preserved():
    segments, tasks = candidates()
    expanded = [tasks[i % 3] for i in range(90)]
    calls = []
    def generate(*args):
        calls.append(args)
        return '{"groups":[]}'
    merged, warnings = reconcile_tasks(expanded, segments, {}, '2026-09-23', generate, max_batches=3)
    assert len(calls) == 3
    assert merged == expanded
    assert any('предел' in warning for warning in warnings)
