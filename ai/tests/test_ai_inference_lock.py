import subprocess
import sys
from pathlib import Path

import pytest

from ai.inference_lock import acquire_inference_lock


ROOT = Path(__file__).resolve().parents[2]


def test_lock_excludes_another_process_and_releases(tmp_path):
    lock_path = tmp_path/'inference.lock'
    script = (
        'import sys; '
        'from pathlib import Path; '
        'from ai.inference_lock import acquire_inference_lock; '
        'lock=acquire_inference_lock(Path(sys.argv[1])); '
        'lock.close()'
    )
    command = [sys.executable, '-c', script, str(lock_path)]
    options = {'cwd': ROOT, 'capture_output': True, 'text': True, 'timeout': 10}
    handle = acquire_inference_lock(lock_path)
    try:
        assert subprocess.run(command, **options).returncode != 0
    finally:
        handle.close()
    assert subprocess.run(command, **options).returncode == 0


def test_missing_lock_directory_is_not_reported_as_success(tmp_path):
    with pytest.raises(OSError):
        acquire_inference_lock(tmp_path/'missing'/'inference.lock')
