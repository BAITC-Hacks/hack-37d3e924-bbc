"""Headless UI regression using synthetic data and no model inference."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from streamlit.testing.v1 import AppTest


def test_source_selection_save_transcript_and_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
    # The first render imports pandas/Arrow and python-docx; allow cold imports
    # while local model inference competes for memory. Later reruns keep 10 s.
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=10).run(timeout=30)
    next(b for b in app.button if b.label == 'Синтетический пример').click().run()
    assert not app.exception
    segments = app.session_state['transcript']['segments']
    names = {'UNKNOWN': 'Говорящий не определён'}
    app.session_state['analysis_hash'] = hashlib.sha256(json.dumps(
        [segments, names, None], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    app.session_state['analysis'] = {'summary': 'Синтетический черновик',
        'tasks': [{'task': 'Подготовить отчёт', 'source_ids': []}]}
    app.session_state['analysis_id'] = 'synthetic-smoke'
    app.run()
    assert not app.exception
    assert any('выберите хотя бы одну' in err.value for err in app.error)
    assert len(app.multiselect) == 1
    app.multiselect[0].select('S0001').run()
    assert not app.exception and not app.error
    next(b for b in app.button if b.label == 'Сохранить протокол и правки локально').click().run()
    assert not app.exception
    path = tmp_path / ('review-' + app.session_state['doc_id'] + '.json')
    first = json.loads(path.read_text())
    next(b for b in app.button if b.label == 'Сохранить транскрипт локально').click().run()
    second = json.loads(path.read_text())
    assert first['analysis'] == second['analysis']
    assert len(second['revisions']) == 2
    next(b for b in app.button if b.label == 'Открыть сохранённое').click().run()
    assert not app.exception
    assert app.session_state['analysis']['tasks'][0]['source_ids'] == ['S0001']
    next(b for b in app.button if b.label == 'Сохранить транскрипт локально').click().run()
    assert len(list(tmp_path.glob('review-*.json'))) == 1
    assert len(json.loads(path.read_text())['revisions']) == 3
