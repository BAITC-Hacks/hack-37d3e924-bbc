import type { Meeting, Result, Review } from "../types";
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.code === "REVISION_CONFLICT"
        ? "Результат уже изменён в другой вкладке. Скопируйте свои правки и откройте актуальную версию."
        : body?.error?.message ||
            "Не удалось выполнить запрос. Проверьте соединение с приложением.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const path = (id: string) => "/api/v1/meetings/" + encodeURIComponent(id);
export const api = {
  list: () => request<{ items: Meeting[] }>("/api/v1/meetings"),
  get: (id: string) => request<Meeting>(path(id)),
  create: (body: FormData) =>
    request<Meeting>("/api/v1/meetings", { method: "POST", body }),
  review: (id: string, revision: number, review: Review) =>
    request<Meeting>(path(id) + "/review", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_revision: revision, ...review }),
    }),
  original: (id: string) => request<Result>(path(id) + "/original"),
  retry: (id: string) =>
    request<Meeting>(path(id) + "/retry", { method: "POST" }),
  remove: (id: string) => request<void>(path(id), { method: "DELETE" }),
  exportURL: (id: string) => path(id) + "/export.docx",
};
