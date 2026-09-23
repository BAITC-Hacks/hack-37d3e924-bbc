"""Local setup must verify artifacts and never fall back to a download."""
import hashlib
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import download_models


@pytest.fixture
def local_models(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    dest = tmp_path / 'destination'
    source.mkdir()
    files = []
    for name, content in [('asr/model.pt', b'test weights'), ('asr/tokens.lst', b'a\nb\n')]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        files.append({'path': name, 'sha256': hashlib.sha256(content).hexdigest(),
                      'bytes': len(content), 'url': 'https://invalid.example/model'})
    (tmp_path / 'models.lock.json').write_text(json.dumps({'files': files}))
    monkeypatch.setattr(download_models, 'ROOT', tmp_path)
    monkeypatch.setattr(download_models, 'DEST', dest)

    def no_network(*args, **kwargs):
        pytest.fail('Local model setup attempted network access')

    monkeypatch.setattr(socket, 'socket', no_network)
    return source, dest


def test_local_copy_and_repeat_without_source(local_models):
    source, dest = local_models
    download_models.main(['--from-local', str(source)])
    for name in ['asr/model.pt', 'asr/tokens.lst']:
        assert (dest / name).read_bytes() == (source / name).read_bytes()
        (source / name).unlink()
    # Verified destinations are reused even after the original files are removed.
    download_models.main(['--from-local', str(source)])
    download_models.main(['--verify-only'])


def test_bad_source_does_not_replace_existing_file(local_models):
    source, dest = local_models
    (source / 'asr/model.pt').write_bytes(b'broken source')
    (dest / 'asr').mkdir(parents=True)
    target = dest / 'asr/model.pt'
    target.write_bytes(b'previous file')
    with pytest.raises(RuntimeError, match='Локальная модель'):
        download_models.main(['--from-local', str(source)])
    assert target.read_bytes() == b'previous file'
    assert not list(dest.rglob('*.download'))


def test_missing_source_fails_offline(local_models):
    source, dest = local_models
    (source / 'asr/model.pt').unlink()
    with pytest.raises(RuntimeError, match='Локальная модель'):
        download_models.main(['--from-local', str(source)])
    assert not dest.exists()


def test_verify_missing_is_read_only(local_models):
    _, dest = local_models
    with pytest.raises(RuntimeError, match='Модель отсутствует'):
        download_models.main(['--verify-only'])
    assert not dest.exists()


def test_verify_rejects_corruption(local_models):
    source, dest = local_models
    download_models.main(['--from-local', str(source)])
    target = dest / 'asr/model.pt'
    target.write_bytes(b'corrupt')
    with pytest.raises(RuntimeError, match='Модель отсутствует'):
        download_models.main(['--verify-only'])
    assert target.read_bytes() == b'corrupt'


def test_copy_corruption_preserves_destination(local_models, monkeypatch):
    source, dest = local_models
    (dest / 'asr').mkdir(parents=True)
    target = dest / 'asr/model.pt'
    target.write_bytes(b'previous file')
    monkeypatch.setattr(download_models.shutil, 'copyfile',
                        lambda src, dst: dst.write_bytes(b'partial copy'))
    with pytest.raises(RuntimeError, match='Контрольная сумма копии'):
        download_models.main(['--from-local', str(source)])
    assert target.read_bytes() == b'previous file'
    assert not list(dest.rglob('*.download'))
