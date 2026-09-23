import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  formatBytes,
  localDateTimeToZonedIso,
  reviewOf,
  validateReview,
} from "../src/domain.ts";
const result = JSON.parse(
  readFileSync(
    new URL("../../contracts/examples/result.json", import.meta.url),
  ),
);
test("existing fixture review is valid and independent of immutable original", () => {
  const review = reviewOf(result);
  assert.equal(validateReview(review, result), null);
  review.tasks[0].text = "Правка";
  assert.notEqual(result.tasks[0].text, review.tasks[0].text);
});
test("manual tasks require evidence", () => {
  const review = reviewOf(result);
  review.tasks[0].source_segment_ids = [];
  assert.match(validateReview(review, result), /реплики/);
  review.tasks[0].source_segment_ids = ["unknown"];
  assert.match(validateReview(review, result), /реплики/);
});
test("impossible dates rejected and leap day accepted", () => {
  const review = reviewOf(result);
  review.tasks[0].due_date = "2026-02-30";
  assert.match(validateReview(review, result), /дату/);
  review.tasks[0].due_date = "2028-02-29";
  assert.equal(validateReview(review, result), null);
});
test("unknown assignee and duplicate speaker ownership rejected", () => {
  const review = reviewOf(result);
  review.tasks[0].assignee_id = "none";
  assert.match(validateReview(review, result), /участника/);
  review.tasks[0].assignee_id = "p1";
  review.participants[0].speaker_ids = ["SPEAKER_00"];
  review.participants[1].speaker_ids = ["SPEAKER_00"];
  assert.match(validateReview(review, result), /голос/);
});
test("missing due date cannot be marked checked", () => {
  const review = reviewOf(result);
  review.tasks[0].due_date = null;
  assert.match(validateReview(review, result), /проверки/);
});
test("local meeting time converts to contract ISO with selected IANA zone", () => {
  assert.equal(
    localDateTimeToZonedIso("2026-09-23T10:30", "Asia/Qyzylorda"),
    "2026-09-23T10:30:00+05:00",
  );
});
test("invalid and ambiguous local meeting times are rejected", () => {
  assert.throws(
    () => localDateTimeToZonedIso("2026-09-23 10:00", "Asia/Qyzylorda"),
    /дату и время/,
  );
  assert.throws(
    () => localDateTimeToZonedIso("2026-09-23T10:00", "Mars/Base"),
    /часовой пояс/,
  );
  assert.throws(
    () => localDateTimeToZonedIso("2026-02-30T10:00", "Asia/Qyzylorda"),
    /дату/,
  );
  assert.throws(
    () => localDateTimeToZonedIso("2026-03-08T02:30", "America/New_York"),
    /такого местного времени/,
  );
  assert.throws(
    () => localDateTimeToZonedIso("2026-11-01T01:30", "America/New_York"),
    /встречается дважды/,
  );
});
test("file sizes are shown in readable binary units", () => {
  assert.equal(formatBytes(0), "0 Б");
  assert.equal(formatBytes(1536), "1.5 КиБ");
  assert.equal(formatBytes(10 * 1024 * 1024), "10 МиБ");
});
