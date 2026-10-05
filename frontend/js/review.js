// The review surface: today's card, the answer, the four grades, and the empty states.
import { describeInterval, describeNext } from "./schedule.js";

const SVG = "http://www.w3.org/2000/svg";

function checkIcon() {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", "M3 8.5l3.2 3.2L13 4.8");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}

export function createReview({ deck, api, strip, els, now = () => Date.now(), reducedMotion = () => false, focusNotes = () => {} }) {
  let current = null;
  let revealed = false;
  let busy = false;
  let doneThisSession = 0;

  const gradeButtons = () => [...els.grades.querySelectorAll("button")];

  function setFeedback(text, kind = "") {
    els.feedback.textContent = text;
    els.feedback.className = `msg${kind ? ` is-${kind}` : ""}`;
  }

  function renderDueLine(all, due) {
    els.dueLine.replaceChildren();
    if (all.length === 0) {
      els.dueLine.textContent = "No cards yet.";
      return;
    }
    if (due.length) {
      const strong = document.createElement("strong");
      strong.textContent = `${due.length} ${due.length === 1 ? "card" : "cards"} due`;
      els.dueLine.append(strong, ` · ${all.length} in your deck`);
    } else {
      els.dueLine.textContent = `Nothing due right now · ${all.length} in your deck`;
    }
  }

  function showEmpty(all, t) {
    els.study.hidden = true;
    els.empty.hidden = false;
    if (all.length === 0) {
      els.emptyTitle.textContent = "No cards yet";
      els.emptyText.textContent = "Paste your notes below and Gemma will turn them into cards. Each one is checked against what you wrote.";
      els.emptyAction.textContent = "Add notes";
    } else {
      els.emptyTitle.textContent = "All caught up";
      els.emptyText.textContent = describeNext(all, t) || "Add more notes to keep going.";
      els.emptyAction.textContent = "Add more notes";
    }
  }

  function renderMark(card) {
    els.mark.replaceChildren();
    els.mark.classList.toggle("is-ok", card.checked === true);
    if (card.checked === true) els.mark.append(checkIcon(), "Checked against your notes");
    else if (card.checked === false) els.mark.append("Not checked against your notes");
    else els.mark.append("Made with simple rules, not checked");
  }

  function renderCard(due, isNewCard) {
    els.empty.hidden = true;
    els.study.hidden = false;
    els.q.textContent = current.q;
    els.a.textContent = current.a;
    renderMark(current);
    els.progress.textContent = `${doneThisSession + 1} of ${doneThisSession + due.length}`;
    els.answerBox.hidden = !revealed;
    els.show.hidden = revealed;
    els.grades.hidden = !revealed;
    if (isNewCard) {
      els.study.classList.remove("is-in");
      void els.study.offsetWidth;   // restart the entrance animation
      els.study.classList.add("is-in");
    }
  }

  function render() {
    const t = now();
    const all = deck.all();
    const due = deck.due();
    renderDueLine(all, due);
    const keep = current && due.some((c) => c.id === current.id);
    const isNewCard = !keep;
    if (!keep) {
      current = due[0] || null;
      revealed = false;
    } else {
      current = due.find((c) => c.id === current.id);
    }
    els.curve.hidden = all.length === 0;   // an empty timeline says nothing, so show it only once there are cards
    strip.render(all, t, current ? current.id : null);
    if (!current) {
      showEmpty(all, t);
      return;
    }
    renderCard(due, isNewCard);
  }

  function reveal() {
    if (!current || revealed) return;
    revealed = true;
    els.answerBox.hidden = false;
    els.show.hidden = true;
    els.grades.hidden = false;
    els.answerBox.classList.remove("is-in");
    void els.answerBox.offsetWidth;
    els.answerBox.classList.add("is-in");
    els.answerBox.focus({ preventScroll: true });   // so a screen reader reads the answer, and Tab reaches the grades
  }

  async function grade(g) {
    if (!current || !revealed || busy) return;
    busy = true;
    gradeButtons().forEach((b) => (b.disabled = true));
    const card = current;
    const from = strip.rectOf(card.id);
    try {
      const next = await api.reviewCard(card, g);
      deck.applyReview(card.id, g, next);
      els.study.classList.remove("flash-good", "flash-bad");
      void els.study.offsetWidth;
      els.study.classList.add(g === "again" || g === "hard" ? "flash-bad" : "flash-good");
      setFeedback(describeInterval(g, next.interval), "");
      doneThisSession += 1;
      revealed = false;
      current = null;
      render();
      strip.hop(card.id, from, reducedMotion());
      if (!els.study.hidden) els.show.focus({ preventScroll: true });
    } catch (e) {
      setFeedback(`${e.message} Your card is still waiting.`, "error");
    } finally {
      busy = false;
      gradeButtons().forEach((b) => (b.disabled = false));
    }
  }

  els.show.addEventListener("click", reveal);
  els.grades.addEventListener("click", (e) => {
    const button = e.target.closest("button[data-g]");
    if (button) grade(button.dataset.g);
  });
  els.emptyAction.addEventListener("click", focusNotes);

  return {
    render,
    reveal,
    grade,
    // Keyboard shortcuts: Space or Enter shows the answer, 1 to 4 grades.
    onKey(e) {
      if (!current || busy) return false;
      if (!revealed && (e.key === " " || e.key === "Enter")) {
        reveal();
        return true;
      }
      const map = { "1": "again", "2": "hard", "3": "good", "4": "easy" };
      if (revealed && map[e.key]) {
        grade(map[e.key]);
        return true;
      }
      return false;
    },
  };
}
