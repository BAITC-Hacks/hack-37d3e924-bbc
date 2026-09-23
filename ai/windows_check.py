"""Check the original local Windows model profile without loading any weights."""

import argparse
import contextlib
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import platform
from pathlib import Path

MANIFEST = Path(__file__).with_name("mac-models.lock.json")
DEPENDENCIES = {
    "torch": "torch",
    "transformers": "transformers",
    "safetensors": "safetensors",
    "sherpa-onnx": "sherpa_onnx",
    "soundfile": "soundfile",
    "imageio-ffmpeg": "imageio_ffmpeg",
}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_model_config(config):
    from .mlx_torch import _validate_config

    _validate_config(config)


def check_windows_models(models, device, verify_hashes=False):
    """Return JSON-safe readiness diagnostics; never download or load a model.

    File failures stop before dependency imports. Size checks alone do not prove
    file identity: callers must request hashes for that stronger verification.
    """
    report = {
        "ok": False,
        "errors": [],
        "models": {
            "source": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
            "revision": None,
            "files_checked": 0,
            "total_bytes": 0,
            "hashes_verified": False,
            "config_valid": False,
        },
        "hardware": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "device": device,
            "cuda_available": None,
            "cuda_runtime": None,
            "bf16_supported": None,
        },
        "packages": {name: None for name in DEPENDENCIES},
    }

    def error(code, message, **details):
        report["errors"].append({"code": code, "message": message, **details})

    if device not in ("cpu", "cuda"):
        error(
            "INVALID_DEVICE",
            "Choose device cpu or cuda; automatic fallback is disabled.",
        )
        return report
    try:
        directory = Path(models).expanduser().resolve()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = manifest["files"]
        if not isinstance(entries, list) or not entries:
            raise ValueError()
        report["models"]["revision"] = manifest["llm_revision"]
        for item in entries:
            relative = item["path"]
            path = (directory / relative).resolve()
            if not path.is_relative_to(directory):
                raise ValueError()
            expected_size = item["bytes"]
            expected_hash = item["sha256"]
            if (
                not isinstance(expected_size, int)
                or expected_size < 0
                or len(expected_hash) != 64
            ):
                raise ValueError()
            report["models"]["total_bytes"] += expected_size
            report["models"]["files_checked"] += 1
            if not path.is_file():
                error(
                    "MODEL_FILE_MISSING",
                    "Restore this file from the original pinned model bundle.",
                    file=relative,
                )
                continue
            if path.stat().st_size != expected_size:
                error(
                    "MODEL_SIZE_MISMATCH",
                    "Restore the complete original pinned file; its size differs.",
                    file=relative,
                )
                continue
            if verify_hashes and _sha256(path) != expected_hash:
                error(
                    "MODEL_HASH_MISMATCH",
                    "Restore the original pinned file; its SHA256 differs.",
                    file=relative,
                )
    except (OSError, ValueError, KeyError, TypeError):
        error(
            "MODEL_FILES_UNREADABLE",
            "Check the model directory, file permissions and ai/mac-models.lock.json.",
        )
    if report["errors"]:
        return report
    report["models"]["hashes_verified"] = bool(verify_hashes)

    modules = {}
    for package, module in DEPENDENCIES.items():
        try:
            modules[package] = importlib.import_module(module)
            try:
                report["packages"][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                version = getattr(modules[package], "__version__", None)
                report["packages"][package] = (
                    str(version) if version is not None else None
                )
        except Exception:
            error(
                "DEPENDENCY_UNAVAILABLE",
                "Install or repair this package in the Python environment used by the Windows launcher.",
                package=package,
            )

    if "torch" in modules:
        try:
            config = json.loads(
                (directory / "llm" / "config.json").read_text(encoding="utf-8")
            )
            _validate_model_config(config)
            report["models"]["config_valid"] = True
        except Exception:
            error(
                "MODEL_FORMAT_INVALID",
                "Use the original Qwen3-4B-Instruct-2507 tied embedding configuration with affine 4-bit groups of 64.",
            )
        torch = modules["torch"]
        try:
            report["hardware"]["cuda_runtime"] = torch.version.cuda
            available = bool(torch.cuda.is_available())
            report["hardware"]["cuda_available"] = available
            if device == "cuda":
                if not available:
                    error(
                        "CUDA_UNAVAILABLE",
                        "Install CUDA-enabled PyTorch and a compatible NVIDIA driver; CPU fallback is disabled.",
                    )
                else:
                    properties = torch.cuda.get_device_properties(0)
                    free, total = torch.cuda.mem_get_info(0)
                    supported = bool(
                        torch.cuda.is_bf16_supported(including_emulation=False)
                    )
                    report["hardware"].update(
                        gpu_name=str(properties.name),
                        gpu_total_bytes=int(total),
                        gpu_free_bytes=int(free),
                        bf16_supported=supported,
                    )
                    if not supported:
                        error(
                            "CUDA_BF16_UNSUPPORTED",
                            "The selected CUDA device must support native BF16 for this original-weight adapter.",
                        )
        except Exception:
            if device == "cuda":
                error(
                    "CUDA_CHECK_FAILED",
                    "Check CUDA-enabled PyTorch and the NVIDIA driver in this Python environment.",
                )
    report["ok"] = not report["errors"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args(argv)
    # Optional libraries can print on import; stdout remains one JSON document.
    with contextlib.redirect_stdout(io.StringIO()):
        result = check_windows_models(args.models, args.device, args.verify_hashes)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
