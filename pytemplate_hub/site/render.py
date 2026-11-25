"""Render the hub's home page with Jinja2, from the packs the index lists.

Every value from an entry is untrusted text. It reaches the page only through Jinja2 with
autoescaping on, and no template uses the ``safe`` filter on entry data. The page's scripts only
show and hide what the page already holds; they never build HTML from strings.
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
STARTER_COUNT = 5

# The category tiles. Each id is a key of the hub's fixed vocabulary (categories.toml); a tile's
# count is the number of listed packs that declare that category.
TILES: tuple[dict[str, str], ...] = (
    {"id": "cli", "label": "Command-line apps", "glyph": "$ _", "example": "cli, script"},
    {"id": "library", "label": "Libraries", "glyph": "import", "example": "library"},
    {
        "id": "web",
        "label": "Web services and APIs",
        "glyph": "GET /",
        "example": "FastAPI, service-sql",
    },
    {
        "id": "worker",
        "label": "Background workers",
        "glyph": "retry()",
        "example": "worker, worker-redis",
    },
    {"id": "data", "label": "Data pipelines", "glyph": "csv → pq", "example": "etl, etl-polars"},
    {"id": "ai", "label": "AI tools and MCP", "glyph": "mcp", "example": "tools, tools-http"},
    {
        "id": "quant",
        "label": "Quant research",
        "glyph": "\u03b1 \u00b7 IC",
        "example": "quant-research, alpha-research",
    },
)

# Placeholder posts. Every one is a draft until the Posts phase (P3).
POSTS: tuple[dict[str, str], ...] = (
    {
        "kind": "Release",
        "title": "pytemplate-uv 3.3 finds packs on the hub",
        "summary": "The skill searches the hub, and inspection commands take the pins.",
    },
    {
        "kind": "Guide",
        "title": "Why every command carries a commit and a digest",
        "summary": "Pins make a generated project reproducible, and refusals make changes visible.",
    },
    {
        "kind": "Packs",
        "title": "Five starter packs to begin with",
        "summary": "Small, typed starting points for a script, a CLI, a library, and more.",
    },
)


@dataclass(frozen=True)
class Command:
    """The create command for one profile of a listed pack."""

    profile: str
    text: str


@dataclass(frozen=True)
class Card:
    """One listed pack, as the page shows it. All text is untrusted; the template escapes it."""

    name: str
    identifier: str
    description: str
    repository: str
    tag: str
    commit: str
    license: str
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


def render_index(cards: Sequence[Card], built_on: str) -> str:
    """Render the home page for the listed packs."""
    tiles: list[dict[str, Any]] = [
        {**tile, "count": sum(tile["id"] in card.categories for card in cards)} for tile in TILES
    ]
    template = _environment().get_template("index.html")
    return template.render(
        categories=tiles,
        posts=POSTS,
        cards=list(cards),
        starter_packs=list(cards[:STARTER_COUNT]),
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
