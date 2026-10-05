import test from "node:test";
import assert from "node:assert/strict";
import {
  DAY, HORIZON, LATER, startOfDay, dayIndex, bucketByDay, describeSchedule, formatWait, nextDue, describeNext, describeInterval,
} from "../../frontend/js/schedule.js";

const NOW = new Date(2026, 9, 5, 14, 30).getTime();   // 5 Oct 2026, 14:30 local
const at = (days, hour = 9) => new Date(2026, 9, 5 + days, hour, 0).getTime();

test("dayIndex: due now, overdue and later today all count as today", () => {
  assert.equal(dayIndex(NOW, NOW), 0);
  assert.equal(dayIndex(NOW - 3 * DAY, NOW), 0);
  assert.equal(dayIndex(NOW + 10 * 60000, NOW), 0);          // an "again" card due in 10 minutes
  assert.equal(dayIndex(new Date(2026, 9, 5, 23, 59).getTime(), NOW), 0);
});

test("dayIndex: uses calendar days, not 24-hour blocks", () => {
  assert.equal(dayIndex(at(1, 0), NOW), 1);     // just after midnight tonight is tomorrow
  assert.equal(dayIndex(at(1, 23), NOW), 1);
  assert.equal(dayIndex(at(2, 0), NOW), 2);
  assert.equal(dayIndex(at(7), NOW), 7);
});

test("dayIndex: clamps to the strip and survives bad input", () => {
  assert.equal(dayIndex(at(HORIZON), NOW), HORIZON);
  assert.equal(dayIndex(at(HORIZON + 1), NOW), LATER);
  assert.equal(dayIndex(at(4000), NOW), LATER);
  assert.equal(dayIndex(NaN, NOW), 0);
  assert.equal(dayIndex(undefined, NOW), 0);
});

test("dayIndex: a daylight-saving shift never moves a card to the wrong day", () => {
  for (let d = 0; d < 400; d++) {
    const now = new Date(2026, 0, 1, 12).getTime() + d * DAY;
    assert.equal(dayIndex(new Date(2026, 0, 1 + d + 3, 12).getTime(), now), 3, `day ${d}`);
  }
});

test("bucketByDay: puts ids in the right buckets and loses none", () => {
  const cards = [
    { id: "a", due: NOW - 1 }, { id: "b", due: at(1) }, { id: "c", due: at(1, 20) },
    { id: "d", due: at(9) }, { id: "e", due: at(500) },
  ];
  const b = bucketByDay(cards, NOW);
  assert.equal(b.length, LATER + 1);
  assert.deepEqual(b[0], ["a"]);
  assert.deepEqual(b[1], ["b", "c"]);
  assert.deepEqual(b[9], ["d"]);
  assert.deepEqual(b[LATER], ["e"]);
  assert.equal(b.flat().length, cards.length);
});

test("describeSchedule: plain sentences for every mix", () => {
  const mk = (list) => bucketByDay(list, NOW);
  assert.equal(describeSchedule(mk([])), "No cards yet.");
  assert.equal(describeSchedule(mk([{ id: "a", due: NOW }])), "1 card due today.");
  assert.equal(
    describeSchedule(mk([{ id: "a", due: NOW }, { id: "b", due: NOW }, { id: "c", due: at(1) }, { id: "d", due: at(3) }, { id: "e", due: at(12) }, { id: "f", due: at(90) }])),
    "2 cards due today, 1 tomorrow, 1 in the next week, 1 later this month, 1 after that."
  );
  assert.equal(describeSchedule(mk([{ id: "a", due: at(2) }])), "Nothing due today, 1 in the next week.");
});

test("formatWait: picks a sensible unit and pluralises", () => {
  assert.equal(formatWait(5000), "less than a minute");
  assert.equal(formatWait(60000), "1 minute");
  assert.equal(formatWait(10 * 60000), "10 minutes");
  assert.equal(formatWait(3600000), "1 hour");
  assert.equal(formatWait(5 * 3600000), "5 hours");
  assert.equal(formatWait(DAY), "1 day");
  assert.equal(formatWait(6 * DAY), "6 days");
});

test("nextDue and describeNext", () => {
  const cards = [{ id: "a", due: NOW - 5 }, { id: "b", due: NOW + 3 * 3600000 }, { id: "c", due: NOW + 9 * DAY }];
  assert.equal(nextDue(cards, NOW), NOW + 3 * 3600000);
  assert.equal(describeNext(cards, NOW), "Next card in 3 hours.");
  assert.equal(nextDue([{ id: "a", due: NOW - 5 }], NOW), null);
  assert.equal(describeNext([], NOW), "");
});

test("describeInterval", () => {
  assert.equal(describeInterval("again", 1), "Back in 10 minutes.");
  assert.equal(describeInterval("good", 1), "Back tomorrow.");
  assert.equal(describeInterval("easy", 15), "Back in 15 days.");
});

test("startOfDay is local midnight", () => {
  const d = new Date(startOfDay(NOW));
  assert.deepEqual([d.getHours(), d.getMinutes(), d.getSeconds(), d.getMilliseconds()], [0, 0, 0, 0]);
});
