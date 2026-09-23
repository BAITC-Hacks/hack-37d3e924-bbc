"""Install, verify and supervise the local application from one entry point."""
import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    # Simple KEY=value config; never execute a shell file.
    path = ROOT / '.env'
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key.replace('_', '').isalnum():
            raise SystemExit('Некорректная строка в .env')
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def call(args, env=None):
    subprocess.run([str(a) for a in args], cwd=ROOT, env=env, check=True)


def environment(args):
    env = dict(os.environ)
    env.update(PIPELINE_MODE='fixture' if args.profile == 'fixture' else 'real',
               AI_MODE='fixture' if args.profile == 'fixture' else 'real',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
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
    return env


def run(args):
    env = environment(args)
    if not (ROOT / 'frontend/dist/index.html').exists():
        raise SystemExit('Интерфейс не собран. Выполните make setup или npm ci --prefix frontend && npm run build --prefix frontend.')
    if args.profile != 'fixture':
        call([args.worker_python or args.python, '-c', 'from ai.settings import Settings; Settings.from_env()'], env)
    children = []
    def stop(signum=None, frame=None):
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for cmd in ([args.worker_python or args.python, '-m', 'backend.worker'],
                    [args.python, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', env.get('BACKEND_PORT', '8000')]):
            children.append(subprocess.Popen(cmd, cwd=ROOT, env=env, start_new_session=True))
        print('Приложение: http://127.0.0.1:'+env.get('BACKEND_PORT','8000'), flush=True)
        print('Режим: '+('ТЕСТОВАЯ ФИКСТУРА — модели не запускаются' if args.profile=='fixture' else 'локальные модели'), flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.3)
        raise SystemExit('Один из процессов завершился. Остановлены и API, и worker; проверьте сообщение выше.')
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        deadline = time.monotonic() + 10
        for child in children:
            try:
                child.wait(timeout=max(.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'run', 'verify'])
    parser.add_argument('--profile', choices=['mac', 'cuda', 'fixture'], default='mac' if sys.platform=='darwin' else 'cuda')
    parser.add_argument('--models')
    parser.add_argument('--worker-python', help='Optional separate preinstalled AI environment')
    parser.add_argument('--python', default=str(ROOT / '.venv/bin/python'))
    args = parser.parse_args()
    load_env()
    if args.action == 'setup':
        if sys.version_info[:2] != (3, 12):
            raise SystemExit('Для установки используйте Python 3.12.')
        if args.profile=='mac' and (platform.system()!='Darwin' or platform.machine()!='arm64'):
            raise SystemExit('Профиль mac требует Apple Silicon.')
        if not Path(args.python).exists():
            call([sys.executable, '-m', 'venv', str(Path(args.python).parent.parent)])
        command = [args.python, '-m', 'pip', 'install', '-r', 'backend/requirements.txt', '-r', 'requirements-test.txt']
        if args.profile != 'fixture':
            command += ['-r', 'ai/requirements-'+args.profile+'.lock.txt']
        call(command)
        call([args.python, '-m', 'pip', 'check'])
        call(['npm', 'ci', '--prefix', 'frontend'])
        call(['npm', 'run', 'build', '--prefix', 'frontend'])
    elif args.action == 'verify':
        for tests in ('backend/tests', 'ai/tests', 'prototypes/meeting-mvp/tests'):
            call([args.python, '-m', 'pytest', tests, '-q'])
        call(['npm', 'test', '--prefix', 'frontend'])
        call(['npm', 'run', 'build', '--prefix', 'frontend'])
        call([args.python, '-m', 'compileall', '-q', 'backend', 'ai', 'scripts'])
    else:
        run(args)


if __name__ == '__main__':
    main()
