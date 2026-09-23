"""Single local worker. Startup recovers abandoned work only after acquiring its lock."""

import argparse
import ctypes
import hashlib
import json
import os
import signal
import time
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from ctypes import wintypes
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai.inference_lock import acquire_inference_lock
from ai.pipeline import run_pipeline
from ai.validation import validate_result

from .settings import Settings
from .store import Store

WAIT_OBJECT_0 = 0
WAIT_ABANDONED = 0x00000080


def fixture_result(data, progress):
    """Explicit app demo adapter; never used after a real pipeline failure."""
    example = json.loads(
        (
            Path(__file__).resolve().parents[1] / "contracts/examples/result.json"
        ).read_text(encoding="utf-8")
    )
    result = deepcopy(example)
    for key in ("meeting_id", "meeting_datetime", "timezone", "participants"):
        result[key] = deepcopy(data[key])
    mapping = {
        p["id"]: data["participants"][i]
        for i, p in enumerate(example["participants"])
        if i < len(data["participants"])
    }
    day = (
        datetime.fromisoformat(data["meeting_datetime"].replace("Z", "+00:00"))
        .astimezone(ZoneInfo(data["timezone"]))
        .date()
    )
    shift = day - date.fromisoformat(example["meeting_datetime"][:10])
    for task in result["tasks"]:
        participant = mapping.get(task["assignee_id"])
        task["assignee_id"] = participant["id"] if participant else None
        if task["due_date"]:
            task["due_date"] = (
                date.fromisoformat(task["due_date"]) + shift
            ).isoformat()
        task["needs_review"] = True
    for segment in result["segments"]:
        for original in example["participants"]:
            replacement = mapping.get(original["id"], {}).get("name")
            if replacement:
                segment["text"] = segment["text"].replace(original["name"], replacement)
    result["summary"] = (
        "ТЕСТОВЫЙ РЕЗУЛЬТАТ. Синтетический пример поручений; загруженное аудио не распознавалось."
    )
    progress({"stage": "validating"})
    return validate_result(result, data)


def process_one(store, pipeline=None):
    """Process one claimed job; return False when the queue is empty."""
    row = store.claim()
    if row is None:
        return False
    try:
        data = json.loads(row["input_json"])
        if not Path(data["audio_path"]).is_file():
            raise ValueError("Missing upload")

        def progress(event):
            return store.progress(row["id"], event)

        # Persisted job mode, not ambient AI_MODE, selects execution. No fallback.
        if row["mode"] == "fixture":
            result = fixture_result(data, progress)
        else:
            os.environ["AI_MODE"] = "real"
            result = (pipeline or run_pipeline)(data, on_progress=progress)
        store.complete(row["id"], result)
    except Exception:
        store.fail(row["id"])
    return True


class WindowsKillOnCloseJob:
    """Let Windows terminate stage subprocesses when this worker exits."""

    def __init__(self):
        self.handle = None

    def __enter__(self):
        if os.name != "nt":
            return self
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OSError(error, "SetInformationJobObject failed")
        ok = kernel32.AssignProcessToJobObject(handle, kernel32.GetCurrentProcess())
        if not ok:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OSError(error, "AssignProcessToJobObject failed")
        self.handle = handle
        self.kernel32 = kernel32
        return self

    def __exit__(self, exc_type, exc, traceback):
        # Keep the kill-on-close handle alive until process teardown. Closing it
        # here would terminate this process too and mask the intended exit code.
        return False


class WindowsNamedMutex:
    """Hold one Windows worker lock per resolved database path."""

    def __init__(self, path):
        self.path = path
        self.handle = None

    def __enter__(self):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        digest = hashlib.sha256(
            str(self.path.resolve()).lower().encode("utf-8")
        ).hexdigest()
        handle = kernel32.CreateMutexW(None, False, "Local\\meeting-worker-" + digest)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
        status = kernel32.WaitForSingleObject(handle, 0)
        if status not in {WAIT_OBJECT_0, WAIT_ABANDONED}:
            kernel32.CloseHandle(handle)
            raise BlockingIOError("Another worker process is already running.")
        self.handle = handle
        self.kernel32 = kernel32
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.handle:
            self.kernel32.ReleaseMutex(self.handle)
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


if os.name == "nt":
    DWORD = ctypes.c_ulong
    SIZE_T = ctypes.c_size_t
    LARGE_INTEGER = ctypes.c_longlong
    ULONG_PTR = SIZE_T
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", LARGE_INTEGER),
            ("PerJobUserTimeLimit", LARGE_INTEGER),
            ("LimitFlags", DWORD),
            ("MinimumWorkingSetSize", SIZE_T),
            ("MaximumWorkingSetSize", SIZE_T),
            ("ActiveProcessLimit", DWORD),
            ("Affinity", ULONG_PTR),
            ("PriorityClass", DWORD),
            ("SchedulingClass", DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", SIZE_T),
            ("JobMemoryLimit", SIZE_T),
            ("PeakProcessMemoryUsed", SIZE_T),
            ("PeakJobMemoryUsed", SIZE_T),
        ]


def isolate_worker():
    if os.name == "nt":
        return WindowsKillOnCloseJob()
    # A direct shell launch otherwise shares the caller's process group.
    # manage.py already gives this process its own session/group.
    if os.getpgrp() != os.getpid():
        os.setsid()
    return nullcontext()


def stop(signum, frame):
    if os.name != "nt":
        # Ignore both our own broadcast and repeated supervisor signals.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            os.killpg(os.getpid(), signal.SIGTERM)
        finally:
            # Unwinds subprocess.run: it kills/reaps its active stage even
            # if that stage ignored SIGTERM. The next worker recovers the job.
            raise SystemExit(128 + signum)
    raise SystemExit(128 + signum)


@contextmanager
def worker_lock(settings):
    lock = settings.database.with_suffix(".worker.lock")
    try:
        if os.name == "nt":
            with WindowsNamedMutex(lock):
                yield
        else:
            with acquire_inference_lock(lock):
                yield
    except BlockingIOError:
        raise SystemExit("Другой worker уже запущен для этой базы.") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued meeting and exit",
    )
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with isolate_worker():
        settings = Settings.from_env()
        store = Store(settings)
        # Same database implies same lock, even when DATA_DIR spelling differs.
        with worker_lock(settings):
            store.recover()
            while True:
                worked = process_one(store)
                if args.once:
                    break
                if not worked:
                    time.sleep(0.5)


if __name__ == "__main__":
    main()
