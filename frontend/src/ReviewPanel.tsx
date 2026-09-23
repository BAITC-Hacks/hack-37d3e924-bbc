import type { Result, Review } from "./types";
import { TaskPanel } from "./TaskPanel";
import { TranscriptPanel } from "./meetingDisplay";

export function ReviewPanel({
  activeSourceId,
  result,
  original,
  review,
  onChange,
  onJumpToSegment,
  onReload,
  onShowOriginal,
}: {
  activeSourceId: string | null;
  result: Result;
  original: Result | null;
  review: Review;
  onChange: (review: Review) => void;
  onJumpToSegment: (id: string) => void;
  onReload: () => Promise<void>;
  onShowOriginal: () => Promise<void>;
}) {
  const speakers = [
    ...new Set(result.segments.map((segment) => segment.speaker_id)),
  ];
  return (
    <div className="review-grid">
      <div className="review-main">
        {result.warnings.map((warning, index) => (
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

        <TaskPanel
          result={result}
          review={review}
          activeSourceId={activeSourceId}
          onChange={onChange}
          onJumpToSegment={onJumpToSegment}
        />

        <TranscriptPanel
          segments={result.segments}
          review={review}
          activeSourceId={activeSourceId}
        />
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
          <button className="full-button" onClick={() => void onShowOriginal()}>
            {original ? "Скрыть JSON" : "Показать JSON"}
          </button>
          {original && <pre>{JSON.stringify(original, null, 2)}</pre>}
        </section>

        <section className="side-card">
          <p className="panel-kicker">Синхронизация</p>
          <button className="full-button" onClick={() => void onReload()}>
            Открыть сохранённую версию
          </button>
        </section>
      </aside>
    </div>
  );
}
