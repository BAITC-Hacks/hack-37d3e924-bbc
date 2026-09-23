import type { Result, Review } from "./types.ts";
export function reviewOf(result: Result): Review {
  return structuredClone({
    participants: result.participants,
    tasks: result.tasks,
    summary: result.summary,
  });
}
export function validateReview(review: Review, result: Result): string | null {
  const participants = new Set(review.participants.map((p) => p.id));
  const sources = new Set(result.segments.map((s) => s.id));
  const speakers = new Set(result.segments.map((s) => s.speaker_id));
  const assigned = review.participants.flatMap((p) => p.speaker_ids);
  if (
    new Set(assigned).size !== assigned.length ||
    assigned.some((s) => !speakers.has(s))
  )
    return "Один голос можно сопоставить только одному участнику.";
  for (const task of review.tasks) {
    if (!task.text.trim()) return "Укажите текст каждого поручения.";
    if (
      !task.source_segment_ids.length ||
      task.source_segment_ids.some((s) => !sources.has(s))
    )
      return "Выберите исходные реплики для каждого поручения.";
    if (task.assignee_id !== null && !participants.has(task.assignee_id))
      return "Выберите существующего участника.";
    if (task.due_date !== null) {
      const date = new Date(task.due_date + "T00:00:00Z");
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(task.due_date) ||
        !Number.isFinite(date.getTime()) ||
        date.toISOString().slice(0, 10) !== task.due_date
      )
        return "Укажите действительную дату в формате YYYY-MM-DD.";
    }
    if (
      (task.assignee_id === null || task.due_date === null) &&
      !task.needs_review
    )
      return "Поручение без исполнителя или срока требует проверки.";
  }
  return null;
}

type DateTimeParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
};

function partsInTimeZone(date: Date, timeZone: string): DateTimeParts {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = (type: string) => {
    const part = parts.find((item) => item.type === type)?.value;
    if (!part) throw new Error("Не удалось прочитать дату для часового пояса.");
    return Number(part);
  };
  return {
    year: value("year"),
    month: value("month"),
    day: value("day"),
    hour: value("hour"),
    minute: value("minute"),
    second: value("second"),
  };
}

function offsetMinutesAt(date: Date, timeZone: string) {
  const parts = partsInTimeZone(date, timeZone);
  const asUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
  );
  return Math.round((asUtc - date.getTime()) / 60000);
}

function formatOffset(minutes: number) {
  const sign = minutes >= 0 ? "+" : "-";
  const abs = Math.abs(minutes);
  const hours = String(Math.floor(abs / 60)).padStart(2, "0");
  const mins = String(abs % 60).padStart(2, "0");
  return `${sign}${hours}:${mins}`;
}

function assertValidTimeZone(timeZone: string) {
  try {
    new Intl.DateTimeFormat("en", { timeZone }).format(new Date(0));
  } catch {
    throw new Error("Укажите действительный часовой пояс, например Asia/Qyzylorda.");
  }
}

export function localDateTimeToZonedIso(localValue: string, timeZone: string) {
  assertValidTimeZone(timeZone);
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(
    localValue,
  );
  if (!match) throw new Error("Укажите дату и время совещания.");
  const [, year, month, day, hour, minute] = match.map(String);
  const localParts: DateTimeParts = {
    year: Number(year),
    month: Number(month),
    day: Number(day),
    hour: Number(hour),
    minute: Number(minute),
    second: 0,
  };
  const normalized = new Date(
    Date.UTC(
      localParts.year,
      localParts.month - 1,
      localParts.day,
      localParts.hour,
      localParts.minute,
    ),
  );
  if (
    normalized.getUTCFullYear() !== localParts.year ||
    normalized.getUTCMonth() !== localParts.month - 1 ||
    normalized.getUTCDate() !== localParts.day ||
    normalized.getUTCHours() !== localParts.hour ||
    normalized.getUTCMinutes() !== localParts.minute
  )
    throw new Error("Укажите действительные дату и время совещания.");
  const guessUtc = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
  );
  const matches: number[] = [];
  for (
    let instant = guessUtc - 18 * 60 * 60_000;
    instant <= guessUtc + 18 * 60 * 60_000;
    instant += 15 * 60_000
  ) {
    const parts = partsInTimeZone(new Date(instant), timeZone);
    if (
      parts.year === localParts.year &&
      parts.month === localParts.month &&
      parts.day === localParts.day &&
      parts.hour === localParts.hour &&
      parts.minute === localParts.minute
    )
      matches.push(instant);
  }
  const offsets = [...new Set(matches.map((value) => offsetMinutesAt(new Date(value), timeZone)))];
  if (!matches.length)
    throw new Error(
      "В выбранном часовом поясе такого местного времени нет. Уточните время совещания.",
    );
  if (offsets.length > 1)
    throw new Error(
      "Это время встречается дважды из-за перевода часов. Уточните дату или часовой пояс.",
    );
  const offset = offsets[0];
  return `${year}-${month}-${day}T${hour}:${minute}:00${formatOffset(offset)}`;
}

export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 Б";
  if (bytes < 1024) return `${bytes} Б`;
  const units = ["КиБ", "МиБ", "ГиБ"];
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}
