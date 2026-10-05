// Pure schedule helpers for the forgetting-curve strip and the "next card" text. No DOM, no storage.
export const DAY = 86400000;
export const HORIZON = 30;          // days drawn on the strip
export const LATER = HORIZON + 1;   // bucket index for anything beyond the horizon

export function startOfDay(ts) {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

// 0 = due now, overdue, or later today; 1 = tomorrow; ... 30; 31 = beyond the strip.
export function dayIndex(due, now) {
  if (!Number.isFinite(due) || due <= now) return 0;
  const idx = Math.round((startOfDay(due) - startOfDay(now)) / DAY);
  return Math.max(0, Math.min(idx, LATER));
}

// Returns LATER + 1 arrays of card ids, one per day bucket.
export function bucketByDay(cards, now) {
  const buckets = Array.from({ length: LATER + 1 }, () => []);
  for (const c of cards) buckets[dayIndex(c.due, now)].push(c.id);
  return buckets;
}

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const sum = (list) => list.reduce((s, b) => s + b.length, 0);

// A text equivalent of the strip, for screen readers.
export function describeSchedule(buckets) {
  const total = sum(buckets);
  if (!total) return "No cards yet.";
  const today = buckets[0].length;
  const parts = [today ? `${plural(today, "card")} due today` : "Nothing due today"];
  const tomorrow = buckets[1].length;
  const week = sum(buckets.slice(2, 8));
  const month = sum(buckets.slice(8, LATER));
  const later = buckets[LATER].length;
  if (tomorrow) parts.push(`${tomorrow} tomorrow`);
  if (week) parts.push(`${week} in the next week`);
  if (month) parts.push(`${month} later this month`);
  if (later) parts.push(`${later} after that`);
  return `${parts.join(", ")}.`;
}

export function formatWait(ms) {
  if (ms < 60000) return "less than a minute";
  const minutes = Math.round(ms / 60000);
  if (minutes < 60) return plural(minutes, "minute");
  const hours = Math.round(ms / 3600000);
  if (hours < 24) return plural(hours, "hour");
  return plural(Math.round(ms / DAY), "day");
}

// The soonest card that is not due yet, or null.
export function nextDue(cards, now) {
  let best = null;
  for (const c of cards) if (c.due > now && (best === null || c.due < best)) best = c.due;
  return best;
}

export function describeNext(cards, now) {
  const t = nextDue(cards, now);
  return t === null ? "" : `Next card in ${formatWait(t - now)}.`;
}

// What a grade means in words, for the confirmation line after grading.
export function describeInterval(grade, interval) {
  if (grade === "again") return "Back in 10 minutes.";
  return interval === 1 ? "Back tomorrow." : `Back in ${interval} days.`;
}
