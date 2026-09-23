# ИИ-модуль: первая поставка

Контракт без изменений: `from ai.pipeline import run_pipeline`.
Синтетический результат: `ai/fixtures/result.json`, точная копия общей фикстуры.

```python
import json, os
from ai.pipeline import run_pipeline
os.environ['AI_MODE'] = 'fixture'  # только интеграционная разработка
result = run_pipeline(json.load(open('ai/fixtures/input.json')))
```

Нужен `jsonschema`. Без явного `AI_MODE=fixture` заглушка выдаёт MODEL_UNAVAILABLE;
она никогда не выдаёт фикстуру за результат обработки записи.
Модуль не меняет contracts/, backend/, frontend/ или общие зависимости.
