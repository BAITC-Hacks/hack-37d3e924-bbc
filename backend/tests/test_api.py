import io
import json
import wave
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.settings import Settings
from backend.store import APIError
from backend.worker import process_one


def audio_bytes():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    return stream.getvalue()


@pytest.fixture
def setup(tmp_path):
    settings = Settings(tmp_path, tmp_path / "meetings.sqlite3", "fixture")
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app.state.store, settings


def upload(client, **overrides):
    metadata = {
        "title": " Обсуждение ",
        "meeting_datetime": "2026-09-23T10:00:00+05:00",
        "timezone": "Asia/Almaty",
        "participants": [{"id": "person-a", "name": "Дарын", "speaker_ids": []}],
    }
    metadata.update(overrides)
    return client.post(
        "/api/v1/meetings",
        data={"metadata": json.dumps(metadata)},
        files={"audio": ("../../recording.wav", audio_bytes(), "audio/wav")},
    )


def finish(client, store):
    response = upload(client)
    assert response.status_code == 202, response.text
    meeting = response.json()
    assert process_one(store)
    result = client.get("/api/v1/meetings/" + meeting["id"]).json()
    assert result["status"] == "done", result
    return result


def review_body(meeting):
    return {
        "expected_revision": meeting["revision"],
        **{
            k: deepcopy(meeting["result"][k])
            for k in ("participants", "tasks", "summary")
        },
    }


def test_complete_workflow_preserves_original_export_and_restart(setup):
    client, store, settings = setup
    assert client.get("/health").json() == {"status": "ok"}
    meeting = finish(client, store)
    path = "/api/v1/meetings/" + meeting["id"]
    assert meeting["mode"] == "fixture"
    assert meeting["revision"] == 1
    original = client.get(path + "/original").json()
    body = review_body(meeting)
    body["summary"] = "Исправлено: келісім дайын."
    body["participants"][0]["speaker_ids"] = ["SPEAKER_00"]
    response = client.put(path + "/review", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert client.get(path + "/original").json() == original
    restarted = TestClient(create_app(settings))
    assert restarted.get(path).json()["result"]["summary"] == body["summary"]
    exported = restarted.get(path + "/export.docx")
    assert exported.status_code == 200
    xml = ZipFile(io.BytesIO(exported.content)).read("word/document.xml").decode()
    assert body["summary"] in xml
    assert "ТЕСТОВЫЙ РЕЗУЛЬТАТ" in xml
    assert client.get("/api/v1/meetings").json()["items"][0]["result"] is None
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert not list(settings.audio_dir.iterdir())


@pytest.mark.parametrize(
    "mutation",
    ["source", "date", "assignee", "speaker", "review", "participants", "empty"],
)
def test_review_rejects_invalid_data(setup, mutation):
    client, store, _ = setup
    meeting = finish(client, store)
    body = review_body(meeting)
    if mutation == "source":
        body["tasks"][0]["source_segment_ids"] = []
    elif mutation == "date":
        body["tasks"][0]["due_date"] = "2026-02-30"
    elif mutation == "assignee":
        body["tasks"][0]["assignee_id"] = "missing"
    elif mutation == "speaker":
        body["participants"][0]["speaker_ids"] = ["not-a-speaker"]
    elif mutation == "review":
        body["tasks"][0]["assignee_id"] = None
        body["tasks"][0]["needs_review"] = False
    elif mutation == "participants":
        body["participants"] = []
    else:
        body["tasks"][0]["text"] = " "
    response = client.put("/api/v1/meetings/" + meeting["id"] + "/review", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert store.get(meeting["id"])["revision"] == 1


def test_concurrent_reviews_allow_exactly_one_revision(setup):
    client, store, _ = setup
    meeting = finish(client, store)
    body = review_body(meeting)

    def save():
        try:
            return store.review(meeting["id"], body)["revision"]
        except APIError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: save(), range(2)))
    assert sorted(map(str, responses)) == ["2", "REVISION_CONFLICT"]


def test_claim_delete_recovery_retry_and_state_guards(setup):
    client, store, _ = setup
    meeting = upload(client).json()
    path = "/api/v1/meetings/" + meeting["id"]
    assert client.get(path + "/original").status_code == 409
    assert client.get(path + "/export.docx").status_code == 409
    assert client.post(path + "/retry").status_code == 409
    assert store.claim()["id"] == meeting["id"]
    assert store.claim() is None
    assert client.delete(path).status_code == 409
    store.recover()
    failed = client.get(path).json()
    assert failed["status"] == "failed"
    assert failed["error"] == {
        "code": "PROCESSING_FAILED",
        "message": "Обработка не завершена",
        "details": {},
    }
    assert client.post(path + "/retry").status_code == 202
    assert process_one(store)
    assert client.get(path).json()["status"] == "done"
    assert client.post(path + "/retry").status_code == 409


def test_real_errors_never_become_fixture_and_retry_same_id(tmp_path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "meetings.sqlite3", "real")
    client = TestClient(create_app(settings))
    store = client.app.state.store
    meeting = upload(client).json()
    monkeypatch.setenv("AI_MODE", "fixture")

    def failing(data, on_progress):
        import os

        assert os.environ["AI_MODE"] == "real"
        on_progress({"stage": "transcribing"})
        raise RuntimeError("PRIVATE TRANSCRIPT /private/path TOKEN")

    assert process_one(store, pipeline=failing)
    failure = store.get(meeting["id"])
    assert failure["status"] == "failed"
    assert failure["mode"] == "real"
    assert "PRIVATE" not in json.dumps(failure)
    assert failure["result"] is None
    assert (
        client.post("/api/v1/meetings/" + meeting["id"] + "/retry").json()["id"]
        == meeting["id"]
    )


def test_invalid_audio_json_metadata_and_limits(setup, tmp_path):
    client, _, settings = setup
    assert upload(client, title=" ").status_code == 422
    assert upload(client, timezone="no-such-timezone").status_code == 422
    response = client.post(
        "/api/v1/meetings", data={"metadata": "{}"}, files={"audio": ("bad.exe", b"x")}
    )
    assert response.status_code == 415
    meta = {
        "title": "Test",
        "meeting_datetime": "2026-09-23T10:00:00+05:00",
        "timezone": "Asia/Almaty",
        "participants": [],
    }
    for metadata, content, expected in [
        ("{", audio_bytes(), 422),
        (json.dumps(meta), b"broken file", 415),
    ]:
        response = client.post(
            "/api/v1/meetings",
            data={"metadata": metadata},
            files={"audio": ("bad.wav", content)},
        )
        assert response.status_code == expected
        assert "error" in response.json()
    assert list(settings.audio_dir.iterdir()) == []
    small = TestClient(
        create_app(Settings(tmp_path / "small", tmp_path / "small/db", "fixture", 100))
    )
    assert upload(small).status_code == 413
    assert client.post("/api/v1/meetings").status_code == 422


def test_unlink_failure_is_not_reported_as_deleted(setup, monkeypatch):
    client, store, _ = setup
    meeting = upload(client).json()

    def denied(*args, **kwargs):
        raise PermissionError("private path")

    monkeypatch.setattr(Path, "unlink", denied)
    response = client.delete("/api/v1/meetings/" + meeting["id"])
    assert response.status_code == 500
    assert store.get(meeting["id"])["status"] == "queued"


def test_missing_audio_and_invalid_pipeline_result_fail(setup):
    client, store, settings = setup
    meeting = upload(client).json()
    next(settings.audio_dir.iterdir()).unlink()
    assert process_one(store)
    assert store.get(meeting["id"])["status"] == "failed"


def test_claim_is_atomic_between_consumers(setup):
    client, store, _ = setup
    meeting = upload(client).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: store.claim(), range(2)))
    assert len([r for r in rows if r is not None]) == 1
    assert next(r for r in rows if r)["id"] == meeting["id"]


def test_renamed_local_playlist_is_rejected(setup, tmp_path):
    client, _, _ = setup
    secret = tmp_path / "private.wav"
    secret.write_bytes(audio_bytes())
    playlist = f"ffconcat version 1.0\nfile '{secret}'\n".encode()
    meta = {
        "title": "Test",
        "meeting_datetime": "2026-09-23T10:00:00+05:00",
        "timezone": "Asia/Almaty",
        "participants": [],
    }
    response = client.post(
        "/api/v1/meetings",
        data={"metadata": json.dumps(meta)},
        files={"audio": ("innocent.wav", playlist)},
    )
    assert response.status_code == 415


def test_actual_worker_process_fixture_and_singleton_lock(setup):
    import os
    import subprocess
    import sys

    from backend.worker import worker_lock

    client, store, settings = setup
    meeting = upload(client).json()
    environment = {
        **os.environ,
        "DATA_DIR": str(settings.data_dir),
        "DATABASE_PATH": str(settings.database),
        "PIPELINE_MODE": "fixture",
    }
    command = [sys.executable, "-m", "backend.worker", "--once"]
    with worker_lock(settings):
        rejected = subprocess.run(
            command, env=environment, capture_output=True, timeout=15
        )
        assert rejected.returncode != 0
        assert store.get(meeting["id"])["status"] == "queued"
    completed = subprocess.run(
        command, env=environment, capture_output=True, timeout=15
    )
    assert completed.returncode == 0, completed.stderr.decode()
    assert store.get(meeting["id"])["status"] == "done"


def test_direct_worker_shutdown_stops_stage_without_signalling_caller(tmp_path):
    import ctypes
    import os
    import signal
    import subprocess
    import sys
    import time

    settings = Settings(tmp_path, tmp_path / "meetings.sqlite3", "real")
    client = TestClient(create_app(settings))
    store = client.app.state.store
    meeting = upload(client).json()
    child_ready = tmp_path / "stage.pid"
    environment = {
        **os.environ,
        "DATA_DIR": str(tmp_path),
        "DATABASE_PATH": str(settings.database),
        "PIPELINE_MODE": "real",
        "TEST_STAGE_PID": str(child_ready),
    }
    # The sleeping child stands in for a long-running model stage. It ignores
    # TERM to prove subprocess.run unwinding forcibly kills and reaps it.
    stage_code = "import os,pathlib,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); pathlib.Path(os.environ['TEST_STAGE_PID']).write_text(str(os.getpid())); time.sleep(60)"
    worker_code = (
        "import subprocess,sys; import backend.worker as worker\n"
        f'def slow(data, on_progress):\n    subprocess.run([sys.executable, "-c", {stage_code!r}], check=True)\n'
        "worker.run_pipeline = slow\nworker.main()\n"
    )
    sibling = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    worker = subprocess.Popen([sys.executable, "-c", worker_code], env=environment)
    try:
        deadline = time.monotonic() + 10
        while not child_ready.exists() and time.monotonic() < deadline:
            assert worker.poll() is None
            time.sleep(0.02)
        assert child_ready.exists(), "Model stage did not start"
        child_pid = int(child_ready.read_text())
        if os.name != "nt":
            assert os.getpgid(worker.pid) == worker.pid
            worker.send_signal(signal.SIGTERM)
            assert worker.wait(timeout=3) == 128 + signal.SIGTERM
        else:
            worker.terminate()
            assert worker.wait(timeout=3) != 0
        assert sibling.poll() is None
        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(0x1000, False, child_pid)
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                assert exit_code.value != 259
            else:
                assert not handle
        else:
            with pytest.raises(ProcessLookupError):
                os.kill(child_pid, 0)
        assert store.get(meeting["id"])["status"] == "processing"
        restarted = subprocess.run(
            [sys.executable, "-m", "backend.worker", "--once"],
            env=environment,
            capture_output=True,
            timeout=10,
        )
        assert restarted.returncode == 0, restarted.stderr.decode()
        assert store.get(meeting["id"])["status"] == "failed"
        assert (
            client.post("/api/v1/meetings/" + meeting["id"] + "/retry").status_code
            == 202
        )
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=3)
        sibling.terminate()
        sibling.wait(timeout=3)
