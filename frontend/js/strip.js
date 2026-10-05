// The forgetting-curve strip: one dot per card on the day it is due. DOM only; the maths lives in schedule.js.
import { bucketByDay, describeSchedule, LATER } from "./schedule.js";

const MAX_STACK = 8;

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function createStrip(track) {
  function column(ids, index, currentId) {
    const col = make("div", `curve-col${index === 0 ? " is-today" : ""}${index === LATER ? " is-later" : ""}`);
    col.style.gridColumn = String(index + 1);   // set from script, so the strict CSP is not involved
    for (const id of ids.slice(0, MAX_STACK)) {
      const dot = make("span", `dot${id === currentId ? " is-current" : ""}`);
      dot.dataset.id = id;
      col.append(dot);
    }
    if (ids.length > MAX_STACK) col.append(make("span", "dot-more", `+${ids.length - MAX_STACK}`));
    return col;
  }

  return {
    render(cards, now, currentId = null) {
      const buckets = bucketByDay(cards, now);
      track.setAttribute("aria-label", describeSchedule(buckets));
      track.replaceChildren(...buckets.map((ids, i) => column(ids, i, currentId)));
    },
    // Where a card's dot is right now (null if it is hidden inside a "+n" stack).
    rectOf(id) {
      const dot = track.querySelector(`.dot[data-id="${CSS.escape(id)}"]`);
      return dot ? dot.getBoundingClientRect() : null;
    },
    // Make the dot hop from where it was to where it is now.
    hop(id, from, reducedMotion) {
      const dot = track.querySelector(`.dot[data-id="${CSS.escape(id)}"]`);
      if (!dot || !from) return;
      const to = dot.getBoundingClientRect();
      const dx = from.left - to.left;
      const dy = from.top - to.top;
      if (reducedMotion) {
        dot.animate([{ opacity: 0.2 }, { opacity: 1 }], { duration: 200, easing: "linear" });
        return;
      }
      dot.animate(
        [
          { transform: `translate(${dx}px, ${dy}px)` },
          { transform: `translate(${dx * 0.5}px, ${Math.min(dy, 0) - 22}px)`, offset: 0.5 },
          { transform: "translate(0, 0)" },
        ],
        { duration: 520, easing: "cubic-bezier(0.23, 1, 0.32, 1)" }
      );
    },
  };
}
