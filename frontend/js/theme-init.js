// Runs before the page paints (loaded in <head>) so the right theme is there from the first frame, with no flash.
// A saved choice wins; otherwise the system setting decides. Kept tiny and dependency-free on purpose.
(function () {
  var saved = null;
  try { saved = window.localStorage.getItem("yaaddost.theme"); } catch (e) { /* storage blocked: use the system setting */ }
  var dark = saved === "dark" || saved === "light"
    ? saved === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
})();
