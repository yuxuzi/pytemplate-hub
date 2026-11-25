"""Render the hub's pages with Jinja2: the home page from the index, and the Learn pages.

Every value from an entry is untrusted text. It reaches the page only through Jinja2 with
autoescaping on, and no template uses the ``safe`` filter on entry data. The page's scripts only
show and hide what the page already holds; they never build HTML from strings. The page names no
pack, publisher, or consumer: every pack on it comes from the index. The Learn pages hold only the
hub's own Markdown, rendered by ``learn`` with raw HTML turned off.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pytemplate_hub.site.learn import LEARN_PATH, PAGES, PAGES_BY_SLUG, Page, render_page, root_of

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
NEWEST_COUNT = 5
HUB_URL = "https://github.com/yuxuzi/pytemplate-hub"
UV_URL = "https://github.com/yuxuzi/pytemplate-uv"
LINKS: dict[str, str] = {
    "contributing": f"{HUB_URL}/blob/main/CONTRIBUTING.md",
    "hub": HUB_URL,
    "whats_new": f"{UV_URL}/blob/main/CHANGELOG.md",
    "pytemplate_uv": UV_URL,
    "pytemplate_uv_issues": f"{UV_URL}/issues",
    "pypi": "https://pypi.org/project/pytemplate-uv/",
}
# Pages of this site, relative to its root; ``links`` prefixes them for the page that links.
SITE_LINKS: dict[str, str] = {
    "home": "index.html",
    "templates": "index.html#templates",
    "learn": f"{LEARN_PATH}index.html",
    "tutorial": f"{PAGES_BY_SLUG['tutorial'].path}index.html",
    "authors": f"{PAGES_BY_SLUG['publish'].path}index.html",
    "trust": f"{PAGES_BY_SLUG['trust'].path}index.html",
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


def links(root: str) -> dict[str, str]:
    """Return every link a page uses, with this site's pages relative to ``root``."""
    return {**LINKS, **{key: root + target for key, target in SITE_LINKS.items()}}


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
        links=links(""),
        root="",
        current="home",
        built_on=built_on,
    )


def _pages(root: str) -> list[dict[str, str]]:
    return [
        {
            "title": page.title,
            "summary": page.summary,
            "href": f"{root}{page.path}index.html",
            "slug": page.slug,
        }
        for page in PAGES
    ]


def render_learn_page(page: Page, built_on: str) -> str:
    """Render one Learn page, with the list of all pages and its own table of contents."""
    root = root_of(page.path)
    rendered = render_page(page)
    template = _environment().get_template("learn.html")
    return template.render(
        page=page,
        body=rendered.html,
        headings=rendered.headings,
        pages=_pages(root),
        links=links(root),
        root=root,
        current="publish" if page.slug == "publish" else "learn",
        built_on=built_on,
    )


def render_learn_index(built_on: str) -> str:
    """Render the Learn page that lists the tutorial and the guides."""
    root = root_of(LEARN_PATH)
    template = _environment().get_template("learn_index.html")
    return template.render(
        pages=_pages(root),
        links=links(root),
        root=root,
        current="learn",
        built_on=built_on,
    )


def _write(output: Path, path: str, html: str) -> None:
    target = output / path / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def write_site(cards: Sequence[Card], built_on: str, output: Path) -> Path:
    """Write the home page, the Learn pages, and the static files; return ``index.html``."""
    output.mkdir(parents=True, exist_ok=True)
    index = output / "index.html"
    index.write_text(render_index(cards, built_on), encoding="utf-8")
    _write(output, LEARN_PATH, render_learn_index(built_on))
    for page in PAGES:
        _write(output, page.path, render_learn_page(page, built_on))
    target = output / "static"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(STATIC_DIR, target)
    return index
