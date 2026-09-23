"""Fail before setup writes anything on an unsupported demo machine."""
import json, os, platform, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    errors = []
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        errors.append('Нужен macOS на Apple Silicon (arm64).')
    if sys.version_info[:2] != (3, 12):
        errors.append(f'Нужен Python 3.12, найден {sys.version.split()[0]}.')
    manifest = json.loads((ROOT / 'models.lock.json').read_text())
    required = sum(int(item['bytes']) for item in manifest['files']) + 2 * 1024**3
    destination = Path(os.environ.get('MEETING_MODEL_DIR', ROOT / 'models')).resolve()
    free = shutil.disk_usage(destination if destination.exists() else destination.parent).free
    if free < required:
        errors.append(f'Недостаточно места для моделей: нужно не менее {required // 1024**3} ГиБ, доступно {free // 1024**3} ГиБ.')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print('Проверка окружения пройдена.')

if __name__ == '__main__':
    main()
