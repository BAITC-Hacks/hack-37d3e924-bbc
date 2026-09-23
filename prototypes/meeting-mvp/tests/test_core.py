import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import due_date, speaker_for, validate_analysis, text_segments, parse_model_json, group_words

def test_dates_do_not_invent_anchor_or_year():
    assert due_date('до пятницы',None) is None
    assert due_date('до пятницы','2026-09-23')=='2026-09-25'
    assert due_date('15 октября',None) is None
    assert due_date('15 октября','2026-09-23')=='2026-10-15'
    assert due_date('15 октября','2026-11-01') is None
    assert due_date('на следующей неделе','2026-09-23') is None
    assert due_date('за две недели','2026-09-23') is None
    assert due_date('15 қазан','2026-09-23')=='2026-10-15'
    assert due_date('к пятнадцатому октября','2026-09-23')=='2026-10-15'
    assert due_date('до двадцать шестого сентября','2026-09-23')=='2026-09-26'
    assert due_date('до тридцатого сентября','2026-09-23')=='2026-09-30'
    assert due_date('31 февраля 2026',None) is None

def test_assignment_is_not_speaker_identity():
    segments=[{'id':'S1','speaker':'BOSS','start':3,'text':'Ерлан подготовит претензию до пятницы.'}]
    raw={'tasks':[{'task':'Подготовить претензию','owner':'Ерлан','due_text':'до пятницы',
        'quote':'Ерлан подготовит претензию до пятницы.','source_ids':['S1']}]}
    result=validate_analysis(raw,segments,{'BOSS':'Руководитель'},'2026-09-23')
    assert result['tasks'][0]['owner']=='Ерлан'
    assert result['tasks'][0]['due_date']=='2026-09-25'

def test_missing_evidence_is_rejected():
    segments=text_segments('Обсудили план закупок.')
    raw={'tasks':[{'task':'Купить оборудование','owner':'Ерлан','quote':'Купите оборудование','source_ids':['S0999']}]}
    assert validate_analysis(raw,segments,{},None)['tasks']==[]

def test_model_cannot_rewrite_source_quotes():
    segments=text_segments('Подготовить уведомление подрядчикам.')
    raw={'tasks':[{'task':'Подготовить уведомление','quote':'Выдуманная цитата','source_ids':['S0001']}]}
    task=validate_analysis(raw,segments,{},None)['tasks'][0]
    assert task['quote']=='[S0001] Подготовить уведомление подрядчикам.'

def test_unknown_owner_deadline_not_fabricated():
    segments=text_segments('Подготовить уведомление подрядчикам.')
    raw={'tasks':[{'task':'Подготовить уведомление','owner':'Иван','due_text':'завтра',
        'quote':'Подготовить уведомление подрядчикам.','source_ids':['S0001']}]}
    task=validate_analysis(raw,segments,{},'2026-09-23')['tasks'][0]
    assert task['owner']==task['due_text']==task['due_date']==''

def test_overlapping_speech_not_assigned_arbitrarily():
    turns=[{'start':0,'end':4,'speaker':'A'},{'start':2,'end':5,'speaker':'B'}]
    assert speaker_for(.5,1,turns)=='A'
    assert speaker_for(2.5,3,turns)=='OVERLAP'
    assert speaker_for(6,7,turns)=='UNKNOWN'

def test_long_import_bounded_and_no_fake_timestamps():
    segments=text_segments('текст '*2000)
    assert len(segments)>1
    assert all(len(s['text'])<=1800 and s['start'] is None for s in segments)

def test_json_and_grouping():
    assert parse_model_json('```json\n{"tasks":[],"summary":"Нет поручений"}\n```')['tasks']==[]
    words=[{'text':'да','start':0,'end':1},{'text':'нет','start':2,'end':3}]
    turns=[{'start':0,'end':1,'speaker':'A'},{'start':2,'end':3,'speaker':'B'}]
    assert len(group_words(words,turns))==2
