"""Replace the entrypoint with the API/worker supervisor, preserving signals."""
import os
from pathlib import Path
import sys


def main():
    profile = os.environ.get('APP_PROFILE', 'brev')
    if profile not in {'brev', 'fixture'}:
        raise SystemExit('APP_PROFILE must be brev (local CPU models) or fixture (synthetic test).')
    root = Path(__file__).resolve().parents[1]
    # An exec, rather than a nested subprocess, lets Docker's SIGTERM reach the
    # supervisor. It stops both process groups before the container exits.
    os.execv(sys.executable, [sys.executable, str(root / 'scripts/manage.py'),
                             'run', '--profile', profile, '--device', 'cpu',
                             '--models', os.environ.get('MEETING_MODEL_DIR', '/models'),
                             '--python', sys.executable])


if __name__ == '__main__':
    main()
