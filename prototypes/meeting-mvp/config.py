from pathlib import Path
import os
from importlib.util import find_spec
import json
import hashlib
import sys

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
SHARED_MODEL_DIR = REPO_ROOT / '.local' / 'models'
DEFAULT_MODEL_DIR = (SHARED_MODEL_DIR if (SHARED_MODEL_DIR / '.meeting-models-verified.json').is_file()
                     else ROOT / 'models')
MODEL_DIR = Path(os.environ.get('MEETING_MODEL_DIR', DEFAULT_MODEL_DIR)).expanduser().resolve()
DATA_DIR = Path(os.environ.get('MEETING_DATA_DIR', ROOT / '.local')).resolve()

def llm_runtime():
    return os.environ.get('MEETING_LLM_RUNTIME', 'mlx_torch' if sys.platform == 'win32' else 'mlx')


def llm_device():
    return os.environ.get('MEETING_DEVICE', 'cpu')


def dependencies_available(*names):
    try:
        return all(find_spec(name) is not None for name in names)
    except (ImportError, ValueError, AttributeError):
        return False


def offline_env():
    python_path = os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get('PYTHONPATH', '')]))
    return {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
            'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1',
            'TOKENIZERS_PARALLELISM': 'false', 'OMP_NUM_THREADS': '4',
            'MEETING_MODEL_DIR': str(MODEL_DIR), 'MEETING_LLM_RUNTIME': llm_runtime(),
            'MEETING_DEVICE': llm_device(), 'PYTHONPATH': python_path}

def model_status():
    try:
        manifest_path = ROOT / 'models.lock.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        receipt = json.loads((MODEL_DIR / '.meeting-models-verified.json').read_text(encoding='utf-8'))
        if receipt.get('schema_version') != 1 or receipt.get('manifest') != digest:
            raise ValueError('stale receipt')
        paths = {item['path']: item for item in manifest['files']}
        verified = {item['path']: item for item in receipt.get('files', [])}
        def group(prefix):
            items = [item for path, item in paths.items() if path.startswith(prefix)]
            return bool(items) and all(verified.get(item['path']) == {'path': item['path'], 'bytes': item['bytes'], 'sha256': item['sha256']} and (MODEL_DIR / item['path']).is_file() and (MODEL_DIR / item['path']).stat().st_size == item['bytes'] for item in items)
        return {'Распознавание речи': group('asr/') and dependencies_available('torch', 'soundfile', 'imageio_ffmpeg'),
                'Разделение говорящих': group('diarization/') and dependencies_available('sherpa_onnx', 'soundfile'),
                'Поручения и саммари': group('llm/') and runtime_notice() is None}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {'Распознавание речи': False, 'Разделение говорящих': False, 'Поручения и саммари': False}


def runtime_notice():
    runtime = llm_runtime()
    if runtime == 'mlx_torch':
        if llm_device() not in ('cpu', 'cuda'):
            return 'Для MEETING_DEVICE поддерживаются только cpu и cuda.'
        if not dependencies_available('torch', 'transformers', 'safetensors', 'tokenizers'):
            return ('Для исходной Qwen3 MLX 4-bit через PyTorch нужны torch, transformers, '
                    'safetensors и tokenizers. Выполните setup.ps1. Автоматической замены модели нет.')
    elif runtime == 'mlx':
        if sys.platform != 'darwin':
            return ('Runtime mlx требует Apple Silicon. Для исходных весов на Windows '
                    'установите MEETING_LLM_RUNTIME=mlx_torch и выполните setup.ps1.')
        if not dependencies_available('mlx', 'mlx_lm'):
            return 'Для выбранного runtime mlx нужны локальные зависимости mlx и mlx_lm.'
    else:
        return 'Неизвестный MEETING_LLM_RUNTIME. Поддерживаются mlx и mlx_torch; автоматического переключения нет.'
    return None
