import test from "node:test";
import assert from "node:assert/strict";
import { createDeck } from "../../frontend/js/deck.js";

const DAY = 86400000;
let ids;
const uuid = () => `id${++ids}`;
const memory = (initial = {}) => {
  const data = { ...initial };
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
};
const KEY = "yaaddost.deck.v1";
const setup = (storage = memory(), t = { now: 1_000_000 }) => {
  ids = 0;
  return { deck: createDeck({ storage, now: () => t.now, uuid }), storage, t };
};

test("a new deck is empty and persistent when storage works", () => {
  const { deck } = setup();
  assert.equal(deck.size(), 0);
  assert.equal(deck.isPersistent(), true);
  assert.deepEqual(deck.due(), []);
});

test("addCards stores new cards as due now with the right defaults", () => {
  const { deck } = setup();
  const added = deck.addCards([{ q: "Q1?", a: "A1" }, { q: "Q2?", a: "A2" }], true);
  assert.equal(added.length, 2);
  assert.deepEqual(added.map((c) => c.id), ["id1", "id2"]);
  assert.deepEqual([added[0].ease, added[0].interval, added[0].reps, added[0].checked], [2.5, 0, 0, true]);
  assert.equal(deck.due().length, 2);
});

test("addCards ignores empty or malformed cards", () => {
  const { deck } = setup();
  const added = deck.addCards([{ q: "", a: "x" }, { q: "ok", a: " " }, { q: "fine?", a: "yes" }, null, { q: 5, a: "x" }].filter((x) => x !== null));
  assert.equal(added.length, 1);
  assert.equal(deck.size(), 1);
});

test("the Verifier flag is kept per card: true, false and unknown", () => {
  const { deck } = setup();
  deck.addCards([{ q: "a?", a: "b" }], true);
  deck.addCards([{ q: "c?", a: "d" }], false);
  deck.addCards([{ q: "e?", a: "f" }]);
  assert.deepEqual(deck.all().map((c) => c.checked), [true, false, null]);
});

test("the deck survives a reload through storage", () => {
  const { deck, storage } = setup();
  deck.addCards([{ q: "Q?", a: "A" }], true);
  const again = createDeck({ storage, now: () => 1_000_000, uuid });
  assert.equal(again.size(), 1);
  assert.equal(again.all()[0].q, "Q?");
  assert.equal(again.all()[0].checked, true);
});

test("grading moves the due date; 'again' comes back in 10 minutes", () => {
  const { deck, t } = setup();
  const [card] = deck.addCards([{ q: "Q?", a: "A" }]);
  deck.applyReview(card.id, "good", { ease: 2.5, interval: 6, reps: 2 });
  assert.equal(deck.all()[0].due, t.now + 6 * DAY);
  assert.deepEqual(deck.due(), []);
  deck.applyReview(card.id, "again", { ease: 2.3, interval: 1, reps: 0 });
  assert.equal(deck.all()[0].due, t.now + 10 * 60000);
  assert.equal(deck.all()[0].reps, 0);
  t.now += 11 * 60000;
  assert.equal(deck.due().length, 1);      // and it is due again once the 10 minutes pass
});

test("applyReview on an unknown id does nothing", () => {
  const { deck } = setup();
  assert.equal(deck.applyReview("nope", "good", { ease: 2.5, interval: 1, reps: 1 }), null);
});

test("due() is oldest first", () => {
  const { deck, t } = setup();
  deck.addCards([{ q: "first?", a: "1" }]);
  t.now += 1000;
  deck.addCards([{ q: "second?", a: "2" }]);
  t.now += 1000;
  assert.deepEqual(deck.due().map((c) => c.q), ["first?", "second?"]);
});

test("clear empties the deck and the storage", () => {
  const { deck, storage } = setup();
  deck.addCards([{ q: "Q?", a: "A" }]);
  deck.clear();
  assert.equal(deck.size(), 0);
  assert.equal(JSON.parse(storage.data[KEY]).length, 0);
});

test("corrupt storage starts a fresh deck instead of crashing", () => {
  for (const bad of ["not json", "{}", "null", "42", '"text"']) {
    const { deck } = setup(memory({ [KEY]: bad }));
    assert.equal(deck.size(), 0, bad);
  }
});

test("old or partial saved cards are repaired, bad ones dropped", () => {
  const raw = JSON.stringify([
    { id: "x", q: "old?", a: "card", ease: 2.5, interval: 3, reps: 1, due: 5 },     // saved before the checked flag existed
    { q: "no id?", a: "gets one" },
    { id: "y", q: "bad ease?", a: "clamped", ease: -4, interval: -2, reps: 1.6, due: "soon" },
    { q: "", a: "dropped" },
    "junk",
  ]);
  const { deck } = setup(memory({ [KEY]: raw }));
  const all = deck.all();
  assert.equal(all.length, 3);
  assert.equal(all[0].checked, null);
  assert.ok(all[1].id);
  assert.deepEqual([all[2].ease, all[2].interval, all[2].reps], [1.3, 0, 2]);
  assert.equal(all[2].due, 1_000_000);
});

test("blocked storage: reading and writing never throw, and the deck says it is not saved", () => {
  const blocked = { getItem() { throw new Error("denied"); }, setItem() { throw new Error("denied"); } };
  ids = 0;
  const deck = createDeck({ storage: blocked, now: () => 1, uuid });
  assert.equal(deck.size(), 0);
  deck.addCards([{ q: "Q?", a: "A" }]);
  assert.equal(deck.size(), 1);              // still works for this session
  assert.equal(deck.isPersistent(), false);
});

test("no storage at all behaves like blocked storage", () => {
  const deck = createDeck({ storage: null, now: () => 1, uuid: () => "u" });
  deck.addCards([{ q: "Q?", a: "A" }]);
  assert.equal(deck.size(), 1);
  assert.equal(deck.isPersistent(), false);
});
