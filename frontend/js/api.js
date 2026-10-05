// Every call to the backend goes through here.
async function request(path, body) {
  const init = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined;
  let r;
  try {
    r = await fetch(path, init);
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `The server had a problem (${r.status}). Try again in a moment.`);
  return data;
}

export const getStatus = () => request("/api/status");
export const makeCards = (notes, language, count) => request("/api/cards", { notes, language, count });
export const explain = (concept, notes, language) => request("/api/explain", { concept, notes, language });
export const reviewCard = (card, grade) =>
  request("/api/review", { ease: card.ease, interval: card.interval, reps: card.reps, grade });
