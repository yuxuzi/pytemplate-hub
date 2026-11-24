"""Build the static site from the index: one searchable page and a JSON copy of the data.

Everything from an entry is untrusted text: the page escapes it, and its script never builds HTML.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from html import escape
from pathlib import Path
from typing import Any

from pytemplate_hub.schema import Entry, Version, load_entry
from pytemplate_hub.verify import entry_files

STARS_TIMEOUT_SECONDS = 15.0
StarSource = Callable[[Entry], int | None]

_STYLE = """
:root { color-scheme: light dark; --bg: #f7f7f5; --card: #fff; --text: #1d1d1b; --muted: #5f5f5a;
  --line: #deded8; --accent: #1f5f8b; --code: #f0f0ec; --reviewed: #1b6e43; }
@media (prefers-color-scheme: dark) { :root { --bg: #171716; --card: #21211f; --text: #ecece8;
  --muted: #a8a8a1; --line: #3a3a36; --accent: #7db8e0; --code: #2b2b28; --reviewed: #6fcf9f; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 860px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { margin: 0 0 8px; font-size: 1.75rem; }
h2 { margin: 0; font-size: 1.15rem; overflow-wrap: anywhere; }
a { color: var(--accent); }
.note { color: var(--muted); margin: 0 0 8px; }
.controls { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: center;
  margin: 24px 0 8px; }
input[type="search"] { flex: 1 1 240px; min-width: 0; padding: 8px 10px; font: inherit;
  color: inherit; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
article { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 16px; margin-top: 12px; }
article[hidden] { display: none; }
.head { display: flex; flex-wrap: wrap; gap: 8px; justify-content: space-between; }
.tier { font-size: .8rem; color: var(--muted); border: 1px solid var(--line); border-radius: 999px;
  padding: 1px 10px; align-self: center; }
.tier.reviewed { color: var(--reviewed); border-color: currentColor; }
.id, .facts { color: var(--muted); font-size: .9rem; margin: 0; overflow-wrap: anywhere; }
.description { margin: 8px 0; overflow-wrap: anywhere; }
pre { background: var(--code); border-radius: 6px; padding: 8px 10px; margin: 8px 0 0;
  white-space: pre-wrap; overflow-wrap: anywhere; font-size: .85rem; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.links { margin: 8px 0 0; font-size: .9rem; }
"""

_SCRIPT = """
const search = document.getElementById("search");
const reviewed = document.getElementById("reviewed");
const count = document.getElementById("count");
const packs = [...document.querySelectorAll("article")];
function filter() {
  const words = search.value.toLowerCase().split(/\\s+/).filter(Boolean);
  let shown = 0;
  for (const pack of packs) {
    const match = words.every((word) => pack.dataset.search.includes(word))
      && (!reviewed.checked || pack.dataset.tier === "reviewed");
    pack.hidden = !match;
    if (match) shown += 1;
  }
  count.textContent = `Showing ${shown} of ${packs.length}`;
}
search.addEventListener("input", filter);
reviewed.addEventListener("change", filter);
filter();
"""


def github_stars(entry: Entry) -> int | None:
    """Return the source repository's star count, or ``None`` if GitHub cannot say."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{entry.owner}/{entry.repository_name}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "pytemplate-hub"},
    )
    try:
        with urllib.request.urlopen(request, timeout=STARS_TIMEOUT_SECONDS) as response:
            stars = json.load(response).get("stargazers_count")
    except (OSError, ValueError, AttributeError):
        return None
    return stars if isinstance(stars, int) else None


def no_stars(_: Entry) -> None:
    """Report no star counts, for building without network access."""


def create_command(entry: Entry, version: Version, profile: str) -> str:
    """Return the command that creates a project from ``profile`` at the listed tag.

    The commit and digest make pytemplate-uv (3.1 or later) refuse the pack if the tag moved or
    its files changed since the hub checked it. ``-y`` (3.2 or later; ``@latest`` guarantees it)
    accepts the defaults without prompting.
    """
    source = f"gh:{entry.owner}/{entry.repository_name}"
    return (
        f"uvx pytemplate-uv@latest create my-project -p {profile} "
        f"--template {source} --template-ref {version.tag} "
        f"--template-commit {version.commit} --template-digest {version.digest} -y"
    )


def build_site(index: Path, output: Path, *, stars: StarSource, built_on: str) -> int:
    """Write ``index.html`` and ``index.json`` to ``output``; return how many packs are shown."""
    data: list[dict[str, Any]] = []
    cards: list[str] = []
    for path in entry_files(index):
        entry = load_entry(path)
        pack = _pack_data(path.stem, entry, stars(entry))
        data.append(pack)
        if entry.latest is not None:
            cards.append(_card(entry, pack))
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(_page(cards, built_on), encoding="utf-8")
    payload = {"format": 1, "built_on": built_on, "packs": data}
    (output / "index.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(cards)


def _pack_data(pack_id: str, entry: Entry, stars: int | None) -> dict[str, Any]:
    latest = entry.latest
    return {
        "id": pack_id,
        "owner": entry.owner,
        "repository": entry.repository,
        "name": entry.name,
        "description": entry.description,
        "stars": stars,
        "latest": latest.tag if latest else None,
        "versions": [
            {**version.model_dump(mode="json"), "tier": version.tier} for version in entry.versions
        ],
    }


def _card(entry: Entry, pack: dict[str, Any]) -> str:
    latest = entry.latest
    assert latest is not None  # only packs with an active version get a card
    title = entry.name or pack["id"]
    identifier = f"{entry.owner}/{pack['id']}"
    profiles = " ".join(profile.id for profile in latest.profiles)
    words = f"{title} {identifier} {entry.description} {latest.license} {profiles}".lower()
    commands = "".join(
        f"<pre><code>{escape(create_command(entry, latest, profile.id))}</code></pre>"
        for profile in latest.profiles
    )
    checks = ", ".join(f"{p.id}: lifecycle {p.lifecycle}" for p in latest.profiles)
    star_text = "stars unavailable" if pack["stars"] is None else f"{pack['stars']} stars"
    tier = "Listed" if latest.tier == "listed" else f"Reviewed by {latest.reviewed_by}"
    facts = (
        f"{latest.tag} · {latest.license} · {star_text} · commit {latest.commit[:12]} · {checks} · "
        f"{latest.checked_with}"
    )
    return f"""<article data-search="{escape(words)}" data-tier="{latest.tier}">
<div class="head"><h2>{escape(title)}</h2>
<span class="tier {latest.tier}">{escape(tier)}</span></div>
<p class="id">{escape(identifier)}</p>
<p class="description">{escape(entry.description)}</p>
<p class="facts" title="{latest.commit}">{escape(facts)}</p>
{commands}
<p class="links"><a href="{escape(entry.repository)}" rel="noopener nofollow">Source</a> ·
<a href="{escape(entry.repository)}/issues" rel="noopener nofollow">Comments and issues</a></p>
</article>"""


def _page(cards: list[str], built_on: str) -> str:
    body = "\n".join(cards) or "<p>No packs are listed yet.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pytemplate Hub</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
<h1>Pytemplate Hub</h1>
<p class="note">An index of pytemplate-uv template packs. Authors keep their packs in their own
repositories; this page records what was checked, at which commit.</p>
<p class="note"><strong>Listed does not mean safe.</strong> Listed packs passed automated checks.
Reviewed packs were read by the named maintainer at that commit. Generated projects run code when
you use them, so read a pack first. Details as of {escape(built_on)}.</p>
<div class="controls">
<input id="search" type="search" placeholder="Search packs" aria-label="Search packs">
<label><input id="reviewed" type="checkbox"> Reviewed only</label>
<span id="count" class="note" role="status"></span>
</div>
{body}
</main>
<script>{_SCRIPT}</script>
</body>
</html>
"""
