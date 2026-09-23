import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from ai.audio import prepare_audio
from ai.errors import PipelineError

def test_evaluation_help_is_available_without_unix_resource():
    result = subprocess.run([sys.executable, '-m', 'ai.evaluate', '--help'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--output' in result.stdout

def test_worker_network_guard_is_process_scoped():
    code='''import sys,socket
from ai.worker import deny_network
sys.addaudithook(deny_network)
for action in (lambda:socket.getaddrinfo("example.com",443),lambda:socket.socket().connect(("127.0.0.1",9))):
 try:action()
 except PermissionError:pass
 else:raise RuntimeError("guard failed")
print("blocked")
'''
    p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert p.returncode==0 and p.stdout.strip()=='blocked'

def test_worker_peak_rss_is_explicitly_unknown_without_resource(monkeypatch):
    from ai import worker
    monkeypatch.setattr(worker,'resource',None)
    assert worker.peak_rss_bytes() is None

def test_input_urls_never_download(tmp_path):
    with pytest.raises(PipelineError) as e:prepare_audio('https://example.com/audio.wav',tmp_path/'out.wav')
    assert e.value.code=='INVALID_AUDIO'

def test_import_has_no_model_side_effects():
    code='import sys;from ai.pipeline import run_pipeline;assert "torch" not in sys.modules;assert "transformers" not in sys.modules'
    assert subprocess.run([sys.executable,'-c',code],capture_output=True).returncode==0

def test_validation_survives_python_optimized_mode():
    code='''import json
from ai.validation import validate_result
from ai.errors import PipelineError
r=json.load(open("ai/fixtures/result.json"));i=json.load(open("ai/fixtures/input.json"))
r["segments"][0]["end"]=0.1;r["segments"][0]["start"]=2
try:validate_result(r,i)
except PipelineError:pass
else:raise RuntimeError("validation bypass")
'''
    assert subprocess.run([sys.executable,'-O','-c',code],capture_output=True).returncode==0
