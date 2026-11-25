"""Render the hub's home page with Jinja2, from the packs the index lists.

Every value from an entry is untrusted text. It reaches the page only through Jinja2 with
autoescaping on, and no template uses the ``safe`` filter on entry data. The page's scripts only
show and hide what the page already holds; they never build HTML from strings. The page names no
pack, publisher, or consumer: every pack on it comes from the index.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
NEWEST_COUNT = 5
HUB_URL = "https://github.com/yuxuzi/pytemplate-hub"
UV_URL = "https://github.com/yuxuzi/pytemplate-uv"
LINKS: dict[str, str] = {
    "tutorial": f"{HUB_URL}/blob/main/docs/tutorial.md",
    "authors": f"{HUB_URL}/blob/main/docs/authors.md",
    "trust": f"{HUB_URL}/blob/main/docs/trust.md",
    "contributing": f"{HUB_URL}/blob/main/CONTRIBUTING.md",
    "hub": HUB_URL,
    "whats_new": f"{UV_URL}/blob/main/CHANGELOG.md",
    "pytemplate_uv": UV_URL,
    "pytemplate_uv_issues": f"{UV_URL}/issues",
    "pypi": "https://pypi.org/project/pytemplate-uv/",
}

# The category tiles. Each id is a key of the hub's fixed vocabulary (categories.toml); a tile's
# count is the number of listed packs that declare that category.
TILES: tuple[dict[str, str], ...] = (
    {"id": "cli", "label": "Command-line apps", "glyph": "$ _", "example": "cli, script"},
    {"id": "library", "label": "Libraries", "glyph": "import", "example": "library"},
    {
        "id": "web",
        "label": "Web services and APIs",
        "glyph": "GET /",
        "example": "FastAPI, service",
    },
    {"id": "worker", "label": "Background workers", "glyph": "retry()", "example": "worker"},
    {"id": "data", "label": "Data pipelines", "glyph": "csv → pq", "example": "etl"},
    {"id": "ai", "label": "AI tools and MCP", "glyph": "mcp", "example": "tools, MCP servers"},
    {"id": "quant", "label": "Quant research", "glyph": "\u03b1 \u00b7 IC", "example": "signals"},
)


@dataclass(frozen=True)
class Command:
    """The create commands for one profile of a listed pack.

    ``text`` is the short command (``-h``) the page shows first; ``pinned`` is the fully pinned
    command for CI and offline use.
    """

    profile: str
    text: str
    pinned: str


@dataclass(frozen=True)
class Card:
    """One listed pack, as the page shows it. All text is untrusted; the template escapes it."""

    name: str
    identifier: str
    description: str
    repository: str
    tag: str
    commit: str
    digest: str
    license: str
    checked_on: str | None
    tier: str
    tier_label: str
    facts: str
    categories: tuple[str, ...]
    search: str
    commands: tuple[Command, ...]


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def newest(cards: Sequence[Card]) -> list[Card]:
    """Return the most recently checked packs, newest first; packs with no date keep index order."""
    ordered = sorted(cards, key=lambda card: card.checked_on or "", reverse=True)
    return ordered[:NEWEST_COUNT]


def render_index(cards: Sequence[Card], built_on: str) -> str:
    """Render the home page for the listed packs."""
    tiles: list[dict[str, Any]] = [
        {**tile, "count": sum(tile["id"] in card.categories for card in cards)} for tile in TILES
    ]
    template = _environment().get_template("index.html")
    return template.render(
        categories=tiles,
        cards=list(cards),
        featured=cards[0] if cards else None,
        newest_packs=newest(cards),
        links=LINKS,
        built_on=built_on,
    )


def write_site(cards: Sequence[Card], built_on: str, output: Path) -> Path:
    """Write ``index.html`` and copy the static files into ``output``; return ``index.html``."""
    output.mkdir(parents=True, exist_ok=True)
    index = output / "index.html"
    index.write_text(render_index(cards, built_on), encoding="utf-8")
    target = output / "static"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(STATIC_DIR, target)
    return index
