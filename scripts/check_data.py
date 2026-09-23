"""Check local audio and DOCX files without exposing meeting content.

Default checks do not load models. Optional diarization uses the original local
Sherpa ONNX bundle. These checks do not measure ASR, LLM or model quality.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.audio import prepare_audio  # noqa: E402 — direct script needs root on sys.path
from ai.diarization import diarize  # noqa: E402
from ai.settings import Settings  # noqa: E402
from ai.worker import OFFLINE_ENV, deny_network  # noqa: E402

AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac"}


def install_offline_guard():
    """Install a permanent guard in this command's process, not on import."""
    os.environ.update(OFFLINE_ENV)
    sys.addaudithook(deny_network)


def snapshot(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def check_diarization(audio_path, duration, settings):
    required = ("segmentation.onnx", "embedding.onnx")
    if not all((Path(settings.diarization_path) / name).is_file() for name in required):
        return {"status": "BLOCKED", "reason": "LOCAL_DIARIZATION_WEIGHTS_MISSING"}
    started = time.perf_counter()
    try:
        turns = diarize(audio_path, settings)["turns"]
        valid = bool(turns) and all(
            isinstance(turn.get("speaker_id"), str)
            and bool(turn["speaker_id"])
            and isinstance(turn.get("start"), (int, float))
            and isinstance(turn.get("end"), (int, float))
            and math.isfinite(turn["start"])
            and math.isfinite(turn["end"])
            and 0 <= turn["start"] < turn["end"] <= duration + 0.25
            for turn in turns
        )
        ordered = valid and all(
            left["start"] <= right["start"] for left, right in zip(turns, turns[1:])
        )
        return {
            "status": "PASS" if ordered else "FAIL",
            "turn_count": len(turns),
            "speaker_count": len({turn["speaker_id"] for turn in turns})
            if valid
            else None,
            "checks": {"valid_intervals": valid, "starts_sorted": ordered},
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as error:
        return {
            "status": "FAIL",
            "error_type": type(error).__name__,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }


def check_audio(path, temporary, settings, with_diarization):
    import soundfile as sf

    decoded = temporary / "audio.wav"
    duration = prepare_audio(
        path,
        decoded,
        settings.max_seconds,
        allowed_formats=("wav", "mp3", "mov", "flac"),
    )
    info = sf.info(str(decoded))
    checks = {
        "is_16khz": info.samplerate == 16000,
        "is_mono": info.channels == 1,
        "duration_positive": duration > 0,
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "duration_seconds": round(duration, 3),
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "checks": checks,
    }
    result["diarization"] = (
        check_diarization(decoded, duration, settings)
        if with_diarization and result["status"] == "PASS"
        else {"status": "NOT_RUN"}
    )
    return result


def check_docx(path, temporary):
    from docx import Document

    original = Document(path)
    copy_path = temporary / "roundtrip.docx"
    original.save(copy_path)
    restored = Document(copy_path)

    def texts(document):
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        cells = [
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        ]
        return paragraphs, cells

    paragraphs, cells = texts(original)
    checks = {
        "text_preserved": (paragraphs, cells) == texts(restored),
        "has_content": any(text.strip() for text in paragraphs + cells),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "paragraph_count": len(paragraphs),
        "table_count": len(original.tables),
        "cell_count": len(cells),
        "checks": checks,
    }


def run_checks(data_dir, output_dir, models, with_diarization=False):
    """Read sources, retain only metadata, and never overwrite earlier reports."""
    data_dir, output_dir = Path(data_dir).resolve(), Path(output_dir).resolve()
    if not data_dir.is_dir():
        raise ValueError("Data directory does not exist")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=output_dir))
    settings = Settings(
        diarizer="sherpa",
        diarization_path=str(Path(models).resolve() / "diarization"),
        device="cpu",
    )
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "File checks only; ASR, LLM and model quality are not evaluated.",
        "network": "Python sockets blocked; FFmpeg restricted to file/pipe protocols.",
        "diarization_requested": with_diarization,
        "files": [],
    }
    for path in sorted(data_dir.iterdir()):
        suffix = path.suffix.lower()
        if not path.is_file() or suffix not in AUDIO_SUFFIXES | {".docx"}:
            continue
        item = {"file": path.name, "kind": "docx" if suffix == ".docx" else "audio"}
        started = time.perf_counter()
        before = None
        try:
            before = snapshot(path)
            item["source"] = before
            with tempfile.TemporaryDirectory(prefix="check-", dir=run_dir) as directory:
                temporary = Path(directory)
                item.update(
                    check_docx(path, temporary)
                    if suffix == ".docx"
                    else check_audio(path, temporary, settings, with_diarization)
                )
        except Exception as error:
            item.update(status="FAIL", error_type=type(error).__name__)
        try:
            item["source_unchanged"] = before is not None and before == snapshot(path)
        except OSError:
            item["source_unchanged"] = False
        if not item["source_unchanged"]:
            item["status"] = "FAIL"
        item["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        report["files"].append(item)
    statuses = [item["status"] for item in report["files"]]
    statuses += [
        item["diarization"]["status"]
        for item in report["files"]
        if "diarization" in item
    ]
    report["status"] = (
        "FAIL"
        if not report["files"] or "FAIL" in statuses
        else "PARTIAL"
        if "BLOCKED" in statuses
        else "PASS"
    )
    report_path = run_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report, report_path


def main(argv=None):
    install_offline_guard()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/data-smoke")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Also check local Sherpa ONNX diarization.",
    )
    args = parser.parse_args(argv)
    try:
        report, path = run_checks(
            args.data_dir, args.output_dir, args.models, args.diarize
        )
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "report": str(path),
                    "audio_count": sum(
                        item["kind"] == "audio" for item in report["files"]
                    ),
                    "docx_count": sum(
                        item["kind"] == "docx" for item in report["files"]
                    ),
                }
            )
        )
        return {"PASS": 0, "FAIL": 1, "PARTIAL": 2}[report["status"]]
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
