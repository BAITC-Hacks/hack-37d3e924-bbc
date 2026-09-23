"""Online provisioning only. Never imported by inference. Downloads no meeting data."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    manifest = json.loads(
        (Path(__file__).parent / "models.json").read_text(encoding="utf-8")
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=manifest)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument(
        "--convert",
        action="store_true",
        help="Convert Whisper checkpoint to a sibling -ct2 directory",
    )
    parser.add_argument(
        "--quantization", choices=["float16", "int8"], default="float16"
    )
    args = parser.parse_args()
    from huggingface_hub import snapshot_download

    spec = manifest[args.model]
    patterns = [
        "*.json",
        "*.safetensors",
        "*.txt",
        "*.model",
        "*.jinja",
        "*.yaml",
        "*.bin",
        "README.md",
        "LICENSE*",
    ]
    if spec["kind"] == "diarization":
        patterns = None
    if spec["kind"] == "ctc":
        patterns = ["asr/rukk/model.pt", "asr/rukk/tokens.lst", "README.md", "LICENSE*"]
    snapshot_download(
        spec["repo"],
        revision=spec["revision"],
        local_dir=args.directory,
        allow_patterns=patterns,
        max_workers=2,
    )
    if spec["kind"] == "ctc":
        for name in ("model.pt", "tokens.lst"):
            shutil.copyfile(args.directory / "asr/rukk" / name, args.directory / name)
    target = args.directory
    if args.convert:
        if spec["kind"] != "whisper":
            parser.error("--convert applies only to Whisper")
        target = Path(str(args.directory) + "-ct2")
        subprocess.run(
            [
                str(Path(sys.executable).with_name("ct2-transformers-converter")),
                "--low_cpu_mem_usage",
                "--model",
                str(args.directory),
                "--output_dir",
                str(target),
                "--copy_files",
                "tokenizer.json",
                "preprocessor_config.json",
                "--quantization",
                args.quantization,
            ],
            check=True,
        )
    files = []
    for p in sorted(target.rglob("*")):
        if not p.is_file() or ".cache" in p.parts or p.name == "provenance.json":
            continue
        h = hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        files.append(
            {
                "path": str(p.relative_to(target)),
                "sha256": h.hexdigest(),
                "bytes": p.stat().st_size,
            }
        )
    (target / "provenance.json").write_text(
        json.dumps(
            {
                **spec,
                "converted": args.convert,
                "quantization": args.quantization if args.convert else None,
                "files": files,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Prepared local model and provenance:", target)


if __name__ == "__main__":
    main()
