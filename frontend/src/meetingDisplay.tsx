import type { Meeting, Result, Review, Segment } from "./types";

export const stages: Record<string, string> = {
  preparing_audio: "Подготовка аудио",
  transcribing: "Распознавание речи",
  diarizing: "Разделение говорящих",
  aligning: "Сопоставление реплик",
  extracting_tasks: "Извлечение поручений",
  summarizing: "Составление саммари",
  validating: "Проверка результата",
};

export const statuses: Record<Meeting["status"], string> = {
  queued: "В очереди",
  processing: "Обрабатывается",
  done: "Готово к проверке",
  failed: "Ошибка обработки",
};

export const statusTone: Record<Meeting["status"], string> = {
  queued: "tone-waiting",
  processing: "tone-active",
  done: "tone-done",
  failed: "tone-failed",
};

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

export function displayDate(value: string, timeZone: string) {
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

export function segmentSpeaker(review: Review, segment: Segment) {
  return (
    review.participants.find((participant) =>
      participant.speaker_ids.includes(segment.speaker_id),
    )?.name || segment.speaker_id
  );
}

export function sourceTitle(result: Result, sourceId: string) {
  const segment = result.segments.find((item) => item.id === sourceId);
  if (!segment) return sourceId;
  return `${segment.start.toFixed(1)} с · ${segment.speaker_id}`;
}

export function StageStrip({ meeting }: { meeting: Meeting | null }) {
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

export function TranscriptPanel({
  segments,
  review,
  activeSourceId,
}: {
  segments: Segment[];
  review: Review;
  activeSourceId: string | null;
}) {
  return (
    <section className="review-section transcript-section">
      <div className="section-heading">
        <div>
          <p className="panel-kicker">Расшифровка</p>
          <h2>Реплики · {segments.length}</h2>
        </div>
      </div>
      <div className="segment-list">
        {segments.map((segment) => (
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
  );
}
