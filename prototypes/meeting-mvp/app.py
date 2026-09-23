import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from copy import deepcopy
from datetime import date, datetime

import pandas as pd
import streamlit as st
from config import ROOT, DATA_DIR, model_status, offline_env, runtime_notice
from core import read_json, write_json, stamp, text_segments, transcript_text
from export_docx import build_docx
from review import save_review_file, validate_review
from process_utils import stop_process_tree, worker_popen_kwargs

st.set_page_config(page_title='Хаттама · Протокол совещания', page_icon='◉', layout='wide')
DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(DATA_DIR, 0o700)

def local_audio_path(value):
    if not isinstance(value, str):
        return None
    candidate = Path(value).resolve()
    return str(candidate) if candidate.is_relative_to(DATA_DIR) and candidate.is_file() else None

# Apply a restore before any widgets with the same keys are instantiated.
if st.session_state.get('restore_file'):
    saved_path = Path(st.session_state.pop('restore_file'))
    saved = read_json(saved_path)
    restored_id = saved_path.stem.removeprefix('review-')
    st.session_state.doc_id = restored_id
    st.session_state.save_id = restored_id
    st.session_state.transcript = saved['transcript']
    st.session_state.original = saved.get('original')
    st.session_state.audio_path = local_audio_path(saved.get('audio_path'))
    original = saved.get('original') or {}
    st.session_state.original_transcript = original.get('transcript', saved['transcript'])
    st.session_state.original_analysis = original.get('analysis', saved.get('analysis'))
    st.session_state.meeting_title = saved.get('title','Совещание')
    st.session_state.meeting_date = date.fromisoformat(saved['meeting_date']) if saved.get('meeting_date') else None
    for speaker, name in saved.get('names',{}).items():
        st.session_state[f'name-{st.session_state.doc_id}-{speaker}'] = name
    for field in ['analysis','analysis_hash']:
        st.session_state.pop(field,None)
        if saved.get(field) is not None:
            st.session_state[field] = saved[field]
    st.session_state.analysis_id = uuid.uuid4().hex[:8]
    st.session_state.setdefault('saved_files',[]).append(str(saved_path))
    if st.session_state.audio_path:
        st.session_state.setdefault('runs',[]).append(str(Path(st.session_state.audio_path).parent))

st.markdown('''<style>
:root{
  --ivory:#f6f5f0;
  --forest:#173d35;
  --green:#26725c;
  --ink:#1d302a;
  --muted:#6b7b73;
  --line:#d9dfd5;
  --panel:#fffdf7;
}
.stApp{background:var(--ivory);color:var(--ink);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
[data-testid="stSidebar"]{background:var(--forest);color:#f6f5f0}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span{color:#f6f5f0}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] textarea{color:var(--ink);background:#fffdf7}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#d6e3dc}
[data-testid="stSidebar"] [data-testid="stExpander"]{background:#214b41;border:1px solid rgba(246,245,240,.18);border-radius:8px}
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] summary *{color:#f6f5f0}
[data-testid="stSidebar"] .stButton>button{background:#f6f5f0;color:var(--forest);border-color:#d6e3dc}
[data-testid="stSidebar"] .stButton>button *{color:var(--forest)}
[data-testid="stSidebar"] [data-baseweb="select"] *{color:var(--ink)}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] [data-testid="stMarkdownContainer"] p{color:#f6f5f0}
.block-container{max-width:1180px;padding-top:3.25rem;padding-bottom:3rem}
h1,h2,h3{letter-spacing:0;color:var(--forest);font-weight:720}
.eyebrow{font-size:12px;letter-spacing:.16em;color:var(--green);text-transform:uppercase;font-weight:800}
.hero{font-size:44px;font-weight:760;line-height:1.08;margin:10px 0 14px;color:var(--forest)}
.hero.compact{font-size:28px;margin:4px 0 4px}
.lead{font-size:17px;color:#51635b;max-width:760px;line-height:1.55;margin-bottom:20px}
.pill{display:inline-block;border:1px solid #bdd1c6;background:#edf4ef;color:var(--forest);border-radius:999px;padding:6px 12px;font-size:12px;font-weight:700}
.stepbar{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:20px 0 18px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.step strong{display:block;color:var(--forest);font-size:14px}
.step span{display:block;color:var(--muted);font-size:12px;margin-top:3px}
.step.active{border-color:var(--green);box-shadow:inset 0 0 0 1px var(--green)}
.section-note{color:var(--muted);font-size:14px;margin-top:-8px;margin-bottom:14px}
.stButton>button{border-radius:8px;border-color:#b9c8bf}
.stButton>button[kind="primary"]{background:var(--green);border-color:var(--green);color:white}
[data-testid="stMetric"],[data-testid="stFileUploader"],[data-testid="stDataFrame"],[data-testid="stExpander"]{background:var(--panel);border-radius:8px}
[data-testid="stDataFrame"]{border:1px solid var(--line)}
@media (max-width:760px){
  .block-container{padding-top:4rem}
  .hero{font-size:30px;line-height:1.12}
  .hero.compact{font-size:24px}
  .lead{font-size:15px}
  .stepbar{grid-template-columns:1fr;gap:8px}
  .step{padding:10px 12px}
}
footer{visibility:hidden}
[data-testid="stAppDeployButton"]{display:none}
</style>''', unsafe_allow_html=True)

def stepbar(active):
    labels = [('01','Запись','аудио или текст'),('02','Проверка','участники и реплики'),('03','Протокол','поручения и экспорт')]
    html = ['<div class="stepbar">']
    for number, title, caption in labels:
        css = 'step active' if number == active else 'step'
        html.append(f'<div class="{css}"><strong>{number} · {title}</strong><span>{caption}</span></div>')
    html.append('</div>')
    st.markdown(''.join(html), unsafe_allow_html=True)

def analysis_disabled_reason(available, busy, segments):
    if busy:
        return 'Дождитесь завершения текущей обработки.'
    if not segments:
        return 'Сначала добавьте запись или текст.'
    if not available['Поручения и саммари']:
        return 'Модель поручений недоступна локально. Можно сохранить транскрипт или открыть синтетический пример.'
    return ''

def digest(segments, names, day):
    return hashlib.sha256(json.dumps([segments,names,day],ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def new_transcript(data, audio_path=None):
    st.session_state.doc_id = uuid.uuid4().hex[:8]
    st.session_state.pop('save_id', None)
    st.session_state.transcript = data
    st.session_state.original_transcript = json.loads(json.dumps(data))
    st.session_state.pop('original_analysis', None)
    st.session_state.audio_path = str(audio_path) if audio_path else None
    st.session_state.original = {'transcript':deepcopy(data), 'analysis':None}
    st.session_state.pop('analysis',None)
    st.session_state.pop('analysis_hash',None)

def save_review(title, meeting_date, transcript, segments, names, current_hash, analysis=None):
    destination = DATA_DIR / f"review-{st.session_state.get('save_id', st.session_state.doc_id)}.json"
    save_review_file(destination, title=title, meeting_date=meeting_date, transcript=transcript,
        segments=segments, names=names, current_hash=current_hash,
        audio_path=st.session_state.get('audio_path'), analysis=analysis,
        original_transcript=(st.session_state.get('original') or {}).get('transcript',
                            st.session_state.get('original_transcript', transcript)),
        original_analysis=(st.session_state.get('original') or {}).get('analysis',
                          st.session_state.get('original_analysis', st.session_state.get('analysis'))))
    st.session_state.save_id = destination.stem.removeprefix('review-')
    st.session_state.setdefault('saved_files',[]).append(str(destination))
    st.success('Сохранено на этом компьютере. Можно открыть из списка в боковой панели.')

def start_job(kind, request, upload=None):
    run = DATA_DIR / uuid.uuid4().hex
    run.mkdir(mode=0o700)
    if upload is not None:
        suffix = Path(upload.name).suffix.lower()
        request['audio_name'] = 'input'+suffix
        (run/request['audio_name']).write_bytes(upload.getbuffer())
    write_json(run/'request.json',request)
    write_json(run/'status.json',{'schema_version':1,'run_id':run.name,'kind':kind,'state':'running','label':'Запускаем обработку','progress':0,
                                  'created_at':datetime.now().isoformat(timespec='seconds')})
    with (run/'worker.log').open('w') as log:
        proc = subprocess.Popen([sys.executable,str(ROOT/'engine.py'),kind,str(run)],
            stdout=log,stderr=log,env=offline_env(),**worker_popen_kwargs())
    st.session_state.job = {'run':str(run),'kind':kind,'proc':proc,'hash':request.get('hash')}
    st.session_state.setdefault('runs',[]).append(str(run))

def managed_runs():
    result=[]
    for run in DATA_DIR.iterdir() if DATA_DIR.exists() else []:
        if not run.is_dir() or run.is_symlink() or len(run.name) != 32:
            continue
        try:
            status=read_json(run/'status.json')
            if status.get('schema_version') == 1 and status.get('run_id') == run.name:
                result.append((run,status))
        except (OSError, ValueError, KeyError):
            continue
    return sorted(result,key=lambda item:item[0].stat().st_mtime,reverse=True)

def recover_run(run, status):
    """Restore only a complete, validated artifact; incomplete work is never resumed."""
    if status.get('state') != 'done':
        return False
    try:
        if status.get('kind') == 'audio' and (run/'transcript.json').is_file() and (run/'audio.wav').is_file():
            new_transcript(read_json(run/'transcript.json'),run/'audio.wav')
        elif status.get('kind') == 'analysis' and (run/'analysis.json').is_file():
            request = read_json(run/'request.json')
            if not isinstance(request.get('segments'), list):
                return False
            new_transcript({'segments':request['segments'],'source':request.get('source','recovered_analysis'),
                            'duration':None,'warnings':request.get('warnings',[])},
                           local_audio_path(request.get('audio_path')))
            st.session_state.meeting_date = date.fromisoformat(request['meeting_date']) if request.get('meeting_date') else None
            for speaker, name in request.get('names', {}).items():
                st.session_state[f'name-{st.session_state.doc_id}-{speaker}'] = name
            st.session_state.analysis=read_json(run/'analysis.json')
            st.session_state.original = {'transcript':request.get('original_transcript'),
                                         'analysis':deepcopy(st.session_state.analysis)}
            st.session_state.original_analysis = json.loads(json.dumps(st.session_state.analysis))
            st.session_state.analysis_hash=request.get('hash')
            st.session_state.analysis_id=uuid.uuid4().hex[:8]
        else:
            return False
        st.session_state.setdefault('runs',[]).append(str(run))
        return True
    except (OSError, ValueError, KeyError):
        return False

@st.fragment(run_every=2)
def job_monitor():
    job = st.session_state.get('job')
    if not job:
        return
    run = Path(job['run'])
    status = read_json(run/'status.json')
    if status['state']=='running' and job['proc'].poll() is not None:
        status = {'state':'error','label':'Обработка прервана. Проверьте журнал и свободную память.'}
    if status['state']=='running':
        st.info(status.get('label','Обработка выполняется.'))
        st.caption('Можно оставить эту страницу открытой. Обработка выполняется на вашем компьютере.')
        if st.button('Остановить обработку'):
            stop_process_tree(job['proc'])
            st.session_state.pop('job')
            st.rerun()
    elif status['state']=='done':
        if job['kind']=='audio':
            new_transcript(read_json(run/'transcript.json'),run/'audio.wav')
        else:
            st.session_state.analysis = read_json(run/'analysis.json')
            original = deepcopy(st.session_state.get('original') or {'transcript':None})
            original['analysis'] = deepcopy(st.session_state.analysis)
            st.session_state.original = original
            st.session_state.original_analysis = json.loads(json.dumps(st.session_state.analysis))
            st.session_state.analysis_hash = job['hash']
            st.session_state.analysis_id = uuid.uuid4().hex[:8]
        st.session_state.last_elapsed = status.get('elapsed_seconds')
        st.session_state.pop('job')
        st.rerun()
    else:
        st.error(status['label'])
        st.caption('Технические подробности сохранены в локальном журнале обработки.')
        if st.button('Закрыть ошибку'):
            st.session_state.pop('job')
            st.rerun()

if st.session_state.get('restore_run'):
    requested_run = st.session_state.pop('restore_run')
    selected = next((pair for pair in managed_runs() if str(pair[0]) == requested_run), None)
    if not selected or not recover_run(*selected):
        st.error('В выбранной задаче нет корректного завершённого результата.')

with st.sidebar:
    st.markdown('### ◉ Хаттама')
    st.caption('Локальный помощник секретаря')
    st.divider()
    st.markdown('**Совещание**')
    title = st.text_input('Название',value='Рабочее совещание',key='meeting_title')
    day = st.date_input('Дата совещания',value=None,key='meeting_date',help='Нужна для сроков «до пятницы». Не подставляем дату автоматически.')
    meeting_date = day.isoformat() if day else None
    count = st.number_input('Число говорящих',min_value=0,max_value=20,value=0,
        help='0 — определить автоматически. Указывайте только тех, чей голос есть в записи.')
    st.divider()
    available = model_status()
    ready_count = sum(1 for ready in available.values() if ready)
    st.caption(f'Локальная готовность: {ready_count}/{len(available)}')
    with st.expander('Диагностика моделей', expanded=False):
        for name, ready in available.items():
            st.caption(('● ' if ready else '○ ')+name+(' · готово' if ready else ' · недоступно'))
        if runtime_notice():
            st.warning(runtime_notice())
    st.caption('Данные хранятся локально. Обработка не обращается к облачным API.')
    st.caption('Для показа третьим лицам используйте обезличенные записи. Синтетический текст доступен ниже.')
    saved_options = {}
    for saved_path in sorted(DATA_DIR.glob('review-*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            record=read_json(saved_path)
            saved_options[str(saved_path)] = record.get('title','Совещание')+' · '+record.get('saved_at','')
        except (ValueError,OSError):
            continue
    with st.expander('Сохранения и восстановление', expanded=bool(saved_options)):
        if saved_options:
            saved_choice = st.selectbox('Сохранённые результаты',options=list(saved_options),format_func=saved_options.get,
                                       disabled=bool(st.session_state.get('job')))
            if st.button('Открыть сохранённое',disabled=bool(st.session_state.get('job'))):
                st.session_state.restore_file = saved_choice
                st.rerun()
            if st.button('Удалить выбранное сохранение',disabled=bool(st.session_state.get('job'))):
                candidate=Path(saved_choice).resolve()
                if candidate.parent == DATA_DIR and candidate.name.startswith('review-') and candidate.suffix == '.json' and not candidate.is_symlink():
                    candidate.unlink(missing_ok=True)
                    st.success('Сохранение удалено.')
                    st.rerun()
        else:
            st.caption('Сохранённые протоколы появятся здесь.')
        completed = [(run,status) for run,status in managed_runs() if status.get('state') == 'done']
        if completed:
            recovery = st.selectbox('Завершённые задачи для восстановления',options=[str(run) for run,_ in completed],
                format_func=lambda value: Path(value).name)
            if st.button('Восстановить результат',disabled=bool(st.session_state.get('job'))):
                st.session_state.restore_run = recovery
                st.rerun()
            if st.button('Удалить выбранную завершённую задачу',disabled=bool(st.session_state.get('job'))):
                candidate=Path(recovery).resolve()
                if candidate.parent == DATA_DIR and len(candidate.name) == 32 and candidate.is_dir() and not candidate.is_symlink():
                    shutil.rmtree(candidate)
                    st.success('Локальные файлы задачи удалены.')
                    st.rerun()
    if st.button('Удалить данные текущей сессии',disabled=bool(st.session_state.get('job'))):
        for run in st.session_state.get('runs',[]):
            candidate=Path(run).resolve()
            if candidate.is_relative_to(DATA_DIR) and candidate != DATA_DIR:
                shutil.rmtree(candidate,ignore_errors=True)
        for saved_file in st.session_state.get('saved_files',[]):
            candidate=Path(saved_file).resolve()
            if candidate.is_relative_to(DATA_DIR):
                candidate.unlink(missing_ok=True)
        for key in list(st.session_state):
            del st.session_state[key]
        st.rerun()

has_transcript = 'transcript' in st.session_state
st.markdown('<div class="eyebrow">Аудио → решения → действия</div>',unsafe_allow_html=True)
if has_transcript:
    st.markdown('<div class="hero compact">Проверьте реплики и протокол</div>',unsafe_allow_html=True)
    st.markdown('<div class="lead">Дальше всё зависит от проверенных источников: участники, исходные реплики и текущий список поручений.</div>',unsafe_allow_html=True)
else:
    st.markdown('<div class="hero">Совещание заканчивается.<br>Поручения остаются.</div>',unsafe_allow_html=True)
    st.markdown('<div class="lead">Превратите запись в протокол. Проверьте участников, уточните сроки и передайте команде понятный список действий.</div>',unsafe_allow_html=True)
st.markdown('<span class="pill">● На вашем компьютере · RU / KZ / смешанная речь</span>',unsafe_allow_html=True)
st.write('')

busy = bool(st.session_state.get('job'))
stepbar('01' if 'transcript' not in st.session_state else ('03' if 'analysis' in st.session_state else '02'))
with st.expander('1 · Добавить запись или текст',expanded='transcript' not in st.session_state):
    audio_tab,text_tab = st.tabs(['Аудиозапись','Готовый текст / демо'])
    with audio_tab:
        uploaded = st.file_uploader('Запись совещания',type=['mp3','wav','m4a','ogg','flac','mp4'],disabled=busy)
        st.caption('До 30 минут и 200 МБ. Участники должны быть уведомлены о записи и обработке.')
        audio_reason = ''
        if busy:
            audio_reason = 'Дождитесь завершения текущей обработки.'
        elif uploaded is None:
            audio_reason = 'Выберите аудиофайл, чтобы начать распознавание.'
        elif not all(list(available.values())[:2]):
            audio_reason = 'Для распознавания нужны локальные модели речи и разделения говорящих.'
        if audio_reason:
            st.caption(audio_reason)
        if st.button('Распознать запись',type='primary',disabled=bool(audio_reason)):
            start_job('audio',{'num_speakers':int(count) if count else -1},uploaded)
            st.rerun()
    with text_tab:
        st.caption('Этот режим анализирует предоставленный текст. Распознавание речи и диаризация в нём не выполняются.')
        demo = 'Руководитель: Алия, подготовьте отчёт по закупкам до 15 октября.\nАлия: Хорошо, подготовлю.\nРуководитель: Претензию поставщику пусть подготовит юрист Ерлан до пятницы.\nРуководитель: Тимур, согласуйте бюджет с отделом безопасности.\nТимур: Принято. Срок пока не определён.'
        raw_text = st.text_area('Текст реплик',height=180,max_chars=40000,placeholder='Вставьте транскрипт с именами участников',disabled=busy)
        a,b = st.columns(2)
        if a.button('Открыть текст',disabled=busy or not raw_text.strip()):
            new_transcript({'segments':text_segments(raw_text),'source':'imported_text','duration':None,'warnings':[]})
            st.rerun()
        if b.button('Синтетический пример',disabled=busy):
            new_transcript({'segments':text_segments(demo),'source':'synthetic_text','duration':None,
                'warnings':['Синтетический текст. Не является результатом распознавания аудио.']})
            st.rerun()

job_monitor()
if 'transcript' not in st.session_state:
    st.write('')
    a,b,c = st.columns(3)
    a.metric('01 · Реплики','Кто что сказал')
    b.metric('02 · Поручения','Кто и к какому сроку')
    c.metric('03 · Протокол','Документ для проверки')
    st.stop()

data = st.session_state.transcript
doc_id = st.session_state.doc_id
if not data['segments']:
    st.warning('Речь не обнаружена. Проверьте запись или импортируйте исправленный текст.')
    st.stop()
for warning in data.get('warnings',[]):
    st.text(warning)
if st.session_state.get('audio_path'):
    st.audio(st.session_state.audio_path)

st.subheader('2 · Проверьте участников и реплики')
speakers = sorted({s['speaker'] for s in data['segments']})
names = {}
with st.expander('Имена говорящих',expanded=data['source']=='audio'):
    st.caption('Голос определяет метку участника, но не его имя. Укажите имя после прослушивания. Ответственный может отсутствовать в записи.')
    for i,speaker in enumerate(speakers):
        if speaker in ('UNKNOWN','OVERLAP'):
            names[speaker] = 'Говорящий не определён' if speaker=='UNKNOWN' else 'Наложение голосов'
        else:
            names[speaker] = st.text_input(speaker,placeholder=f'Имя участника {i+1}',key=f'name-{doc_id}-{speaker}',disabled=busy).strip() or speaker

rows = [{'id':s['id'],'start':s['start'],'end':s['end'],'speaker':s['speaker'],'text':s['text']} for s in data['segments']]
edited = st.data_editor(pd.DataFrame(rows,columns=['id','start','end','speaker','text']),hide_index=True,width='stretch',
    disabled=True if busy else ['id','start','end'],key=f'transcript-{doc_id}',
    column_config={'id':st.column_config.TextColumn('ID реплики'),
        'start':st.column_config.NumberColumn('Начало, сек',format='%.1f'),
        'end':None,'speaker':st.column_config.SelectboxColumn('Говорящий',options=speakers,required=True),
        'text':st.column_config.TextColumn('Реплика',width='large',required=True)})
segments = json.loads(edited.to_json(orient='records',force_ascii=False))
current_hash = digest(segments,names,meeting_date)
st.download_button('Скачать транскрипт TXT',transcript_text(segments,names),file_name='transcript.txt',mime='text/plain')
save_transcript = st.button('Сохранить транскрипт локально',disabled=busy)
analysis_reason = analysis_disabled_reason(available, busy, segments)
if analysis_reason:
    st.caption(analysis_reason)
if st.button('Сформировать поручения и саммари',type='primary',disabled=bool(analysis_reason)):
    start_job('analysis',{'segments':segments,'names':names,'meeting_date':meeting_date,'hash':current_hash,
                         'source':data.get('source'),'warnings':data.get('warnings',[]),
                         'audio_path':local_audio_path(st.session_state.get('audio_path')),
                         'original_transcript':(st.session_state.get('original') or {}).get('transcript')})
    st.rerun()

if 'analysis' not in st.session_state:
    if save_transcript:
        save_review(title,meeting_date,data,segments,names,current_hash)
    st.stop()
st.subheader('3 · Проверьте протокол')
analysis = st.session_state.analysis
stale = st.session_state.get('analysis_hash') != current_hash
if stale:
    st.warning('Протокол не подтверждён для текущих реплик, имён и даты. Сформируйте поручения заново перед экспортом.')
for warning in analysis.get('warnings',[]):
    st.text(warning)
aid = st.session_state.analysis_id
summary = st.text_area('Краткое содержание',value=analysis.get('summary',''),height=180,key=f'summary-{aid}',disabled=busy)
source_control_cols = ['quote','start','source_ids']
task_cols = ['task','owner','due_text','due_date','review','status']
base_tasks = analysis.get('tasks',[])
table = pd.DataFrame([{column: task.get(column,'') for column in task_cols} for task in base_tasks],columns=task_cols)
for column in ['task', 'owner', 'due_text', 'due_date', 'review', 'status']:
    table[column] = table[column].fillna('').astype(str)
tasks_edit = st.data_editor(table,hide_index=True,width='stretch',num_rows='dynamic',key=f'tasks-{aid}',
    disabled=busy,column_config={
        'task':st.column_config.TextColumn('Поручение',width='large',required=True),
        'owner':st.column_config.TextColumn('Ответственный'),
        'due_text':st.column_config.TextColumn('Срок из речи'),
        'due_date':st.column_config.TextColumn('Дата YYYY-MM-DD'),
        'review':st.column_config.TextColumn('Уточнить'),
        'status':st.column_config.SelectboxColumn('Статус',options=['На проверке','В работе','Выполнено'])})
edited_rows = json.loads(tasks_edit.to_json(orient='records',force_ascii=False))
tasks = []
for index, row in enumerate(edited_rows):
    if not row.get('task'):
        continue
    base = base_tasks[index] if index < len(base_tasks) and isinstance(base_tasks[index], dict) else {}
    preserved = {column: base.get(column) for column in source_control_cols if column in base}
    tasks.append({**preserved, **row})
with st.expander('Выбрать источники и проверить поручения', expanded=True):
    source_labels = {s['id']: f"{s['id']} · {s['text'][:160]}" for s in segments}
    for i, t in enumerate(tasks, 1):
        st.text(f"{i}. {t['task']}")
        selected = t.get('source_ids') if isinstance(t.get('source_ids'), list) else []
        task_key = hashlib.sha256(t['task'].encode()).hexdigest()[:12]
        t['source_ids'] = st.multiselect('Исходные реплики', options=list(source_labels),
            default=[source for source in selected if source in source_labels],
            format_func=source_labels.get, key=f'sources-{aid}-{i}-{task_key}', disabled=busy)
        selected_rows = [s for s in segments if s['id'] in t['source_ids']]
        for source in selected_rows:
            st.text(f"[{source['id']}] {source['text']}")
        starts = [s['start'] for s in selected_rows if s['start'] is not None]
        if starts and st.session_state.get('audio_path'):
            st.audio(st.session_state.audio_path,start_time=max(0,int(min(starts))-1))

final = {**analysis,'summary':summary,'tasks':tasks}
valid = True
try:
    final = validate_review(final, segments)
except ValueError as error:
    valid = False
    st.error(str(error))
st.caption('Экспортируется проверяемый черновик с текущими правками. Сохраните протокол, чтобы открыть эти правки позже.')
if save_transcript:
    save_review(title,meeting_date,data,segments,names,
                st.session_state.get('analysis_hash') if stale else current_hash)
include = st.checkbox('Включить транскрипт в DOCX',value=True)
if not stale and valid:
    if st.button('Сохранить протокол и правки локально',disabled=busy):
        save_review(title,meeting_date,data,segments,names,current_hash,final)
    docx = build_docx(title,meeting_date,final,segments,names,include,source=data.get('source'))
    a,b = st.columns(2)
    a.download_button('Скачать протокол DOCX',docx,file_name='meeting-protocol.docx',
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',type='primary')
    b.download_button('Скачать поручения JSON',json.dumps({'title':title,'meeting_date':meeting_date,
        'source':data.get('source'),**final},ensure_ascii=False,indent=2),
        file_name='meeting-tasks.json',mime='application/json')
