"""Brev profile must use server paths and preserve the real processing boundary."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('manage_brev', Path(__file__).parents[1] / 'manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def test_brev_resolves_models_and_overrides_incompatible_mac_settings(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_MODE', 'fixture')
    monkeypatch.setenv('PIPELINE_MODE', 'fixture')
    monkeypatch.setenv('AI_LLM', 'mlx')
    monkeypatch.setenv('AI_DEVICE', 'cuda')
    monkeypatch.setenv('AI_QUANTIZATION', 'nf4')
    monkeypatch.setenv('MEETING_MODEL_DIR', str(tmp_path / 'mounted-models'))
    for key in ('AI_CONTEXT_TOKENS', 'AI_MAX_NEW_TOKENS', 'AI_THREADS'):
        monkeypatch.delenv(key, raising=False)
    env = manage.environment(SimpleNamespace(profile='brev', models=None, device='cpu'))
    assert env['AI_MODE'] == env['PIPELINE_MODE'] == 'real'
    assert env['AI_LLM'] == 'mlx_torch'
    assert env['AI_DEVICE'] == 'cpu'
    assert env['AI_QUANTIZATION'] == 'none'
    assert env['AI_ASR_PATH'] == str(tmp_path / 'mounted-models/asr')
    assert env['AI_DIARIZATION_PATH'] == str(tmp_path / 'mounted-models/diarization')
    assert env['AI_LLM_PATH'] == str(tmp_path / 'mounted-models/llm')
    assert env['AI_CONTEXT_TOKENS'] == '2048'
    assert env['AI_MAX_NEW_TOKENS'] == '512'
    assert env['AI_THREADS'] == '4'


def test_missing_server_models_fail_before_processes_start(tmp_path, monkeypatch):
    (tmp_path / 'frontend/dist').mkdir(parents=True)
    (tmp_path / 'frontend/dist/index.html').write_text('synthetic UI')
    monkeypatch.setattr(manage, 'ROOT', tmp_path)
    monkeypatch.setattr(manage, 'check_models', lambda *_: (_ for _ in ()).throw(SystemExit('missing models')))
    monkeypatch.setattr(manage.subprocess, 'Popen', lambda *_a, **_kw: pytest.fail('must not start API or worker'))
    args = SimpleNamespace(profile='brev', models=str(tmp_path / 'missing'), device='cpu')
    with pytest.raises(SystemExit, match='missing models'):
        manage.run(args)


def test_listener_defaults_to_loopback_and_supports_container_binding():
    assert manage.listen_address({}) == ('127.0.0.1', 8000)
    assert manage.listen_address({'BACKEND_HOST': '0.0.0.0', 'BACKEND_PORT': '8080'}) == ('0.0.0.0', 8080)


@pytest.mark.parametrize('env', [{'BACKEND_HOST': 'https://brev.example'}, {'BACKEND_PORT': '0'},
                                 {'BACKEND_PORT': '65536'}, {'BACKEND_PORT': 'invalid'}])
def test_invalid_listener_is_rejected(env):
    with pytest.raises(SystemExit):
        manage.listen_address(env)
