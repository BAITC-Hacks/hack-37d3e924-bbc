"""Synthetic tiny tensors validate runtime mechanics, never model quality."""
import json
import socket

import pytest

torch = pytest.importorskip('torch')
from torch import nn
from torch.nn import functional as F

from ai.errors import PipelineError
from ai.mlx_torch import (MAX_ROW_CHUNK, PackedAffine4, PackedEmbedding, PackedLinear,
                          _load_packed_weights, _validate_config, load_mlx_torch)
from ai.settings import Settings


def original_config():
    return {'model_type': 'qwen3', 'hidden_size': 2560, 'intermediate_size': 9728,
            'num_hidden_layers': 36, 'num_attention_heads': 32,
            'num_key_value_heads': 8, 'head_dim': 128, 'vocab_size': 151936,
            'rope_theta': 5000000, 'tie_word_embeddings': True,
            'attention_bias': False, 'attention_dropout': 0.0, 'rms_norm_eps': 1e-6,
            'hidden_act': 'silu', 'torch_dtype': 'bfloat16',
            'quantization': {'bits': 4, 'group_size': 64},
            'quantization_config': {'bits': 4, 'group_size': 64}}


def pack(codes):
    shifts = torch.arange(0, 32, 4, dtype=torch.int64)
    return (codes.reshape(codes.shape[0], -1, 8).long() << shifts).sum(-1).to(torch.int32)


def matrix(rows=5, columns=64, row_chunk=2):
    codes = torch.arange(rows * columns).reshape(rows, columns) % 16
    scales = torch.full((rows, columns // 64), .125, dtype=torch.bfloat16)
    biases = torch.full_like(scales, -.75)
    return PackedAffine4(pack(codes), scales, biases, row_chunk=row_chunk), codes


def test_packed_sign_bit_low_nibble_order_and_affine_groups():
    codes = torch.arange(128).reshape(1, 128) % 16
    weight = pack(codes)
    assert (weight < 0).any(), 'fixture must exercise uint32 sign bit'
    scales = torch.tensor([[.125, -.25]], dtype=torch.bfloat16)
    biases = torch.tensor([[-.75, 2.5]], dtype=torch.bfloat16)
    packed = PackedAffine4(weight.view(torch.uint32), scales, biases)
    expected = (codes.reshape(1, 2, 64).float() * scales.float().unsqueeze(-1)
                + biases.float().unsqueeze(-1)).reshape(1, 128).to(torch.bfloat16)
    torch.testing.assert_close(packed.dequantize_rows(slice(0, 1)), expected, rtol=0, atol=0)
    assert packed.weight.data_ptr() == weight.data_ptr()


def test_affine_expression_rounds_to_bfloat16_only_once():
    codes = torch.full((1, 64), 15)
    scale = torch.tensor([[1.0078125]], dtype=torch.bfloat16)
    bias = torch.tensor([[-.03125]], dtype=torch.bfloat16)
    packed = PackedAffine4(pack(codes), scale, bias)
    expected = (codes.float() * scale.float() + bias.float()).to(torch.bfloat16)
    sequential = codes.to(torch.bfloat16) * scale + bias
    assert not torch.equal(expected, sequential)
    torch.testing.assert_close(packed.dequantize_rows(slice(0, 1)), expected, rtol=0, atol=0)


def test_embedding_and_vocab_head_share_buffers_and_match_dense_math():
    packed, codes = matrix()
    embedding, head = PackedEmbedding(packed), PackedLinear(packed)
    assert embedding.packed is head.packed
    for name in ('weight', 'scales', 'biases'):
        assert getattr(embedding.packed, name).data_ptr() == getattr(head.packed, name).data_ptr()
    dense = (codes.float() * .125 - .75).to(torch.bfloat16)
    indices = torch.tensor([[4, 1, 4], [0, 2, 3]])
    torch.testing.assert_close(embedding(indices), F.embedding(indices, dense), rtol=0, atol=0)
    inputs = torch.arange(128).reshape(2, 1, 64).to(torch.bfloat16) / 128
    torch.testing.assert_close(head(inputs), F.linear(inputs, dense), rtol=0, atol=0)


def test_vocabulary_head_never_dequantizes_more_than_one_chunk(monkeypatch):
    packed, _ = matrix(rows=2 * MAX_ROW_CHUNK + 3, row_chunk=MAX_ROW_CHUNK)
    calls = []
    original = packed.dequantize_rows

    def bounded(selection):
        calls.append(selection.stop - selection.start)
        return original(selection)

    monkeypatch.setattr(packed, 'dequantize_rows', bounded)
    result = PackedLinear(packed)(torch.ones(1, 1, 64, dtype=torch.bfloat16))
    assert result.shape == (1, 1, 2051)
    assert calls == [1024, 1024, 3]
    with pytest.raises(PipelineError, match='bounded chunk'):
        original(slice(0, 1025))


@pytest.mark.parametrize('tokens', [1, 17])
def test_cpu_linear_matches_independent_dense_affine_reference(tokens):
    generator = torch.Generator().manual_seed(37)
    codes = torch.randint(0, 16, (13, 128), generator=generator)
    scales = torch.randn((13, 2), generator=generator).to(torch.bfloat16)
    biases = torch.randn((13, 2), generator=generator).to(torch.bfloat16)
    packed = PackedAffine4(pack(codes), scales, biases, row_chunk=3)
    inputs = torch.randn((1, tokens, 128), generator=generator).to(torch.bfloat16)
    # Independent dense oracle: double accumulation on BF16-rounded weights.
    dense = (codes.reshape(13, 2, 64).double() * scales.double().unsqueeze(-1)
             + biases.double().unsqueeze(-1)).reshape(13, 128).to(torch.bfloat16)
    expected = torch.matmul(inputs.double(), dense.double().T).to(torch.bfloat16)
    actual = PackedLinear(packed)(inputs)
    assert actual.dtype == inputs.dtype and actual.shape == (1, tokens, 13)
    torch.testing.assert_close(actual, expected, rtol=0.008, atol=0.001)


@pytest.mark.parametrize('fault', ['weight_dtype', 'weight_rank', 'width', 'scale_dtype',
                                  'scale_shape', 'bias_shape', 'row_chunk'])
def test_invalid_packed_formats_fail_clearly(fault):
    weight = torch.zeros((2, 8), dtype=torch.int32)
    scales = torch.ones((2, 1), dtype=torch.bfloat16)
    biases = torch.zeros_like(scales)
    row_chunk = 2
    if fault == 'weight_dtype':
        weight = weight.float()
    elif fault == 'weight_rank':
        weight = weight[0]
    elif fault == 'width':
        weight = weight[:, :7]
    elif fault == 'scale_dtype':
        scales = scales.float()
    elif fault == 'scale_shape':
        scales = scales[:, :0]
    elif fault == 'bias_shape':
        biases = biases[:1]
    else:
        row_chunk = MAX_ROW_CHUNK + 1
    with pytest.raises(PipelineError, match='Unsupported original MLX snapshot'):
        PackedAffine4(weight, scales, biases, row_chunk=row_chunk)


@pytest.mark.parametrize('change', [
    {'model_type': 'other'}, {'tie_word_embeddings': False}, {'hidden_size': 2048},
    {'quantization': {'bits': 8, 'group_size': 64}},
    {'quantization_config': {'bits': 4, 'group_size': 32}},
    {'quantization': {'bits': 4, 'group_size': 64, 'mode': 'mxfp4'}},
    {'rope_scaling': {'type': 'linear', 'factor': 2}},
])
def test_unsupported_checkpoint_config_is_rejected(change):
    config = original_config()
    config.update(change)
    with pytest.raises(PipelineError, match='Unsupported original MLX snapshot'):
        _validate_config(config)


def tiny_qwen_fixture():
    transformers = pytest.importorskip('transformers')
    config = transformers.Qwen3Config(hidden_size=64, intermediate_size=128,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
        head_dim=32, vocab_size=128, tie_word_embeddings=True, attention_bias=False,
        bos_token_id=1, eos_token_id=127, pad_token_id=127, dtype='bfloat16')
    config._attn_implementation = 'sdpa'
    with torch.device('meta'):
        model = transformers.Qwen3ForCausalLM(config)
    tensors, matrix_names = {}, set()
    for name, module in model.named_modules():
        if isinstance(module, (nn.Linear, nn.Embedding)) and name != 'lm_head':
            rows, columns = module.weight.shape
            packed, _ = matrix(rows, columns)
            tensors[name + '.weight'] = packed.weight.view(torch.uint32)
            tensors[name + '.scales'] = packed.scales
            tensors[name + '.biases'] = packed.biases
            matrix_names.add(name + '.weight')
    for name, parameter in model.named_parameters():
        if name not in matrix_names and name != 'lm_head.weight':
            tensors[name] = torch.ones(parameter.shape, dtype=torch.bfloat16)
    return config, model, tensors


def test_loader_rejects_missing_or_extra_tensors():
    _, model, tensors = tiny_qwen_fixture()
    tensors['unexpected.weight'] = torch.ones(1)
    with pytest.raises(PipelineError, match='tensor names'):
        _load_packed_weights(model, tensors, 'cpu')


def test_local_loader_and_bounded_greedy_generation_without_network(tmp_path, monkeypatch):
    transformers = pytest.importorskip('transformers')
    safetensors = pytest.importorskip('safetensors.torch')
    config, _, tensors = tiny_qwen_fixture()
    (tmp_path / 'config.json').write_text(json.dumps(original_config()), encoding='utf-8')
    generation_config = {'bos_token_id': 1, 'eos_token_id': [126, 127], 'pad_token_id': 127}
    (tmp_path / 'generation_config.json').write_text(json.dumps(generation_config), encoding='utf-8')
    safetensors.save_file(tensors, str(tmp_path / 'model.safetensors'))
    monkeypatch.setattr(transformers.Qwen3Config, 'from_dict', classmethod(lambda cls, data: config))
    tokenizer_calls = []
    tokenizer = object()

    def local_tokenizer(path, **kwargs):
        tokenizer_calls.append((path, kwargs))
        assert kwargs == {'local_files_only': True, 'trust_remote_code': False}
        return tokenizer

    def forbidden(*args, **kwargs):
        raise AssertionError('synthetic model loading/generation attempted network access')

    monkeypatch.setattr(transformers.AutoTokenizer, 'from_pretrained', local_tokenizer)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    model, actual_tokenizer = load_mlx_torch(tmp_path, threads=1)
    assert actual_tokenizer is tokenizer and len(tokenizer_calls) == 1
    assert model.model.embed_tokens.packed is model.lm_head.packed
    assert model.generation_config.eos_token_id == [126, 127]
    assert all(not tensor.is_meta for tensor in (*model.parameters(), *model.buffers()))
    assert next(model.parameters()).dtype == torch.bfloat16
    sizes = []
    hook = model.lm_head.register_forward_pre_hook(lambda module, args: sizes.append(args[0].shape[-2]))
    try:
        with torch.inference_mode():
            output = model.generate(input_ids=torch.tensor([[1, 2, 3]]),
                                    max_new_tokens=3, do_sample=False, logits_to_keep=1)
    finally:
        hook.remove()
    assert 3 < output.shape[1] <= 6
    assert sizes and all(size == 1 for size in sizes)


def test_settings_select_explicit_original_runtime_with_small_defaults(tmp_path, monkeypatch):
    for key in ('AI_CONTEXT_TOKENS', 'AI_MAX_NEW_TOKENS', 'AI_QUANTIZATION'):
        monkeypatch.delenv(key, raising=False)
    for key, value in {'AI_LLM': 'mlx_torch', 'AI_ASR': 'mixed_ctc', 'AI_DIARIZER': 'sherpa',
                       'AI_DEVICE': 'cpu', 'AI_ASR_PATH': str(tmp_path),
                       'AI_DIARIZATION_PATH': str(tmp_path), 'AI_LLM_PATH': str(tmp_path)}.items():
        monkeypatch.setenv(key, value)
    (tmp_path / 'model.pt').touch()
    (tmp_path / 'tokens.lst').touch()
    settings = Settings.from_env()
    assert (settings.llm, settings.context_tokens, settings.max_new_tokens) == ('mlx_torch', 2048, 512)
    monkeypatch.setenv('AI_QUANTIZATION', 'nf4')
    with pytest.raises(PipelineError):
        Settings.from_env()
