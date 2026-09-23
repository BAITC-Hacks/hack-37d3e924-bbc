"""Single local worker. Startup recovers abandoned work only after acquiring its lock."""
import argparse
import fcntl
import json
import os
import signal
import time
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai.pipeline import run_pipeline
from ai.validation import validate_result
from .settings import Settings
from .store import Store


def fixture_result(data, progress):
    """Explicit app demo adapter; never used after a real pipeline failure."""
    example = json.loads((Path(__file__).resolve().parents[1] / 'contracts/examples/result.json').read_text())
    result = deepcopy(example)
    for key in ('meeting_id', 'meeting_datetime', 'timezone', 'participants'):
        result[key] = deepcopy(data[key])
    mapping = {p['id']: data['participants'][i] for i, p in enumerate(example['participants'])
               if i < len(data['participants'])}
    day = datetime.fromisoformat(data['meeting_datetime'].replace('Z', '+00:00')).astimezone(ZoneInfo(data['timezone'])).date()
    shift = day - date.fromisoformat(example['meeting_datetime'][:10])
    for task in result['tasks']:
        participant = mapping.get(task['assignee_id'])
        task['assignee_id'] = participant['id'] if participant else None
        if task['due_date']:
            task['due_date'] = (date.fromisoformat(task['due_date']) + shift).isoformat()
        task['needs_review'] = True
    for segment in result['segments']:
        for original in example['participants']:
            replacement = mapping.get(original['id'], {}).get('name')
            if replacement:
                segment['text'] = segment['text'].replace(original['name'], replacement)
    result['summary'] = 'ТЕСТОВЫЙ РЕЗУЛЬТАТ. Синтетический пример поручений; загруженное аудио не распознавалось.'
    progress({'stage': 'validating'})
    return validate_result(result, data)


def process_one(store, pipeline=None):
    row = store.claim()
    if row is None:
        return False
    try:
        data = json.loads(row['input_json'])
        if not Path(data['audio_path']).is_file():
            raise ValueError('Missing upload')
        progress = lambda event: store.progress(row['id'], event)
        # Persisted job mode, not ambient AI_MODE, selects execution. No fallback.
        if row['mode'] == 'fixture':
            result = fixture_result(data, progress)
        else:
            os.environ['AI_MODE'] = 'real'
            result = (pipeline or run_pipeline)(data, on_progress=progress)
        store.complete(row['id'], result)
    except Exception:
        store.fail(row['id'])
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Process at most one queued meeting and exit')
    args = parser.parse_args()
    # A direct shell launch otherwise shares the caller's process group.
    # manage.py already gives this process its own session/group.
    if os.getpgrp() != os.getpid():
        os.setsid()

    def stop(signum, frame):
        # Ignore both our own broadcast and repeated supervisor signals.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            os.killpg(os.getpid(), signal.SIGTERM)
        finally:
            # Unwinds subprocess.run: it kills/reaps its active stage even
            # if that stage ignored SIGTERM. The next worker recovers the job.
            raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    settings = Settings.from_env()
    store = Store(settings)
    # Same database implies same lock, even when DATA_DIR spelling differs.
    with settings.database.with_suffix('.worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Другой worker уже запущен для этой базы.') from None
        store.recover()
        while True:
            worked = process_one(store)
            if args.once:
                break
            if not worked:
                time.sleep(.5)


if __name__ == '__main__':
    main()
