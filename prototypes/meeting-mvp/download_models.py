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

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--from-local', type=Path, metavar='MODELS_DIR',
                      help='Copy verified weights from an existing models directory; never download.')
    mode.add_argument('--verify-only', action='store_true',
                      help='Verify every locked file in MEETING_MODEL_DIR without network or writes.')
    args = parser.parse_args(argv)
    source_dir = args.from_local.expanduser().resolve() if args.from_local else None
    manifest = json.loads((ROOT/'models.lock.json').read_text())
    for item in manifest['files']:
        target = DEST/item['path']
        if target.is_file() and sha256(target)==item['sha256']:
            print('Проверено:',item['path'],flush=True)
            continue
        if args.verify_only:
            raise RuntimeError('Модель отсутствует или повреждена: '+item['path'])
        if source_dir is not None:
            source = source_dir/item['path']
            if not source.is_file() or sha256(source) != item['sha256']:
                raise RuntimeError('Локальная модель отсутствует или повреждена: '+item['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix+'.download')
            try:
                shutil.copyfile(source, temp)
                if sha256(temp) != item['sha256']:
                    raise RuntimeError('Контрольная сумма копии не совпала: '+item['path'])
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
            print('Скопировано и проверено:', item['path'], flush=True)
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
        if sha256(temp)!=item['sha256']:
            raise RuntimeError('Контрольная сумма не совпала: '+item['path'])
        temp.replace(target)
    print('Все модели проверены. Можно работать без сети.')

if __name__=='__main__':
    main()
