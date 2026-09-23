"""The team-owned contracts are the only schema source."""
import json
import math
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo
from jsonschema import Draft202012Validator, FormatChecker
from .errors import PipelineError

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'

def _schema(data, name):
    schema = json.loads((CONTRACTS / f'{name}.schema.json').read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(data)

def _participants(items):
    assert len({p['id'] for p in items}) == len(items)
    speakers = [s for p in items for s in p['speaker_ids']]
    assert len(set(speakers)) == len(speakers)

def validate_input(data):
    try:
        _schema(data, 'input')
        dt = datetime.fromisoformat(data['meeting_datetime'].replace('Z', '+00:00'))
        zone = ZoneInfo(data['timezone'])
        assert dt.utcoffset() is not None
        assert dt.utcoffset() == dt.astimezone(zone).utcoffset()
        _participants(data['participants'])
    except Exception:
        raise PipelineError('INVALID_INPUT', 'Проверьте входные поля, дату, часовой пояс и участников.') from None

def validate_result(result, input_data):
    try:
        _schema(result, 'result')
        assert all(result[k] == input_data[k] for k in ('meeting_id', 'meeting_datetime', 'timezone'))
        _participants(result['participants'])
        participants = {p['id'] for p in result['participants']}
        segments = {s['id'] for s in result['segments']}
        assert len(segments) == len(result['segments'])
        assert len({t['id'] for t in result['tasks']}) == len(result['tasks'])
        last = -1
        for s in result['segments']:
            assert math.isfinite(s['start']) and math.isfinite(s['end'])
            assert 0 <= s['start'] < s['end'] and s['start'] >= last
            last = s['start']
        for task in result['tasks']:
            assert set(task['source_segment_ids']) <= segments
            assert task['assignee_id'] is None or task['assignee_id'] in participants
            if task['due_date'] is not None:
                assert date.fromisoformat(task['due_date']).isoformat() == task['due_date']
    except Exception:
        raise PipelineError('INVALID_MODEL_OUTPUT', 'Результат ИИ не прошёл проверку формата или ссылок.') from None
    return result
