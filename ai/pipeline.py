"""Stable team entry point. No model imports or downloads at import time."""
import json
import os
from pathlib import Path
from .errors import PipelineError
from .validation import validate_input, validate_result

def run_pipeline(input_data, on_progress=None):
    validate_input(input_data)
    if os.environ.get('AI_MODE', 'real') == 'fixture':
        fixture = Path(__file__).parent / 'fixtures'
        example = json.loads((fixture / 'input.json').read_text())
        if input_data != example:
            raise PipelineError('INVALID_INPUT', 'Тестовый режим принимает только общий синтетический пример.')
        if on_progress:
            on_progress({'stage': 'validating'})
        return validate_result(json.loads((fixture / 'result.json').read_text()), input_data)
    raise PipelineError('MODEL_UNAVAILABLE', 'Локальный конвейер ещё не настроен. Тестовый режим включается отдельно.')
