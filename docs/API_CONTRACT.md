# Frontend ↔ Backend: HTTP baseline

Действующая HTTP-оболочка приложения. Результат строго из contracts/result.schema.json. HTTP-поля находятся в оболочке, а не в результате ИИ.

База /api/v1. GET /health → 200 {"status":"ok"} (не доказывает готовность моделей).

Ошибка всех маршрутов, включая валидацию:
{"error":{"code":"VALIDATION_ERROR","message":"Проверьте данные","details":{}}}

422 VALIDATION_ERROR, 413 FILE_TOO_LARGE, 415 UNSUPPORTED_AUDIO, 404 NOT_FOUND, 409 INVALID_STATE или REVISION_CONFLICT, 500 INTERNAL_ERROR. details — безопасные описания полей; не включать исключения или содержимое записи.

## Создание и очередь

POST /api/v1/meetings, multipart/form-data:
- audio — файл;
- metadata — JSON-строка:
{"title":"Демо","meeting_datetime":"2026-09-23T10:00:00+05:00","timezone":"Asia/Qyzylorda","participants":[{"id":"p1","name":"Марсель","speaker_ids":[]}]}

title: 1–200 символов после trim; остальные поля по входной схеме. Сервер генерирует meeting_id и безопасный audio_path. Ограничения: 100 MiB, WAV/MP3/M4A/FLAC; проверять размер потока и фактическое декодирование. Успех только после сохранения файла и задания. Ответ 202 Meeting.

## Список и статус

GET /api/v1/meetings → 200 {"items":[Meeting]}, новые первыми. В списке result всегда null; содержимое получают отдельным GET.

GET /api/v1/meetings/{id} → 200 Meeting:
{"id":"demo-mixed-001","title":"Демо","meeting_datetime":"2026-09-23T10:00:00+05:00","timezone":"Asia/Qyzylorda","status":"queued","stage":null,"mode":"real","error":null,"revision":0,"result":null}

Meeting имеет ровно эти поля:
- status: queued | processing | done | failed.
- stage: null либо стадия из ML_CONTRACT; при done/failed null.
- mode: real | fixture, задаётся конфигурацией backend, не клиентом.
- error: null или {"code":"PROCESSING_FAILED","message":"Обработка не завершена","details":{}}; при failed обязателен.
- result: null до done, затем исправленный результат или original.
- revision: целое >=0; первая сохранённая машинная версия 1, каждая правка +1.

UI опрашивает статус; искусственного процента нет.
GET /api/v1/meetings/{id}/original → 200 исходный неизменяемый Result; до done 409.

## Исправления

PUT /api/v1/meetings/{id}/review:
{"expected_revision":1,"participants":[{"id":"p1","name":"Марсель","speaker_ids":["SPEAKER_00"]}],"tasks":[],"summary":"Исправленное саммари"}

Только done. Полная замена трёх редактируемых полей, типы по Result. Сервер собирает и валидирует весь результат, ссылки и уникальность меток. Метки speaker_ids берутся из segments; segments и метаданные неизменяемы. Нельзя удалить участника и сохранить ссылку на него. При null исполнителе/сроке needs_review=true. Новая задача требует источника. expected_revision проверять транзакционно; конфликт → 409 REVISION_CONFLICT. Успех → 200 Meeting с новой revision. Original не перезаписывать.

## Retry, удаление, DOCX

- POST /api/v1/meetings/{id}/retry: без тела, только failed → queued; ответ 202 Meeting, error/stage очищены. Для queued/processing/done → 409. Это не переработка успешного результата с потерей правок.
- DELETE /api/v1/meetings/{id}: 204 после удаления файла, результатов и очереди. processing → 409. Для queued удаление атомарно согласуется с захватом worker: либо удалено до захвата, либо 409. Ошибку удаления файла не скрывать успешным ответом.
- GET /api/v1/meetings/{id}/export.docx: только done, иначе 409. 200 с application/vnd.openxmlformats-officedocument.wordprocessingml.document и Content-Disposition attachment с безопасным именем. Одна согласованная последняя сохранённая версия. title, дата/зона, участники, саммари, поручения и транскрипт; null — «требует уточнения», fixture — «ТЕСТОВЫЙ РЕЗУЛЬТАТ».

## Интеграционная проверка

Общий fixture → UI → правка → PUT → повторный GET → DOCX с этой правкой. Затем тот же сценарий mode=real с worker и моделями на сервере. Битый JSON/сбой → failed. После рестарта правки сохраняются. Проверки сценария: `backend/tests/test_api.py`; запуск и ограничения — в корневом README.
