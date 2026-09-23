from pathlib import Path
import os
from importlib.util import find_spec
import json
import hashlib

ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get('MEETING_MODEL_DIR', ROOT / 'models')).expanduser().resolve()
DATA_DIR = Path(os.environ.get('MEETING_DATA_DIR', ROOT / '.local')).resolve()

def offline_env():
    return {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
            'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1',
            'TOKENIZERS_PARALLELISM': 'false', 'OMP_NUM_THREADS': '4',
            'MEETING_MODEL_DIR': str(MODEL_DIR)}

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
        return {'Распознавание речи': group('asr/'), 'Разделение говорящих': group('diarization/'),
                'Поручения и саммари': group('llm/') and find_spec('mlx_lm') is not None}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {'Распознавание речи': False, 'Разделение говорящих': False, 'Поручения и саммари': False}


def runtime_notice():
    if os.name == 'nt' and find_spec('mlx_lm') is None:
        return ('Интерфейс работает на Windows. Исходная модель поручений использует MLX для Apple Silicon; '
                'её автоматический анализ здесь недоступен. Модель не заменена. '
                'Распознавание и диаризация требуют исходных весов в каталоге models.')
    return None
