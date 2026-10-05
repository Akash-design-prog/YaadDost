// The deck: cards and their schedule. Lives only in this browser (localStorage), and keeps working in memory
// if the browser blocks storage. Storage, clock and id generator are injected so this can be tested without a browser.
const KEY = "yaaddost.deck.v1";
const DAY = 86400000;
const AGAIN_DELAY = 10 * 60000;

const finite = (v, fallback) => (Number.isFinite(v) ? v : fallback);

function clean(raw, now) {
  if (!raw || typeof raw.q !== "string" || typeof raw.a !== "string" || !raw.q.trim() || !raw.a.trim()) return null;
  return {
    id: typeof raw.id === "string" && raw.id ? raw.id : null,
    q: raw.q,
    a: raw.a,
    ease: Math.max(1.3, finite(raw.ease, 2.5)),
    interval: Math.max(0, Math.round(finite(raw.interval, 0))),
    reps: Math.max(0, Math.round(finite(raw.reps, 0))),
    due: finite(raw.due, now),
    checked: raw.checked === true ? true : raw.checked === false ? false : null,
  };
}

export function createDeck({ storage = null, now = () => Date.now(), uuid = () => crypto.randomUUID() } = {}) {
  let persistent = storage !== null;
  let cards = load();

  function load() {
    if (!storage) return [];
    try {
      const parsed = JSON.parse(storage.getItem(KEY));
      if (!Array.isArray(parsed)) return [];
      return parsed
        .map((c) => clean(c, now()))
        .filter(Boolean)
        .map((c) => ({ ...c, id: c.id || uuid() }));
    } catch {
      return [];   // empty, unreadable or blocked: start fresh
    }
  }

  function save() {
    if (!storage) return;
    try {
      storage.setItem(KEY, JSON.stringify(cards));
    } catch {
      persistent = false;   // blocked or full: the deck stays in memory for this session
    }
  }

  return {
    all: () => cards,
    size: () => cards.length,
    isPersistent: () => persistent,
    // Cards due now, oldest first.
    due() {
      const t = now();
      return cards.filter((c) => c.due <= t).sort((a, b) => a.due - b.due);
    },
    // `checked` is true when the Verifier ran, false when it did not, null when unknown (offline rules).
    addCards(list, checked = null) {
      const t = now();
      const added = list
        .map((c) => clean({ q: c.q, a: c.a, due: t, checked: c.checked ?? checked }, t))
        .filter(Boolean)
        .map((c) => ({ ...c, id: uuid() }));
      cards = cards.concat(added);
      save();
      return added;
    },
    // `next` is the scheduling state from the backend: { ease, interval, reps }.
    applyReview(id, grade, next) {
      const card = cards.find((c) => c.id === id);
      if (!card) return null;
      card.ease = next.ease;
      card.interval = next.interval;
      card.reps = next.reps;
      card.due = now() + (grade === "again" ? AGAIN_DELAY : next.interval * DAY);
      save();
      return card;
    },
    clear() {
      cards = [];
      save();
    },
  };
}
