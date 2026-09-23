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


@pytest.fixture
def component_models(local_models):
    source, dest = local_models
    manifest_path = download_models.ROOT / 'models.lock.json'
    manifest = json.loads(manifest_path.read_text())
    for name, content in [('diarization/segmentation.onnx', b'test segmentation'),
                          ('diarization/embedding.onnx', b'test embedding'),
                          ('llm/model.safetensors', b'test language weights')]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest['files'].append({'path': name, 'bytes': len(content),
                                  'sha256': hashlib.sha256(content).hexdigest(),
                                  'url': 'https://invalid.example/model'})
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    return source, dest, manifest


def read_receipt(dest):
    receipt = json.loads((dest / '.meeting-models-verified.json').read_text(encoding='utf-8'))
    assert receipt['schema_version'] == 1
    assert receipt['manifest'] == download_models.sha256(download_models.ROOT / 'models.lock.json')
    return receipt['files']


def test_component_copy_receipt_contains_only_verified_files(component_models):
    source, dest, manifest = component_models
    # Missing unselected weights must neither trigger a download nor enter the receipt.
    (source / 'asr/model.pt').unlink()
    download_models.main(['--from-local', str(source), '--component', 'diarization'])
    assert not (dest / 'asr').exists()
    assert not (dest / 'llm').exists()
    expected = [{key: item[key] for key in ('path', 'bytes', 'sha256')}
                for item in manifest['files'] if item['path'].startswith('diarization/')]
    assert read_receipt(dest) == expected


def test_repeated_components_preserve_previously_verified_group(component_models):
    source, dest, manifest = component_models
    download_models.main(['--from-local', str(source), '--component', 'diarization'])
    for path in (source / 'diarization').iterdir():
        path.unlink()
    download_models.main(['--from-local', str(source), '--component', 'asr', '--component', 'llm'])
    assert {item['path'] for item in read_receipt(dest)} == {
        item['path'] for item in manifest['files']}


def test_verify_only_checks_selected_component_offline(component_models):
    source, dest, _ = component_models
    download_models.main(['--from-local', str(source), '--component', 'diarization'])
    original_receipt = read_receipt(dest)
    download_models.main(['--verify-only', '--component', 'diarization'])
    assert read_receipt(dest) == original_receipt
    assert not (dest / 'asr').exists()


def test_receipt_rechecks_unselected_files_even_when_size_matches(component_models):
    source, dest, manifest = component_models
    download_models.main(['--from-local', str(source)])
    corrupted = dest / 'asr/model.pt'
    corrupted.write_bytes(b'x' * corrupted.stat().st_size)
    download_models.main(['--verify-only', '--component', 'diarization'])
    assert {item['path'] for item in read_receipt(dest)} == {
        item['path'] for item in manifest['files'] if item['path'] != 'asr/model.pt'}


def test_failed_verification_invalidates_old_receipt(local_models):
    source, dest = local_models
    download_models.main(['--from-local', str(source)])
    corrupted = dest / 'asr/model.pt'
    corrupted.write_bytes(b'x' * corrupted.stat().st_size)
    with pytest.raises(RuntimeError, match='Модель отсутствует'):
        download_models.main(['--verify-only'])
    assert not (dest / '.meeting-models-verified.json').exists()
