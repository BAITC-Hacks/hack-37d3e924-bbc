"""API liveness only; model readiness requires an explicit real inference run."""
import json
import os
import sys
from urllib.request import ProxyHandler, build_opener


def main():
    try:
        port = int(os.environ.get('BACKEND_PORT', '8000'))
        if not 1 <= port <= 65535:
            return 1
        # A local health check must never be sent through an HTTP proxy.
        with build_opener(ProxyHandler({})).open(f'http://127.0.0.1:{port}/health', timeout=3) as response:
            return 0 if response.status == 200 and json.load(response) == {'status': 'ok'} else 1
    except (OSError, ValueError):
        return 1


if __name__ == '__main__':
    sys.exit(main())
