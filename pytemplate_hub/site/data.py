"""The site's data: the JSON copy of the index, its JSON Schema, star counts, and create commands.

Everything from an entry is untrusted text. The page is rendered by ``render`` with autoescaping.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from pytemplate_hub.schema import CATEGORIES, Entry, Version, load_entry
from pytemplate_hub.site.render import (
    KIND_LABELS,
    Card,
    Command,
    Profile,
    VersionRow,
    write_site,
)
from pytemplate_hub.verify import entry_files

STARS_TIMEOUT_SECONDS = 15.0
StarSource = Callable[[Entry], int | None]
INDEX_FORMAT = 1
INDEX_FILE = "index.json"
SCHEMA_FILE = "index.schema.json"
# Display names for the stack filter. A pack's stack is every name here that appears among its
# profiles' dependencies or its own keywords; both come from the pack, so nothing is guessed.
STACKS: dict[str, str] = {
    "alembic": "Alembic",
    "celery": "Celery",
    "django": "Django",
    "duckdb": "DuckDB",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "httpx": "HTTPX",
    "mcp": "MCP",
    "numpy": "NumPy",
    "pandas": "pandas",
    "polars": "Polars",
    "pydantic": "Pydantic",
    "redis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "typer": "Typer",
    "uvicorn": "Uvicorn",
}

_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_TEXT: dict[str, Any] = {"type": "string"}
_NULLABLE_TEXT: dict[str, Any] = {"type": ["string", "null"]}
_TEXT_LIST: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
_NULLABLE_TEXT_LIST: dict[str, Any] = {"type": ["array", "null"], "items": {"type": "string"}}


def _object(properties: dict[str, Any], *required: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


_PROFILE_SCHEMA = _object(
    {
        "id": _TEXT,
        "lifecycle": {"enum": ["passed", "not-run"]},
        "name": _NULLABLE_TEXT,
        "description": _NULLABLE_TEXT,
        "kind": {"enum": ["cli", "library", "service", None]},
        "supported_python": _NULLABLE_TEXT_LIST,
        "dependencies": _NULLABLE_TEXT_LIST,
        "security_posture": _NULLABLE_TEXT,
    },
    "id",
    "lifecycle",
    "name",
    "description",
    "kind",
    "supported_python",
    "dependencies",
    "security_posture",
)
_VERSION_SCHEMA = _object(
    {
        "tag": _TEXT,
        "commit": _TEXT,
        "digest": _TEXT,
        "pack_version": _TEXT,
        "license": _TEXT,
        "checked_with": _TEXT,
        "checked_on": {"type": ["string", "null"], "format": "date"},
        "profiles": {"type": "array", "items": _PROFILE_SCHEMA},
        "reviewed_by": _NULLABLE_TEXT,
        "yanked": _NULLABLE_TEXT,
        "tier": {"enum": ["listed", "reviewed"]},
    },
    "tag",
    "commit",
    "digest",
    "pack_version",
    "license",
    "checked_with",
    "checked_on",
    "profiles",
    "reviewed_by",
    "yanked",
    "tier",
)
_PACK_SCHEMA = _object(
    {
        "id": _TEXT,
        "owner": _TEXT,
        "repository": _TEXT,
        "name": _TEXT,
        "description": _TEXT,
        "categories": {"type": ["array", "null"], "items": {"enum": list(CATEGORIES)}},
        "keywords": _NULLABLE_TEXT_LIST,
        "stars": {"type": ["integer", "null"]},
        "latest": _NULLABLE_TEXT,
        "versions": {"type": "array", "items": _VERSION_SCHEMA},
    },
    "id",
    "owner",
    "repository",
    "name",
    "description",
    "categories",
    "keywords",
    "stars",
    "latest",
    "versions",
)

INDEX_SCHEMA: dict[str, Any] = {
    "$schema": _SCHEMA_DRAFT,
    "title": "pytemplate-hub index.json",
    "description": "The data behind the hub's site. Every string comes from pack authors.",
    **_object(
        {
            "format": {"const": INDEX_FORMAT},
            "built_on": {"type": "string", "format": "date"},
            "categories": {
                "type": "array",
                "items": _object({"id": _TEXT, "label": _TEXT}, "id", "label"),
            },
            "packs": {"type": "array", "items": _PACK_SCHEMA},
        },
        "format",
        "built_on",
        "categories",
        "packs",
    ),
}


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

    The commit and digest make pytemplate-uv (3.1 or later) refuse a fetched pack if the tag moved
    or its files changed since the hub checked it; a cached copy is checked against the digest.
    ``-y`` (3.2 or later; ``@latest`` guarantees it) accepts the defaults without prompting.
    """
    source = f"gh:{entry.owner}/{entry.repository_name}"
    return (
        f"uvx pytemplate-uv@latest create my-project -p {profile} "
        f"--template {source} --template-ref {version.tag} "
        f"--template-commit {version.commit} --template-digest {version.digest} -y"
    )


def hub_command(entry: Entry, pack_id: str, version: Version, profile: str) -> str:
    """Return the short command: pytemplate-uv reads the pinned commit and digest from the hub.

    ``-h`` (``--hub``, pytemplate-uv 3.5 or later) names the pack by its index path, ``owner/pack``,
    and the tag. pytemplate-uv checks the commit and digest the hub lists for that tag exactly as
    the fully pinned command does, so the short form is refused on the same terms.
    """
    return (
        f"uvx pytemplate-uv@latest create my-project -h {entry.owner.lower()}/{pack_id}"
        f"@{version.tag} -p {profile} -y"
    )


def build_site(index: Path, output: Path, *, stars: StarSource, built_on: str) -> int:
    """Write every page, ``index.json``, and ``index.schema.json``; return the packs shown."""
    data: list[dict[str, Any]] = []
    cards: list[Card] = []
    for path in entry_files(index):
        entry = load_entry(path)
        pack_stars = stars(entry)
        data.append(_pack_data(path.stem, entry, pack_stars))
        if entry.latest is not None:
            cards.append(_card(entry, path.stem, pack_stars, built_on))
    write_site(cards, built_on, output)
    payload = {
        "format": INDEX_FORMAT,
        "built_on": built_on,
        "categories": [{"id": key, "label": label} for key, label in CATEGORIES.items()],
        "packs": data,
    }
    (output / INDEX_FILE).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (output / SCHEMA_FILE).write_text(json.dumps(INDEX_SCHEMA, indent=2) + "\n", encoding="utf-8")
    return len(cards)


def stack_of(names: tuple[str, ...]) -> tuple[str, ...]:
    """Return the display names of the known stack items among ``names``, without repeats."""
    found: list[str] = []
    for name in names:
        label = STACKS.get(name.lower().replace("_", "-"))
        if label and label not in found:
            found.append(label)
    return tuple(found)


def recommended(version: Version, stars: int | None, built_on: str) -> float:
    """Return the published ranking score: 0.4 trust + 0.3 freshness + 0.3 popularity.

    trust is 1.0 for a reviewed version, 0.6 when every profile passed its lifecycle, else 0.3;
    freshness is 1.0 when checked in the last 30 days, falling linearly to 0 at 365 days; and
    popularity is ``min(1, log10(1 + stars) / 3)``, so 1,000 stars score 1.0.
    """
    if version.tier == "reviewed":
        trust = 1.0
    elif version.profiles and all(p.lifecycle == "passed" for p in version.profiles):
        trust = 0.6
    else:
        trust = 0.3
    freshness = 0.0
    if version.checked_on is not None:
        days = (date.fromisoformat(built_on) - version.checked_on).days
        freshness = 1.0 if days <= 30 else max(0.0, 1 - (days - 30) / 335)
    popularity = min(1.0, math.log10(1 + (stars or 0)) / 3)
    return round(0.4 * trust + 0.3 * freshness + 0.3 * popularity, 4)


def _card(entry: Entry, pack_id: str, stars: int | None, built_on: str) -> Card:
    latest = entry.latest
    assert latest is not None  # only packs with an active version get a card
    title = entry.name or pack_id
    owner = entry.owner.lower()
    identifier = f"{entry.owner}/{pack_id}"
    categories = tuple(entry.categories or ())
    keywords = tuple(entry.keywords or ())
    profiles = tuple(_profile(entry, pack_id, latest, check) for check in latest.profiles)
    dependencies = tuple(name for check in latest.profiles for name in check.dependencies or ())
    stack = stack_of((*dependencies, *keywords))
    topics = (*categories, *(CATEGORIES.get(c, c) for c in categories), *keywords, *stack)
    profile_words = [word for p in profiles for word in (p.id, p.name, p.kind or "")]
    search = " ".join(
        [title, identifier, entry.description, latest.license, *profile_words, *topics]
    )
    checks = ", ".join(f"{p.id}: lifecycle {p.lifecycle}" for p in latest.profiles)
    star_text = "stars unavailable" if stars is None else f"{stars} stars"
    facts = (
        f"{latest.tag} · {latest.license} · {star_text} · commit {latest.commit[:12]} · {checks} · "
        f"{latest.checked_with}"
    )
    return Card(
        name=title,
        identifier=identifier,
        owner=owner,
        pack_id=pack_id,
        path=f"templates/{owner}/{pack_id}/",
        description=entry.description,
        repository=entry.repository,
        tag=latest.tag,
        commit=latest.commit,
        digest=latest.digest,
        license=latest.license,
        checked_on=latest.checked_on.isoformat() if latest.checked_on else None,
        checked_with=latest.checked_with,
        tier=latest.tier,
        tier_label=_tier_label(latest),
        facts=facts,
        categories=categories,
        keywords=keywords,
        stack=stack,
        kinds=tuple(dict.fromkeys(p.kind for p in profiles if p.kind)),
        python=tuple(sorted({v for p in profiles for v in p.python}, key=_python_order)),
        stars=stars,
        recommended=recommended(latest, stars, built_on),
        search=search.lower(),
        search_name=title.lower(),
        search_id=f"{owner} {pack_id}",
        search_tags=" ".join([*topics, *profile_words]).lower(),
        search_text=" ".join([entry.description, *(p.description for p in profiles)]).lower(),
        commands=tuple(profile.command for profile in profiles),
        profiles=profiles,
        versions=tuple(_version_row(version) for version in reversed(entry.versions)),
    )


def _python_order(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _tier_label(version: Version) -> str:
    return "Listed" if version.tier == "listed" else f"Reviewed by {version.reviewed_by}"


def _profile(entry: Entry, pack_id: str, version: Version, check: Any) -> Profile:
    kind = check.kind
    return Profile(
        id=check.id,
        name=check.name or check.id,
        description=check.description or "",
        kind=kind,
        kind_label=KIND_LABELS.get(kind) if kind else None,
        python=tuple(check.supported_python or ()),
        stack=stack_of(tuple(check.dependencies or ())),
        lifecycle=check.lifecycle,
        security_posture=check.security_posture,
        command=Command(
            profile=check.id,
            text=hub_command(entry, pack_id, version, check.id),
            pinned=create_command(entry, version, check.id),
        ),
    )


def _version_row(version: Version) -> VersionRow:
    return VersionRow(
        tag=version.tag,
        commit=version.commit,
        checked_on=version.checked_on.isoformat() if version.checked_on else None,
        checked_with=version.checked_with,
        license=version.license,
        tier_label=_tier_label(version),
        yanked=version.yanked,
    )


def _pack_data(pack_id: str, entry: Entry, stars: int | None) -> dict[str, Any]:
    latest = entry.latest
    return {
        "id": pack_id,
        "owner": entry.owner,
        "repository": entry.repository,
        "name": entry.name,
        "description": entry.description,
        "categories": None if entry.categories is None else list(entry.categories),
        "keywords": None if entry.keywords is None else list(entry.keywords),
        "stars": stars,
        "latest": latest.tag if latest else None,
        "versions": [
            {**version.model_dump(mode="json"), "tier": version.tier} for version in entry.versions
        ],
    }
