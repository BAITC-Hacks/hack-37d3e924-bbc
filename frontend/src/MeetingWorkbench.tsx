import type { ReactNode } from "react";
import type { Meeting } from "./types";
import { api } from "./api/client";
import { displayDate, StageStrip, stages, statuses, statusTone } from "./meetingDisplay";

export function MeetingWorkbench({
  busy,
  meeting,
  onDelete,
  onRetry,
  children,
}: {
  busy: boolean;
  meeting: Meeting;
  onDelete: () => Promise<void>;
  onRetry: () => Promise<void>;
  children: ReactNode;
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
          <button disabled={busy} onClick={() => void onRetry()}>
            Повторить обработку
          </button>
        </section>
      )}

      {children}
    </>
  );
}

export function SaveBar({
  dirty,
  invalid,
  meeting,
  busy,
  onReload,
  onSave,
}: {
  dirty: boolean;
  invalid: string | null;
  meeting: Meeting;
  busy: boolean;
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
          onClick={() => void onSave()}
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
        <button disabled={busy} onClick={() => void onReload()}>
          Отменить правки
        </button>
      </div>
    </div>
  );
}
