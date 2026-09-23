# Сценарий демо

Целевая длительность: 270 секунд. Использовать только синтетические или обезличенные записи. Аудио и текст совещаний нельзя отправлять во внешние cloud API.

Финальная фраза "working private meeting protocol pipeline" допустима только если приемка в docs/ACCEPTANCE.md фактически PASS. Если есть только fixture или неполный локальный прогон, говорить "partial demo" или "fixture smoke".

## Подготовить перед показом

- русскую, казахскую и mixed short recording из docs/ACCEPTANCE.md;
- локальный запуск приложения по README;
- три результата real local models, по одному на каждую запись;
- один completed meeting с edited saved version и DOCX export;
- один failed meeting для retry;
- contracts/result.schema.json и contracts/examples/result.json для быстрой демонстрации контракта.

Fixture можно держать как запасной smoke-тест интерфейса, но он не доказывает ИИ, offline/repro или качество.

## Измерения

Заполнять только после реальных прогонов. Не выдумывать.

| Metric | Value |
|---|---|
| Russian recording duration | NOT MEASURED |
| Kazakh recording duration | NOT MEASURED |
| Mixed recording duration | NOT MEASURED |
| End-to-end processing time RU | NOT MEASURED |
| End-to-end processing time KZ | NOT MEASURED |
| End-to-end processing time mixed | NOT MEASURED |
| GPU model and VRAM | NOT MEASURED |
| Peak VRAM/RAM | NOT MEASURED |
| Model versions/revisions | NOT MEASURED |
| Task misses / extra tasks | NOT MEASURED |
| Speaker turn errors | NOT MEASURED |

## 270-second talk track

1. Проблема, 20 секунд.

   "После встреч теряются поручения, сроки и контекст. Мы делаем систему, которая из локальной аудиозаписи собирает транскрипт по говорящим, поручения, summary, ручную проверку и DOCX-протокол."

2. Ограничение приватности, 20 секунд.

   "Главное ограничение: аудио и текст совещаний не уходят во внешние cloud API. Распознавание, диаризация, извлечение поручений и summary рассчитаны на self-hosted модели и закрытый контур."

3. Архитектура, 35 секунд.

   Показать или проговорить:

   ```text
   React UI
     -> FastAPI backend
     -> SQLite storage and processing queue
     -> separate worker process
     -> ai/pipeline.py run_pipeline(input_data, on_progress)
     -> validated result schema
     -> manual review
     -> DOCX export
   ```

   Акценты: статусы queued/processing/done/failed; stage отдельно от result; original machine result отдельно от edited saved version; неизвестные assignee/due_date остаются null и требуют review.

4. Живой сценарий, 120 секунд.

   Показать:

   - список meetings;
   - upload короткой записи с `meeting_datetime=2026-09-23T10:00:00+05:00` и `timezone=Asia/Qyzylorda`;
   - переход статусов через очередь;
   - transcript с speaker labels;
   - извлеченные tasks с source evidence;
   - пример относительной даты: "завтра" или "ертең" -> 2026-09-24;
   - ручную правку participant/task/summary;
   - сохранение и refresh, где edited saved version осталась;
   - original machine result отдельно;
   - DOCX export из edited saved version.

   Если используется fixture, прямо сказать: "Это fixture smoke, он не доказывает работу моделей".

5. Проверки качества, 40 секунд.

   Показать или назвать только проверенное:

   - три real local model runs: RU, KZ, mixed;
   - ручной эталон: пропуски tasks, лишние tasks, верные assignee/date/source, ошибки speaker turns;
   - retry failed job;
   - delete queued и 409 при delete processing;
   - transcript text вроде `<b>task</b>` отображается как текст, не HTML;
   - hostile transcript sentence treated as data;
   - DOCX visual QA: Ә Ғ Қ Ң Ө Ұ Ү Һ І, длинные таблицы, переносы, все поля, сохраненные правки.

6. Ограничения и claim, 35 секунд.

   Если PASS:

   "Проверены локальная обработка трёх смоделированных записей и сквозной офлайн-сценарий: загрузка, обработка, ручная проверка, сохранение, повторное открытие и экспорт DOCX. Покажем результаты и известные ограничения."

   Если не PASS:

   "Сейчас это partial demo. Контракты и fixture flow готовы, но финальный working claim мы не делаем, пока нет трех реальных локальных model runs и полного offline/repro PASS."

   Ограничения говорить честно:

   - speaker identity требует ручной проверки;
   - неоднозначные сроки требуют review;
   - long audio требует проверки chunk timestamps и dedupe;
   - качество и скорость заполняются только после измерений;
   - итоговый выбор моделей зависит от доступной GPU, VRAM, тарифа и бюджета.

## Safety notes

- Не отправлять аудио, транскрипты и результаты совещаний, включая демонстрационные и обезличенные, в OpenAI, hosted ASR, hosted LLM, hosted diarization или онлайн-переводчики.
- Не заявлять accuracy, diarization quality, GPU cost, processing time или VRAM/RAM без измерения.
- Если fixture mode используется в демо, произнести "fixture mode" вслух и показать это в интерфейсе или DOCX.
- Если real local models не готовы, показывать flow честно как incomplete.

## Fast fallback при live failure

Если live processing падает:

"Live worker run упал во время демо, поэтому я переключаюсь на сохраненный синтетический run. Failure path является частью продукта: job остается failed с безопасной ошибкой, может быть retried и не раскрывает traceback или meeting text."

После этого показать:

- saved edited result;
- original machine result;
- DOCX export;
- retry behavior на failed item;
- README startup command;
- что это fallback, а не доказательство полного PASS.
