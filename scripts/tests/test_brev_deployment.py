"""Container startup and health failures without requiring a Docker daemon."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('profile', ['brev', 'fixture'])
def test_entrypoint_replaces_itself_with_supervisor(monkeypatch, profile):
    container = load_module('container')
    monkeypatch.setenv('APP_PROFILE', profile)
    monkeypatch.setenv('MEETING_MODEL_DIR', '/models with spaces')
    calls = []
    monkeypatch.setattr(container.os, 'execv', lambda executable, args: calls.append((executable, args)))
    container.main()
    executable, args = calls[0]
    assert executable == sys.executable
    assert args == [sys.executable, str(ROOT / 'scripts/manage.py'), 'run',
                    '--profile', profile, '--device', 'cpu', '--models', '/models with spaces',
                    '--python', sys.executable]


def test_entrypoint_rejects_unknown_profile_before_starting(monkeypatch):
    container = load_module('container')
    monkeypatch.setenv('APP_PROFILE', 'cuda')
    monkeypatch.setattr(container.os, 'execv', lambda *_: pytest.fail('invalid profile was launched'))
    with pytest.raises(SystemExit, match='APP_PROFILE'):
        container.main()


@pytest.mark.parametrize(('status', 'body', 'expected'), [
    (200, b'{"status":"ok"}', 0),
    (200, b'{"status":"loading"}', 1),
    (200, b'not json', 1),
    (503, b'{"status":"ok"}', 1),
])
def test_healthcheck_requires_successful_api_response(monkeypatch, status, body, expected):
    healthcheck = load_module('healthcheck')

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == '/health'
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv('BACKEND_PORT', str(server.server_port))
        monkeypatch.setenv('http_proxy', 'http://127.0.0.1:1')
        monkeypatch.setenv('no_proxy', '')
        assert healthcheck.main() == expected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('port', ['not-a-number', '0', '65536'])
def test_healthcheck_rejects_invalid_port(monkeypatch, port):
    healthcheck = load_module('healthcheck')
    monkeypatch.setenv('BACKEND_PORT', port)
    assert healthcheck.main() == 1
