"""Synthetic regression cases; these do not measure model quality."""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import text_segments
from review import save_review_file, validate_review
from export_docx import build_docx


def sample():
    segments = text_segments('Алия подготовит отчёт к пятнице.\nСрок отчёта согласовали на понедельник.')
    analysis = {'summary': 'Согласовали отчёт.', 'tasks': [{'task': 'Подготовить отчёт',
        'owner': 'Алия', 'due_date': '2026-09-28', 'source_ids': ['S0001', 'S0002']}]}
    return segments, analysis


def test_transcript_save_preserves_review_hash_original_and_history(tmp_path):
    segments, analysis = sample()
    machine = deepcopy(analysis)
    machine['summary'] = 'Машинный черновик'
    path = tmp_path / 'review.json'
    options = dict(title='Совещание', meeting_date='2026-09-23',
        transcript={'source': 'synthetic_text', 'segments': segments}, segments=segments,
        names={}, current_hash='first', original_analysis=machine)
    first = save_review_file(path, analysis=analysis, **options)
    changed = deepcopy(segments)
    changed[0]['text'] = 'Исправленный текст'
    options.update(segments=changed, current_hash='changed')
    second = save_review_file(path, **options)
    assert second['analysis'] == first['analysis']
    assert second['analysis_hash'] == 'first'  # UI will mark analysis stale.
    assert second['original']['analysis'] == machine
    assert second['original']['transcript']['segments'] == segments
    assert len(second['revisions']) == 2
    assert second['revisions'][0]['transcript']['segments'] == segments
    third_analysis = deepcopy(analysis)
    third_analysis['summary'] = 'Правки секретаря'
    third = save_review_file(path, analysis=third_analysis, **options)
    assert third['original'] == first['original']
    assert third['analysis']['summary'] == 'Правки секретаря'
    assert third['analysis_hash'] == 'changed'
    assert len(third['revisions']) == 3


def test_legacy_review_migration_preserves_only_existing_version(tmp_path):
    segments, analysis = sample()
    path = tmp_path / 'review.json'
    path.write_text(json.dumps({'version': 1, 'transcript': {'segments': segments},
        'analysis': analysis, 'analysis_hash': 'legacy'}))
    updated = save_review_file(path, title='Обновление', meeting_date=None,
        transcript={'segments': segments}, segments=segments, names={}, current_hash='new')
    assert updated['original']['analysis'] == analysis
    assert updated['revisions'][0]['version'] == 1
    assert updated['analysis_hash'] == 'legacy'


@pytest.mark.parametrize('field,value', [('source_ids', []), ('source_ids', ['unknown']),
    ('source_ids', 'S0001'), ('due_date', '2026-02-30'), ('due_date', '20260928'),
    ('due_date', '28.09.2026'), ('due_date', 20260928), ('task', ' '), ('status', 'approved')])
def test_invalid_manual_edits_block_save_and_export(tmp_path, field, value):
    segments, analysis = sample()
    analysis['tasks'][0][field] = value
    with pytest.raises(ValueError):
        validate_review(analysis, segments)
    with pytest.raises(ValueError):
        build_docx('Тест', None, analysis, segments, {})
    path = tmp_path / 'review.json'
    with pytest.raises(ValueError):
        save_review_file(path, title='Тест', meeting_date=None, transcript={'segments': segments},
            segments=segments, names={}, current_hash='hash', analysis=analysis)
    assert not path.exists()


def test_manual_evidence_is_rebuilt_and_unknown_fields_require_review():
    segments, analysis = sample()
    analysis['tasks'][0].update(quote='Выдуманная цитата', source_ids=['S0002', 'S0001', 'S0001'],
                               owner=None, due_date=None)
    task = validate_review(analysis, segments)['tasks'][0]
    assert task['source_ids'] == ['S0001', 'S0002']
    assert 'Выдуманная' not in task['quote']
    assert segments[0]['text'] in task['quote']
    assert 'Уточнить ответственного' in task['review']
    assert 'Уточнить календарную дату' in task['review']
