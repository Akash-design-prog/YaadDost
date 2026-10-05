// Adding notes: ask the backend for cards, show progress, and explain exactly what the Verifier did.
const SAMPLE_NOTES = [
  "Deadlock: a situation where two or more processes wait forever for resources held by each other.",
  "Four conditions for deadlock: mutual exclusion, hold and wait, no preemption, and circular wait.",
  "Banker's algorithm: avoids deadlock by granting a request only if the system stays in a safe state.",
  "Paging divides memory into fixed-size blocks, which removes external fragmentation.",
  "Thrashing happens when a system spends more time swapping pages than executing instructions.",
].join("\n");

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function createNotes({ deck, api, els, onAdded }) {
  let timer = null;

  function say(text, kind = "") {
    els.msg.textContent = text;
    els.msg.className = `msg${kind ? ` is-${kind}` : ""}`;
  }

  function showRemoved(dropped) {
    els.dropped.hidden = dropped.length === 0;
    els.droppedTitle.textContent = `${plural(dropped.length, "card")} removed: not supported by your notes`;
    els.droppedList.replaceChildren(
      ...dropped.map((d) => {
        const li = document.createElement("li");
        li.textContent = `${d.q} → ${d.a} `;   // textContent: model output is never parsed as HTML
        const why = document.createElement("span");
        why.textContent = `(${d.reason})`;
        li.append(why);
        return li;
      })
    );
  }

  function startWorking() {
    const started = Date.now();
    els.working.hidden = false;
    const tick = () => {
      const s = Math.floor((Date.now() - started) / 1000);
      els.workingText.textContent = `Gemma is writing your cards and checking each one against your notes. This takes about 30 to 45 seconds. ${s}s so far.`;
    };
    tick();
    timer = setInterval(tick, 1000);
  }

  function stopWorking() {
    clearInterval(timer);
    timer = null;
    els.working.hidden = true;
  }

  async function make() {
    const notes = els.notes.value.trim();
    if (notes.length < 20) {
      say("Add a few more lines of notes first.", "error");
      els.notes.focus();
      return;
    }
    const language = els.form.querySelector('input[name="lang"]:checked').value;
    els.make.disabled = true;
    say("");
    showRemoved([]);
    startWorking();
    try {
      const r = await api.makeCards(notes, language, Number(els.count.value));
      // Per card, the backend says whether the Verifier checked it. Without that flag, fall back to the run's overall result.
      const runChecked = r.source === "gemma" ? r.verified : null;
      const added = deck.addCards(r.cards, runChecked);
      showRemoved(r.dropped || []);
      if (r.source !== "gemma") {
        say(`Added ${plural(added.length, "card")} using simple rules, because Gemma isn't connected. They are basic, so connect Gemma for better cards.`, "warn");
      } else if (r.verified) {
        say(`Added ${plural(added.length, "card")}. Each one was checked against your notes.`, "good");
      } else {
        say(`Added ${plural(added.length, "card")}. The check against your notes didn't run, so read them before you trust them.`, "warn");
      }
      onAdded();
    } catch (e) {
      say(e.message, "error");
    } finally {
      stopWorking();
      els.make.disabled = false;
    }
  }

  els.form.addEventListener("submit", (e) => {
    e.preventDefault();
    make();
  });
  els.sample.addEventListener("click", () => {
    els.notes.value = SAMPLE_NOTES;
    els.notes.focus();
  });

  return { make };
}
