// The catalog: search, filters, counts, and sorting over the rows the page already holds.
// It shows, hides, and reorders those rows and sets text only; it never builds HTML from strings.
// The address keeps the state (?q=…&category=…&sort=…), so a filtered view can be shared.

const $ = (id) => document.getElementById(id);
const list = $("list");
const rows = [...document.querySelectorAll("[data-pack]")];
const boxes = [...document.querySelectorAll("input[data-facet]")];
const FACETS = ["category", "kind", "stack", "license"];
const SPLIT = { category: " ", kind: " ", stack: "|", license: "\u0000" };

// A small, tested vocabulary: a query word also matches these words.
const SYNONYMS = {
  rest: ["web", "fastapi"], api: ["web", "fastapi"], http: ["web", "fastapi"], endpoint: ["web"],
  server: ["web", "service"], etl: ["data", "duckdb", "polars"], pipeline: ["data"],
  dataframe: ["data", "polars"], csv: ["data"], parquet: ["data"], queue: ["worker", "redis"],
  job: ["worker"], jobs: ["worker"], celery: ["worker"], background: ["worker"], task: ["worker"],
  agent: ["ai", "mcp"], agents: ["ai", "mcp"], llm: ["ai", "mcp"], claude: ["ai", "mcp"],
  backtest: ["quant"], alpha: ["quant"], risk: ["quant"], trading: ["quant"], finance: ["quant"],
  portfolio: ["quant"], factor: ["quant"], db: ["sqlalchemy", "sql"], database: ["sqlalchemy", "sql"],
  sql: ["sqlalchemy"], postgres: ["sqlalchemy", "sql"], sqlite: ["sqlalchemy", "sql"],
  command: ["cli"], terminal: ["cli"], console: ["cli"], package: ["library"], pypi: ["library"],
  lib: ["library"],
};

const words = (text) => (text || "").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);

function withinOne(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  if (a.length === b.length) {
    const diff = [];
    for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) diff.push(i);
    return diff.length <= 1
      || (diff.length === 2 && diff[1] === diff[0] + 1 && a[diff[0]] === b[diff[1]] && a[diff[1]] === b[diff[0]]);
  }
  let [long, short] = a.length > b.length ? [a, b] : [b, a];
  let i = 0, j = 0, misses = 0;
  while (i < long.length && j < short.length) {
    if (long[i] === short[j]) { i += 1; j += 1; } else { misses += 1; if (misses > 1) return false; i += 1; }
  }
  return true;
}

function wordScore(query, word) {
  if (query === word) return 1;
  if (query.length >= 2 && word.startsWith(query)) return 0.8;
  if (query.length >= 5 && word.length >= 4 && withinOne(query, word)) return 0.6;
  return 0;
}

function fieldScore(query, fields) {
  let best = 0;
  for (const [weight, list] of fields) for (const word of list) best = Math.max(best, weight * wordScore(query, word));
  return best;
}

function queryScore(query, fields) {
  let score = fieldScore(query, fields);
  for (const synonym of SYNONYMS[query] || []) score = Math.max(score, 0.8 * fieldScore(synonym, fields));
  return score;
}

const packs = rows.map((row) => ({
  row,
  title: row.dataset.title,
  rec: Number(row.dataset.rec) || 0,
  stars: Number(row.dataset.stars) || 0,
  checked: row.dataset.checked || "",
  tier: row.dataset.tier,
  python: (row.dataset.python || "").split(" ").filter(Boolean),
  values: Object.fromEntries(FACETS.map((key) => [key, (row.dataset[key] || "").split(SPLIT[key]).filter(Boolean)])),
  fields: [[5, words(row.dataset.name)], [4, words(row.dataset.id)], [3, words(row.dataset.tags)], [1, words(row.dataset.text)]],
  chips: [...row.querySelectorAll("[data-profile]")].map((chip) => ({ chip, fields: [[3, words(chip.dataset.words)]] })),
  copy: row.querySelector("[data-row-copy]"),
  copyLabel: row.querySelector("[data-row-copy-label]"),
  titleLink: row.querySelector(".row-title"),
  detailsLink: row.querySelector(".side-actions a"),
}));
for (const pack of packs) {
  pack.defaultCommand = pack.copy ? pack.copy.dataset.copy : "";
  pack.defaultLabel = pack.copyLabel ? pack.copyLabel.textContent : "";
  pack.baseHref = pack.titleLink ? pack.titleLink.getAttribute("href") : "";
}

const state = { q: "", sort: "recommended", reviewed: false, python: "", picked: Object.fromEntries(FACETS.map((k) => [k, new Set()])) };

function readAddress() {
  const params = new URLSearchParams(location.search);
  state.q = params.get("q") || "";
  state.sort = params.get("sort") || "recommended";
  state.reviewed = params.get("reviewed") === "1";
  state.python = params.get("python") || "";
  for (const key of FACETS) state.picked[key] = new Set(params.getAll(key));
  $("q").value = state.q;
  $("sort").value = [...$("sort").options].some((o) => o.value === state.sort) ? state.sort : "recommended";
  state.sort = $("sort").value;
  $("f-reviewed").checked = state.reviewed;
  if ($("f-python")) $("f-python").value = state.python;
  for (const box of boxes) box.checked = state.picked[box.dataset.facet].has(box.value);
}

function writeAddress() {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  for (const key of FACETS) for (const value of state.picked[key]) params.append(key, value);
  if (state.reviewed) params.set("reviewed", "1");
  if (state.python) params.set("python", state.python);
  if (state.sort !== "recommended") params.set("sort", state.sort);
  const query = params.toString();
  history.replaceState(null, "", query ? `?${query}` : location.pathname);
}

function passes(pack, except) {
  for (const key of FACETS) {
    if (key === except) continue;
    const picked = state.picked[key];
    if (picked.size && !pack.values[key].some((value) => picked.has(value))) return false;
  }
  if (except !== "reviewed" && state.reviewed && pack.tier !== "reviewed") return false;
  if (except !== "python" && state.python && !pack.python.includes(state.python)) return false;
  return true;
}

function search() {
  const tokens = words(state.q);
  for (const pack of packs) {
    if (!tokens.length) { pack.score = 0; pack.all = true; pack.hit = null; continue; }
    const each = tokens.map((token) => queryScore(token, pack.fields));
    pack.score = each.reduce((a, b) => a + b, 0);
    pack.all = each.every((score) => score > 0);
    let best = 0;
    pack.hit = null;
    for (const { chip, fields } of pack.chips) {
      const score = tokens.reduce((sum, token) => sum + queryScore(token, fields), 0);
      if (score > best) { best = score; pack.hit = chip; }
    }
  }
  let matched = packs.filter((pack) => pack.all);
  let partial = false;
  if (tokens.length && !matched.length) {
    matched = packs.filter((pack) => pack.score > 0);
    partial = matched.length > 0;
  }
  return { tokens, matched, partial };
}

function render() {
  const { tokens, matched, partial } = search();
  for (const box of boxes) {
    const count = matched.filter((pack) => passes(pack, box.dataset.facet) && pack.values[box.dataset.facet].includes(box.value)).length;
    box.parentElement.querySelector("[data-count]").textContent = String(count);
    box.parentElement.classList.toggle("zero", count === 0);
  }
  $("n-reviewed").textContent = String(matched.filter((pack) => passes(pack, "reviewed") && pack.tier === "reviewed").length);

  const shown = matched.filter((pack) => passes(pack));
  const best = Math.max(1e-9, ...shown.map((pack) => pack.score));
  const byName = (a, b) => a.title.localeCompare(b.title);
  const order = {
    recommended: (a, b) => (tokens.length
      ? (b.score / best) * (0.7 + 0.3 * b.rec) - (a.score / best) * (0.7 + 0.3 * a.rec)
      : b.rec - a.rec) || byName(a, b),
    stars: (a, b) => b.stars - a.stars || byName(a, b),
    recent: (a, b) => b.checked.localeCompare(a.checked) || byName(a, b),
    name: byName,
  };
  shown.sort(order[state.sort]);
  const visible = new Set(shown);
  for (const pack of packs) {
    pack.row.hidden = !visible.has(pack);
    for (const { chip } of pack.chips) chip.classList.toggle("hit", chip === pack.hit);
    if (pack.copy) {
      const chip = pack.hit;
      pack.copy.dataset.copy = chip ? chip.dataset.command : pack.defaultCommand;
      pack.copyLabel.textContent = chip ? `Copy ${chip.dataset.profile}` : pack.defaultLabel;
    }
    if (pack.baseHref) {
      const href = pack.hit ? `${pack.baseHref}?profile=${encodeURIComponent(pack.hit.dataset.profile)}` : pack.baseHref;
      if (pack.titleLink) pack.titleLink.setAttribute("href", href);
      if (pack.detailsLink) pack.detailsLink.setAttribute("href", href);
    }
  }
  for (const pack of shown) list.append(pack.row);

  const profiles = shown.reduce((sum, pack) => sum + pack.chips.length, 0);
  $("count").textContent = `${shown.length} of ${packs.length} packs · ${profiles} profiles`
    + (partial ? " · no pack matches every word, so partial matches are shown" : "");
  const expanded = tokens.filter((token) => SYNONYMS[token]).map((token) => `${token} → ${SYNONYMS[token].join(", ")}`);
  $("expand").textContent = expanded.length ? `Also matched: ${expanded.join("; ")}` : "";
  $("empty").hidden = shown.length > 0;

  const active = FACETS.reduce((n, key) => n + state.picked[key].size, 0) + (state.reviewed ? 1 : 0) + (state.python ? 1 : 0);
  $("clear").hidden = active === 0;
  if ($("clear-inline")) $("clear-inline").hidden = active === 0;
  $("filter-toggle").textContent = active ? `Filters (${active})` : "Filters";
  writeAddress();
}

function clearFilters() {
  for (const key of FACETS) state.picked[key].clear();
  state.reviewed = false;
  state.python = "";
  for (const box of boxes) box.checked = false;
  $("f-reviewed").checked = false;
  if ($("f-python")) $("f-python").value = "";
}

if (list) {
  readAddress();
  $("q").addEventListener("input", (event) => { state.q = event.target.value; render(); });
  $("q").form.addEventListener("submit", (event) => { event.preventDefault(); render(); });
  $("sort").addEventListener("change", (event) => { state.sort = event.target.value; render(); });
  $("f-reviewed").addEventListener("change", (event) => { state.reviewed = event.target.checked; render(); });
  if ($("f-python")) $("f-python").addEventListener("change", (event) => { state.python = event.target.value; render(); });
  for (const box of boxes) {
    box.addEventListener("change", () => {
      const picked = state.picked[box.dataset.facet];
      if (box.checked) picked.add(box.value); else picked.delete(box.value);
      render();
    });
  }
  $("clear").addEventListener("click", () => { clearFilters(); render(); });
  if ($("clear-inline")) $("clear-inline").addEventListener("click", () => { clearFilters(); render(); });
  $("reset").addEventListener("click", () => { clearFilters(); state.q = ""; $("q").value = ""; render(); $("q").focus(); });
  for (const hint of document.querySelectorAll("[data-hint]")) {
    hint.addEventListener("click", () => { state.q = hint.dataset.hint; $("q").value = state.q; render(); $("q").focus(); });
  }
  $("filter-toggle").addEventListener("click", (event) => {
    const open = $("facets").classList.toggle("open");
    event.currentTarget.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
      const tag = event.target instanceof Element ? event.target.tagName : "";
      if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        event.preventDefault();
        $("q").focus();
        $("q").select();
      }
    } else if (event.key === "Escape" && document.activeElement === $("q") && $("q").value) {
      state.q = "";
      $("q").value = "";
      render();
    }
  });
  render();
}
