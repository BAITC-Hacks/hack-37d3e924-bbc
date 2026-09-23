import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inference_lock import acquire_inference_lock


def test_lock_excludes_another_process_and_releases(tmp_path):
    lock_path = tmp_path / 'inference.lock'
    script = (
        'from pathlib import Path; from inference_lock import acquire_inference_lock; '
        'import sys; lock = acquire_inference_lock(Path(sys.argv[1])); lock.close()'
    )
    command = [sys.executable, '-c', script, str(lock_path)]
    options = {'cwd': Path(__file__).resolve().parents[1], 'capture_output': True, 'timeout': 10}
    handle = acquire_inference_lock(lock_path)
    try:
        assert subprocess.run(command, **options).returncode != 0
    finally:
        handle.close()
    assert subprocess.run(command, **options).returncode == 0


def test_missing_lock_directory_is_not_reported_as_success(tmp_path):
    with pytest.raises(OSError):
        acquire_inference_lock(tmp_path / 'missing' / 'inference.lock')
