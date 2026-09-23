"""Pure data transformations. No model loading or external requests."""
import json
import re
from datetime import date, timedelta
from copy import deepcopy
from pathlib import Path

def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def stamp(seconds):
    if seconds is None:
        return '—'
    n = max(0, int(float(seconds)))
    return f'{n//3600:02d}:{n//60%60:02d}:{n%60:02d}' if n >= 3600 else f'{n//60:02d}:{n%60:02d}'

def normalize(text):
    return re.sub(r'\s+', ' ', str(text).lower().replace('ё', 'е')).strip()

def due_date(text, meeting_date):
    """Conservative normalization: only unambiguous dates; never use today's date."""
    if not text:
        return None
    s = normalize(text)
    ordinals = {'перв':1,'втор':2,'треть':3,'четверт':4,'пят':5,'шест':6,'седьм':7,'восьм':8,'девят':9,
        'десят':10,'одиннадцат':11,'двенадцат':12,'тринадцат':13,'четырнадцат':14,'пятнадцат':15,
        'шестнадцат':16,'семнадцат':17,'восемнадцат':18,'девятнадцат':19,'двадцат':20,'тридцат':30}
    # Replace only complete ordinal day words; preserve the original due_text separately.
    for stem, value in sorted(ordinals.items(), key=lambda item:-len(item[0])):
        for prefix, tens in [('двадцать ',20),('тридцать ',30),('',0)]:
            if prefix and value>9:
                continue
            s = re.sub(r'\b'+prefix+stem+r'(?:ого|ому|ое|ый|ой|ий|его|ему)\b',str(tens+value),s)
    anchor = date.fromisoformat(meeting_date) if meeting_date else None
    iso = re.search(r'\b(20\d\d)-(\d\d)-(\d\d)\b', s)
    try:
        if iso:
            return date(*map(int, iso.groups())).isoformat()
        numeric = re.search(r'\b(\d{1,2})[./](\d{1,2})[./](20\d\d)\b', s)
        if numeric:
            d, m, y = map(int, numeric.groups())
            return date(y, m, d).isoformat()
        months = ['январ','феврал','март','апрел','мая','июн','июл','август','сентябр','октябр','ноябр','декабр']
        kk = ['қаңтар','ақпан','наурыз','сәуір','мамыр','маусым','шілде','тамыз','қыркүйек','қазан','қараша','желтоқсан']
        for i, alternatives in enumerate(zip(months, kk), 1):
            for month in alternatives:
                match = re.search(r'(\d{1,2})\s+' + month + r'\w*(?:\s+(20\d\d))?', s)
                if match:
                    year = int(match[2]) if match[2] else (anchor.year if anchor else None)
                    if not year:
                        return None
                    result = date(year, i, int(match[1]))
                    # A past day with unspecified year is ambiguous; do not roll it forward.
                    if not match[2] and anchor and result < anchor:
                        return None
                    return result.isoformat()
        if not anchor:
            return None
        if s in ('завтра', 'до завтра', 'ертең'):
            return (anchor + timedelta(days=1)).isoformat()
        if s in ('сегодня', 'бүгін'):
            return anchor.isoformat()
        weekdays = ['понедельник', 'вторник', 'сред', 'четверг', 'пятниц', 'суббот', 'воскресень']
        for i, day in enumerate(weekdays):
            if re.fullmatch(r'(?:до |к |в )?' + day + r'\w*', s):
                return (anchor + timedelta(days=(i-anchor.weekday()) % 7)).isoformat()
        # Week/month ranges, working days and vague relative durations require review.
        return None
    except ValueError:
        return None

def speaker_for(start, end, turns):
    scores = {}
    for turn in turns:
        overlap = max(0, min(end, turn['end']) - max(start, turn['start']))
        if overlap:
            speaker = turn['speaker']
            scores[speaker] = scores.get(speaker, 0) + overlap
    if not scores:
        return 'UNKNOWN'
    ranked = sorted(scores, key=scores.get, reverse=True)
    if len(ranked) > 1 and scores[ranked[1]] >= scores[ranked[0]] * .8:
        return 'OVERLAP'
    return ranked[0]

def group_words(words, turns):
    segments = []
    for word in words:
        speaker = speaker_for(word['start'], word['end'], turns)
        if (segments and segments[-1]['speaker'] == speaker
            and word['start'] - segments[-1]['end'] < 1.2
            and word['end'] - segments[-1]['start'] < 18):
            segments[-1]['text'] += ' ' + word['text']
            segments[-1]['end'] = word['end']
        else:
            segments.append({**word, 'speaker': speaker, 'id': f'S{len(segments)+1:04d}'})
    return segments

def text_segments(text):
    """An explicitly imported transcript has no inferred audio timestamps or voices."""
    result = []
    for line in text.splitlines():
        line = line.strip()
        while line:
            cut = min(len(line), 1800)
            if len(line) > cut:
                cut = line.rfind(' ', 0, cut) or 1800
                if cut < 1:
                    cut = 1800
            fragment, line = line[:cut].strip(), line[cut:].strip()
            result.append({'id': f'S{len(result)+1:04d}', 'speaker': 'UNKNOWN',
                           'start': None, 'end': None, 'text': fragment})
    return result

def parse_model_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    start = text.find('{')
    if start < 0:
        raise ValueError('Модель не вернула JSON. Транскрипт сохранён; повторите анализ.')
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict) or not isinstance(obj.get('tasks'), list):
        raise ValueError('Неверная структура ответа модели.')
    return obj

def validate_analysis(raw, segments, names, meeting_date):
    by_id = {s['id']: s for s in segments}
    tasks, warnings = [], []
    for item in raw.get('tasks', []):
        if not isinstance(item, dict) or not isinstance(item.get('task'), str) or not item['task'].strip():
            warnings.append('Пропущено поручение с неверной структурой.')
            continue
        ids = item.get('source_ids', [])
        ids = list(dict.fromkeys(x for x in ids if isinstance(x, str) and x in by_id)) if isinstance(ids, list) else []
        if not ids:
            warnings.append('Пропущено поручение без существующих исходных реплик: ' + item['task'][:100])
            continue
        # Never trust an LLM to copy a quotation. Copy selected source rows ourselves.
        # A valid ID is provenance, not proof of semantic correctness: the reviewer checks it.
        ids.sort(key=lambda x: list(by_id).index(x))
        source = ' '.join(by_id[x]['text'] for x in ids)
        quote = '\n'.join(f"[{x}] {by_id[x]['text']}" for x in ids)
        owner = item.get('owner') if isinstance(item.get('owner'), str) else None
        due = item.get('due_text') if isinstance(item.get('due_text'), str) else None
        if owner and normalize(owner) in ('null','none','не указан','неизвестно'):
            owner = None
        if due and normalize(due) in ('null','none','не указан','неизвестно'):
            due = None
        notes = ['Проверить поручение по исходным репликам']
        # Owner may be a confirmed name of a speaker in source segments, or explicitly mentioned.
        known_owners = [names.get(by_id[x]['speaker'], '') for x in ids]
        if owner and normalize(owner) not in normalize(source) and owner not in known_owners:
            notes.append('Исполнитель не подтверждён исходными репликами')
            owner = None
        if due and normalize(due) not in normalize(source):
            notes.append('Формулировка срока не найдена в исходных репликах')
            due = None
        normalized_due = due_date(due, meeting_date)
        if not owner:
            notes.append('Уточнить ответственного')
        if due and not normalized_due:
            notes.append('Уточнить календарную дату')
        if not due:
            notes.append('Срок не указан')
        starts = [by_id[x]['start'] for x in ids if by_id[x]['start'] is not None]
        tasks.append({'task': item['task'].strip(), 'owner': owner or '', 'due_text': due or '',
                      'due_date': normalized_due or '', 'quote': quote, 'source_ids': ids,
                      'start': min(starts) if starts else None, 'review': '; '.join(notes),
                      'status': 'На проверке'})
    summary = raw.get('summary', '')
    return {'summary': summary if isinstance(summary, str) else '', 'tasks': tasks, 'warnings': warnings}

def validate_review(analysis, segments):
    if not isinstance(analysis, dict):
        raise ValueError('Протокол должен быть объектом с саммари и поручениями.')
    if not isinstance(analysis.get('summary'), str):
        raise ValueError('Краткое содержание должно быть строкой.')
    raw_tasks = analysis.get('tasks')
    if not isinstance(raw_tasks, list):
        raise ValueError('Поручения должны быть списком.')
    by_id = {s.get('id'): s for s in segments if isinstance(s, dict) and isinstance(s.get('id'), str)}
    order = {segment_id: index for index, segment_id in enumerate(by_id)}
    result = deepcopy(analysis)
    result['summary'] = analysis['summary']
    normalized_tasks = []
    allowed_statuses = {'На проверке', 'В работе', 'Выполнено'}
    for index, item in enumerate(raw_tasks, 1):
        if not isinstance(item, dict):
            raise ValueError(f'Поручение {index}: строка должна быть объектом.')
        task_text = item.get('task')
        if not isinstance(task_text, str) or not task_text.strip():
            raise ValueError(f'Поручение {index}: текст поручения обязателен.')
        ids = item.get('source_ids')
        if not isinstance(ids, list) or not ids or not all(isinstance(x, str) for x in ids):
            raise ValueError(f'Поручение {index}: укажите исходные реплики.')
        if any(x not in by_id for x in ids):
            raise ValueError(f'Поручение {index}: исходная реплика не найдена.')
        ids = sorted(dict.fromkeys(ids), key=lambda x: order[x])
        owner = item.get('owner')
        due_text = item.get('due_text')
        review = item.get('review')
        due = item.get('due_date')
        status = item.get('status')
        if owner is None:
            owner = ''
        if due_text is None:
            due_text = ''
        if review is None:
            review = ''
        if due is None:
            due = ''
        if status is None:
            status = 'На проверке'
        if not isinstance(owner, str):
            raise ValueError(f'Поручение {index}: ответственный должен быть строкой.')
        if not isinstance(due_text, str):
            raise ValueError(f'Поручение {index}: срок текстом должен быть строкой.')
        if not isinstance(review, str):
            raise ValueError(f'Поручение {index}: комментарий проверки должен быть строкой.')
        if not isinstance(due, str):
            raise ValueError(f'Поручение {index}: дата срока должна быть строкой.')
        due = due.strip()
        if due:
            try:
                valid_due = re.fullmatch(r'\d{4}-\d{2}-\d{2}', due) and date.fromisoformat(due).isoformat() == due
            except ValueError:
                valid_due = False
            if not valid_due:
                raise ValueError(f'Поручение {index}: дата срока должна быть в формате YYYY-MM-DD.')
        if not isinstance(status, str) or status not in allowed_statuses:
            raise ValueError(f'Поручение {index}: неизвестный статус.')
        starts = [by_id[x].get('start') for x in ids if by_id[x].get('start') is not None]
        normalized_tasks.append({'task': task_text.strip(), 'owner': owner.strip(), 'due_text': due_text.strip(),
            'due_date': due, 'review': review.strip(), 'status': status,
            'quote': '\n'.join(f"[{x}] {by_id[x].get('text','')}" for x in ids), 'source_ids': ids,
            'start': min(starts) if starts else None})
    result['tasks'] = normalized_tasks
    return result

def transcript_text(segments, names):
    return '\n'.join(f"[{s['id']} · {stamp(s['start'])}] {names.get(s['speaker'], s['speaker'])}: {s['text']}" for s in segments)
