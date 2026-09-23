# Hackathon Team Kit — команда из 3 человек

Этот набор копируется в корень нового репозитория до начала разработки.

## Роли

| Человек | Ветка | Рабочая папка | Главный skill | Дополнительная ответственность |
|---|---|---|---|---|
| Frontend | `feat/frontend` | `frontend/` | `$frontend-ship` | frontend Dockerfile, Nginx/UI build |
| Backend | `feat/backend` | `backend/` | `$backend-ship` | DB, Compose, `.env.example`, финальные merge |
| ML | `feat/ml` | `ml/` | `$ml-ship` | README, метрики, финальный rubric audit |

## 0. Установка на каждом ноутбуке

Нужны Node.js 20+, Git и авторизованный Codex CLI.

```bash
codex --version
npm install -g oh-my-codex
omx doctor
codex login status
```

Если Codex CLI ещё не установлен:

```bash
npm install -g @openai/codex
npm install -g oh-my-codex
omx doctor
codex login status
```

## 1. Первые 15–20 минут — все вместе

1. Backend создаёт GitHub-репозиторий и кладёт туда этот набор.
2. Все читают условие и вместе запускают `$hackathon-intake`.
3. Заполняют `ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/ML_CONTRACT.md`.
4. Раскладывают P0/P1 задачи по трём backlog-файлам.
5. Backend фиксирует базовый commit в `main`.
6. Только после этого создаются рабочие ветки.

Главная цель intake: определить один настоящий вертикальный сценарий:

```text
User -> Frontend -> Backend API -> DB/ML -> Backend response -> Frontend result
```

## 2. Ветки

Каждый клонирует один и тот же репозиторий и создаёт только свою ветку.

Frontend:

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY>
git switch -c feat/frontend
omx setup --scope project --merge-agents
omx doctor
cd frontend
omx --madmax --xhigh
```

Backend:

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY>
git switch -c feat/backend
omx setup --scope project --merge-agents
omx doctor
cd backend
omx --madmax --xhigh
```

ML:

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY>
git switch -c feat/ml
omx setup --scope project --merge-agents
omx doctor
cd ml
omx --madmax --xhigh
```

`--madmax` даёт широкие права. Используйте его только в доверенном хакатон-репозитории без секретов. Если сомневаетесь, запускайте обычный `omx --xhigh`.

## 3. Первое сообщение каждому Codex

Скопируйте соответствующий файл из `prompts/`:

- Frontend: `prompts/FRONTEND_START.md`
- Backend: `prompts/BACKEND_START.md`
- ML: `prompts/ML_START.md`

Запускайте только один основной role-skill. Не загружайте все skills одновременно.

## 4. Контракты нельзя угадывать

- Frontend читает `docs/API_CONTRACT.md` и не придумывает поля.
- Backend реализует `API_CONTRACT.md` и адаптер к `ML_CONTRACT.md`.
- ML выдаёт ровно интерфейс из `ML_CONTRACT.md`.
- После freeze контракт меняет только Backend после согласования всех троих.

## 5. Синхронизации

- `~1:30`: первый merge и обязательный end-to-end smoke test.
- `~3:30`: второй merge, затем приоритет у Docker, тестов и стабильности.
- За 40 минут до конца: feature freeze и `$judge-readiness`.

Перед PR каждый:

```bash
git status
git diff --check
git diff --stat
```

Один логический кусок — один commit. Backend мерджит только после проверки diff, ownership и тестов.

## 6. Минимальное определение готовности

- `docker compose up --build` запускается на чистом окружении.
- Миграции применяются автоматически или одной документированной командой.
- `/health` отвечает.
- P0-сценарий проходит от UI до результата.
- ML prediction настоящий, артефакт загружается.
- Невалидные данные дают понятную ошибку, а не падение.
- Backend tests и frontend build проходят.
- README позволяет жюри запустить проект без устных подсказок.
