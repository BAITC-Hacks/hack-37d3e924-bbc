"""Synthetic byte fixtures: transport integrity, never model quality."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('release_download', Path(__file__).parents[1] / 'download_models.py')
download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download)


def manifest(parts=(b'first', b'second')):
    whole = b''.join(parts)
    assets = [{'name': f'model.part-{i}', 'bytes': len(data),
               'sha256': hashlib.sha256(data).hexdigest()} for i, data in enumerate(parts)]
    return {'schema_version': 1, 'repository': 'owner/repo', 'tag': 'models-v1',
            'files': [{'path': 'asr/model.pt', 'bytes': len(whole),
                       'sha256': hashlib.sha256(whole).hexdigest(), 'assets': assets}]}


def fake_gh(monkeypatch, payloads):
    calls = []
    monkeypatch.setattr(download.shutil, 'which', lambda _: '/bin/gh')

    def run(args):
        name = args[args.index('--pattern') + 1]
        calls.append(name)
        (Path(args[args.index('--dir') + 1]) / name).write_bytes(payloads[name])
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(download.subprocess, 'run', run)
    return calls


def test_split_download_assembly_and_offline_reuse(tmp_path, monkeypatch):
    calls = fake_gh(monkeypatch, {'model.part-0': b'first', 'model.part-1': b'second'})
    download.install(manifest(), tmp_path)
    assert (tmp_path / 'asr/model.pt').read_bytes() == b'firstsecond'
    assert calls == ['model.part-0', 'model.part-1']
    monkeypatch.setattr(download.subprocess, 'run', lambda _: pytest.fail('Unexpected network'))
    download.install(manifest(), tmp_path, verify_only=True)


def test_bad_chunk_preserves_existing_file_and_reuses_good_part(tmp_path, monkeypatch):
    target = tmp_path / 'asr/model.pt'
    target.parent.mkdir()
    target.write_bytes(b'old-model')
    calls = fake_gh(monkeypatch, {'model.part-0': b'first', 'model.part-1': b'broken'})
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        download.install(manifest(), tmp_path)
    assert target.read_bytes() == b'old-model'
    assert (tmp_path / '.github-model-cache/model.part-0').exists()
    calls = fake_gh(monkeypatch, {'model.part-1': b'second'})
    download.install(manifest(), tmp_path)
    assert calls == ['model.part-1']
    assert target.read_bytes() == b'firstsecond'


def test_correct_parts_cannot_bypass_whole_file_hash(tmp_path, monkeypatch):
    data = manifest()
    data['files'][0]['sha256'] = '0' * 64
    fake_gh(monkeypatch, {'model.part-0': b'first', 'model.part-1': b'second'})
    with pytest.raises(RuntimeError, match='File SHA-256 mismatch'):
        download.install(data, tmp_path)
    assert not (tmp_path / 'asr/model.pt').exists()
    assert not (tmp_path / 'asr/model.pt.assembling').exists()


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'asr/../../escape', 'C:\\escape'])
def test_path_traversal_rejected_before_network(tmp_path, monkeypatch, name):
    data = manifest()
    data['files'][0]['path'] = name
    monkeypatch.setattr(download.subprocess, 'run', lambda _: pytest.fail('Unexpected network'))
    with pytest.raises(ValueError):
        download.install(data, tmp_path)


def test_symlink_escape_rejected(tmp_path):
    (tmp_path / 'asr').symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        download.install(manifest(), tmp_path)


def test_verify_only_does_not_fetch_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(download.subprocess, 'run', lambda _: pytest.fail('Unexpected network'))
    with pytest.raises(RuntimeError, match='отсутствует'):
        download.install(manifest(), tmp_path, verify_only=True)


def test_single_asset_and_component_selection(tmp_path, monkeypatch):
    calls = fake_gh(monkeypatch, {'model.part-0': b'first'})
    download.install(manifest((b'first',)), tmp_path, components=['diarization'])
    assert not calls
    download.install(manifest((b'first',)), tmp_path, components=['asr'])
    assert (tmp_path / 'asr/model.pt').read_bytes() == b'first'


def test_interrupted_download_is_retried(tmp_path, monkeypatch):
    calls = fake_gh(monkeypatch, {'model.part-0': b'first'})
    success = download.subprocess.run
    attempts = []

    def interrupted(args):
        attempts.append(args)
        if len(attempts) == 1:
            (Path(args[args.index('--dir') + 1]) / 'model.part-0').write_bytes(b'fi')
            return type('Result', (), {'returncode': 1})()
        return success(args)

    monkeypatch.setattr(download.subprocess, 'run', interrupted)
    monkeypatch.setattr(download.time, 'sleep', lambda _: None)
    download.install(manifest((b'first',)), tmp_path)
    assert len(attempts) == 2
    assert (tmp_path / 'asr/model.pt').read_bytes() == b'first'


def test_release_preserves_original_model_pins():
    import json
    root = Path(__file__).parents[2]
    release = json.loads((root / 'models/github-release.lock.json').read_text())
    download.validate_manifest(release)
    by_path = {item['path']: item for item in release['files']}
    for source in ['ai/mac-models.lock.json', 'prototypes/meeting-mvp/models.lock.json']:
        upstream = json.loads((root / source).read_text())
        for item in upstream['files']:
            assert all(by_path[item['path']][key] == value for key, value in item.items())
    assert all(asset['bytes'] < 2 * 1024**3 for item in release['files'] for asset in item['assets'])
