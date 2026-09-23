"""Regression coverage for local review; all meeting content here is synthetic."""
import os
from pathlib import Path
import subprocess
import sys
import pytest


PREAMBLE = r'''
import hashlib, json, os
from pathlib import Path
from streamlit.testing.v1 import AppTest
folder = Path(os.environ['MEETING_DATA_DIR'])
folder.mkdir(parents=True)
segments = [{'id':'S1', 'speaker':'SPEAKER_00', 'start':0.0, 'end':1.0,
             'text':'Синтетическая реплика для теста.'}]
names = {'SPEAKER_00':'Айжан'}
day = '2026-09-23'
key = hashlib.sha256(json.dumps([segments,names,day],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
analysis = {'summary':'Синтетическое саммари', 'tasks':[{'task':'Тестовое поручение',
    'owner':'Айжан','due_date':'2026-09-24','due_text':'завтра','review':'Проверить',
    'status':'На проверке','quote':'Синтетическая цитата','source_ids':['S1'],'start':0.0}],
    'warnings':[]}
def write(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
def saved():
    write(folder/'review-fixture.json', {'version':1,'title':'Синтетический тест',
        'meeting_date':day,'transcript':{'source':'synthetic_text','segments':segments,'warnings':[]},
        'names':names,'audio_path':None,'analysis':analysis,'analysis_hash':key,
        'original':{'transcript':{'source':'synthetic_text','segments':segments},'analysis':analysis}})
def open_saved():
    at = AppTest.from_file('app.py',default_timeout=20).run()
    next(b for b in at.button if b.label=='Открыть сохранённое').click().run()
    assert not at.exception
    return at
'''


def run_ui(tmp_path, script):
    result = subprocess.run([sys.executable, '-c', PREAMBLE + script],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding='utf-8',
        env={**os.environ, 'MEETING_DATA_DIR':str(tmp_path/'data'),
             'MEETING_MODEL_DIR':str(tmp_path/'models'), 'PYTHONUTF8':'1'}, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def test_completed_analysis_recovers_date_before_widgets(tmp_path):
    run_ui(tmp_path, r'''
run = folder / ('a'*32)
run.mkdir()
import wave
audio = run/'audio.wav'
with wave.open(str(audio),'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(16000)
    wav.writeframes(b'\x00\x00'*16000)
original_transcript = {'segments':segments,'source':'synthetic_text'}
write(run/'status.json',{'schema_version':1,'run_id':run.name,'kind':'analysis','state':'done'})
write(run/'request.json',{'segments':segments,'names':names,'meeting_date':day,'hash':key,
    'source':'synthetic_text','warnings':['Синтетический тест'],
    'original_transcript':original_transcript,'audio_path':str(audio)})
write(run/'analysis.json',analysis)
at = AppTest.from_file('app.py',default_timeout=20).run()
next(b for b in at.button if b.label=='Восстановить результат').click().run()
assert not at.exception, at.exception
assert at.session_state.meeting_date.isoformat()==day
assert at.session_state.analysis['summary']==analysis['summary']
assert at.session_state.audio_path==str(audio.resolve())
assert at.session_state.transcript['source']=='synthetic_text'
assert at.session_state.transcript['warnings']==['Синтетический тест']
assert at.session_state.original=={'transcript':original_transcript,'analysis':analysis}
''')


def test_transcript_save_does_not_erase_reviewed_protocol(tmp_path):
    run_ui(tmp_path, r'''
saved()
at = open_saved()
next(t for t in at.text_area if t.label=='Краткое содержание').set_value('Исправленное тестовое саммари')
next(b for b in at.button if b.label=='Сохранить протокол и правки локально').click().run()
assert not at.exception
record_path = folder/f'review-{at.session_state.doc_id}.json'
before = json.loads(record_path.read_text(encoding='utf-8'))
next(b for b in at.button if b.label=='Сохранить транскрипт локально').click().run()
assert not at.exception
after = json.loads(record_path.read_text(encoding='utf-8'))
assert after['analysis']==before['analysis']
assert after['analysis']['summary']=='Исправленное тестовое саммари'
assert after['original']['analysis']['summary']=='Синтетическое саммари'
assert after['original']==before['original']
''')


def test_meeting_text_is_not_rendered_as_markdown(tmp_path):
    run_ui(tmp_path, r'''
unsafe = '![synthetic](https://invalid.example/meeting-content)'
analysis['tasks'][0]['task'] = unsafe
analysis['tasks'][0]['quote'] = unsafe
analysis['warnings'] = [unsafe]
saved()
at = open_saved()
assert all(unsafe not in m.value for m in at.markdown)
assert all(unsafe not in m.value for m in at.warning)
assert any(unsafe in t.value for t in at.text)
''')


@pytest.mark.parametrize('missing', [True, False])
def test_legacy_review_without_hash_stays_stale_after_save_and_reopen(tmp_path, missing):
    run_ui(tmp_path, 'missing = ' + repr(missing) + '\n' + r'''
analysis['tasks'] = []
saved()
record = json.loads((folder/'review-fixture.json').read_text(encoding='utf-8'))
if missing:
    record.pop('analysis_hash')
else:
    record['analysis_hash'] = None
write(folder/'review-fixture.json', record)
at = open_saved()
assert any('заново перед экспортом' in warning.value for warning in at.warning)
assert len(at.get('download_button')) == 1  # transcript only, no protocol export
next(b for b in at.button if b.label=='Сохранить транскрипт локально').click().run()
assert not at.exception
record_path = folder/f'review-{at.session_state.doc_id}.json'
after = json.loads(record_path.read_text(encoding='utf-8'))
assert after['analysis_hash'] is None
assert after['analysis']['tasks'] == []
at.session_state.restore_file = str(record_path)
at.run()
assert not at.exception
assert any('заново перед экспортом' in warning.value for warning in at.warning)
assert len(at.get('download_button')) == 1
''')
