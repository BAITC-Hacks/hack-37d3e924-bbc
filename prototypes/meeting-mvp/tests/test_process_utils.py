import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from process_utils import stop_process_tree, worker_popen_kwargs


def test_worker_popen_kwargs_are_platform_specific():
    kwargs = worker_popen_kwargs()
    if os.name == 'nt':
        assert kwargs['creationflags'] & subprocess.CREATE_NEW_PROCESS_GROUP
        assert kwargs['creationflags'] & subprocess.CREATE_NO_WINDOW
        assert 'start_new_session' not in kwargs
    else:
        assert kwargs == {'start_new_session': True}


def test_stop_process_tree_stops_running_worker():
    proc = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(60)'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **worker_popen_kwargs(),
    )
    try:
        time.sleep(0.2)
        assert proc.poll() is None
        stop_process_tree(proc, timeout=5)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
