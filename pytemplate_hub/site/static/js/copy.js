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

export async function copyText(text, what, fallbackElement) {
  try {
    await navigator.clipboard.writeText(text);
    announce(`${what} copied`);
  } catch {
    if (fallbackElement) selectElement(fallbackElement);
    announce("Copying is blocked here. The text is selected: press Ctrl+C or ⌘C.");
  }
}

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  copyText(button.dataset.copy ?? "", button.dataset.what || "Text", button.previousElementSibling);
});
