export type Participant = {
  id: string;
  name: string | null;
  speaker_ids: string[];
};
export type Segment = {
  id: string;
  speaker_id: string;
  start: number;
  end: number;
  text: string;
};
export type Task = {
  id: string;
  text: string;
  assignee_id: string | null;
  due_date: string | null;
  source_segment_ids: string[];
  needs_review: boolean;
};
export type Result = {
  schema_version: 1;
  meeting_id: string;
  meeting_datetime: string;
  timezone: string;
  participants: Participant[];
  segments: Segment[];
  tasks: Task[];
  summary: string;
  warnings: string[];
};
export type Meeting = {
  id: string;
  title: string;
  meeting_datetime: string;
  timezone: string;
  status: "queued" | "processing" | "done" | "failed";
  stage: string | null;
  mode: "real" | "fixture";
  error: { code: string; message: string; details: object } | null;
  revision: number;
  result: Result | null;
};
export type Review = Pick<Result, "participants" | "tasks" | "summary">;
