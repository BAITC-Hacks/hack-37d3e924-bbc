"""Synthetic review validation coverage only."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import validate_review


SEGMENTS = [
    {'id':'S1','speaker':'A','start':3.5,'end':5,'text':'Айжан тексеріс жоспарын дайындайды.'},
    {'id':'S2','speaker':'B','start':8.0,'end':9,'text':'Срок указан как 2026-09-24.'},
]


def review(**task_updates):
    task = {'task':'Дайындау жоспарын','owner':'Айжан','due_text':'2026-09-24','due_date':'2026-09-24',
            'review':'Проверить','status':'В работе','quote':'Выдуманная цитата','source_ids':['S2','S1']}
    task.update(task_updates)
    return {'summary':'Синтетическое саммари','tasks':[task],'warnings':['Синтетическое предупреждение'],
            'model':'synthetic-local'}


def test_review_normalizes_empty_dates_and_nullable_fields_without_mutating_original():
    raw = review(owner=None,due_text=None,due_date='',status=None,review=None)
    original = copy.deepcopy(raw)
    checked = validate_review(raw, SEGMENTS)
    assert raw == original
    task = checked['tasks'][0]
    assert task['owner'] == ''
    assert task['due_text'] == ''
    assert task['due_date'] == ''
    assert task['status'] == 'На проверке'
    assert checked['model'] == 'synthetic-local'


def test_review_accepts_valid_exact_date_and_unicode_owner():
    task = validate_review(review(owner='Айжан Қали'), SEGMENTS)['tasks'][0]
    assert task['owner'] == 'Айжан Қали'
    assert task['due_date'] == '2026-09-24'


@pytest.mark.parametrize('due_date',['2026-9-24','2026-02-30','24.09.2026'])
def test_review_rejects_invalid_due_dates(due_date):
    with pytest.raises(ValueError, match='YYYY-MM-DD'):
        validate_review(review(due_date=due_date), SEGMENTS)


@pytest.mark.parametrize('source_ids',[[],['S404'],['S1',7]])
def test_review_rejects_missing_or_invalid_source_ids(source_ids):
    with pytest.raises(ValueError, match='исходн'):
        validate_review(review(source_ids=source_ids), SEGMENTS)


def test_review_derives_quote_and_start_from_current_segments():
    checked = validate_review(review(source_ids=['S2','S1']), SEGMENTS)
    task = checked['tasks'][0]
    assert task['quote'] == '[S1] Айжан тексеріс жоспарын дайындайды.\n[S2] Срок указан как 2026-09-24.'
    assert task['start'] == 3.5
