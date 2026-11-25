"""Render the hub's pages with Jinja2: home, the catalog, a page per pack, and the Learn pages.

Every value from an entry is untrusted text. It reaches the page only through Jinja2 with
autoescaping on, and no template uses the ``safe`` filter on entry data. The page's scripts only
show, hide, reorder, and count what the page already holds, and set text; they never build HTML
from strings. The pages name no pack, publisher, or consumer: every pack on them comes from the
index. The Learn pages hold only the hub's own Markdown, rendered by ``learn`` with raw HTML off.
"""

from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pytemplate_hub.schema import CATEGORIES
from pytemplate_hub.site.learn import LEARN_PATH, PAGES, PAGES_BY_SLUG, Page, render_page, root_of

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
NEWEST_COUNT = 5
CATALOG_PATH = "templates/"
HUB_URL = "https://github.com/yuxuzi/pytemplate-hub"
UV_URL = "https://github.com/yuxuzi/pytemplate-uv"
LINKS: dict[str, str] = {
    "contributing": f"{HUB_URL}/blob/main/CONTRIBUTING.md",
    "hub": HUB_URL,
    "request": f"{HUB_URL}/issues/new?title=Template%20request%3A%20",
    "whats_new": f"{UV_URL}/blob/main/CHANGELOG.md",
    "pytemplate_uv": UV_URL,
    "pytemplate_uv_issues": f"{UV_URL}/issues",
    "pypi": "https://pypi.org/project/pytemplate-uv/",
}
# Pages of this site, relative to its root; ``links`` prefixes them for the page that links.
SITE_LINKS: dict[str, str] = {
    "home": "index.html",
    "templates": f"{CATALOG_PATH}index.html",
    "learn": f"{LEARN_PATH}index.html",
    "tutorial": f"{PAGES_BY_SLUG['tutorial'].path}index.html",
    "authors": f"{PAGES_BY_SLUG['publish'].path}index.html",
    "trust": f"{PAGES_BY_SLUG['trust'].path}index.html",
}
KIND_LABELS: dict[str, str] = {
    "cli": "Command-line app",
    "library": "Library",
    "service": "Service",
}
# Example searches offered under the catalog's search box.
SEARCH_HINTS: tuple[str, ...] = ("rest api", "etl", "agent tools", "backtest", "postgres", "worker")

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
class Profile:
    """One profile of a pack's latest version, with the details its ``profile.toml`` gives."""

    id: str
    name: str
    description: str
    kind: str | None
    kind_label: str | None
    python: tuple[str, ...]
    stack: tuple[str, ...]
    lifecycle: str
    security_posture: str | None
    command: Command


@dataclass(frozen=True)
class VersionRow:
    """One listed version, for a pack page's version table."""

    tag: str
    commit: str
    checked_on: str | None
    checked_with: str
    license: str
    tier_label: str
    yanked: str | None


@dataclass(frozen=True)
class Card:
    """One listed pack, as the pages show it. All text is untrusted; the templates escape it.

    ``search_*`` hold the words the catalog's script matches, by weight: name, id, tags (categories,
    keywords, stack, and profile ids, names, and kinds), and descriptions. ``recommended`` is the
    published ranking score.
    """

    name: str
    identifier: str
    owner: str
    pack_id: str
    path: str
    description: str
    repository: str
    tag: str
    commit: str
    digest: str
    license: str
    checked_on: str | None
    checked_with: str
    tier: str
    tier_label: str
    facts: str
    categories: tuple[str, ...]
    keywords: tuple[str, ...]
    stack: tuple[str, ...]
    kinds: tuple[str, ...]
    python: tuple[str, ...]
    stars: int | None
    recommended: float
    search: str
    search_name: str
    search_id: str
    search_tags: str
    search_text: str
    commands: tuple[Command, ...]
    profiles: tuple[Profile, ...]
    versions: tuple[VersionRow, ...]

    @property
    def category_labels(self) -> tuple[str, ...]:
        """The labels of the pack's categories."""
        return tuple(CATEGORIES.get(category, category) for category in self.categories)


@dataclass(frozen=True)
class Option:
    """One value of a catalog filter, and how many listed packs have it."""

    value: str
    label: str
    count: int


@dataclass(frozen=True)
class Facet:
    """One catalog filter: its key in the page's address, its title, and its values."""

    key: str
    title: str
    options: tuple[Option, ...]


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


def _options(
    values: Iterable[tuple[str, str]], cards: Sequence[Card], key: str
) -> tuple[Option, ...]:
    counts: Counter[str] = Counter()
    for card in cards:
        counts.update(set(_facet_values(card, key)))
    return tuple(Option(value, label, counts[value]) for value, label in values if counts[value])


def _facet_values(card: Card, key: str) -> tuple[str, ...]:
    return {
        "category": card.categories,
        "kind": card.kinds,
        "stack": card.stack,
        "license": (card.license,),
    }[key]


def facets(cards: Sequence[Card]) -> tuple[Facet, ...]:
    """Return the catalog's filters; a value no listed pack has is left out."""
    stacks = sorted({item for card in cards for item in card.stack}, key=str.lower)
    licenses = sorted({card.license for card in cards})
    groups = (
        Facet("category", "Category", _options(CATEGORIES.items(), cards, "category")),
        Facet("kind", "Kind", _options(KIND_LABELS.items(), cards, "kind")),
        Facet("stack", "Stack", _options(((s, s) for s in stacks), cards, "stack")),
        Facet("license", "License", _options(((x, x) for x in licenses), cards, "license")),
    )
    return tuple(group for group in groups if group.options)


def python_versions(cards: Sequence[Card]) -> list[str]:
    """Return every Python version a listed profile supports, oldest first."""
    found = {version for card in cards for version in card.python}
    return sorted(found, key=lambda version: tuple(int(part) for part in version.split(".")))


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
        profile_count=sum(len(card.profiles) for card in cards),
        links=links(""),
        root="",
        current="home",
        built_on=built_on,
    )


def render_catalog(cards: Sequence[Card], built_on: str) -> str:
    """Render the catalog: every listed pack, with search, filters, and sorting."""
    root = root_of(CATALOG_PATH)
    ordered = sorted(cards, key=lambda card: (-card.recommended, card.name.lower()))
    template = _environment().get_template("catalog.html")
    return template.render(
        cards=ordered,
        facets=facets(cards),
        python=python_versions(cards),
        reviewed=sum(card.tier == "reviewed" for card in cards),
        hints=SEARCH_HINTS,
        profile_count=sum(len(card.profiles) for card in cards),
        links=links(root),
        root=root,
        current="templates",
        built_on=built_on,
    )


def render_pack(card: Card, cards: Sequence[Card], built_on: str) -> str:
    """Render one pack's page: its profiles, the command builder, checks, and versions."""
    root = root_of(card.path)
    similar = [
        other
        for other in cards
        if other.identifier != card.identifier and set(other.categories) & set(card.categories)
    ]
    template = _environment().get_template("pack.html")
    return template.render(
        card=card,
        similar=similar[:4],
        links=links(root),
        root=root,
        current="templates",
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
    """Write every page and the static files into ``output``; return ``index.html``."""
    output.mkdir(parents=True, exist_ok=True)
    index = output / "index.html"
    index.write_text(render_index(cards, built_on), encoding="utf-8")
    _write(output, CATALOG_PATH, render_catalog(cards, built_on))
    for card in cards:
        _write(output, card.path, render_pack(card, cards, built_on))
    _write(output, LEARN_PATH, render_learn_index(built_on))
    for page in PAGES:
        _write(output, page.path, render_learn_page(page, built_on))
    target = output / "static"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(STATIC_DIR, target)
    return index
