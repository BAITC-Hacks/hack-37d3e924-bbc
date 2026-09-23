from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get('MEETING_MODEL_DIR', ROOT / 'models')).expanduser().resolve()
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
        'Поручения и саммари': all((MODEL_DIR / p).is_file() for p in ['llm/model.safetensors', 'llm/config.json', 'llm/tokenizer.json']),
    }
