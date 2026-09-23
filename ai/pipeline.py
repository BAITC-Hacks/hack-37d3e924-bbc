"""Stable synchronous entry point for the application worker. No HTTP server."""
import getpass
import json
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from .errors import PipelineError
from .inference_lock import acquire_inference_lock
from .validation import validate_input, validate_result


def default_state_dir():
    if hasattr(os, 'getuid'):
        scope = str(os.getuid())
    else:
        scope = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in getpass.getuser()) or 'user'
    return Path(tempfile.gettempdir())/f'meeting-ai-{scope}'


def run_pipeline(input_data, on_progress=None):
    input_data=deepcopy(input_data)
    validate_input(input_data)
    mode=os.environ.get('AI_MODE','real')
    if mode=='fixture':
        fixture=Path(__file__).parent/'fixtures'
        example=json.loads((fixture/'input.json').read_text(encoding='utf-8'))
        if input_data!=example:
            raise PipelineError('INVALID_INPUT','Тестовый режим принимает только общий синтетический пример.')
        if on_progress:
            on_progress({'stage':'validating'})
        return validate_result(json.loads((fixture/'result.json').read_text(encoding='utf-8')),input_data)
    if mode!='real':
        raise PipelineError('INVALID_INPUT','Неизвестный режим ИИ-модуля.')
    from .settings import Settings
    from .audio import align
    from .worker import OFFLINE_ENV
    settings=Settings.from_env()
    input_data["audio_path"]=str(Path(input_data["audio_path"]).resolve())
    # Lock spans every stage and subprocess. Backend owns queueing/retries.
    state_dir=Path(os.environ.get('AI_STATE_DIR',str(default_state_dir())))
    state_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        lock = acquire_inference_lock(state_dir/'inference.lock')
    except BlockingIOError:
        raise PipelineError('RESOURCE_EXHAUSTED','ИИ-модуль уже обрабатывает другую запись.') from None
    with lock:
        with tempfile.TemporaryDirectory(prefix='meeting-',dir=state_dir) as temporary:
            folder=Path(temporary)
            (folder/'request.json').write_text(
                json.dumps({'input':input_data,'settings':settings.to_dict()},ensure_ascii=False),
                encoding='utf-8')
            metrics=[]
            started=time.monotonic()
            env={**os.environ,**OFFLINE_ENV}
            root=str(Path(__file__).resolve().parents[1])
            env['PYTHONPATH']=root+os.pathsep+env.get('PYTHONPATH','')
            def progress(stage):
                if on_progress:
                    on_progress({'stage':stage})
            def stage(name):
                progress(name)
                try:
                    proc=subprocess.run([sys.executable,'-m','ai.worker',name,str(folder)],
                        env=env,cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                        timeout=int(os.environ.get('AI_STAGE_TIMEOUT','3600')))
                except subprocess.TimeoutExpired:
                    raise PipelineError('PROCESSING_FAILED','Превышено время обработки этапа.') from None
                if proc.returncode:
                    error=folder/'error.json'
                    if error.exists():
                        detail=json.loads(error.read_text(encoding='utf-8'))
                        raise PipelineError(detail['code'],detail['message'])
                    raise PipelineError('PROCESSING_FAILED','Процесс ИИ завершился до получения результата.')
                metrics.append(json.loads((folder/f'{name}.metrics.json').read_text(encoding='utf-8')))
                return json.loads((folder/f'{name}.json').read_text(encoding='utf-8'))
            prepared=stage('preparing_audio')
            words=stage('transcribing')
            diarization=stage('diarizing')
            progress('aligning')
            segments,uncertain=align(words,diarization['turns'])
            if not words and diarization['turns']:
                raise PipelineError('INVALID_MODEL_OUTPUT','Речь обнаружена, но распознавание не дало текста.')
            if words and not diarization['turns']:
                raise PipelineError('INVALID_MODEL_OUTPUT','Диаризация не определила речь в распознанной записи.')
            (folder/'segments.json').write_text(json.dumps(segments,ensure_ascii=False),encoding='utf-8')
            analysis=stage('extracting_tasks')
            progress('summarizing')
            warnings=analysis['warnings']+['Автоматическая расшифровка: проверьте имена, числа и исходный язык.',
                'Метки говорящих сами по себе не подтверждают личность.']
            if uncertain or diarization['overlap']:
                warnings.append('Есть пересечение голосов или реплики с неопределённым говорящим; проверьте таймкоды.')
            result={'schema_version':1,**{k:input_data[k] for k in ('meeting_id','meeting_datetime','timezone','participants')},
                'segments':segments,'tasks':analysis['tasks'],'summary':analysis['summary'],'warnings':warnings}
            progress('validating')
            validate_result(result,input_data)
            # Optional metrics have no audio, transcript, participant names, or meeting IDs.
            if os.environ.get('AI_METRICS_PATH'):
                report={'duration_seconds':prepared['duration'],'wall_seconds':round(time.monotonic()-started,3),
                        'stages':metrics,'profile':{'asr':settings.asr,'diarizer':settings.diarizer,'llm':settings.llm,
                        'device':settings.device,'quantization':settings.quantization if settings.llm=='transformers' else 'checkpoint',
                        'compute_type':settings.compute_type if settings.asr=='whisper' else 'checkpoint'}}
                Path(os.environ['AI_METRICS_PATH']).write_text(json.dumps(report,indent=2),encoding='utf-8')
            return result
