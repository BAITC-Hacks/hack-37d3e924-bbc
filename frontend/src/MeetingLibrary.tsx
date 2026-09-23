import { useMemo, useState } from "react";
import type { Meeting } from "./types";
import { displayDate, statuses, statusTone } from "./meetingDisplay";

export function MeetingLibrary({
  items,
  selectedMeetingId,
  busy,
  libraryOpen,
  onCreate,
  onToggle,
  onSelect,
}: {
  items: Meeting[];
  selectedMeetingId: string | null;
  busy: boolean;
  libraryOpen: boolean;
  onCreate: () => void;
  onToggle: () => void;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | Meeting["status"]>("all");

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

  return (
    <aside className="sidebar">
      <div className="brand" aria-label="Хаттама">
        <span className="brand-mark">Х</span>
        <div>
          <strong>Хаттама</strong>
          <small>Локальные протоколы</small>
        </div>
      </div>

      <button className="primary create-button" disabled={busy} onClick={onCreate}>
        <span aria-hidden="true">+</span>
        Новое совещание
      </button>

      <button
        className="library-toggle"
        type="button"
        aria-expanded={libraryOpen}
        aria-controls="meeting-library"
        onClick={onToggle}
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
              className={selectedMeetingId === item.id ? "selected" : ""}
              disabled={busy}
              onClick={() => onSelect(item.id)}
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
  );
}
