"""ASR-only benchmark on local labeled clips; never an application pipeline fallback.
Manifest: [{"id":"kk-1","audio_path":"/data/kk.wav","reference":"..."}].
Outputs local hypotheses and normalized WER/CER; keep private meeting references off Git.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from .extraction import normal


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = new
    return row[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    from .asr import transcribe
    from .audio import prepare_audio
    from .settings import Settings
    from .worker import OFFLINE_ENV, deny_network, peak_rss_bytes

    os.environ.update(OFFLINE_ENV)
    os.umask(0o077)
    sys.addaudithook(deny_network)
    settings = Settings.from_env()
    results = []
    for item in json.loads(args.manifest.read_text(encoding="utf-8")):
        with tempfile.TemporaryDirectory(prefix="asr-eval-") as d:
            audio = Path(d) / "audio.wav"
            duration = prepare_audio(item["audio_path"], audio, settings.max_seconds)
            started = time.monotonic()
            words = transcribe(audio, settings)
            elapsed = time.monotonic() - started
            hypothesis = " ".join(w["text"].strip() for w in words)
            ref, hyp = normal(item["reference"]), normal(hypothesis)
            result = {
                "id": item["id"],
                "duration_seconds": duration,
                "asr_seconds": round(elapsed, 3),
                "rtf": elapsed / duration,
                "reference_words": len(ref.split()),
                "audio_sha256": hashlib.sha256(
                    Path(item["audio_path"]).read_bytes()
                ).hexdigest(),
                "reference_sha256": hashlib.sha256(
                    item["reference"].encode()
                ).hexdigest(),
                "word_edits": distance(ref.split(), hyp.split()),
                "char_edits": distance(ref, hyp),
                "wer": distance(ref.split(), hyp.split()) / max(1, len(ref.split())),
                "cer": distance(ref, hyp) / max(1, len(ref)),
                "hypothesis": hypothesis,
                "words": words,
            }
            results.append(result)
            print(item["id"], "complete", flush=True)
    args.output.write_text(
        json.dumps(
            {
                "asr": settings.asr,
                "compute_type": settings.compute_type
                if settings.asr == "whisper"
                else "checkpoint",
                "device": settings.device,
                "language": settings.language,
                "peak_rss_bytes": peak_rss_bytes(),
                "normalization": "Unicode lower-case, punctuation removed, digits are NOT expanded; no translation.",
                "clips": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
