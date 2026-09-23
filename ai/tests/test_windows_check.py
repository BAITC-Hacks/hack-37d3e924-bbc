"""Synthetic readiness fixtures; these tests are not model inference evidence."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ai import windows_check as check


class WindowsCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.models = self.directory / 'synthetic-models'
        files = {'llm/config.json': b'{"synthetic_fixture":true}',
                 'llm/model.safetensors': b'SYNTHETIC NOT MODEL WEIGHTS',
                 'asr/model.pt': b'SYNTHETIC NOT ASR WEIGHTS'}
        entries = []
        for relative, content in files.items():
            target = self.models / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            entries.append({'path': relative, 'bytes': len(content),
                            'sha256': hashlib.sha256(content).hexdigest()})
        manifest = self.directory / 'synthetic-manifest.json'
        manifest.write_text(json.dumps({'llm_revision': 'synthetic-revision', 'files': entries}), encoding='utf-8')
        self.patch(check, 'MANIFEST', manifest)
        self.validator = self.patch(check, '_validate_model_config', Mock())
        self.cuda = SimpleNamespace(
            is_available=Mock(return_value=True),
            is_bf16_supported=Mock(return_value=True),
            get_device_properties=Mock(return_value=SimpleNamespace(name='Synthetic GPU')),
            mem_get_info=Mock(return_value=(3 * 1024**3, 4 * 1024**3)))
        self.torch = SimpleNamespace(version=SimpleNamespace(cuda='synthetic-cuda'), cuda=self.cuda)
        self.imports = self.patch(check.importlib, 'import_module',
                                 Mock(side_effect=lambda name: self.torch if name == 'torch' else SimpleNamespace()))
        self.patch(check.importlib.metadata, 'version', Mock(return_value='synthetic-version'))

    def patch(self, owner, name, value):
        patcher = patch.object(owner, name, value)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_cpu_success_does_not_hash_or_load_weights(self):
        hasher = self.patch(check, '_sha256', Mock(side_effect=AssertionError('Unexpected weight read')))
        result = check.check_windows_models(self.models, 'cpu')
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['models']['hashes_verified'])
        self.assertEqual(result['models']['revision'], 'synthetic-revision')
        self.assertEqual(result['models']['files_checked'], 3)
        self.validator.assert_called_once_with({'synthetic_fixture': True})
        self.assertEqual(self.imports.call_count, 6)
        hasher.assert_not_called()
        self.cuda.mem_get_info.assert_not_called()
        json.dumps(result)

    def test_hash_verification_streams_synthetic_files(self):
        result = check.check_windows_models(self.models, 'cpu', verify_hashes=True)
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['models']['hashes_verified'])

    def test_missing_file_stops_before_imports(self):
        (self.models / 'asr/model.pt').unlink()
        result = check.check_windows_models(self.models, 'cpu')
        self.assertEqual(result['errors'][0]['code'], 'MODEL_FILE_MISSING')
        self.assertFalse(result['ok'])
        self.imports.assert_not_called()

    def test_size_mismatch_stops_before_hashing(self):
        (self.models / 'llm/model.safetensors').write_bytes(b'short')
        hasher = self.patch(check, '_sha256', Mock(return_value='0' * 64))
        result = check.check_windows_models(self.models, 'cpu')
        self.assertEqual(result['errors'][0]['code'], 'MODEL_SIZE_MISMATCH')
        hasher.assert_not_called()
        self.imports.assert_not_called()

    def test_wrong_hash_rejects_same_size_files(self):
        self.patch(check, '_sha256', Mock(return_value='0' * 64))
        result = check.check_windows_models(self.models, 'cpu', verify_hashes=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['errors'][0]['code'], 'MODEL_HASH_MISMATCH')
        self.imports.assert_not_called()

    def test_missing_dependency_has_safe_actionable_error(self):
        def dependency(name):
            if name == 'transformers':
                raise ImportError('SECRET SHOULD NOT APPEAR')
            return self.torch if name == 'torch' else SimpleNamespace()
        self.imports.side_effect = dependency
        result = check.check_windows_models(self.models, 'cpu')
        self.assertFalse(result['ok'])
        self.assertEqual(result['errors'][0]['package'], 'transformers')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_cuda_missing_never_falls_back(self):
        self.cuda.is_available.return_value = False
        result = check.check_windows_models(self.models, 'cuda')
        self.assertFalse(result['ok'])
        self.assertEqual(result['hardware']['device'], 'cuda')
        self.assertEqual(result['errors'][0]['code'], 'CUDA_UNAVAILABLE')

    def test_cuda_requires_native_bf16(self):
        self.cuda.is_bf16_supported.return_value = False
        result = check.check_windows_models(self.models, 'cuda')
        self.assertFalse(result['ok'])
        self.assertEqual(result['errors'][0]['code'], 'CUDA_BF16_UNSUPPORTED')
        self.cuda.is_bf16_supported.assert_called_once_with(including_emulation=False)

    def test_cuda_success_reports_memory(self):
        result = check.check_windows_models(self.models, 'cuda')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['hardware']['gpu_free_bytes'], 3 * 1024**3)
        self.assertTrue(result['hardware']['bf16_supported'])

    def test_cpu_does_not_require_working_cuda_driver(self):
        self.cuda.is_available.side_effect = RuntimeError('No working CUDA driver')
        result = check.check_windows_models(self.models, 'cpu')
        self.assertTrue(result['ok'], result)
        self.assertIsNone(result['hardware']['cuda_available'])

    def test_invalid_config_and_cuda_driver_errors_are_sanitized(self):
        self.validator.side_effect = ValueError('SECRET CONFIG')
        self.cuda.is_available.side_effect = RuntimeError('SECRET DRIVER')
        result = check.check_windows_models(self.models, 'cuda')
        self.assertFalse(result['ok'])
        self.assertEqual([e['code'] for e in result['errors']], ['MODEL_FORMAT_INVALID', 'CUDA_CHECK_FAILED'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_cli_reports_json_and_failure_exit(self):
        (self.models / 'asr/model.pt').unlink()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = check.main(['--models', str(self.models), '--device', 'cpu'])
        self.assertEqual(status, 1)
        self.assertFalse(json.loads(output.getvalue())['ok'])

    def test_cli_keeps_import_noise_out_of_json(self):
        def noisy_import(name):
            print('Third-party import diagnostic')
            return self.torch if name == 'torch' else SimpleNamespace()
        self.imports.side_effect = noisy_import
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = check.main(['--models', str(self.models), '--device', 'cpu'])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(output.getvalue())['ok'])


if __name__ == '__main__':
    unittest.main()
