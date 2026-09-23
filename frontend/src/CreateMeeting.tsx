import type { FormEvent } from "react";
import { formatBytes } from "./domain";
import { StageStrip } from "./meetingDisplay";

const defaultTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function CreateMeeting({
  busy,
  selectedFile,
  onCreate,
  onFile,
}: {
  busy: boolean;
  selectedFile: File | null;
  onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void>;
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
