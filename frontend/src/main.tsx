import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api/client";
import type { Meeting, Result, Review, Segment, Task } from "./types";
import {
  formatBytes,
  localDateTimeToZonedIso,
  reviewOf,
  validateReview,
} from "./domain";
import "./style.css";

const stages: Record<string, string> = {
  preparing_audio: "Подготовка аудио",
  transcribing: "Распознавание речи",
  diarizing: "Разделение говорящих",
  aligning: "Сопоставление реплик",
  extracting_tasks: "Извлечение поручений",
  summarizing: "Составление саммари",
  validating: "Проверка результата",
};

const statuses: Record<Meeting["status"], string> = {
  queued: "В очереди",
  processing: "Обрабатывается",
  done: "Готово к проверке",
  failed: "Ошибка обработки",
};

const statusTone: Record<Meeting["status"], string> = {
  queued: "tone-waiting",
  processing: "tone-active",
  done: "tone-done",
  failed: "tone-failed",
};

const defaultTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
const stageOrder = ["upload", "process", "review"] as const;

function stageState(meeting: Meeting | null, name: (typeof stageOrder)[number]) {
  if (!meeting) return name === "upload" ? "active" : "idle";
  if (name === "upload") return "done";
  if (name === "process") {
    if (meeting.status === "queued" || meeting.status === "processing")
      return "active";
    if (meeting.status === "failed") return "failed";
    return "done";
  }
  return meeting.status === "done" ? "active" : "idle";
}

function displayDate(value: string, timeZone: string) {
  const parsed = new Date(value);
  if (Number.isFinite(parsed.getTime())) {
    try {
      return new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone,
      }).format(parsed);
    } catch {
      return new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(parsed);
    }
  }
  return value;
}

function segmentSpeaker(review: Review, segment: Segment) {
  return (
    review.participants.find((participant) =>
      participant.speaker_ids.includes(segment.speaker_id),
    )?.name || segment.speaker_id
  );
}

function sourceTitle(result: Result, sourceId: string) {
  const segment = result.segments.find((item) => item.id === sourceId);
  if (!segment) return sourceId;
  return `${segment.start.toFixed(1)} с · ${segment.speaker_id}`;
}

function App() {
  const [items, setItems] = useState<Meeting[]>([]);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [original, setOriginal] = useState<Result | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [creating, setCreating] = useState(true);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | Meeting["status"]>("all");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesStatus = filter === "all" || item.status === filter;
      const matchesQuery =
        !needle ||
        item.title.toLowerCase().includes(needle) ||
        item.timezone.toLowerCase().includes(needle) ||
        item.meeting_datetime.toLowerCase().includes(needle);
      return matchesStatus && matchesQuery;
    });
  }, [items, query, filter]);

  async function refresh() {
    const data = await api.list();
    setItems(data.items);
  }

  function show(value: Meeting) {
    setMeeting(value);
    setReview(value.result ? reviewOf(value.result) : null);
    setOriginal(null);
    setDirty(false);
    setActiveSourceId(null);
    setCreating(false);
  }

  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ошибка приложения.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refresh().catch(() =>
      setError("Не удалось загрузить совещания. Проверьте запуск сервера."),
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(() => {
      void refresh().catch(() => {});
      if (meeting && ["queued", "processing"].includes(meeting.status)) {
        void api
          .get(meeting.id)
          .then((value) => {
            if (!cancelled) show(value);
          })
          .catch(() => setError("Не удалось обновить статус."));
      }
    }, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [meeting?.id, meeting?.status]);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  function canLeave() {
    return !dirty || window.confirm("Есть несохранённые правки. Отбросить их?");
  }

  function openCreate() {
    if (!canLeave()) return;
    setLibraryOpen(false);
    setCreating(true);
    setDirty(false);
    setMeeting(null);
    setReview(null);
    setOriginal(null);
    setError("");
    setNotice("");
  }

  function change(next: Review) {
    setReview(next);
    setDirty(true);
    setNotice("");
  }

  function taskChange(id: string, patch: Partial<Task>) {
    if (!review) return;
    change({
      ...review,
      tasks: review.tasks.map((task) => {
        if (task.id !== id) return task;
        const next = { ...task, ...patch };
        if (!next.assignee_id || !next.due_date) next.needs_review = true;
        return next;
      }),
    });
  }

  function jumpToSegment(id: string) {
    const target = document.getElementById(`segment-${id}`);
    setActiveSourceId(id);
    target?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
    target?.focus({ preventScroll: true });
  }

  const invalid =
    review && meeting?.result ? validateReview(review, meeting.result) : null;

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await act(async () => {
      const form = event.currentTarget;
      const data = new FormData(form);
      const timezone = String(data.get("timezone") || "").trim();
      const audio = data.get("audio");
      if (!(audio instanceof File) || !audio.size)
        throw new Error("Выберите аудиофайл для обработки.");
      const names = String(data.get("names"))
        .split("\n")
        .map((name) => name.trim())
        .filter(Boolean);
      const body = new FormData();
      body.set("audio", audio);
      body.set(
        "metadata",
        JSON.stringify({
          title: String(data.get("title") || "").trim(),
          meeting_datetime: localDateTimeToZonedIso(
            String(data.get("datetime")),
            timezone,
          ),
          timezone,
          participants: names.map((name, index) => ({
            id: "p" + (index + 1),
            name,
            speaker_ids: [],
          })),
        }),
      );
      show(await api.create(body));
      setSelectedFile(null);
      form.reset();
      await refresh();
    });
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand" aria-label="Хаттама">
          <span className="brand-mark">Х</span>
          <div>
            <strong>Хаттама</strong>
            <small>Локальные протоколы</small>
          </div>
        </div>

        <button className="primary create-button" disabled={busy} onClick={openCreate}>
          <span aria-hidden="true">+</span>
          Новое совещание
        </button>

        <button
          className="library-toggle"
          type="button"
          aria-expanded={libraryOpen}
          aria-controls="meeting-library"
          onClick={() => setLibraryOpen(!libraryOpen)}
        >
          {libraryOpen ? "Свернуть список" : `Совещания · ${items.length}`}
          <span aria-hidden="true">{libraryOpen ? "−" : "+"}</span>
        </button>

        <div id="meeting-library" className={`meeting-library${libraryOpen ? " is-open" : ""}`}>
          <label className="search-label">
            <span>Поиск</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Название, дата, зона"
            />
          </label>

          <div className="filter-row" aria-label="Фильтр статуса">
            {(["all", "processing", "done", "failed"] as const).map((value) => (
              <button
                key={value}
                className={filter === value ? "active-chip" : ""}
                onClick={() => setFilter(value)}
                type="button"
              >
                {value === "all" ? "Все" : statuses[value]}
              </button>
            ))}
          </div>

          <nav className="meeting-nav" aria-label="Совещания">
            {filteredItems.map((item) => (
              <button
                key={item.id}
                className={meeting?.id === item.id && !creating ? "selected" : ""}
                disabled={busy}
                onClick={() => {
                  if (canLeave()) void act(async () => {
                    show(await api.get(item.id));
                    setLibraryOpen(false);
                    document.getElementById("workspace")?.focus();
                  });
                }}
              >
                <span className={`status-dot ${statusTone[item.status]}`} />
                <span>
                  <strong>{item.title}</strong>
                  <small>
                    {statuses[item.status]} ·{" "}
                    {displayDate(item.meeting_datetime, item.timezone)}
                    {item.mode === "fixture" ? " · ТЕСТ" : ""}
                  </small>
                </span>
              </button>
            ))}
          </nav>

          {!filteredItems.length && (
            <p className="sidebar-empty">
              {items.length ? "По этому фильтру ничего нет." : "Загрузите первую запись."}
            </p>
          )}

          <footer className="sidebar-note">
            Аудио и текст остаются в локальном контуре. Тестовые результаты отмечены отдельно.
          </footer>
        </div>
      </aside>

      <main className="workspace" id="workspace" tabIndex={-1}>
        {(error || notice) && (
          <div className="message-stack">
            {error && (
              <div role="alert" className="alert">
                {error}
              </div>
            )}
            {notice && (
              <div role="status" className="success">
                {notice}
              </div>
            )}
          </div>
        )}

        {creating ? (
          <CreateMeeting
            busy={busy}
            selectedFile={selectedFile}
            onCreate={create}
            onFile={setSelectedFile}
          />
        ) : (
          meeting && (
            <MeetingWorkbench
              busy={busy}
              dirty={dirty}
              invalid={invalid}
              meeting={meeting}
              original={original}
              review={review}
              onAct={act}
              onChange={change}
              onDelete={async () => {
                if (
                  !canLeave() ||
                  !window.confirm("Удалить запись и все её результаты?")
                )
                  return;
                await act(async () => {
                  await api.remove(meeting.id);
                  setMeeting(null);
                  setReview(null);
                  setCreating(true);
                  setDirty(false);
                  await refresh();
                });
              }}
              activeSourceId={activeSourceId}
              onJumpToSegment={jumpToSegment}
              onReload={async () => {
                if (!canLeave()) return;
                show(await api.get(meeting.id));
              }}
              onRetry={async () => show(await api.retry(meeting.id))}
              onSave={async () => {
                if (!review) return;
                show(await api.review(meeting.id, meeting.revision, review));
                setNotice("Правки сохранены. DOCX содержит эту версию.");
                await refresh();
              }}
              onShowOriginal={async () =>
                setOriginal(original ? null : await api.original(meeting.id))
              }
              onTaskChange={taskChange}
            />
          )
        )}
      </main>
    </div>
  );
}

function CreateMeeting({
  busy,
  selectedFile,
  onCreate,
  onFile,
}: {
  busy: boolean;
  selectedFile: File | null;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
  onFile: (file: File | null) => void;
}) {
  return (
    <section className="create-panel">
      <div className="panel-kicker">Новая запись</div>
      <div className="create-grid">
        <div>
          <h1>Соберите протокол из записи совещания</h1>
          <p className="lead">
            Загрузите аудио, дождитесь локальной обработки и проверьте итог перед
            экспортом DOCX.
          </p>
          <StageStrip meeting={null} />
        </div>
        <form className="create-form" onSubmit={onCreate}>
          <label>
            Название
            <input
              name="title"
              required
              maxLength={200}
              placeholder="Рабочее совещание"
            />
          </label>

          <div className="two-fields">
            <label>
              Дата и время
              <input
                name="datetime"
                type="datetime-local"
                required
                aria-describedby="datetime-help"
              />
            </label>
            <label>
              Часовой пояс
              <input name="timezone" required defaultValue={defaultTimeZone} />
            </label>
          </div>
          <p id="datetime-help" className="field-help">
            Укажите дату записи. По ней рассчитываются сроки «завтра» и «до
            пятницы».
          </p>

          <label>
            Известные участники
            <textarea
              name="names"
              rows={4}
              placeholder={"Марсель\nАйжан"}
            />
          </label>

          <label className="drop-zone">
            <input
              type="file"
              name="audio"
              required
              accept=".wav,.mp3,.m4a,.flac"
              onChange={(event) => onFile(event.currentTarget.files?.[0] || null)}
            />
            <span className="drop-icon" aria-hidden="true">
              ↑
            </span>
            <span className="drop-title">
              {selectedFile ? selectedFile.name : "Выберите или перетащите аудио"}
            </span>
            <span className="drop-meta">
              {selectedFile
                ? formatBytes(selectedFile.size)
                : "WAV, MP3, M4A, FLAC · до 100 МиБ по умолчанию"}
            </span>
          </label>

          <button className="primary submit-button" disabled={busy}>
            {busy ? "Сохраняем..." : "Загрузить и обработать"}
          </button>
        </form>
      </div>
    </section>
  );
}

function MeetingWorkbench({
  activeSourceId,
  busy,
  dirty,
  invalid,
  meeting,
  original,
  review,
  onAct,
  onChange,
  onDelete,
  onJumpToSegment,
  onReload,
  onRetry,
  onSave,
  onShowOriginal,
  onTaskChange,
}: {
  activeSourceId: string | null;
  busy: boolean;
  dirty: boolean;
  invalid: string | null;
  meeting: Meeting;
  original: Result | null;
  review: Review | null;
  onAct: (action: () => Promise<void>) => Promise<void>;
  onChange: (review: Review) => void;
  onDelete: () => Promise<void>;
  onJumpToSegment: (id: string) => void;
  onReload: () => Promise<void>;
  onRetry: () => Promise<void>;
  onSave: () => Promise<void>;
  onShowOriginal: () => Promise<void>;
  onTaskChange: (id: string, patch: Partial<Task>) => void;
}) {
  return (
    <>
      <header className="meeting-header">
        <div>
          <div className={`status-pill ${statusTone[meeting.status]}`}>
            {statuses[meeting.status]}
          </div>
          <h1>{meeting.title}</h1>
          <p>
            {displayDate(meeting.meeting_datetime, meeting.timezone)} ·{" "}
            {meeting.timezone} · версия {meeting.revision}
          </p>
        </div>
        <button
          className="danger-button"
          disabled={busy || meeting.status === "processing"}
          onClick={() => void onDelete()}
        >
          Удалить
        </button>
      </header>

      <StageStrip meeting={meeting} />

      {meeting.mode === "fixture" && (
        <div className="fixture-note" role="note">
          Тестовый режим. Это синтетический пример для проверки приложения;
          аудио и модели не анализировались.
        </div>
      )}

      {["queued", "processing"].includes(meeting.status) && (
        <section className="status-card" aria-live="polite">
          <span className="loader" aria-hidden="true" />
          <div>
            <h2>
              {meeting.stage
                ? stages[meeting.stage] || meeting.stage
                : "Запись ожидает обработки"}
            </h2>
            <p>
              Статус обновляется автоматически. Можно открыть другое совещание и
              вернуться позже.
            </p>
          </div>
        </section>
      )}

      {meeting.status === "failed" && (
        <section className="status-card failed-card">
          <div>
            <h2>Обработка не завершена</h2>
            <p>{meeting.error?.message}</p>
          </div>
          <button disabled={busy} onClick={() => void onAct(onRetry)}>
            Повторить обработку
          </button>
        </section>
      )}

      {review && meeting.result && (
        <fieldset disabled={busy}>
          <ReviewPanel
            activeSourceId={activeSourceId}
            meeting={meeting as Meeting & { result: Result }}
            original={original}
            review={review}
            onAct={onAct}
            onChange={onChange}
            onJumpToSegment={onJumpToSegment}
            onReload={onReload}
            onShowOriginal={onShowOriginal}
            onTaskChange={onTaskChange}
          />
          <SaveBar
            dirty={dirty}
            invalid={invalid}
            meeting={meeting}
            busy={busy}
            onAct={onAct}
            onReload={onReload}
            onSave={onSave}
          />
        </fieldset>
      )}
    </>
  );
}

function StageStrip({ meeting }: { meeting: Meeting | null }) {
  const labels = {
    upload: "Загрузка",
    process: "Обработка",
    review: "Проверка",
  };
  return (
    <ol className="stage-strip" aria-label="Этапы работы">
      {stageOrder.map((stage, index) => (
        <li key={stage} className={`stage-${stageState(meeting, stage)}`}>
          <span>{index + 1}</span>
          {labels[stage]}
        </li>
      ))}
    </ol>
  );
}

function ReviewPanel({
  activeSourceId,
  meeting,
  original,
  review,
  onAct,
  onChange,
  onJumpToSegment,
  onReload,
  onShowOriginal,
  onTaskChange,
}: {
  activeSourceId: string | null;
  meeting: Meeting & { result: Result };
  original: Result | null;
  review: Review;
  onAct: (action: () => Promise<void>) => Promise<void>;
  onChange: (review: Review) => void;
  onJumpToSegment: (id: string) => void;
  onReload: () => Promise<void>;
  onShowOriginal: () => Promise<void>;
  onTaskChange: (id: string, patch: Partial<Task>) => void;
}) {
  const speakers = [
    ...new Set(meeting.result.segments.map((segment) => segment.speaker_id)),
  ];
  return (
    <div className="review-grid">
      <div className="review-main">
        {meeting.result.warnings.map((warning, index) => (
          <p key={index} className="warning">
            {warning}
          </p>
        ))}

        <section className="review-section summary-section">
          <div className="section-heading">
            <div>
              <p className="panel-kicker">Саммари</p>
              <h2>Краткое содержание</h2>
            </div>
          </div>
          <textarea
            aria-label="Краткое содержание"
            rows={7}
            value={review.summary}
            onChange={(event) =>
              onChange({ ...review, summary: event.target.value })
            }
          />
        </section>

        <section className="review-section">
          <div className="section-heading">
            <div>
              <p className="panel-kicker">Поручения</p>
              <h2>{review.tasks.length} в протоколе</h2>
            </div>
            <button
              onClick={() =>
                onChange({
                  ...review,
                  tasks: [
                    ...review.tasks,
                    {
                      id: crypto.randomUUID(),
                      text: "",
                      assignee_id: null,
                      due_date: null,
                      source_segment_ids: [],
                      needs_review: true,
                    },
                  ],
                })
              }
            >
              + Поручение
            </button>
          </div>

          {!review.tasks.length && (
            <p className="empty-inline">Поручений пока нет. Добавьте вручную и выберите источник.</p>
          )}

          <div className="task-list">
            {review.tasks.map((task, index) => (
              <article className="task-card" key={task.id}>
                <div className="task-card-top">
                  <span className={task.needs_review ? "review-badge" : "ready-badge"}>
                    {task.needs_review ? "Требует проверки" : "Готово"}
                  </span>
                  <button
                    className="text-button"
                    onClick={() =>
                      onChange({
                        ...review,
                        tasks: review.tasks.filter((item) => item.id !== task.id),
                      })
                    }
                  >
                    Удалить
                  </button>
                </div>

                <label>
                  Поручение {index + 1}
                  <textarea
                    rows={3}
                    value={task.text}
                    onChange={(event) =>
                      onTaskChange(task.id, { text: event.target.value })
                    }
                  />
                </label>

                <div className="two-fields">
                  <label>
                    Ответственный
                    <select
                      value={task.assignee_id || ""}
                      onChange={(event) =>
                        onTaskChange(task.id, {
                          assignee_id: event.target.value || null,
                        })
                      }
                    >
                      <option value="">Требует уточнения</option>
                      {review.participants.map((participant) => (
                        <option key={participant.id} value={participant.id}>
                          {participant.name || "Участник без имени"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Срок
                    <input
                      type="date"
                      value={task.due_date || ""}
                      onChange={(event) =>
                        onTaskChange(task.id, {
                          due_date: event.target.value || null,
                        })
                      }
                    />
                  </label>
                </div>

                <label className="check">
                  <input
                    type="checkbox"
                    checked={task.needs_review}
                    disabled={!task.assignee_id || !task.due_date}
                    onChange={(event) =>
                      onTaskChange(task.id, {
                        needs_review: event.target.checked,
                      })
                    }
                  />
                  Оставить на ручной проверке
                </label>

                <details className="source-picker">
                  <summary>Источники: {task.source_segment_ids.length}</summary>
                  <div className="source-list">
                    {meeting.result.segments.map((segment) => (
                      <label className="source-option" key={segment.id}>
                        <input
                          type="checkbox"
                          checked={task.source_segment_ids.includes(segment.id)}
                          onChange={(event) =>
                            onTaskChange(task.id, {
                              source_segment_ids: event.target.checked
                                ? [...task.source_segment_ids, segment.id]
                                : task.source_segment_ids.filter(
                                    (id) => id !== segment.id,
                                  ),
                            })
                          }
                        />
                        <span>
                          <strong>
                            {segment.start.toFixed(1)} с ·{" "}
                            {segmentSpeaker(review, segment)}
                          </strong>
                          {segment.text}
                        </span>
                      </label>
                    ))}
                  </div>
                </details>

                {!!task.source_segment_ids.length && (
                  <div className="source-chips">
                    {task.source_segment_ids.map((sourceId) => (
                      <button
                        type="button"
                        key={sourceId}
                        className={activeSourceId === sourceId ? "is-active" : ""}
                        onClick={() => onJumpToSegment(sourceId)}
                      >
                        {sourceTitle(meeting.result, sourceId)}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="review-section transcript-section">
          <div className="section-heading">
            <div>
              <p className="panel-kicker">Расшифровка</p>
              <h2>Реплики · {meeting.result.segments.length}</h2>
            </div>
          </div>
          <div className="segment-list">
            {meeting.result.segments.map((segment) => (
              <article
                className={
                  activeSourceId === segment.id
                    ? "segment-card is-active"
                    : "segment-card"
                }
                id={`segment-${segment.id}`}
                key={segment.id}
                tabIndex={-1}
              >
                <time>
                  {segment.start.toFixed(1)}-{segment.end.toFixed(1)} с
                </time>
                <strong>{segmentSpeaker(review, segment)}</strong>
                <p>{segment.text}</p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <aside className="review-aside" aria-label="Параметры проверки">
        <section className="side-card">
          <p className="panel-kicker">Участники</p>
          <h2>{review.participants.length}</h2>
          {review.participants.map((participant, index) => (
            <div className="participant-card" key={participant.id}>
              <input
                aria-label={"Имя участника " + (index + 1)}
                value={participant.name || ""}
                onChange={(event) =>
                  onChange({
                    ...review,
                    participants: review.participants.map((item) =>
                      item.id === participant.id
                        ? {
                            ...item,
                            name: event.target.value.trim()
                              ? event.target.value
                              : null,
                          }
                        : item,
                    ),
                  })
                }
              />
              <div className="speaker-grid">
                {speakers.map((speaker) => (
                  <label className="check" key={speaker}>
                    <input
                      type="checkbox"
                      checked={participant.speaker_ids.includes(speaker)}
                      onChange={(event) =>
                        onChange({
                          ...review,
                          participants: review.participants.map((item) =>
                            item.id === participant.id
                              ? {
                                  ...item,
                                  speaker_ids: event.target.checked
                                    ? [...item.speaker_ids, speaker]
                                    : item.speaker_ids.filter((id) => id !== speaker),
                                }
                              : item,
                          ),
                        })
                      }
                    />
                    {speaker}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button
            className="full-button"
            onClick={() =>
              onChange({
                ...review,
                participants: [
                  ...review.participants,
                  {
                    id: crypto.randomUUID(),
                    name: null,
                    speaker_ids: [],
                  },
                ],
              })
            }
          >
            + Участник
          </button>
        </section>

        <section className="side-card">
          <p className="panel-kicker">Исходный результат</p>
          <p className="side-copy">
            Машинная версия открывается только для сверки. Правки сохраняются отдельно.
          </p>
          <button className="full-button" onClick={() => void onAct(onShowOriginal)}>
            {original ? "Скрыть JSON" : "Показать JSON"}
          </button>
          {original && <pre>{JSON.stringify(original, null, 2)}</pre>}
        </section>

        <section className="side-card">
          <p className="panel-kicker">Синхронизация</p>
          <button className="full-button" onClick={() => void onAct(onReload)}>
            Открыть сохранённую версию
          </button>
        </section>
      </aside>
    </div>
  );
}

function SaveBar({
  dirty,
  invalid,
  meeting,
  busy,
  onAct,
  onReload,
  onSave,
}: {
  dirty: boolean;
  invalid: string | null;
  meeting: Meeting;
  busy: boolean;
  onAct: (action: () => Promise<void>) => Promise<void>;
  onReload: () => Promise<void>;
  onSave: () => Promise<void>;
}) {
  return (
    <div className="savebar">
      <div>
        {invalid ? (
          <p role="alert" className="save-error">
            {invalid}
          </p>
        ) : (
          <p>
            {dirty ? "Есть несохранённые правки" : "Все правки сохранены"} ·
            версия {meeting.revision}
          </p>
        )}
      </div>
      <div className="actions">
        <button
          className="primary"
          disabled={busy || !dirty || !!invalid}
          onClick={() => void onAct(onSave)}
        >
          Сохранить правки
        </button>
        {!dirty && !invalid ? (
          <a className="button" href={api.exportURL(meeting.id)}>
            Скачать DOCX
          </a>
        ) : (
          <button disabled>Сначала сохраните</button>
        )}
        <button disabled={busy} onClick={() => void onAct(onReload)}>
          Отменить правки
        </button>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
