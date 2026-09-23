"""Windows launch profile selects the original local model formats explicitly."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('manage_windows', Path(__file__).parents[1] / 'manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def test_windows_profile_preserves_models_and_bounds_context(tmp_path, monkeypatch):
    for key in ('AI_CONTEXT_TOKENS', 'AI_MAX_NEW_TOKENS', 'MEETING_MODEL_DIR'):
        monkeypatch.delenv(key, raising=False)
    # A previous Linux/NF4 profile must not re-quantize the original MLX snapshot.
    monkeypatch.setenv('AI_QUANTIZATION', 'nf4')
    args = SimpleNamespace(profile='windows', models=str(tmp_path), device='cuda')
    env = manage.environment(args)
    assert env['AI_MODE'] == env['PIPELINE_MODE'] == 'real'
    assert env['AI_ASR'] == 'mixed_ctc'
    assert env['AI_DIARIZER'] == 'sherpa'
    assert env['AI_LLM'] == 'mlx_torch'
    assert env['AI_DEVICE'] == 'cuda'
    assert env['AI_QUANTIZATION'] == 'none'
    assert env['AI_LLM_PATH'] == str(tmp_path / 'llm')
    assert env['AI_CONTEXT_TOKENS'] == '2048'
    assert env['AI_MAX_NEW_TOKENS'] == '512'
    assert env['HF_HUB_OFFLINE'] == '1'
    assert env['PYTHONUTF8'] == '1'


def test_doctor_uses_ai_environment_and_verifies_hashes(tmp_path, monkeypatch):
    args = SimpleNamespace(worker_python='worker-python', python='api-python')
    env = {'MEETING_MODEL_DIR': str(tmp_path), 'AI_DEVICE': 'cpu'}
    calls = []
    monkeypatch.setattr(manage, 'call', lambda cmd, environment: calls.append((cmd, environment)))
    manage.check_models(args, env, verify_hashes=True)
    assert calls == [(['worker-python', '-m', 'ai.model_check', '--models', str(tmp_path),
                      '--device', 'cpu', '--verify-hashes'], env)]
