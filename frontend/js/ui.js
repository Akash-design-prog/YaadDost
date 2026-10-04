import * as api from "./api.js";
import * as deck from "./deck.js";

const $ = (id) => document.getElementById(id);
let current = null;

const SAMPLE_NOTES = [
  "Deadlock: a situation where two or more processes wait forever for resources held by each other.",
  "Four conditions for deadlock: mutual exclusion, hold and wait, no preemption, and circular wait.",
  "Banker's algorithm: avoids deadlock by granting a request only if the system stays in a safe state.",
  "Paging divides memory into fixed-size blocks, which removes external fragmentation.",
  "Thrashing happens when a system spends more time swapping pages than executing instructions.",
].join("\n");

async function checkStatus() {
  const b = $("badge");
  try {
    const s = await api.getStatus();
    b.textContent = s.available ? "Gemma connected · " + s.model : "Offline mode · Gemma not reachable";
    b.className = "badge " + (s.available ? "ok" : "off");
  } catch {
    b.textContent = "Offline mode";
    b.className = "badge off";
  }
}

function render() {
  const due = deck.due();
  $("due").textContent = deck.size() ? `· ${due.length} due of ${deck.size()}` : "";
  current = due[0] || null;
  $("empty").hidden = !!current;
  $("study").hidden = !current;
  if (current) {
    $("q").textContent = current.q;
    $("a").textContent = current.a;
    $("a").hidden = true;
    $("grades").hidden = true;
    $("show").hidden = false;
  } else {
    $("empty").textContent = deck.size()
      ? "All caught up. Come back when the next card is due."
      : "No cards due. Make some above.";
  }
}

function showDropped(dropped) {
  $("dropped").hidden = dropped.length === 0;
  $("droppedTitle").textContent = `${dropped.length} card${dropped.length === 1 ? "" : "s"} removed: not supported by your notes`;
  $("droppedList").replaceChildren(...dropped.map((d) => {
    const li = document.createElement("li");
    li.textContent = `${d.q} → ${d.a} (${d.reason})`;   // textContent: model output is never parsed as HTML
    return li;
  }));
}

function say(text, warn = false) {
  $("msg").textContent = text;
  $("msg").className = "note" + (warn ? " warn" : "");
}

$("make").onclick = async () => {
  const notes = $("notes").value.trim();
  if (notes.length < 20) return say("Add a few more lines of notes first.", true);
  $("make").disabled = true;
  say("Making cards… (the first call can take a minute)");
  try {
    const r = await api.makeCards(notes, $("lang").value, +$("count").value);
    deck.addCards(r.cards);
    render();
    showDropped(r.dropped || []);
    if (r.source !== "gemma") say(`Added ${r.cards.length} cards using the simple offline rules. Connect Gemma for better, Hinglish-aware cards.`, true);
    else if (r.verified) say(`Added ${r.cards.length} cards by ${r.model}, each checked against your notes.`);
    else say(`Added ${r.cards.length} cards by ${r.model}. The notes check didn't run, so read them before trusting them.`, true);
  } catch (e) {
    say(e.message, true);
  }
  $("make").disabled = false;
};

$("show").onclick = () => {
  $("a").hidden = false;
  $("grades").hidden = false;
  $("show").hidden = true;
};

$("grades").onclick = async (e) => {
  const grade = e.target.dataset.g;
  if (!grade || !current) return;
  try {
    deck.applyReview(current, grade, await api.reviewCard(current, grade));
    render();
  } catch (err) {
    say(err.message, true);
  }
};

$("explain").onclick = async () => {
  const concept = $("concept").value.trim();
  if (concept.length < 2) return;
  $("explain").disabled = true;
  $("explainOut").textContent = "Thinking…";
  try {
    $("explainOut").textContent = (await api.explain(concept, $("notes").value, $("lang").value)).text;
  } catch (e) {
    $("explainOut").textContent = e.message;
  }
  $("explain").disabled = false;
};

$("reset").onclick = () => {
  if (confirm("Delete all saved cards?")) {
    deck.clear();
    render();
  }
};

$("sample").onclick = () => { $("notes").value = SAMPLE_NOTES; };

checkStatus();
render();
setInterval(render, 60000);
