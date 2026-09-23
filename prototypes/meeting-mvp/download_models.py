"""Only setup uses the network. No meeting data is read or transmitted here."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parent
DEST = Path(os.environ.get('MEETING_MODEL_DIR', ROOT/'models')).expanduser().resolve()

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def verified(path, item):
    return (path.is_file() and path.stat().st_size == item['bytes']
            and sha256(path) == item['sha256'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=['asr', 'diarization', 'llm'], action='append',
                        help='Download only this original component; may be repeated. Default: all.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--from-local', type=Path, metavar='MODELS_DIR',
                      help='Copy verified weights from an existing models directory; never download.')
    mode.add_argument('--verify-only', action='store_true',
                      help='Verify selected locked files in MEETING_MODEL_DIR without network.')
    args = parser.parse_args(argv)
    source_dir = args.from_local.expanduser().resolve() if args.from_local else None
    manifest = json.loads((ROOT/'models.lock.json').read_text(encoding='utf-8'))
    selected = set(args.component or ['asr', 'diarization', 'llm'])
    verified_files = []
    receipt_path = DEST/'.meeting-models-verified.json'
    # A failed verification must not leave an older receipt claiming readiness.
    receipt_path.unlink(missing_ok=True)
    for item in manifest['files']:
        if item['path'].split('/')[0] not in selected:
            continue
        target = DEST/item['path']
        if verified(target, item):
            verified_files.append(item)
            print('Проверено:',item['path'],flush=True)
            continue
        if args.verify_only:
            raise RuntimeError('Модель отсутствует или повреждена: '+item['path'])
        if source_dir is not None:
            source = source_dir/item['path']
            if not verified(source, item):
                raise RuntimeError('Локальная модель отсутствует или повреждена: '+item['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix+'.download')
            try:
                shutil.copyfile(source, temp)
                if not verified(temp, item):
                    raise RuntimeError('Контрольная сумма копии не совпала: '+item['path'])
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
            print('Скопировано и проверено:', item['path'], flush=True)
            verified_files.append(item)
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        temp = target.with_suffix(target.suffix+'.download')
        print('Загрузка:',item['path'],flush=True)
        import requests
        with requests.get(item['url'],stream=True,timeout=(20,180)) as response:
            if response.status_code in (401, 403):
                raise RuntimeError(
                    'Источник модели недоступен ('+str(response.status_code)+'): '+item['path']+
                    '. Укажите MEETING_MODEL_DIR с готовыми весами или используйте '
                    '--from-local /path/to/models. Подробности в README.md.'
                )
            response.raise_for_status()
            with temp.open('wb') as output:
                for block in response.iter_content(1024*1024):
                    output.write(block)
        if item.get('archive_member'):
            import tarfile
            archive = temp
            extracted = target.with_suffix(target.suffix+'.extracted')
            with tarfile.open(archive,'r:bz2') as tar:
                source = tar.extractfile(item['archive_member'])
                if source is None:
                    raise RuntimeError('Модель отсутствует в архиве')
                with extracted.open('wb') as output:
                    for block in iter(lambda:source.read(1024*1024),b''):
                        output.write(block)
            archive.unlink()
            temp = extracted
        if not verified(temp, item):
            raise RuntimeError('Контрольная сумма не совпала: '+item['path'])
        temp.replace(target)
        verified_files.append(item)
    # Preserve other installed components only after checking their actual files.
    # Never carry entries from an old receipt forward without a fresh hash pass.
    for item in manifest['files']:
        if item['path'].split('/')[0] not in selected and verified(DEST/item['path'], item):
            verified_files.append(item)
    receipt = {'schema_version': 1, 'manifest': sha256(ROOT/'models.lock.json'),
               'files': [{'path': item['path'], 'bytes': item['bytes'], 'sha256': item['sha256']} for item in verified_files]}
    DEST.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
    temporary.replace(receipt_path)
    print('Выбранные модели проверены. Можно работать без сети.')

if __name__=='__main__':
    main()
