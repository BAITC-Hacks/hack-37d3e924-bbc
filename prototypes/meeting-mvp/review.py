"""Validate reviewed drafts and keep original output separate from saved revisions."""
from copy import deepcopy
from datetime import date, datetime
import re

from core import read_json, write_json


def validate_review(analysis, segments):
    """Reject invalid edits; regenerate evidence exclusively from transcript rows."""
    by_id = {segment['id']: segment for segment in segments}
    if not isinstance(analysis, dict) or not isinstance(analysis.get('tasks'), list):
        raise ValueError('Неверная структура протокола.')
    if not isinstance(analysis.get('summary', ''), str):
        raise ValueError('Краткое содержание должно быть текстом.')
    result = deepcopy(analysis)
    for index, task in enumerate(result['tasks'], 1):
        label = f'Поручение {index}: '
        if not isinstance(task, dict) or not isinstance(task.get('task'), str) or not task['task'].strip():
            raise ValueError(label + 'укажите текст поручения.')
        task['task'] = task['task'].strip()
        ids = task.get('source_ids')
        if not isinstance(ids, list) or not ids:
            raise ValueError(label + 'выберите хотя бы одну исходную реплику.')
        if any(not isinstance(source, str) or source not in by_id for source in ids):
            raise ValueError(label + 'выбрана несуществующая исходная реплика.')
        task['source_ids'] = [source for source in by_id if source in ids]
        for field in ('owner', 'due_text', 'due_date', 'review', 'status'):
            value = task.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(label + 'поля поручения должны содержать текст.')
            task[field] = (value or '').strip()
        task['status'] = task['status'] or 'На проверке'
        if task['status'] not in ('На проверке', 'В работе', 'Выполнено'):
            raise ValueError(label + 'выберите допустимый статус.')
        if task['due_date']:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', task['due_date']):
                    raise ValueError
                date.fromisoformat(task['due_date'])
            except ValueError:
                raise ValueError(label + 'дата должна существовать и иметь формат YYYY-MM-DD.') from None
        task['quote'] = '\n'.join(f"[{source}] {by_id[source]['text']}" for source in task['source_ids'])
        starts = [by_id[source].get('start') for source in task['source_ids']]
        task['start'] = min((start for start in starts if start is not None), default=None)
        notes = [task['review']] if task['review'] else []
        for missing, note in ((not task['owner'], 'Уточнить ответственного'),
                              (not task['due_date'], 'Уточнить календарную дату')):
            if missing and not any(note in text for text in notes):
                notes.append(note)
        task['review'] = '; '.join(notes)
    return result


def save_review_file(destination, *, title, meeting_date, transcript, segments, names,
                     current_hash, audio_path=None, analysis=None, original_transcript=None,
                     original_analysis=None):
    """A transcript-only save preserves the existing analysis and its input hash."""
    previous = read_json(destination) if destination.exists() else {}
    checked = validate_review(analysis, segments) if analysis is not None else previous.get('analysis')
    original = deepcopy(previous.get('original') or {
        'transcript': previous.get('transcript', original_transcript or transcript),
        'analysis': previous.get('analysis'),
    })
    if original.get('analysis') is None and original_analysis is not None:
        original['analysis'] = deepcopy(original_analysis)
    payload = {
        'version': 2, 'title': title, 'saved_at': datetime.now().isoformat(timespec='microseconds'),
        'meeting_date': meeting_date, 'transcript': {**transcript, 'segments': deepcopy(segments)},
        'names': deepcopy(names), 'audio_path': audio_path, 'analysis': checked,
        'analysis_hash': current_hash if analysis is not None else previous.get('analysis_hash'),
    }
    revisions = deepcopy(previous.get('revisions', []))
    # Migrate v1 without discarding the only previously saved version.
    if previous and not revisions:
        revisions.append({key: deepcopy(value) for key, value in previous.items()
                          if key not in ('original', 'revisions')})
    revisions.append(deepcopy(payload))
    payload.update(original=original, revisions=revisions)
    write_json(destination, payload)
    return payload
