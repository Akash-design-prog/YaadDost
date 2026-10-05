// The light/dark switch. theme-init.js has already set data-theme on <html>; this wires the button and remembers the choice.
const KEY = "yaaddost.theme";

export function createTheme({ button, storage = null }) {
  const root = document.documentElement;
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const isDark = () => root.dataset.theme === "dark";

  const saved = () => {
    try {
      const v = storage && storage.getItem(KEY);
      return v === "dark" || v === "light" ? v : null;
    } catch {
      return null;
    }
  };

  function paint() {
    button.setAttribute("aria-pressed", String(isDark()));
    const meta = document.querySelector('meta[name="theme-color"]');   // tints the phone's browser bar to match
    if (meta) meta.setAttribute("content", getComputedStyle(root).getPropertyValue("--canvas").trim());
  }

  button.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    root.dataset.theme = next;
    try {
      if (storage) storage.setItem(KEY, next);
    } catch { /* blocked: the choice lasts for this visit only */ }
    paint();
  });

  // With no saved choice, follow the system if it changes while the page is open.
  media.addEventListener("change", (e) => {
    if (saved() === null) {
      root.dataset.theme = e.matches ? "dark" : "light";
      paint();
    }
  });

  paint();
  return { isDark };
}
