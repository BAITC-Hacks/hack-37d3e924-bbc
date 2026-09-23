import { useEffect, useState, type FormEvent } from "react";
import { api } from "./api/client";
import type { Meeting, Result, Review } from "./types";
import { localDateTimeToZonedIso, reviewOf, validateReview } from "./domain";
import { CreateMeeting } from "./CreateMeeting";
import { MeetingLibrary } from "./MeetingLibrary";
import { MeetingWorkbench, SaveBar } from "./MeetingWorkbench";
import { ReviewPanel } from "./ReviewPanel";

export function App() {
  const [items, setItems] = useState<Meeting[]>([]);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [original, setOriginal] = useState<Result | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [creating, setCreating] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [libraryOpen, setLibraryOpen] = useState(false);

  async function refreshMeetings() {
    const data = await api.list();
    setItems(data.items);
  }

  function showMeeting(value: Meeting) {
    setMeeting(value);
    setReview(value.result ? reviewOf(value.result) : null);
    setOriginal(null);
    setDirty(false);
    setActiveSourceId(null);
    setCreating(false);
  }

  async function runAction(action: () => Promise<void>) {
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
    void refreshMeetings().catch(() =>
      setError("Не удалось загрузить совещания. Проверьте запуск сервера."),
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(() => {
      void refreshMeetings().catch(() => {});
      if (meeting && ["queued", "processing"].includes(meeting.status)) {
        void api
          .get(meeting.id)
          .then((value) => {
            if (!cancelled) showMeeting(value);
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

  function canDiscardChanges() {
    return !dirty || window.confirm("Есть несохранённые правки. Отбросить их?");
  }

  function openCreateForm() {
    if (!canDiscardChanges()) return;
    setLibraryOpen(false);
    setCreating(true);
    setDirty(false);
    setMeeting(null);
    setReview(null);
    setOriginal(null);
    setError("");
    setNotice("");
  }

  function openMeeting(id: string) {
    if (!canDiscardChanges()) return;
    void runAction(async () => {
      showMeeting(await api.get(id));
      setLibraryOpen(false);
      document.getElementById("workspace")?.focus();
    });
  }

  function updateReview(next: Review) {
    setReview(next);
    setDirty(true);
    setNotice("");
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

  async function createMeeting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction(async () => {
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
      showMeeting(await api.create(body));
      setSelectedFile(null);
      form.reset();
      await refreshMeetings();
    });
  }

  async function deleteMeeting() {
    if (
      !meeting ||
      !canDiscardChanges() ||
      !window.confirm("Удалить запись и все её результаты?")
    )
      return;
    await runAction(async () => {
      await api.remove(meeting.id);
      setMeeting(null);
      setReview(null);
      setCreating(true);
      setDirty(false);
      await refreshMeetings();
    });
  }

  async function reloadMeeting() {
    if (!meeting || !canDiscardChanges()) return;
    showMeeting(await api.get(meeting.id));
  }

  async function retryMeeting() {
    if (meeting) showMeeting(await api.retry(meeting.id));
  }

  async function saveReview() {
    if (!meeting || !review) return;
    showMeeting(await api.review(meeting.id, meeting.revision, review));
    setNotice("Правки сохранены. DOCX содержит эту версию.");
    await refreshMeetings();
  }

  async function toggleOriginal() {
    if (meeting) setOriginal(original ? null : await api.original(meeting.id));
  }

  return (
    <div className="shell">
      <MeetingLibrary
        items={items}
        selectedMeetingId={!creating ? meeting?.id ?? null : null}
        busy={busy}
        libraryOpen={libraryOpen}
        onCreate={openCreateForm}
        onToggle={() => setLibraryOpen(!libraryOpen)}
        onSelect={openMeeting}
      />

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
            onCreate={createMeeting}
            onFile={setSelectedFile}
          />
        ) : (
          meeting && (
            <MeetingWorkbench
              busy={busy}
              meeting={meeting}
              onDelete={deleteMeeting}
              onRetry={() => runAction(retryMeeting)}
            >
              {review && meeting.result && (
                <fieldset disabled={busy}>
                  <ReviewPanel
                    activeSourceId={activeSourceId}
                    result={meeting.result}
                    original={original}
                    review={review}
                    onChange={updateReview}
                    onJumpToSegment={jumpToSegment}
                    onReload={() => runAction(reloadMeeting)}
                    onShowOriginal={() => runAction(toggleOriginal)}
                  />
                  <SaveBar
                    dirty={dirty}
                    invalid={invalid}
                    meeting={meeting}
                    busy={busy}
                    onReload={() => runAction(reloadMeeting)}
                    onSave={() => runAction(saveReview)}
                  />
                </fieldset>
              )}
            </MeetingWorkbench>
          )
        )}
      </main>
    </div>
  );
}
