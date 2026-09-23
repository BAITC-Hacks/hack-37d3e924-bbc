"""Install, verify and supervise the local application from one entry point."""
import argparse
import os
import platform
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IS_WINDOWS = os.name == 'nt'


def load_env():
    # Simple KEY=value config; never execute a shell file.
    path = ROOT / '.env'
    if not path.exists():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key.replace('_', '').isalnum():
            raise SystemExit('Некорректная строка в .env')
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def default_python():
    if IS_WINDOWS:
        candidates = [ROOT / '.venv/Scripts/python.exe']
    else:
        candidates = [ROOT / '.venv/bin/python']
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def executable(name):
    if IS_WINDOWS and name == 'npm':
        resolved = shutil.which('npm.cmd') or shutil.which('npm')
        return resolved or 'npm.cmd'
    return name


def worker_popen_kwargs():
    if IS_WINDOWS:
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {'start_new_session': True}


def stop_process_tree(child, timeout=10):
    if child.poll() is not None:
        return
    if IS_WINDOWS:
        subprocess.run(['taskkill', '/PID', str(child.pid), '/T'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    else:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if IS_WINDOWS:
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        else:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait()


def call(args, env=None):
    subprocess.run([str(a) for a in args], cwd=ROOT, env=env, check=True)


def environment(args):
    env = dict(os.environ)
    env.update(PIPELINE_MODE='fixture' if args.profile == 'fixture' else 'real',
               AI_MODE='fixture' if args.profile == 'fixture' else 'real',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    env.setdefault('DATA_DIR', str(ROOT / '.local/app'))
    env.setdefault('AI_STATE_DIR', str(Path(env['DATA_DIR']).resolve() / 'ai-private'))
    if args.profile == 'mac':
        if platform.system() != 'Darwin' or platform.machine() != 'arm64':
            raise SystemExit('Профиль mac требует macOS Apple Silicon. Для Linux используйте --profile cuda.')
        models = args.models or env.get('MEETING_MODEL_DIR')
        if not models:
            raise SystemExit('Укажите --models /path/to/models или MEETING_MODEL_DIR в .env.')
        folder = Path(models).expanduser().resolve()
        env.update(AI_ASR='mixed_ctc', AI_ASR_PATH=str(folder / 'asr'),
                   AI_DIARIZER='sherpa', AI_DIARIZATION_PATH=str(folder / 'diarization'),
                   AI_LLM='mlx', AI_LLM_PATH=str(folder / 'llm'), AI_DEVICE='cpu')
    elif args.profile in ('windows', 'brev'):
        folder = Path(args.models or env.get('MEETING_MODEL_DIR') or ROOT / 'models').expanduser().resolve()
        env.update(MEETING_MODEL_DIR=str(folder), AI_ASR='mixed_ctc',
                   AI_ASR_PATH=str(folder / 'asr'), AI_DIARIZER='sherpa',
                   AI_DIARIZATION_PATH=str(folder / 'diarization'),
                   AI_LLM='mlx_torch', AI_LLM_PATH=str(folder / 'llm'),
                   AI_DEVICE=args.device, AI_QUANTIZATION='none')
        env.setdefault('AI_CONTEXT_TOKENS', '2048')
        env.setdefault('AI_MAX_NEW_TOKENS', '512')
        env.setdefault('AI_THREADS', '4')
    return env


def check_models(args, env, verify_hashes=False):
    command = [args.worker_python or args.python, '-m', 'ai.model_check',
               '--models', env['MEETING_MODEL_DIR'], '--device', env['AI_DEVICE']]
    if verify_hashes:
        command.append('--verify-hashes')
    call(command, env)


def run(args):
    env = environment(args)
    host, port = listen_address(env)
    if not (ROOT / 'frontend/dist/index.html').exists():
        raise SystemExit('Интерфейс не собран. Выполните make setup или npm ci --prefix frontend && npm run build --prefix frontend.')
    if args.profile != 'fixture':
        if args.profile in ('windows', 'brev'):
            check_models(args, env)
        call([args.worker_python or args.python, '-c', 'from ai.settings import Settings; Settings.from_env()'], env)
    children = []
    def stop(signum=None, frame=None):
        for child in children:
            stop_process_tree(child)
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for cmd in ([args.worker_python or args.python, '-m', 'backend.worker'],
                    [args.python, '-m', 'uvicorn', 'backend.app:app', '--host', host, '--port', str(port)]):
            children.append(subprocess.Popen(cmd, cwd=ROOT, env=env, **worker_popen_kwargs()))
        print(f'HTTP API и интерфейс: {host}:{port}', flush=True)
        print('Режим: '+('ТЕСТОВАЯ ФИКСТУРА — модели не запускаются' if args.profile=='fixture' else 'локальные модели'), flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.3)
        raise SystemExit('Один из процессов завершился. Остановлены и API, и worker; проверьте сообщение выше.')
    except KeyboardInterrupt:
        pass
    finally:
        stop()


def listen_address(env):
    """A server may bind all interfaces; developer runs remain loopback by default."""
    import ipaddress
    try:
        host = str(ipaddress.ip_address(env.get('BACKEND_HOST', '127.0.0.1')))
        port = int(env.get('BACKEND_PORT', '8000'))
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise SystemExit('BACKEND_HOST должен быть IP-адресом, BACKEND_PORT — числом от 1 до 65535.') from None
    return host, port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'run', 'verify', 'doctor'])
    parser.add_argument('--profile', choices=['brev', 'mac', 'cuda', 'windows', 'fixture'],
                        default='windows' if IS_WINDOWS else 'mac' if sys.platform=='darwin' else 'brev')
    parser.add_argument('--models')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu',
                        help='Device for the Brev/Windows original-weight runtime; no automatic fallback')
    parser.add_argument('--worker-python', help='Optional separate preinstalled AI environment')
    parser.add_argument('--python', default=default_python())
    args = parser.parse_args()
    load_env()
    if args.action == 'setup':
        if sys.version_info < (3, 12):
            raise SystemExit('Для установки используйте Python 3.12 или новее.')
        if args.profile=='mac' and (platform.system()!='Darwin' or platform.machine()!='arm64'):
            raise SystemExit('Профиль mac требует Apple Silicon.')
        if args.profile=='brev' and (platform.system()!='Linux' or platform.machine() not in ('x86_64', 'AMD64')):
            raise SystemExit('Устанавливайте профиль brev на Linux x86_64 (машина Brev); для Mac используйте mac.')
        if args.profile=='brev' and sys.version_info[:2] != (3, 12):
            raise SystemExit('Зафиксированное окружение Brev требует Python 3.12.')
        if args.profile=='brev' and args.device!='cpu':
            raise SystemExit('Профиль brev устанавливает CPU PyTorch. GPU-окружение задайте отдельно через --worker-python.')
        if not Path(args.python).exists():
            call([sys.executable, '-m', 'venv', str(Path(args.python).parent.parent)])
        pip_command = [args.python, '-m', 'pip', 'install', '-r', 'requirements-test.txt']
        if args.profile != 'fixture':
            pip_command += ['-r', 'ai/requirements-'+args.profile+'.lock.txt']
        call(pip_command)
        call([args.python, '-m', 'pip', 'check'])
        call([executable('npm'), 'ci', '--prefix', 'frontend'])
        call([executable('npm'), 'run', 'build', '--prefix', 'frontend'])
    elif args.action == 'verify':
        for tests in ('backend/tests', 'ai/tests', 'scripts/tests'):
            call([args.python, '-m', 'pytest', tests, '-q'])
        call([executable('npm'), 'test', '--prefix', 'frontend'])
        call([executable('npm'), 'run', 'build', '--prefix', 'frontend'])
        call([args.python, '-m', 'compileall', '-q', 'backend', 'ai', 'scripts'])
    elif args.action == 'doctor':
        if args.profile not in ('windows', 'brev'):
            parser.error('doctor проверяет исходные веса в профилях brev и windows')
        check_models(args, environment(args), verify_hashes=True)
    else:
        run(args)


if __name__ == '__main__':
    main()
