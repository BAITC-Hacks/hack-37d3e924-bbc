"""Download pinned GitHub Release weights. Requires Python 3.10+ and GitHub CLI.

Only this setup command uses the network; it never reads meeting data.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def verified(path, item):
    return (path.is_file() and path.stat().st_size == item['bytes']
            and digest(path) == item['sha256'])


def safe_target(root, name):
    relative = PurePosixPath(name)
    if (relative.is_absolute() or '..' in relative.parts or '\\' in name
            or ':' in name or not relative.parts):
        raise ValueError('Unsafe model path: ' + name)
    result = root.joinpath(*relative.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Model path escapes destination: ' + name)
    return result


def validate_manifest(manifest):
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported release manifest')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', manifest['repository']):
        raise ValueError('Invalid repository')
    if not re.fullmatch(r'[\w.-]+', manifest['tag']) or manifest['tag'].startswith('-'):
        raise ValueError('Invalid release tag')
    assets, paths = set(), set()
    for item in manifest['files']:
        if item['path'] in paths or not item['assets']:
            raise ValueError('Duplicate path or missing assets')
        paths.add(item['path'])
        if sum(asset['bytes'] for asset in item['assets']) != item['bytes']:
            raise ValueError('Asset sizes do not match file')
        for part in [item, *item['assets']]:
            if (not isinstance(part['bytes'], int) or part['bytes'] < 0
                    or not re.fullmatch(r'[0-9a-f]{64}', part['sha256'])):
                raise ValueError('Invalid file size or SHA-256')
        for asset in item['assets']:
            name = asset['name']
            if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name)
                    or name in assets):
                raise ValueError('Invalid or duplicate asset name')
            assets.add(name)


def fetch_asset(manifest, asset, cache):
    target = safe_target(cache, asset['name'])
    if verified(target, asset):
        return target
    if not shutil.which('gh'):
        raise RuntimeError('Install GitHub CLI (gh), then run gh auth login.')
    cache.mkdir(parents=True, exist_ok=True)
    # gh authenticates private release downloads without putting tokens in URLs.
    for attempt in range(3):
        result = subprocess.run([
            'gh', 'release', 'download', manifest['tag'],
            '--repo', manifest['repository'], '--pattern', asset['name'],
            '--dir', str(cache), '--clobber',
        ])
        if result.returncode == 0:
            break
        if attempt < 2:
            print('Повтор загрузки:', asset['name'], flush=True)
            time.sleep(2 ** attempt)
    if result.returncode:
        raise RuntimeError('Download failed. Check gh auth status and repository access; '
                           'rerun the same command to reuse verified files.')
    if not verified(target, asset):
        target.unlink(missing_ok=True)
        raise RuntimeError('SHA-256 mismatch: ' + asset['name'])
    return target


def install(manifest, destination, components=None, verify_only=False):
    validate_manifest(manifest)
    destination = destination.expanduser().resolve()
    # Validate all paths before doing any IO, including existing symlinks.
    targets = {item['path']: safe_target(destination, item['path'])
               for item in manifest['files']}
    cache = safe_target(destination, '.github-model-cache')
    for item in manifest['files']:
        if components and item['path'].split('/')[0] not in {*components, 'licenses'}:
            continue
        target = targets[item['path']]
        if verified(target, item):
            print('Проверено:', item['path'], flush=True)
            continue
        if verify_only:
            raise RuntimeError('Файл отсутствует или повреждён: ' + item['path'])
        print('Загрузка:', item['path'], flush=True)
        parts = [fetch_asset(manifest, asset, cache) for asset in item['assets']]
        target.parent.mkdir(parents=True, exist_ok=True)
        if len(parts) == 1:
            if not verified(parts[0], item):
                raise RuntimeError('File SHA-256 mismatch: ' + item['path'])
            parts[0].replace(target)
        else:
            temporary = safe_target(destination, item['path'] + '.assembling')
            try:
                with temporary.open('wb') as output:
                    for part in parts:
                        with part.open('rb') as source:
                            shutil.copyfileobj(source, output, 1024 * 1024)
                if not verified(temporary, item):
                    raise RuntimeError('File SHA-256 mismatch: ' + item['path'])
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            for part in parts:
                part.unlink()
        print('Установлено и проверено:', item['path'], flush=True)
    print('Модели проверены. Каталог:', destination, flush=True)


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    local_manifest = Path(__file__).resolve().with_name('github-release.lock.json')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('.local/models'))
    parser.add_argument('--manifest', type=Path,
                        default=local_manifest if local_manifest.is_file()
                        else root / 'models/github-release.lock.json')
    parser.add_argument('--component', action='append', choices=['asr', 'diarization', 'llm'])
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    install(manifest, args.directory, args.component, args.verify_only)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
