"""Run the original MLX affine-4 Qwen snapshot without expanding its full weights.

MLX stores eight low-nibble-first codes in each uint32 word. Each group of 64
codes has BF16 scale and additive bias. The affine expression is evaluated in
float32 and rounded to BF16 once, as in MLX's dequantization helper.
"""
import json
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from .errors import PipelineError


MAX_ROW_CHUNK = 1024
GROUP_SIZE = 64


def _unsupported(detail):
    raise PipelineError('MODEL_UNAVAILABLE', 'Unsupported original MLX snapshot: ' + detail)


class PackedAffine4(nn.Module):
    """Shared packed matrix; no operation expands more than one row chunk."""

    def __init__(self, weight, scales, biases, row_chunk=MAX_ROW_CHUNK):
        super().__init__()
        if not 1 <= row_chunk <= MAX_ROW_CHUNK:
            _unsupported('row chunk must be between 1 and 1024.')
        if weight.dtype not in (torch.uint32, torch.int32) or weight.ndim != 2:
            _unsupported('packed weights must be a two-dimensional uint32 matrix.')
        rows, packed_columns = weight.shape
        columns = packed_columns * 8
        if rows < 1 or columns < GROUP_SIZE or columns % GROUP_SIZE:
            _unsupported('matrix width must be a positive multiple of 64.')
        if scales.dtype != torch.bfloat16 or biases.dtype != torch.bfloat16:
            _unsupported('affine scales and biases must be BF16.')
        expected = (rows, columns // GROUP_SIZE)
        if tuple(scales.shape) != expected or tuple(biases.shape) != expected:
            _unsupported('affine scale/bias shapes do not match packed weights.')
        if weight.device != scales.device or weight.device != biases.device:
            _unsupported('packed tensors must use one device.')
        # A view preserves the uint32 bit pattern, including its sign bit, without
        # an int64 copy of the checkpoint. Masking removes arithmetic-shift bits.
        self.register_buffer('weight', weight.view(torch.int32))
        self.register_buffer('scales', scales)
        self.register_buffer('biases', biases)
        self.rows, self.columns, self.row_chunk = rows, columns, row_chunk

    def dequantize_rows(self, selection):
        weight = self.weight[selection]
        if weight.ndim != 2 or not 1 <= weight.shape[0] <= self.row_chunk:
            _unsupported('dequantization row selection exceeds the bounded chunk.')
        shifts = torch.arange(0, 32, 4, dtype=torch.int32, device=weight.device)
        codes = ((weight.unsqueeze(-1) >> shifts) & 15).reshape(weight.shape[0], -1, GROUP_SIZE)
        values = codes.float() * self.scales[selection].float().unsqueeze(-1)
        values.add_(self.biases[selection].float().unsqueeze(-1))
        return values.reshape(weight.shape[0], self.columns).to(torch.bfloat16)


class PackedLinear(nn.Module):
    def __init__(self, packed):
        super().__init__()
        self.packed = packed
        self.in_features, self.out_features = packed.columns, packed.rows

    def forward(self, inputs):
        if inputs.shape[-1] != self.in_features:
            _unsupported('linear input width does not match packed weights.')
        output = inputs.new_empty((*inputs.shape[:-1], self.out_features))
        # CPU BF16 prefill can use a slow software kernel. Accumulate multiple
        # tokens in native float32, rounding back to the activation dtype. Keep
        # single-token decoding and GPU execution on their existing path.
        cpu_prefill = (inputs.device.type == 'cpu' and inputs.dtype == torch.bfloat16
                       and inputs.numel() > self.in_features)
        compute_inputs = inputs.float() if cpu_prefill else inputs
        for start in range(0, self.out_features, self.packed.row_chunk):
            stop = min(start + self.packed.row_chunk, self.out_features)
            weight = self.packed.dequantize_rows(slice(start, stop)).to(compute_inputs.dtype)
            output[..., start:stop] = F.linear(compute_inputs, weight)
        return output


class PackedEmbedding(nn.Module):
    def __init__(self, packed):
        super().__init__()
        self.packed = packed
        self.num_embeddings, self.embedding_dim = packed.rows, packed.columns

    def forward(self, input_ids):
        if input_ids.dtype not in (torch.int32, torch.int64):
            _unsupported('embedding indices must be integers.')
        flat = input_ids.reshape(-1)
        if flat.numel() and (flat.min() < 0 or flat.max() >= self.num_embeddings):
            _unsupported('embedding index is outside the vocabulary.')
        output = torch.empty((flat.numel(), self.embedding_dim),
                             dtype=torch.bfloat16, device=self.packed.weight.device)
        for start in range(0, flat.numel(), self.packed.row_chunk):
            stop = min(start + self.packed.row_chunk, flat.numel())
            output[start:stop] = self.packed.dequantize_rows(flat[start:stop])
        return output.reshape(*input_ids.shape, self.embedding_dim)


def _validate_config(config):
    expected = {'model_type': 'qwen3', 'hidden_size': 2560, 'intermediate_size': 9728,
                'num_hidden_layers': 36, 'num_attention_heads': 32,
                'num_key_value_heads': 8, 'head_dim': 128, 'vocab_size': 151936,
                'rope_theta': 5000000, 'tie_word_embeddings': True,
                'attention_bias': False, 'attention_dropout': 0.0, 'rms_norm_eps': 1e-6,
                'hidden_act': 'silu', 'torch_dtype': 'bfloat16'}
    if not isinstance(config, dict) or any(config.get(key) != value for key, value in expected.items()):
        _unsupported('expected the original tied Qwen3-4B-Instruct-2507 architecture.')
    if (config.get('rope_scaling') is not None or config.get('rope_parameters') is not None
            or config.get('use_sliding_window', False)):
        _unsupported('modified rotary or sliding-window configuration is not supported.')
    for key in ('quantization', 'quantization_config'):
        quant = config.get(key)
        if not isinstance(quant, dict) or quant.get('bits') != 4 or quant.get('group_size') != GROUP_SIZE:
            _unsupported('quantization must be affine 4-bit with group size 64.')
        if set(quant) - {'bits', 'group_size', 'mode'} or quant.get('mode', 'affine') != 'affine':
            _unsupported('only uniform affine quantization is supported.')


def _replace_module(model, name, replacement):
    parent, _, leaf = name.rpartition('.')
    setattr(model.get_submodule(parent) if parent else model, leaf, replacement)


def _load_packed_weights(model, tensors, device):
    """Install one checkpoint tensor at a time; useful independently in tiny tests."""
    modules = [(name, module) for name, module in model.named_modules()
               if isinstance(module, (nn.Linear, nn.Embedding)) and name != 'lm_head']
    expected = set()
    for name, module in modules:
        if isinstance(module, nn.Linear) and module.bias is not None:
            _unsupported('quantized linear layers must not contain ordinary biases.')
        expected.update(name + suffix for suffix in ('.weight', '.scales', '.biases'))
    matrix_names = {name + '.weight' for name, _ in modules} | {'lm_head.weight'}
    ordinary = [(name, parameter) for name, parameter in model.named_parameters()
                if name not in matrix_names]
    expected.update(name for name, _ in ordinary)
    if set(tensors.keys()) != expected:
        _unsupported('checkpoint tensor names do not match the original tied model.')
    for name, module in modules:
        packed = PackedAffine4(*(tensors.get_tensor(name + suffix).to(device)
                                for suffix in ('.weight', '.scales', '.biases')))
        if (packed.rows, packed.columns) != tuple(module.weight.shape):
            _unsupported('packed matrix dimensions do not match the model configuration.')
        replacement = PackedEmbedding(packed) if isinstance(module, nn.Embedding) else PackedLinear(packed)
        _replace_module(model, name, replacement)
    embedding = model.get_input_embeddings()
    if not isinstance(embedding, PackedEmbedding):
        _unsupported('the tied token embedding is missing.')
    # Share the SAME module/buffers. Never duplicate or fully expand vocabulary weights.
    model.set_output_embeddings(PackedLinear(embedding.packed))
    for name, parameter in ordinary:
        tensor = tensors.get_tensor(name)
        if tensor.dtype != torch.bfloat16 or tuple(tensor.shape) != tuple(parameter.shape):
            _unsupported('normalization tensor dtype or shape does not match the model.')
        parent, _, leaf = name.rpartition('.')
        owner = model.get_submodule(parent) if parent else model
        owner._parameters[leaf] = nn.Parameter(tensor.to(device), requires_grad=False)


def load_mlx_torch(model_path, device='cpu', threads=4):
    """Load only the local original snapshot, returning a standard HF model/tokenizer.

    Callers must bound input plus output tokens and pass ``logits_to_keep=1`` and
    ``do_sample=False`` to ``generate``. No conversion is written to disk.
    """
    root = Path(model_path)
    if device not in ('cpu', 'cuda') or not isinstance(threads, int) or threads < 1:
        _unsupported('device must be cpu/cuda and the thread count must be positive.')
    if device == 'cuda' and not torch.cuda.is_available():
        _unsupported('the explicitly selected CUDA device is unavailable.')
    try:
        config_data = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        _unsupported('the local model configuration is missing or invalid.')
    _validate_config(config_data)
    if not all((root / name).is_file() for name in ('model.safetensors', 'generation_config.json')):
        _unsupported('the original local weights or generation configuration are missing.')
    from safetensors import SafetensorError, safe_open
    from transformers import AutoTokenizer, GenerationConfig, Qwen3Config, Qwen3ForCausalLM
    from transformers.models.qwen3.modeling_qwen3 import Qwen3RotaryEmbedding

    torch.set_num_threads(threads)
    # These describe MLX storage, not a Transformers quantizer. Keep original
    # files intact while giving HF only its architecture configuration.
    runtime_config = {key: value for key, value in config_data.items()
                      if key not in ('quantization', 'quantization_config', 'torch_dtype')}
    runtime_config['dtype'] = config_data['torch_dtype']
    config = Qwen3Config.from_dict(runtime_config)
    config._attn_implementation = 'sdpa'
    with torch.device('meta'):
        model = Qwen3ForCausalLM(config)
    try:
        with safe_open(str(root / 'model.safetensors'), framework='pt', device='cpu') as tensors:
            _load_packed_weights(model, tensors, device)
    except (OSError, SafetensorError):
        _unsupported('the original safetensors checkpoint could not be read.')
    # Rotary frequencies are nonpersistent buffers, hence absent from safetensors.
    model.model.rotary_emb = Qwen3RotaryEmbedding(config).to(device)
    if any(value.is_meta for value in (*model.parameters(), *model.buffers())):
        _unsupported('a model tensor was not initialized from the local snapshot.')
    model.generation_config = GenerationConfig.from_pretrained(str(root), local_files_only=True)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False)
    return model, tokenizer
