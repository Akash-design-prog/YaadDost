// The deck: cards and their schedule. Lives only in this browser (localStorage).
const KEY = "yaaddost.deck.v1";
const DAY = 86400000;
const AGAIN_DELAY = 10 * 60000;

let deck = load();

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; }
}

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(deck)); } catch { /* storage blocked: deck stays in memory */ }
}

export const size = () => deck.length;
export const due = () => deck.filter((c) => c.due <= Date.now());

export function addCards(cards) {
  const now = Date.now();
  cards.forEach((c) =>
    deck.push({ id: crypto.randomUUID(), q: c.q, a: c.a, ease: 2.5, interval: 0, reps: 0, due: now })
  );
  save();
}

// `next` is the scheduling state returned by the backend (ease, interval, reps).
export function applyReview(card, grade, next) {
  Object.assign(card, next, { due: Date.now() + (grade === "again" ? AGAIN_DELAY : next.interval * DAY) });
  save();
}

export function clear() {
  deck = [];
  save();
}
