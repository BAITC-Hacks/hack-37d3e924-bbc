# Model provenance and third-party notices

This distribution redistributes the exact files pinned by `ai/mac-models.lock.json`
and `prototypes/meeting-mvp/models.lock.json`. Model bytes are unchanged.
The large ASR and MLX weight files are split for Git transport and reassembled
byte-for-byte. The release copy splits only the MLX weight file.
No recordings, transcripts, training datasets, credentials or caches are included.

## Kazakh/Russian mixed STT — alibiserikbay

- Source: https://huggingface.co/alibiserikbay/kazakh-russian-mixed-stt
- Revision: `26298d2a61dc1573bfc11b7055c7d09a1e64b8a4`
- Files: `asr/model.pt`, `asr/tokens.lst`, from upstream `asr/rukk/`.
- License: Apache-2.0; full text in `licenses/Apache-2.0.txt`.
- Attribution: alibiserikbay, *Kazakh and Kazakh-Russian Mixed STT* (2026).
- The model card credits ISSAI KSC2 (Saida Mussakhojayeva, Yerbolat
  Khassanov, Huseyin Atakan Varol, *KSC2: An Industrial-Scale Open-Source
  Kazakh Speech Corpus*, Interspeech 2022), NCSpeech YO-CPT-ru (CC BY 4.0,
  derived from YODAS2 audio under CC BY 3.0), and Google FLEURS.
  These datasets are not included in this release.

## Qwen3-4B-Instruct-2507 — MLX 4-bit conversion

- Conversion: https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit
- Revision: `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`
- Base model: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Files: complete pinned `llm/` directory, including its original README.
- License: Apache-2.0; original text in `licenses/Qwen-LICENSE.txt`,
  Copyright 2024 Alibaba Cloud.
- The upstream MLX community conversion uses mlx-lm 0.26.2. This release
  makes no additional model conversion or quantization.

## Speaker segmentation and embedding

- `diarization/segmentation.onnx`: Sherpa ONNX export of
  https://huggingface.co/pyannote/segmentation-3.0;
  MIT License, Copyright (c) 2022 CNRS. The original archive license is
  preserved in `licenses/pyannote-MIT.txt`.
- Export: https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models
- `diarization/embedding.onnx`: 3D-Speaker ERes2Net base, Chinese 16 kHz;
  https://github.com/modelscope/3D-Speaker; Apache-2.0,
  original license in `licenses/3D-Speaker-LICENSE.txt`.
- Export: https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models
- Sherpa ONNX is an Apache-2.0 project:
  https://github.com/k2-fsa/sherpa-onnx.

Original download URLs and SHA-256 hashes are retained in
`github-release.lock.json`. These models keep their respective licenses;
they are not relicensed as project-owned weights. Retain this notice and
the license files when copying or redistributing the model directory.
