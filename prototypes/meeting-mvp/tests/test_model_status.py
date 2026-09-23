"""Model readiness combines verified weights with the available local runtime."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


@pytest.fixture
def verified_models(tmp_path, monkeypatch):
    model_dir = tmp_path / 'models'
    files = []
    for name in ['asr/model.pt', 'diarization/segmentation.onnx', 'llm/model.safetensors']:
        content = b'synthetic test weights'
        path = model_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        files.append({'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    manifest = tmp_path / 'models.lock.json'
    manifest.write_text(json.dumps({'files': files}), encoding='utf-8')
    receipt = {'schema_version': 1, 'manifest': hashlib.sha256(manifest.read_bytes()).hexdigest(), 'files': files}
    receipt_path = model_dir / '.meeting-models-verified.json'
    receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    monkeypatch.setattr(config, 'MODEL_DIR', model_dir)
    monkeypatch.setattr(config, 'find_spec', lambda name: object())
    return model_dir, receipt_path, receipt


def test_verified_llm_still_needs_runtime(verified_models, monkeypatch):
    assert all(config.model_status().values())
    monkeypatch.setattr(config, 'find_spec', lambda name: None)
    status = config.model_status()
    assert status['Распознавание речи'] and status['Разделение говорящих']
    assert not status['Поручения и саммари']


def test_partial_receipt_only_enables_verified_component(verified_models):
    _, path, receipt = verified_models
    receipt['files'] = [item for item in receipt['files'] if item['path'].startswith('diarization/')]
    path.write_text(json.dumps(receipt), encoding='utf-8')
    assert config.model_status() == {
        'Распознавание речи': False, 'Разделение говорящих': True, 'Поручения и саммари': False,
    }


@pytest.mark.parametrize('fault', ['missing_receipt', 'stale_receipt', 'missing_weight', 'wrong_size'])
def test_unverified_or_changed_weights_are_not_ready(verified_models, fault):
    model_dir, path, receipt = verified_models
    if fault == 'missing_receipt':
        path.unlink()
    elif fault == 'stale_receipt':
        receipt['manifest'] = 'outdated'
        path.write_text(json.dumps(receipt), encoding='utf-8')
    elif fault == 'missing_weight':
        (model_dir / 'asr/model.pt').unlink()
    else:
        (model_dir / 'asr/model.pt').write_bytes(b'truncated')
    assert not config.model_status()['Распознавание речи']
