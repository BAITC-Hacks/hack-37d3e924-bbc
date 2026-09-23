from pathlib import Path
import os
from importlib.util import find_spec

ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get('MEETING_MODEL_DIR', ROOT / 'models')).resolve()
DATA_DIR = Path(os.environ.get('MEETING_DATA_DIR', ROOT / '.local')).resolve()

def offline_env():
    return {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
            'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1',
            'TOKENIZERS_PARALLELISM': 'false', 'OMP_NUM_THREADS': '4',
            'MEETING_MODEL_DIR': str(MODEL_DIR)}

def model_status():
    return {
        'Распознавание речи': all((MODEL_DIR / p).is_file() for p in ['asr/model.pt', 'asr/tokens.lst']),
        'Разделение говорящих': all((MODEL_DIR / p).is_file() for p in ['diarization/segmentation.onnx', 'diarization/embedding.onnx']),
        'Поручения и саммари': find_spec('mlx_lm') is not None and all((MODEL_DIR / p).is_file() for p in ['llm/model.safetensors', 'llm/config.json', 'llm/tokenizer.json']),
    }


def runtime_notice():
    if os.name == 'nt' and find_spec('mlx_lm') is None:
        return ('Интерфейс работает на Windows. Исходная модель поручений использует MLX для Apple Silicon; '
                'её автоматический анализ здесь недоступен. Модель не заменена. '
                'Распознавание и диаризация требуют исходных весов в каталоге models.')
    return None
