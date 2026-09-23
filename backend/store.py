"""Short SQLite transactions coordinate HTTP requests and the separate worker."""
import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy

from ai.validation import validate_input, validate_result

STAGES = {'preparing_audio', 'transcribing', 'diarizing', 'aligning',
          'extracting_tasks', 'summarizing', 'validating'}
FAILURE = {'code': 'PROCESSING_FAILED', 'message': 'Обработка не завершена', 'details': {}}


class APIError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


class Store:
    def __init__(self, settings):
        self.settings = settings
        settings.audio_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, input_json TEXT NOT NULL,
                    mode TEXT NOT NULL, status TEXT NOT NULL, stage TEXT,
                    error_json TEXT, revision INTEGER NOT NULL DEFAULT 0,
                    original_json TEXT, review_json TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                CREATE INDEX IF NOT EXISTS queue_status ON meetings(status, created_at);
            ''')

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.settings.database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def row(db, meeting_id):
        row = db.execute('SELECT * FROM meetings WHERE id=?', (meeting_id,)).fetchone()
        if row is None:
            raise APIError(404, 'NOT_FOUND', 'Совещание не найдено')
        return row

    @staticmethod
    def meeting(row, include_result=True):
        data = json.loads(row['input_json'])
        return {'id': row['id'], 'title': row['title'],
                'meeting_datetime': data['meeting_datetime'], 'timezone': data['timezone'],
                'status': row['status'], 'stage': row['stage'], 'mode': row['mode'],
                'error': json.loads(row['error_json']) if row['error_json'] else None,
                'revision': row['revision'],
                'result': json.loads(row['review_json'] or row['original_json'])
                if include_result and row['status'] == 'done' else None}

    def create(self, title, data):
        with self.connect(write=True) as db:
            db.execute('INSERT INTO meetings(id,title,input_json,mode,status) VALUES(?,?,?,?,?)',
                       (data['meeting_id'], title, json.dumps(data, ensure_ascii=False), self.settings.mode, 'queued'))
            return self.meeting(self.row(db, data['meeting_id']))

    def get(self, meeting_id):
        with self.connect() as db:
            return self.meeting(self.row(db, meeting_id))

    def list(self):
        with self.connect() as db:
            return {'items': [self.meeting(row, False) for row in db.execute(
                'SELECT * FROM meetings ORDER BY created_at DESC, rowid DESC')]}

    def original(self, meeting_id):
        with self.connect() as db:
            row = self.row(db, meeting_id)
            self.done(row)
            return json.loads(row['original_json'])

    @staticmethod
    def done(row):
        if row['status'] != 'done':
            raise APIError(409, 'INVALID_STATE', 'Дождитесь завершения обработки')

    def review(self, meeting_id, changes):
        if not isinstance(changes, dict) or set(changes) != {'expected_revision', 'participants', 'tasks', 'summary'}:
            raise APIError(422, 'VALIDATION_ERROR', 'Проверьте поля исправлений')
        if type(changes['expected_revision']) is not int or changes['expected_revision'] < 1:
            raise APIError(422, 'VALIDATION_ERROR', 'Проверьте номер версии')
        with self.connect(write=True) as db:
            row = self.row(db, meeting_id)
            self.done(row)
            if row['revision'] != changes['expected_revision']:
                raise APIError(409, 'REVISION_CONFLICT', 'Сохранена другая версия. Обновите данные перед повторным сохранением')
            result = json.loads(row['review_json'] or row['original_json'])
            result.update({key: changes[key] for key in ('participants', 'tasks', 'summary')})
            data = json.loads(row['input_json'])
            # Review may rename/add/remove participants without rewriting original metadata.
            data['participants'] = deepcopy(result['participants'])
            try:
                validate_input(data)
                validate_result(result, data)
                speakers = {segment['speaker_id'] for segment in result['segments']}
                if any(not set(p['speaker_ids']) <= speakers for p in result['participants']):
                    raise ValueError('Unknown speaker')
                if any(not t['text'].strip() for t in result['tasks']):
                    raise ValueError('Empty task')
            except Exception:
                raise APIError(422, 'VALIDATION_ERROR', 'Проверьте участников, источники поручений и даты') from None
            db.execute('UPDATE meetings SET review_json=?,revision=revision+1 WHERE id=?',
                       (json.dumps(result, ensure_ascii=False), meeting_id))
            return self.meeting(self.row(db, meeting_id))

    def retry(self, meeting_id):
        with self.connect(write=True) as db:
            row = self.row(db, meeting_id)
            if row['status'] != 'failed':
                raise APIError(409, 'INVALID_STATE', 'Повтор доступен только после ошибки обработки')
            db.execute("UPDATE meetings SET status='queued',stage=NULL,error_json=NULL WHERE id=?", (meeting_id,))
            return self.meeting(self.row(db, meeting_id))

    def delete(self, meeting_id):
        with self.connect(write=True) as db:
            row = self.row(db, meeting_id)
            if row['status'] == 'processing':
                raise APIError(409, 'INVALID_STATE', 'Нельзя удалить совещание во время обработки')
            from pathlib import Path
            audio = Path(json.loads(row['input_json'])['audio_path'])
            if audio.parent.resolve() != self.settings.audio_dir.resolve():
                raise APIError(500, 'INTERNAL_ERROR', 'Не удалось удалить файл совещания')
            try:
                audio.unlink(missing_ok=True)
            except OSError:
                raise APIError(500, 'INTERNAL_ERROR', 'Не удалось удалить файл совещания') from None
            db.execute('DELETE FROM meetings WHERE id=?', (meeting_id,))

    def recover(self):
        with self.connect(write=True) as db:
            db.execute("UPDATE meetings SET status='failed',stage=NULL,error_json=? WHERE status='processing'",
                       (json.dumps(FAILURE),))

    def claim(self):
        with self.connect(write=True) as db:
            row = db.execute("SELECT * FROM meetings WHERE status='queued' ORDER BY created_at,rowid LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE meetings SET status='processing',stage=NULL WHERE id=?", (row['id'],))
            return dict(row)

    def progress(self, meeting_id, event):
        stage = event.get('stage') if isinstance(event, dict) else None
        if stage not in STAGES:
            return
        with self.connect(write=True) as db:
            db.execute("UPDATE meetings SET stage=? WHERE id=? AND status='processing'", (stage, meeting_id))

    def complete(self, meeting_id, result):
        with self.connect(write=True) as db:
            row = self.row(db, meeting_id)
            validate_result(result, json.loads(row['input_json']))
            if row['status'] != 'processing' or row['original_json'] is not None:
                raise ValueError('Invalid completion state')
            db.execute("UPDATE meetings SET original_json=?,revision=1,status='done',stage=NULL,error_json=NULL WHERE id=?",
                       (json.dumps(result, ensure_ascii=False), meeting_id))

    def fail(self, meeting_id):
        with self.connect(write=True) as db:
            db.execute("UPDATE meetings SET status='failed',stage=NULL,error_json=? WHERE id=? AND status='processing'",
                       (json.dumps(FAILURE), meeting_id))
