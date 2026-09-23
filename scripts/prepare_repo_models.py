"""Assemble and verify model files bundled in Git. No network or extra packages."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

if __package__:
    from .download_models import safe_target, verified
else:
    from download_models import safe_target, verified

ROOT = Path(__file__).resolve().parents[1]


def validate(manifest, directory):
    if manifest.get('schema_version') != 1:
        raise ValueError('Неизвестный формат списка моделей')
    seen = set()
    for item in manifest['files']:
        for record in [item, *item.get('parts', [])]:
            safe_target(directory, record['path'])
            if record['path'] in seen:
                raise ValueError('Повторяющийся путь модели')
            seen.add(record['path'])
            if (not isinstance(record['bytes'], int) or record['bytes'] <= 0
                    or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'])):
                raise ValueError('Неверный размер или SHA-256')
        if 'parts' in item and (not item['parts'] or
                sum(part['bytes'] for part in item['parts']) != item['bytes']):
            raise ValueError('Размеры частей не совпадают с размером модели')


def prepare(manifest, directory, components=None, verify_only=False):
    directory = directory.expanduser().resolve()
    validate(manifest, directory)
    selected = set(components or ['asr', 'diarization', 'llm'])
    for item in manifest['files']:
        if item['path'].split('/')[0] not in selected:
            continue
        target = safe_target(directory, item['path'])
        if verified(target, item):
            print('Проверено:', item['path'], flush=True)
            continue
        if verify_only or not item.get('parts'):
            raise RuntimeError('Файл отсутствует или повреждён: ' + item['path'] +
                               '. Получите полный репозиторий через git pull.')
        for part in item['parts']:
            if not verified(safe_target(directory, part['path']), part):
                raise RuntimeError('Часть модели отсутствует или повреждена: ' + part['path'] +
                                   '. Получите полный репозиторий через git pull.')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = safe_target(directory, item['path'] + '.assembling')
        print('Сборка:', item['path'], flush=True)
        try:
            with temporary.open('wb') as output:
                for part in item['parts']:
                    with safe_target(directory, part['path']).open('rb') as source:
                        shutil.copyfileobj(source, output, 1024 * 1024)
            if not verified(temporary, item):
                raise RuntimeError('SHA-256 собранной модели не совпал: ' + item['path'])
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print('Собрано и проверено:', item['path'], flush=True)
    print('Модели готовы:', directory, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'models')
    parser.add_argument('--component', action='append', choices=['asr', 'diarization', 'llm'])
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(argv)
    manifest = json.loads((ROOT / 'models/repository-models.lock.json').read_text(encoding='utf-8'))
    prepare(manifest, args.directory, args.component, args.verify_only)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
