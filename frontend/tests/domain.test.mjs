import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { reviewOf, validateReview } from "../src/domain.ts";
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
