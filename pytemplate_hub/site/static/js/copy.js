// Copy buttons: a button with data-copy puts that text on the clipboard and confirms in the toast.
// If the clipboard is blocked, the text next to the button is selected so the reader can copy it.
// Toast text is set with textContent only; nothing here builds HTML from strings.

const toast = document.getElementById("toast");
let toastTimer = 0;

function announce(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function selectElement(element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

export async function copyText(text, what, fallbackElement, button) {
  try {
    await navigator.clipboard.writeText(text);
    announce(`${what} copied`);
    if (button) {
      button.classList.add("copied");
      clearTimeout(Number(button.dataset.copiedTimer || 0));
      button.dataset.copiedTimer = String(setTimeout(() => button.classList.remove("copied"), 1400));
    }
  } catch {
    if (fallbackElement) selectElement(fallbackElement);
    announce("Copying is blocked here. The text is selected: press Ctrl+C or ⌘C.");
  }
}

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  copyText(button.dataset.copy ?? "", button.dataset.what || "Text", button.previousElementSibling, button);
});

const themeBtn = document.getElementById("theme");
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "dark" || theme === "light") root.dataset.theme = theme;
  else delete root.dataset.theme;
  const isDark = theme ? theme === "dark" : darkQuery.matches;
  if (themeBtn) {
    themeBtn.setAttribute("aria-pressed", String(isDark));
    themeBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    const moon = themeBtn.querySelector(".icon-moon");
    const sun = themeBtn.querySelector(".icon-sun");
    if (moon) moon.hidden = isDark;
    if (sun) sun.hidden = !isDark;
  }
}

let savedTheme = null;
try { savedTheme = localStorage.getItem("pytemplate-theme"); } catch {}
applyTheme(savedTheme);
darkQuery.addEventListener("change", () => {
  if (!document.documentElement.dataset.theme) applyTheme(null);
});
if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const current = document.documentElement.dataset.theme;
    const isDark = current ? current === "dark" : darkQuery.matches;
    const next = isDark ? "light" : "dark";
    try { localStorage.setItem("pytemplate-theme", next); } catch {}
    applyTheme(next);
  });
}
