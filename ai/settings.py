"""Deployment settings, deliberately outside the shared input/result contract."""
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from .errors import PipelineError
from .validation import require

@dataclass
class Settings:
    asr: str = 'whisper'
    diarizer: str = 'community1'
    llm: str = 'transformers'
    asr_path: str = ''
    diarization_path: str = ''
    llm_path: str = ''
    device: str = 'cuda'
    compute_type: str = 'float16'
    language: str | None = None
    quantization: str = 'none'
    num_speakers: int = 0
    max_seconds: int = 3600
    context_tokens: int = 8192
    max_new_tokens: int = 2048
    threads: int = 4

    @classmethod
    def from_env(cls):
        try:
            llm = os.getenv('AI_LLM', 'transformers')
            s = cls(asr=os.getenv('AI_ASR', 'whisper'), diarizer=os.getenv('AI_DIARIZER', 'community1'),
                llm=llm, asr_path=os.getenv('AI_ASR_PATH', ''),
                diarization_path=os.getenv('AI_DIARIZATION_PATH', ''), llm_path=os.getenv('AI_LLM_PATH', ''),
                device=os.getenv('AI_DEVICE', 'cuda'), compute_type=os.getenv('AI_COMPUTE_TYPE', 'float16'),
                language=os.getenv('AI_LANGUAGE') or None, quantization=os.getenv('AI_QUANTIZATION', 'none'),
                num_speakers=int(os.getenv('AI_NUM_SPEAKERS', '0')), max_seconds=int(os.getenv('AI_MAX_SECONDS', '3600')),
                context_tokens=int(os.getenv('AI_CONTEXT_TOKENS', '2048' if llm == 'mlx_torch' else '8192')),
                max_new_tokens=int(os.getenv('AI_MAX_NEW_TOKENS', '512' if llm == 'mlx_torch' else '2048')))
            require(s.asr in ('whisper', 'mixed_ctc') and s.diarizer in ('community1', 'sherpa'))
            require(s.llm in ('transformers', 'mlx', 'mlx_torch') and s.device in ('cpu', 'cuda'))
            require(s.quantization in ('none', 'nf4') and s.language in (None, 'ru', 'kk'))
            require(s.llm != 'mlx_torch' or s.quantization == 'none')
            require(0 <= s.num_speakers <= 32 and 1 <= s.max_seconds <= 7200)
            require(2048 <= s.context_tokens <= 16384 and 256 <= s.max_new_tokens <= s.context_tokens // 2)
            for p in (s.asr_path, s.diarization_path, s.llm_path):
                require(p and Path(p).is_dir())
            if s.asr == 'whisper':
                require(all((Path(s.asr_path)/n).is_file() for n in ('model.bin', 'tokenizer.json', 'preprocessor_config.json')))
            if s.asr == 'mixed_ctc':
                require(all((Path(s.asr_path)/n).is_file() for n in ('model.pt', 'tokens.lst')))
            s.asr_path = str(Path(s.asr_path).resolve())
            s.diarization_path = str(Path(s.diarization_path).resolve())
            s.llm_path = str(Path(s.llm_path).resolve())
            return s
        except Exception:
            raise PipelineError('MODEL_UNAVAILABLE', 'Проверьте настройки и локальные каталоги моделей ИИ.') from None

    def to_dict(self):
        return asdict(self)
