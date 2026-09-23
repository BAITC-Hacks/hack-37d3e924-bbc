import pytest
from ai.audio import windows,owned_words,deduplicate_words,align
from ai.extraction import resolve_date,checked_tasks,merge_tasks,segment_batches,parse_json
from ai.errors import PipelineError

DT='2026-09-23T23:30:00+05:00'
@pytest.mark.parametrize('phrase,expected',[
    ('завтра','2026-09-24'),('к завтрашнему дню','2026-09-24'),('ертеңге дейін','2026-09-24'),
    ('через неделю','2026-09-30'),('бір апта ішінде','2026-09-30'),
    ('екі аптадан кейін','2026-10-07'),('үш күн ішінде','2026-09-26'),
    ('через 3 дня','2026-09-26'),('3 күн ішінде','2026-09-26'),('до 25 сентября 2026','2026-09-25'),
    ('2026-09-25','2026-09-25'),('до 25.09.2026','2026-09-25'),
    ('пятница',None),('до конца недели',None),('после согласования',None),('30.02.2026',None),
    ('завтра или послезавтра',None),('за три рабочих дня',None),
])
def test_dates(phrase,expected):
    assert resolve_date(phrase,DT,'Asia/Almaty')==expected

def test_long_boundary_times_and_repetitions():
    # Same word returned in two overlap contexts belongs to exactly one core window.
    source=[{'start':23.7,'end':24.3,'text':'отчёт'}, {'start':24.4,'end':24.7,'text':'да'},
            {'start':24.8,'end':25.1,'text':'да'}, {'start':48,'end':48.5,'text':'дайын'}]
    out=[]
    for a,b,left,right in windows(55):
        out+=owned_words([w for w in source if w['start']>=left and w['end']<=right],a,b)
    assert deduplicate_words(out)==source
    turns=[{'start':0,'end':30,'speaker_id':'A'},{'start':30,'end':55,'speaker_id':'B'}]
    segments,_=align(out,turns)
    assert segments[0]['start']==23.7 and segments[-1]['start']==48
    assert [s['speaker_id'] for s in segments]==['A','B']
    assert 'да да' in segments[0]['text']

def test_alignment_does_not_invent_speaker():
    segments,uncertain=align([{'start':0,'end':1,'text':'слово'}],[])
    assert uncertain and segments[0]['speaker_id']=='SPEAKER_UNKNOWN'

def test_owner_is_not_speaker_and_quotes_required():
    req={'meeting_datetime':DT,'timezone':'Asia/Almaty'}
    people=[{'id':'boss','name':'Марсель','speaker_ids':['A']},{'id':'p2','name':'Айжан','speaker_ids':[]}]
    segments=[{'id':'s1','speaker_id':'A','text':'Айжан, подготовь отчёт к завтрашнему дню.'}]
    raw={'summary':'Отчёт','tasks':[{'text':'Подготовить отчёт','owner':'Айжан','due_text':'к завтрашнему дню','source_segment_ids':['s1']}]}
    task=checked_tasks(raw,segments,people,req)[0]
    assert task['assignee_id']=='p2' and task['due_date']=='2026-09-24'
    raw['tasks'][0].update(owner='Марсель',due_text='2026-09-25')
    task=checked_tasks(raw,segments,people,req)[0]
    assert task['assignee_id'] is None and task['due_date'] is None and task['needs_review']
    raw['tasks'][0]['source_segment_ids']=['injected']
    with pytest.raises(PipelineError):checked_tasks(raw,segments,people,req)

def test_unknown_deadline_not_model_invention():
    assert resolve_date('к 25 сентября',DT,'Asia/Almaty') is None

def test_task_dedup_keeps_distinct_actions():
    tasks=[{'id':'pending','text':t,'assignee_id':'p1','due_date':None,'source_segment_ids':['s1'],'needs_review':True}
            for t in ['Подготовить отчёт','Подготовить отчёт','Проверить бюджет']]
    merged=merge_tasks(tasks)
    assert len(merged)==2 and [t['id'] for t in merged]==['t1','t2']

def test_bounded_text_batches_cover_all_segments():
    source=[{'id':f's{i}'} for i in range(10)]
    batches=list(segment_batches(source,lambda c:len(c)<=3))
    assert all(len(c)<=3 for c in batches)
    assert {s['id'] for c in batches for s in c}=={s['id'] for s in source}

def test_malformed_json_fails():
    with pytest.raises(PipelineError):parse_json('not a result')
