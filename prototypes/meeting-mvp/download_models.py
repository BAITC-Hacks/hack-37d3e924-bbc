"""Only setup uses the network. No meeting data is read or transmitted here."""
import hashlib
import json
from pathlib import Path
import os
import requests

ROOT = Path(__file__).resolve().parent
DEST = Path(os.environ.get('MEETING_MODEL_DIR', ROOT/'models')).resolve()

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    manifest = json.loads((ROOT/'models.lock.json').read_text())
    for item in manifest['files']:
        target = DEST/item['path']
        if target.is_file() and sha256(target)==item['sha256']:
            print('Проверено:',item['path'],flush=True)
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        temp = target.with_suffix(target.suffix+'.download')
        print('Загрузка:',item['path'],flush=True)
        with requests.get(item['url'],stream=True,timeout=(20,180)) as response:
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
    print('Все модели загружены и проверены. Можно отключить сеть.')

if __name__=='__main__':
    main()
