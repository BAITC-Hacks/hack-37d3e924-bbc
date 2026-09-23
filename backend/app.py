"""HTTP application. Model inference runs only in backend.worker."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai.audio import prepare_audio
from ai.validation import validate_input
from .export import export_docx
from .settings import Settings
from .store import APIError, Store


class UploadLimit:
    """Limit bytes while Starlette consumes the multipart stream, including chunked bodies."""
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        maximum = self.limit + 1024 * 1024 if scope['path'] == '/api/v1/meetings' else 4 * 1024 * 1024
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = 0
        if length > maximum:
            return await JSONResponse({'error': {'code': 'FILE_TOO_LARGE', 'message': 'Файл слишком большой', 'details': {}}},
                                      status_code=413)(scope, receive, send)
        count = 0
        async def bounded_receive():
            nonlocal count
            message = await receive()
            count += len(message.get('body', b''))
            if count > maximum:
                raise HTTPException(status_code=413)
            return message
        await self.app(scope, bounded_receive, send)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    store = Store(settings)
    app = FastAPI(title='Локальный протокол совещаний', docs_url=None, redoc_url=None)
    app.state.store = store
    app.add_middleware(UploadLimit, limit=settings.max_upload)

    @app.exception_handler(APIError)
    async def api_error(request, error):
        return JSONResponse({'error': {'code': error.code, 'message': error.message, 'details': error.details}},
                            status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return await api_error(request, APIError(422, 'VALIDATION_ERROR', 'Проверьте данные'))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        codes = {404: 'NOT_FOUND', 413: 'FILE_TOO_LARGE', 415: 'UNSUPPORTED_AUDIO'}
        status = error.status_code if error.status_code in {404, 413, 415, 405} else 422
        return await api_error(request, APIError(status, codes.get(status, 'VALIDATION_ERROR'), 'Проверьте запрос'))

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        return await api_error(request, APIError(500, 'INTERNAL_ERROR', 'Не удалось выполнить операцию'))

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/api/v1/meetings', status_code=202)
    async def create_meeting(audio: UploadFile = File(...), metadata: str = Form(...)):
        meeting_id = uuid4().hex
        suffix = Path(audio.filename or '').suffix.lower()
        if suffix not in {'.wav', '.mp3', '.m4a', '.flac'}:
            raise APIError(415, 'UNSUPPORTED_AUDIO', 'Используйте WAV, MP3, M4A или FLAC')
        path = settings.audio_dir / (meeting_id + suffix)
        try:
            if len(metadata.encode('utf-8')) > 65536:
                raise ValueError('Metadata too large')
            meta = json.loads(metadata)
            if not isinstance(meta, dict) or set(meta) != {'title', 'meeting_datetime', 'timezone', 'participants'}:
                raise ValueError('Metadata fields')
            title = meta['title'].strip()
            if not 1 <= len(title) <= 200:
                raise ValueError('Title')
            data = {'meeting_id': meeting_id, 'audio_path': str(path),
                    **{key: meta[key] for key in ('meeting_datetime', 'timezone', 'participants')}}
            validate_input(data)
        except Exception:
            raise APIError(422, 'VALIDATION_ERROR', 'Проверьте название, дату, часовой пояс и участников') from None
        created = False
        try:
            count = 0
            with path.open('xb') as output:
                path.chmod(0o600)
                while chunk := await audio.read(1024 * 1024):
                    count += len(chunk)
                    if count > settings.max_upload:
                        raise APIError(413, 'FILE_TOO_LARGE', 'Файл превышает допустимый размер')
                    output.write(chunk)
            # Full local decode before enqueue: extensions and MIME are not trusted.
            def check_audio():
                with tempfile.TemporaryDirectory(dir=settings.data_dir) as temporary:
                    prepare_audio(path, Path(temporary) / 'verified.wav', allowed_formats=('wav', 'mp3', 'mov', 'flac'))
            try:
                await run_in_threadpool(check_audio)
            except Exception:
                raise APIError(415, 'UNSUPPORTED_AUDIO', 'Аудио не декодируется или имеет недопустимую длительность') from None
            meeting = await run_in_threadpool(store.create, title, data)
            created = True
            return meeting
        finally:
            await audio.close()
            if not created:
                path.unlink(missing_ok=True)

    @app.get('/api/v1/meetings')
    def list_meetings():
        return store.list()

    @app.get('/api/v1/meetings/{meeting_id}')
    def get_meeting(meeting_id: str):
        return store.get(meeting_id)

    @app.get('/api/v1/meetings/{meeting_id}/original')
    def original(meeting_id: str):
        return store.original(meeting_id)

    @app.put('/api/v1/meetings/{meeting_id}/review')
    async def review(meeting_id: str, request: Request):
        try:
            data = await request.json()
        except Exception:
            raise APIError(422, 'VALIDATION_ERROR', 'Некорректный JSON') from None
        return await run_in_threadpool(store.review, meeting_id, data)

    @app.post('/api/v1/meetings/{meeting_id}/retry', status_code=202)
    def retry(meeting_id: str):
        return store.retry(meeting_id)

    @app.delete('/api/v1/meetings/{meeting_id}', status_code=204)
    def delete(meeting_id: str):
        store.delete(meeting_id)
        return Response(status_code=204)

    @app.get('/api/v1/meetings/{meeting_id}/export.docx')
    def export(meeting_id: str):
        meeting = store.get(meeting_id)
        store.done(meeting)
        return Response(export_docx(meeting),
                        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        headers={'Content-Disposition': f'attachment; filename="meeting-{meeting_id}.docx"'})

    frontend = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
    if frontend.is_dir():
        app.mount('/assets', StaticFiles(directory=frontend / 'assets', check_dir=False), name='assets')
        @app.get('/')
        def index():
            return FileResponse(frontend / 'index.html')
    return app


app = create_app()
