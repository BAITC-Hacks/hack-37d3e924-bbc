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
from core import read_json, write_json, stamp, text_segments, transcript_text, validate_review
from export_docx import build_docx
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
    restored_id = uuid.uuid4().hex[:8]
    st.session_state.doc_id = restored_id
    st.session_state.transcript = saved['transcript']
    st.session_state.original = saved.get('original')
    st.session_state.audio_path = local_audio_path(saved.get('audio_path'))
    st.session_state.meeting_title = saved.get('title','Совещание')
    st.session_state.meeting_date = date.fromisoformat(saved['meeting_date']) if saved.get('meeting_date') else None
    for speaker, name in saved.get('names',{}).items():
        st.session_state[f'name-{restored_id}-{speaker}'] = name
    for field in ['analysis','analysis_hash']:
        st.session_state.pop(field,None)
        if saved.get(field) is not None:
            st.session_state[field] = saved[field]
    st.session_state.analysis_id = uuid.uuid4().hex[:8]
    st.session_state.setdefault('saved_files',[]).append(str(saved_path))
    if st.session_state.audio_path:
        st.session_state.setdefault('runs',[]).append(str(Path(st.session_state.audio_path).parent))

st.markdown('''<style>
.stApp{background:#f6f5f0;color:#202e31}
[data-testid="stSidebar"]{background:#e9ece5}
.block-container{max-width:1200px;padding-top:2.8rem}
h1,h2,h3{letter-spacing:-.035em;color:#183c38}
.eyebrow{font-size:12px;letter-spacing:.18em;color:#687b71;text-transform:uppercase;font-weight:700}
.hero{font-size:48px;font-weight:650;line-height:1.12;letter-spacing:-.05em;margin:12px 0 16px;color:#183c38}
.lead{font-size:17px;color:#66716e;max-width:700px;line-height:1.6;margin-bottom:28px}
.pill{display:inline-block;border:1px solid #c6d4c7;background:#edf3e9;color:#41604b;border-radius:100px;padding:5px 12px;font-size:12px}
.stButton>button[kind="primary"]{background:#234e43;border-color:#234e43;border-radius:8px}
[data-testid="stMetric"]{background:#fff;border:1px solid #e0e5dc;border-radius:12px;padding:14px}
[data-testid="stFileUploader"]{background:white;border-radius:12px}
[data-testid="stDataFrame"]{border-radius:10px}
footer{visibility:hidden}
[data-testid="stAppDeployButton"]{display:none}
</style>''', unsafe_allow_html=True)

def digest(segments, names, day):
    return hashlib.sha256(json.dumps([segments,names,day],ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def new_transcript(data, audio_path=None):
    st.session_state.doc_id = uuid.uuid4().hex[:8]
    st.session_state.transcript = data
    st.session_state.audio_path = str(audio_path) if audio_path else None
    st.session_state.original = {'transcript':deepcopy(data), 'analysis':None}
    st.session_state.pop('analysis',None)
    st.session_state.pop('analysis_hash',None)

def save_review(title, meeting_date, transcript, segments, names, current_hash, analysis=None):
    if analysis is not None:
        analysis = validate_review(analysis, segments)
    destination = DATA_DIR/f'review-{st.session_state.doc_id}.json'
    payload = {'version':1,'title':title,'saved_at':datetime.now().isoformat(timespec='seconds'),
               'meeting_date':meeting_date,'transcript':{**transcript,'segments':segments},'names':names,
               'audio_path':st.session_state.get('audio_path'),'analysis':analysis,
               'original':st.session_state.get('original'),
               'analysis_hash':current_hash if analysis is not None else None}
    write_json(destination,payload)
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
        st.progress(float(status.get('progress',0)),text=status['label'])
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
    st.markdown('**Готовность моделей**')
    available = model_status()
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

st.markdown('<div class="eyebrow">Аудио → решения → действия</div>',unsafe_allow_html=True)
st.markdown('<div class="hero">Совещание заканчивается.<br>Поручения остаются.</div>',unsafe_allow_html=True)
st.markdown('<div class="lead">Превратите запись в протокол. Проверьте участников, уточните сроки и передайте команде понятный список действий.</div>',unsafe_allow_html=True)
st.markdown('<span class="pill">● На вашем компьютере · RU / KZ / смешанная речь</span>',unsafe_allow_html=True)
st.write('')

busy = bool(st.session_state.get('job'))
with st.expander('1 · Добавить запись или текст',expanded='transcript' not in st.session_state):
    audio_tab,text_tab = st.tabs(['Аудиозапись','Готовый текст / демо'])
    with audio_tab:
        uploaded = st.file_uploader('Запись совещания',type=['mp3','wav','m4a','ogg','flac','mp4'],disabled=busy)
        st.caption('До 30 минут и 200 МБ. Участники должны быть уведомлены о записи и обработке.')
        if st.button('Распознать запись',type='primary',disabled=busy or uploaded is None or not all(list(available.values())[:2])):
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
if st.button('Сформировать поручения и саммари',type='primary',disabled=busy or not available['Поручения и саммари'] or not segments):
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
task_cols = ['task','owner','due_text','due_date','review','status','quote','start','source_ids']
table = pd.DataFrame(analysis.get('tasks',[]),columns=task_cols)
tasks_edit = st.data_editor(table,hide_index=True,width='stretch',num_rows='dynamic',key=f'tasks-{aid}',
    disabled=True if busy else ['quote','start'],column_config={
        'task':st.column_config.TextColumn('Поручение',width='large',required=True),
        'owner':st.column_config.TextColumn('Ответственный'),
        'due_text':st.column_config.TextColumn('Срок из речи'),
        'due_date':st.column_config.TextColumn('Дата YYYY-MM-DD'),
        'review':st.column_config.TextColumn('Уточнить'),
        'status':st.column_config.SelectboxColumn('Статус',options=['На проверке','В работе','Выполнено']),
        'quote':None,'start':None,
        'source_ids':st.column_config.MultiselectColumn('Исходные реплики',
            options=[s['id'] for s in segments],required=True)})
tasks = json.loads(tasks_edit.to_json(orient='records',force_ascii=False))
tasks = [t for t in tasks if t.get('task')]
try:
    final = validate_review({**analysis,'summary':summary,'tasks':tasks}, segments)
except ValueError as error:
    st.error(str(error))
    st.stop()
tasks = final['tasks']
if save_transcript:
    save_review(title,meeting_date,data,segments,names,
                st.session_state.get('analysis_hash') if stale else current_hash,final)
with st.expander('Проверить поручения по исходным цитатам'):
    for i,t in enumerate(tasks,1):
        st.text(f"{i}. {t['task']}")
        st.text(t.get('quote') or 'Добавлено вручную — укажите основание перед утверждением.')
        if t.get('start') is not None and st.session_state.get('audio_path'):
            st.audio(st.session_state.audio_path,start_time=max(0,int(t['start'])-1))

st.caption('Экспортируется черновик. Проверьте факты и сроки; изменения в таблице попадут в документ.')
include = st.checkbox('Включить транскрипт в DOCX',value=True)
if not stale:
    if st.button('Сохранить протокол и правки локально',disabled=busy):
        save_review(title,meeting_date,data,segments,names,current_hash,final)
    docx = build_docx(title,meeting_date,final,segments,names,include,source=data.get('source'))
    a,b = st.columns(2)
    a.download_button('Скачать протокол DOCX',docx,file_name='meeting-protocol.docx',
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',type='primary')
    b.download_button('Скачать поручения JSON',json.dumps({'title':title,'meeting_date':meeting_date,
        'source':data.get('source'),**final},ensure_ascii=False,indent=2),
        file_name='meeting-tasks.json',mime='application/json')
