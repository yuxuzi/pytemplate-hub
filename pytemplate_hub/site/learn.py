"""The site's Learn pages: the tutorial and the guides, rendered from Markdown in ``learn/``.

These pages are the project's user documentation. The repositories keep only a README that links
here, so a guide changes in one place. The Markdown is the hub's own text and never holds entry
data; it renders with raw HTML turned off, so HTML written in a source shows as text.

A link to another page is written as its source file, such as ``publish.md#2-tag-a-release``, and
becomes a relative link to that page; a link to an unknown page fails the build.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markupsafe import Markup, escape

from pytemplate_hub.errors import SiteError

SOURCE_DIR = Path(__file__).resolve().parent / "learn"
SITE_URL = "https://yuxuzi.github.io/pytemplate-hub/"
HUB_URL = "https://github.com/yuxuzi/pytemplate-hub"
LEARN_PATH = "learn/"
_PAGE_LINK = re.compile(r"^([a-z0-9-]+)\.md(#[a-z0-9-]*)?$")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:")
_COPY_LANGUAGES = frozenset({"bash", "sh", "shell"})


@dataclass(frozen=True)
class Page:
    """One Learn page: its source ``learn/<slug>.md`` and the directory it is published in."""

    slug: str
    path: str
    title: str
    summary: str

    @property
    def source(self) -> Path:
        """The page's Markdown source."""
        return SOURCE_DIR / f"{self.slug}.md"

    @property
    def url(self) -> str:
        """The page's public address."""
        return SITE_URL + self.path

    @property
    def edit_url(self) -> str:
        """The page's source on GitHub."""
        return f"{HUB_URL}/blob/main/pytemplate_hub/site/learn/{self.slug}.md"


PAGES: tuple[Page, ...] = (
    Page(
        "tutorial",
        "learn/tutorial/",
        "Tutorial",
        "From your first generated project to a pack of your own, listed on the hub.",
    ),
    Page(
        "guide",
        "learn/guide/",
        "Using pytemplate-uv",
        "Every command and option: create, plan, request files, status, agents, and Python.",
    ),
    Page(
        "packs",
        "learn/packs/",
        "Template packs",
        "Use a pack from the hub, write your own, and pin it to a commit and digest.",
    ),
    Page(
        "publish",
        "publish/",
        "Publish a pack",
        "List your pack on the hub: requirements, the entry, the pull request, and CI.",
    ),
    Page(
        "trust",
        "learn/trust/",
        "What the checks mean",
        "What listing, review, and lifecycle results prove, and what they do not.",
    ),
    Page(
        "compatibility",
        "learn/compatibility/",
        "Compatibility and versioning",
        "What each pytemplate-uv release keeps stable, and how changes are announced.",
    ),
)
PAGES_BY_SLUG: dict[str, Page] = {page.slug: page for page in PAGES}


@dataclass(frozen=True)
class Heading:
    """A section heading of a rendered page, for its table of contents."""

    level: int
    anchor: str
    text: str


@dataclass(frozen=True)
class Rendered:
    """A page's HTML and its second-level headings."""

    html: Markup
    headings: tuple[Heading, ...]


def root_of(path: str) -> str:
    """Return the relative prefix from a page published in ``path`` back to the site's root."""
    return "../" * path.count("/")


def slugify(text: str) -> str:
    """Return GitHub's anchor for a heading: lowercase, punctuation dropped, spaces as hyphens."""
    kept = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return kept.replace(" ", "-")


def _fence(tokens: Sequence[Token], index: int, default: str) -> str:
    """Wrap a shell block with a copy button, whose text is the block's commands."""
    token = tokens[index]
    language = token.info.strip().split(" ")[0]
    if language not in _COPY_LANGUAGES:
        return default
    return (
        f'<div class="code">{default}<button type="button" class="copy" '
        f'data-copy="{escape(token.content.rstrip())}" data-what="Commands">Copy</button></div>\n'
    )


def render_markdown(text: str, path: str) -> Rendered:
    """Render one page's Markdown for a page published in ``path``.

    Headings get GitHub's anchors, links to other pages' sources become relative links, and shell
    blocks get a copy button. Raises ``SiteError`` for a link to a page that does not exist.
    """
    markdown = MarkdownIt("commonmark", {"html": False}).enable("table")
    renderer = markdown.renderer
    assert isinstance(renderer, RendererHTML)
    default_fence = renderer.rules["fence"]

    def fence(_renderer: Any, tokens: Sequence[Token], index: int, options: Any, env: Any) -> str:
        return _fence(tokens, index, default_fence(tokens, index, options, env))

    markdown.add_render_rule("fence", fence)
    # A wide table scrolls inside its own box instead of widening the page on a phone.
    markdown.add_render_rule("table_open", lambda *_: '<div class="table"><table>\n')
    markdown.add_render_rule("table_close", lambda *_: "</table></div>\n")
    tokens = markdown.parse(text)
    root = root_of(path)
    headings: list[Heading] = []
    seen: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            title = _plain_text(tokens[index + 1])
            anchor = slugify(title)
            count = seen.get(anchor, 0)
            seen[anchor] = count + 1
            if count:
                anchor = f"{anchor}-{count}"
            token.attrSet("id", anchor)
            if token.tag == "h2":
                headings.append(Heading(2, anchor, title))
        for child in token.children or ():
            if child.type == "link_open":
                child.attrSet("href", _link(str(child.attrGet("href") or ""), root))
    html = markdown.renderer.render(tokens, markdown.options, {})
    return Rendered(Markup(html), tuple(headings))


def _plain_text(inline: Token) -> str:
    return "".join(child.content for child in inline.children or () if child.content)


def _link(href: str, root: str) -> str:
    if _SCHEME.match(href):
        return href
    match = _PAGE_LINK.match(href)
    if match is None:
        if href.endswith(".md") or ".md#" in href:
            raise SiteError(f"The link {href!r} must name a page as '<slug>.md' or a full URL.")
        return href
    page = PAGES_BY_SLUG.get(match.group(1))
    if page is None:
        raise SiteError(f"The link {href!r} names no Learn page; add it to PAGES or fix the link.")
    return f"{root}{page.path}index.html{match.group(2) or ''}"


def render_page(page: Page) -> Rendered:
    """Render one Learn page from its source."""
    return render_markdown(page.source.read_text(encoding="utf-8"), page.path)
