"""Synthetic runtime integration only; these tests do not measure model quality."""
from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


@pytest.fixture(scope='module', autouse=True)
def worker_engine():
    # Exercise a separate module instance without installing an irreversible
    # audit hook into pytest or changing the normal engine module cache.
    global engine
    hooks = []
    spec = importlib.util.spec_from_file_location('synthetic_worker_engine', Path(__file__).resolve().parents[1] / 'engine.py')
    engine = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, 'addaudithook', hooks.append)
        spec.loader.exec_module(engine)
    assert hooks == [engine.deny_network]
    yield
    del engine


def test_production_audit_hook_blocks_outgoing_network():
    with pytest.raises(PermissionError):
        engine.deny_network('socket.getaddrinfo', ())
    with pytest.raises(PermissionError):
        engine.deny_network('socket.connect', (SimpleNamespace(family=2), ('example.invalid', 443)))


class SyntheticInput:
    def __init__(self, length):
        self.shape = (1, length)
        self.device = None

    def to(self, device):
        self.device = device
        return self


class SyntheticTokenizer:
    def __init__(self, answers=()):
        self.answers = answers

    def encode(self, text, add_special_tokens):
        assert add_special_tokens is False
        return list(text)

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        assert tokenize is False and add_generation_prompt is True
        return '\n'.join(item['content'] for item in messages)

    def __call__(self, prompt, return_tensors, add_special_tokens):
        assert return_tensors == 'pt' and add_special_tokens is False
        self.last_prompt = prompt
        return {'input_ids': SyntheticInput(len(prompt)), 'attention_mask': SyntheticInput(len(prompt))}

    def decode(self, tokens, skip_special_tokens):
        assert skip_special_tokens is True
        return self.answers[tokens[0]]


@pytest.fixture
def synthetic_runtime(monkeypatch):
    monkeypatch.setenv('MEETING_LLM_RUNTIME', 'mlx_torch')
    monkeypatch.setenv('MEETING_DEVICE', 'cpu')
    tokenizer = SyntheticTokenizer(['{"summary":"Синтетический ответ","tasks":[]}'])
    calls, loads = [], []
    def generate(**kwargs):
        calls.append(kwargs)
        return [[0] * kwargs['input_ids'].shape[1] + [len(calls) - 1]]
    model = SimpleNamespace(generate=generate)
    def load(path, device, threads):
        loads.append((path, device, threads))
        return model, tokenizer
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, 'ai.mlx_torch', SimpleNamespace(load_mlx_torch=load))
    return tokenizer, calls, loads


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_original_loader_and_exact_generation_api(synthetic_runtime, monkeypatch, device):
    tokenizer, calls, loads = synthetic_runtime
    monkeypatch.setenv('MEETING_DEVICE', device)
    actual_tokenizer, generate = engine.load_analysis_generator()
    observed = []
    assert generate('synthetic prompt', 512, observed.append) == tokenizer.answers[0]
    assert actual_tokenizer is tokenizer
    assert loads == [(engine.MODEL_DIR / 'llm', device, 4)]
    assert calls[0]['input_ids'].device == device
    assert calls[0]['attention_mask'].device == device
    assert calls[0]['max_new_tokens'] == 512
    assert calls[0]['do_sample'] is False
    assert calls[0]['logits_to_keep'] == 1
    assert observed == [1]


@pytest.mark.parametrize('prompt_length,output', [(1537, 512), (10, 513)])
def test_context_and_output_are_bounded_without_truncation(synthetic_runtime, prompt_length, output):
    _, calls, _ = synthetic_runtime
    _, generate = engine.load_analysis_generator()
    with pytest.raises(engine.AnalysisLimitError):
        generate('x' * prompt_length, output)
    assert calls == []


def test_unknown_runtime_is_not_replaced(monkeypatch):
    monkeypatch.setenv('MEETING_LLM_RUNTIME', 'unknown')
    with pytest.raises(ValueError, match='Автоматического переключения нет'):
        engine.load_analysis_generator()


def test_unverified_weights_are_rejected_before_loading(synthetic_runtime, monkeypatch, tmp_path):
    _, _, loads = synthetic_runtime
    monkeypatch.setattr(config, 'runtime_notice', lambda: None)
    monkeypatch.setattr(config, 'model_status', lambda: {'Поручения и саммари': False})
    with pytest.raises(ValueError, match='не подтверждены'):
        engine.analyze(tmp_path)
    assert loads == []


def synthetic_segments(count=6):
    return [{'id': f'S{i:04d}', 'speaker': 'SPEAKER_00', 'start': None,
             'text': f'Синтетическая реплика {i}. ' + 'x' * 250} for i in range(1, count + 1)]


def test_token_chunks_preserve_every_source_and_overlap(monkeypatch):
    monkeypatch.setattr(engine, 'SYSTEM', 'Synthetic instructions.')
    tokenizer = SyntheticTokenizer()
    segments = synthetic_segments()
    chunks = engine.analysis_chunks(segments, {}, tokenizer, input_budget=1100)
    assert len(chunks) > 1
    assert {s['id'] for chunk in chunks for s in chunk} == {s['id'] for s in segments}
    for index, chunk in enumerate(chunks):
        assert all(s == segments[int(s['id'][1:]) - 1] for s in chunk)
        assert len(engine.analysis_prompt(tokenizer, chunk, {}, [], 1100)) <= 1100
        if index:
            assert set(s['id'] for s in chunk) & set(s['id'] for s in chunks[index - 1])


def test_auxiliary_candidates_shrink_but_actual_source_is_unchanged(monkeypatch):
    monkeypatch.setattr(engine, 'SYSTEM', 'Synthetic instructions.')
    tokenizer = SyntheticTokenizer()
    segments = synthetic_segments(1)
    results = [{'task': 'z' * 500, 'owner': 'Synthetic owner'}] * 8
    prompt = engine.analysis_prompt(tokenizer, segments, {}, results, 1100)
    assert segments[0]['text'] in prompt
    assert len(prompt) <= 1100
    assert len(results) == 8


def test_single_oversized_source_is_rejected(monkeypatch):
    monkeypatch.setattr(engine, 'SYSTEM', 'Synthetic instructions.')
    segments = synthetic_segments(1)
    segments[0]['text'] = 'x' * 2000
    with pytest.raises(engine.AnalysisLimitError, match='Разделите длинную реплику'):
        engine.analysis_chunks(segments, {}, SyntheticTokenizer(), 1536)
    assert len(segments[0]['text']) == 2000


def test_analysis_keeps_validation_reconciliation_and_saved_output(synthetic_runtime, monkeypatch, tmp_path):
    tokenizer, calls, _ = synthetic_runtime
    monkeypatch.setattr(engine, 'SYSTEM', 'Synthetic instructions.')
    monkeypatch.setattr(config, 'runtime_notice', lambda: None)
    monkeypatch.setattr(config, 'model_status', lambda: {'Поручения и саммари': True})
    segments = [
        {'id': 'S0001', 'speaker': 'SPEAKER_00', 'start': None, 'text': 'Ерлан подготовит смету до пятницы.'},
        {'id': 'S0002', 'speaker': 'SPEAKER_00', 'start': None, 'text': 'Алия проверит отчёт.'},
    ]
    tokenizer.answers = [json.dumps({'summary': 'Синтетическая проверка.', 'tasks': [
        {'task': 'Подготовить смету', 'owner': 'Ерлан', 'due_text': 'до пятницы', 'source_ids': ['S0001']},
        {'task': 'Проверить отчёт', 'owner': 'Алия', 'due_text': None, 'source_ids': ['S0002']},
        {'task': 'Выдуманное поручение', 'owner': None, 'due_text': None, 'source_ids': ['S9999']},
    ]}, ensure_ascii=False), '{"groups":[]}']
    engine.write_json(tmp_path/'request.json', {'segments': segments, 'names': {}, 'meeting_date': '2026-09-23'})
    engine.analyze(tmp_path)
    result = engine.read_json(tmp_path/'analysis.json')
    assert len(result['tasks']) == 2
    assert result['tasks'][0]['source_ids'] == ['S0001']
    assert result['tasks'][0]['due_date'] == '2026-09-25'
    assert result['tasks'][0]['quote'] == '[S0001] Ерлан подготовит смету до пятницы.'
    assert (tmp_path/'model-answer-0.txt').read_text(encoding='utf-8') == tokenizer.answers[0]
    assert len(calls) == 2
    assert all(call['max_new_tokens'] == 512 for call in calls)
    assert result['model'] == 'Qwen3-4B-Instruct-2507-4bit'


def test_mlx_still_streams_and_clears_cache(monkeypatch):
    monkeypatch.setenv('MEETING_LLM_RUNTIME', 'mlx')
    cache, generation, observed = [], [], []
    mx = SimpleNamespace(set_cache_limit=lambda size: cache.append(size), clear_cache=lambda: cache.append('cleared'))
    def stream(model, tokenizer, **kwargs):
        generation.append(kwargs)
        yield SimpleNamespace(text='synthetic ', generation_tokens=32)
        yield SimpleNamespace(text='answer', generation_tokens=33)
    monkeypatch.setitem(sys.modules, 'mlx', SimpleNamespace(core=mx))
    monkeypatch.setitem(sys.modules, 'mlx.core', mx)
    monkeypatch.setitem(sys.modules, 'mlx_lm', SimpleNamespace(load=lambda path: ('model', 'tokenizer'), stream_generate=stream))
    monkeypatch.setitem(sys.modules, 'mlx_lm.sample_utils', SimpleNamespace(make_sampler=lambda temp: temp))
    _, generate = engine.load_analysis_generator()
    assert generate('synthetic prompt', 2600, observed.append) == 'synthetic answer'
    assert generation[0]['max_tokens'] == 2600
    assert observed == [32]
    assert cache == [128 * 1024 * 1024, 'cleared']


def test_worker_environment_keeps_repo_importable_and_selection_explicit(monkeypatch):
    monkeypatch.setenv('MEETING_LLM_RUNTIME', 'mlx_torch')
    monkeypatch.setenv('MEETING_DEVICE', 'cuda')
    monkeypatch.setenv('PYTHONPATH', 'existing-path')
    env = config.offline_env()
    assert env['PYTHONPATH'].split(os.pathsep) == [str(config.REPO_ROOT), 'existing-path']
    assert env['MEETING_LLM_RUNTIME'] == 'mlx_torch'
    assert env['MEETING_DEVICE'] == 'cuda'
    assert env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == '1'


def test_child_context_error_is_visible_in_orchestrator_status(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, 'DATA_DIR', tmp_path)
    def failed_stage(*args, **kwargs):
        engine.write_json(tmp_path/'status.json', {'state': 'error', 'error_code': 'CONTEXT_LIMIT', 'label': 'Разделите длинную реплику.'})
        raise subprocess.CalledProcessError(1, ['synthetic-worker'])
    monkeypatch.setattr(engine.subprocess, 'run', failed_stage)
    with pytest.raises(subprocess.CalledProcessError):
        engine.orchestrate(tmp_path, 'analysis')
    assert engine.read_json(tmp_path/'status.json')['label'] == 'Разделите длинную реплику.'
