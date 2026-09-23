import type { Result, Review, Task } from "./types";
import { segmentSpeaker, sourceTitle } from "./meetingDisplay";

export function TaskPanel({
  result,
  review,
  activeSourceId,
  onChange,
  onJumpToSegment,
}: {
  result: Result;
  review: Review;
  activeSourceId: string | null;
  onChange: (review: Review) => void;
  onJumpToSegment: (id: string) => void;
}) {
  function onTaskChange(id: string, patch: Partial<Task>) {
    onChange({
      ...review,
      tasks: review.tasks.map((task) => {
        if (task.id !== id) return task;
        const next = { ...task, ...patch };
        if (!next.assignee_id || !next.due_date) next.needs_review = true;
        return next;
      }),
    });
  }

  return (
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
                {result.segments.map((segment) => (
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
                    {sourceTitle(result, sourceId)}
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
