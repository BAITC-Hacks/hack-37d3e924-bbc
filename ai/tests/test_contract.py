import copy
import json
from pathlib import Path
import pytest
from ai.pipeline import run_pipeline
from ai.validation import validate_input,validate_result
from ai.errors import PipelineError

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def pair():
    return tuple(json.loads((ROOT/'fixtures'/f'{name}.json').read_text(encoding='utf-8')) for name in ('input','result'))

def test_fixture_explicit_and_valid(monkeypatch,pair):
    request,result=pair
    monkeypatch.setenv('AI_MODE','fixture')
    events=[]
    assert run_pipeline(request,events.append)==result
    assert events==[{'stage':'validating'}]
    altered=copy.deepcopy(request);altered['meeting_id']='real-upload'
    with pytest.raises(PipelineError):run_pipeline(altered)

def test_no_fixture_fallback(monkeypatch,pair):
    monkeypatch.delenv('AI_MODE',raising=False)
    monkeypatch.delenv('AI_ASR_PATH',raising=False)
    with pytest.raises(PipelineError) as e:run_pipeline(pair[0])
    assert e.value.code=='MODEL_UNAVAILABLE'

@pytest.mark.parametrize('change',[
    lambda r:r['segments'][0].update(end=0),
    lambda r:r['segments'][0].update(start=float('nan')),
    lambda r:r['segments'].reverse(),
    lambda r:r['segments'][1].update(id='s1'),
    lambda r:r['tasks'][0].update(source_segment_ids=['missing']),
    lambda r:r['tasks'][0].update(assignee_id='missing'),
    lambda r:r['tasks'][0].update(due_date='2026-02-30'),
    lambda r:r['tasks'][0].update(assignee_id=None,needs_review=False),
    lambda r:r['participants'][0].update(speaker_ids=['same']) or r['participants'][1].update(speaker_ids=['same']),
    lambda r:r.update(meeting_id='wrong'),
])
def test_bad_outputs_fail(pair,change):
    request,result=pair;change(result)
    with pytest.raises(PipelineError):validate_result(result,request)

@pytest.mark.parametrize('dt,zone',[
    ('2026-09-23T10:00:00','Asia/Almaty'),
    ('2026-09-23 10:00:00+05:00','Asia/Almaty'),
    ('2026-09-23T10:00:00+06:00','Asia/Almaty'),
    ('2026-09-23T10:00:00+05:00','Bad/Zone'),
])
def test_invalid_time(pair,dt,zone):
    request,_=pair;request.update(meeting_datetime=dt,timezone=zone)
    with pytest.raises(PipelineError):validate_input(request)
