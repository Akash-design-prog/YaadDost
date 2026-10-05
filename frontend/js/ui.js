// Bootstrap: wires the deck, the strip, the review surface, the notes panel and the explainer together.
import * as api from "./api.js";
import { createDeck } from "./deck.js";
import { createStrip } from "./strip.js";
import { createReview } from "./review.js";
import { createNotes } from "./notes.js";
import { createTheme } from "./theme.js";

const $ = (id) => document.getElementById(id);

function openStorage() {
  try {
    const s = window.localStorage;
    const probe = "yaaddost.probe";
    s.setItem(probe, "1");
    s.removeItem(probe);
    return s;
  } catch {
    return null;   // blocked (private window, strict settings): the deck lives in memory for this session
  }
}

const storage = openStorage();
const deck = createDeck({ storage });
createTheme({ button: $("themeToggle"), storage });
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const focusNotes = () => {
  $("notesPanel").scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
  $("notes").focus({ preventScroll: true });
};

const strip = createStrip($("curveTrack"));
const review = createReview({
  deck, api, strip, reducedMotion, focusNotes,
  els: {
    empty: $("empty"), emptyTitle: $("emptyTitle"), emptyText: $("emptyText"), emptyAction: $("emptyAction"),
    study: $("study"), mark: $("mark"), progress: $("progress"), q: $("q"), answerBox: $("answerBox"), a: $("a"),
    show: $("show"), grades: $("grades"), feedback: $("feedback"), dueLine: $("dueLine"), curve: $("curve"),
  },
});
createNotes({
  deck, api,
  onAdded: () => {
    review.render();
    $("review").scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
  },
  els: {
    form: $("notesForm"), notes: $("notes"), count: $("count"), make: $("make"), sample: $("sample"),
    working: $("working"), workingText: $("workingText"), msg: $("msg"),
    dropped: $("dropped"), droppedTitle: $("droppedTitle"), droppedList: $("droppedList"),
  },
});

// ---- Gemma status ----
async function checkStatus() {
  const badge = $("badge");
  try {
    const s = await api.getStatus();
    badge.textContent = s.available ? `Gemma connected · ${s.model}` : "Offline mode";
    badge.className = `pill ${s.available ? "is-on" : "is-off"}`;
    badge.title = s.available ? "Cards are written and checked by your Gemma server." : "Gemma isn't reachable, so cards are made with simple rules.";
  } catch {
    badge.textContent = "Offline mode";
    badge.className = "pill is-off";
  }
}

// ---- explain a concept ----
$("explain").addEventListener("click", async () => {
  const concept = $("concept").value.trim();
  const out = $("explainOut");
  if (concept.length < 2) {
    out.hidden = false;
    out.className = "note is-error";
    out.textContent = "Type the concept you want explained.";
    $("concept").focus();
    return;
  }
  $("explain").disabled = true;
  out.hidden = false;
  out.className = "note";
  out.textContent = "Thinking about it…";
  try {
    const language = document.querySelector('input[name="lang"]:checked').value;
    out.textContent = (await api.explain(concept, $("notes").value, language)).text;
  } catch (e) {
    out.className = "note is-error";
    out.textContent = e.message;
  } finally {
    $("explain").disabled = false;
  }
});

// ---- delete everything ----
$("reset").addEventListener("click", () => {
  const n = deck.size();
  if (n === 0) return;
  if (window.confirm(`Delete all ${n} ${n === 1 ? "card" : "cards"}? This can't be undone.`)) {
    deck.clear();
    review.render();
  }
});

// ---- keyboard ----
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = e.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target.isContentEditable) return;
  if (tag === "BUTTON" && (e.key === " " || e.key === "Enter")) return;   // let the focused button handle it
  if (review.onKey(e)) e.preventDefault();
});

if (!deck.isPersistent()) {
  $("storageNote").textContent = "This browser is blocking storage, so your cards won't be saved after you close this tab.";
}

checkStatus();
review.render();
setInterval(review.render, 30000);   // cards come due while the page is open
