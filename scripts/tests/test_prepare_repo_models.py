"""Synthetic byte fixtures for offline assembly; no inference or network."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import manage
from scripts import prepare_repo_models as bundle


def record(path, data):
    return {
        "path": path,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def fixture(tmp_path):
    parts = [
        record("asr/model.pt.part-001", b"first"),
        record("asr/model.pt.part-002", b"second"),
    ]
    for part, data in zip(parts, (b"first", b"second")):
        path = tmp_path / part["path"]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
    return {
        "schema_version": 1,
        "files": [{**record("asr/model.pt", b"firstsecond"), "parts": parts}],
    }


def test_assemble_then_verify_and_reuse(tmp_path):
    manifest = fixture(tmp_path)
    bundle.prepare(manifest, tmp_path)
    target = tmp_path / "asr/model.pt"
    assert target.read_bytes() == b"firstsecond"
    modified = target.stat().st_mtime_ns
    bundle.prepare(manifest, tmp_path, verify_only=True)
    bundle.prepare(manifest, tmp_path)
    assert target.stat().st_mtime_ns == modified
    assert all(
        (tmp_path / part["path"]).exists() for part in manifest["files"][0]["parts"]
    )


def test_bad_part_preserves_existing_model(tmp_path):
    manifest = fixture(tmp_path)
    target = tmp_path / "asr/model.pt"
    target.write_bytes(b"previous")
    (tmp_path / "asr/model.pt.part-002").write_bytes(b"broken")
    with pytest.raises(RuntimeError, match="Часть модели"):
        bundle.prepare(manifest, tmp_path)
    assert target.read_bytes() == b"previous"
    assert not (tmp_path / "asr/model.pt.assembling").exists()


def test_bad_final_hash_preserves_existing_model(tmp_path):
    manifest = fixture(tmp_path)
    manifest["files"][0]["sha256"] = "0" * 64
    target = tmp_path / "asr/model.pt"
    target.write_bytes(b"previous")
    with pytest.raises(RuntimeError, match="SHA-256"):
        bundle.prepare(manifest, tmp_path)
    assert target.read_bytes() == b"previous"
    assert not (tmp_path / "asr/model.pt.assembling").exists()


def test_component_selection_and_verify_only_do_not_assemble(tmp_path):
    manifest = fixture(tmp_path)
    bundle.prepare(manifest, tmp_path, components=["diarization"])
    assert not (tmp_path / "asr/model.pt").exists()
    with pytest.raises(RuntimeError, match="отсутствует"):
        bundle.prepare(manifest, tmp_path, verify_only=True)
    assert not (tmp_path / "asr/model.pt").exists()


def test_missing_unsplit_file_is_an_error(tmp_path):
    manifest = {"schema_version": 1, "files": [record("asr/tokens.lst", b"token")]}
    with pytest.raises(RuntimeError, match="asr/tokens.lst"):
        bundle.prepare(manifest, tmp_path)


def test_path_escape_is_rejected(tmp_path):
    manifest = fixture(tmp_path)
    manifest["files"][0]["parts"][0]["path"] = "../escape"
    with pytest.raises(ValueError, match="Unsafe"):
        bundle.prepare(manifest, tmp_path)


def test_size_mismatch_is_rejected(tmp_path):
    manifest = fixture(tmp_path)
    manifest["files"][0]["bytes"] += 1
    with pytest.raises(ValueError, match="Размеры"):
        bundle.prepare(manifest, tmp_path)


def test_bundle_matches_both_original_manifests():
    root = Path(__file__).parents[2]
    manifest = json.loads((root / "models/repository-models.lock.json").read_text())
    bundle.validate(manifest, root / "models")
    by_path = {item["path"]: item for item in manifest["files"]}
    for name in ["ai/mac-models.lock.json"]:
        original = json.loads((root / name).read_text())
        for item in original["files"]:
            assert all(
                by_path[item["path"]][key] == value for key, value in item.items()
            )
    assert all(
        part["bytes"] <= 48 * 1024**2
        for item in manifest["files"]
        for part in item.get("parts", [item])
    )


def test_launcher_defaults_to_bundled_models_and_preserves_overrides(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(manage.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(manage.platform, "machine", lambda: "arm64")
    monkeypatch.delenv("MEETING_MODEL_DIR", raising=False)
    args = SimpleNamespace(profile="mac", models=None)
    assert manage.environment(args)["AI_ASR_PATH"] == str(manage.ROOT / "models/asr")
    monkeypatch.setenv("MEETING_MODEL_DIR", str(tmp_path / "env-models"))
    assert manage.environment(args)["AI_ASR_PATH"] == str(tmp_path / "env-models/asr")
    args.models = str(tmp_path / "explicit")
    assert manage.environment(args)["AI_ASR_PATH"] == str(tmp_path / "explicit/asr")
