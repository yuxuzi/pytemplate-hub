// Pack filter: shows each listing whose search words contain every word typed, and only the
// reviewed ones while "Reviewed only" is checked. It sets the hidden attribute and text only;
// it never builds HTML from strings.

const search = document.getElementById("search");
const reviewed = document.getElementById("reviewed");
const count = document.getElementById("count");
const packs = [...document.querySelectorAll("article.pack")];

function filter() {
  if (!search || !reviewed) return;
  const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
  let shown = 0;
  for (const pack of packs) {
    const match = words.every((word) => (pack.dataset.search || "").includes(word))
      && (!reviewed.checked || pack.dataset.tier === "reviewed");
    pack.hidden = !match;
    if (match) shown += 1;
  }
  if (count) count.textContent = `Showing ${shown} of ${packs.length}`;
}

if (search && reviewed) {
  search.addEventListener("input", filter);
  reviewed.addEventListener("change", filter);
  filter();
}
