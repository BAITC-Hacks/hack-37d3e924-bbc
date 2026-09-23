import json
import os
from pathlib import Path
import subprocess
import sys


def test_ui_synthetic_transcript_save_reopen_without_models(tmp_path):
    # Run in a separate process: config reads the data path at import time.
    script = r'''
import json
import os
from pathlib import Path
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('app.py', default_timeout=20).run()
assert not at.exception, at.exception
next(b for b in at.button if b.label == 'Синтетический пример').click().run()
assert not at.exception, at.exception
assert at.session_state.transcript['source'] == 'synthetic_text'
next(b for b in at.button if b.label == 'Сохранить транскрипт локально').click().run()
assert not at.exception, at.exception
saved = list(Path(os.environ['MEETING_DATA_DIR']).glob('review-*.json'))
assert len(saved) == 1
record = json.loads(saved[0].read_text(encoding='utf-8'))
assert record['transcript']['source'] == 'synthetic_text'
assert record['analysis'] is None
fresh = AppTest.from_file('app.py', default_timeout=20).run()
next(b for b in fresh.button if b.label == 'Открыть сохранённое').click().run()
assert not fresh.exception, fresh.exception
assert fresh.session_state.transcript['segments'] == record['transcript']['segments']
assert next(b for b in fresh.button if b.label == 'Сформировать поручения и саммари').disabled
'''
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, 'MEETING_DATA_DIR': str(tmp_path / 'data'),
             'MEETING_MODEL_DIR': str(tmp_path / 'models'), 'PYTHONUTF8': '1'},
        capture_output=True, text=True, encoding='utf-8', timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
