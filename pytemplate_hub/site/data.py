"""The site's data: the JSON copy of the index, its JSON Schema, star counts, and create commands.

Everything from an entry is untrusted text. The page is rendered by ``render`` with autoescaping.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pytemplate_hub.schema import CATEGORIES, Entry, Version, load_entry
from pytemplate_hub.site.render import Card, Command, write_site
from pytemplate_hub.verify import entry_files

STARS_TIMEOUT_SECONDS = 15.0
StarSource = Callable[[Entry], int | None]
INDEX_FORMAT = 1
INDEX_FILE = "index.json"
SCHEMA_FILE = "index.schema.json"

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
    """Write ``index.html``, ``index.json``, and ``index.schema.json``; return packs shown."""
    data: list[dict[str, Any]] = []
    cards: list[Card] = []
    for path in entry_files(index):
        entry = load_entry(path)
        pack_stars = stars(entry)
        data.append(_pack_data(path.stem, entry, pack_stars))
        if entry.latest is not None:
            cards.append(_card(entry, path.stem, pack_stars))
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


def _card(entry: Entry, pack_id: str, stars: int | None) -> Card:
    latest = entry.latest
    assert latest is not None  # only packs with an active version get a card
    title = entry.name or pack_id
    identifier = f"{entry.owner}/{pack_id}"
    topics = (*(entry.categories or ()), *(entry.keywords or ()))
    profile_ids = [profile.id for profile in latest.profiles]
    search = " ".join([title, identifier, entry.description, latest.license, *profile_ids, *topics])
    checks = ", ".join(f"{p.id}: lifecycle {p.lifecycle}" for p in latest.profiles)
    star_text = "stars unavailable" if stars is None else f"{stars} stars"
    facts = (
        f"{latest.tag} · {latest.license} · {star_text} · commit {latest.commit[:12]} · {checks} · "
        f"{latest.checked_with}"
    )
    return Card(
        name=title,
        identifier=identifier,
        description=entry.description,
        repository=entry.repository,
        tag=latest.tag,
        commit=latest.commit,
        digest=latest.digest,
        license=latest.license,
        checked_on=latest.checked_on.isoformat() if latest.checked_on else None,
        tier=latest.tier,
        tier_label="Listed" if latest.tier == "listed" else f"Reviewed by {latest.reviewed_by}",
        facts=facts,
        categories=tuple(entry.categories or ()),
        search=search.lower(),
        commands=tuple(
            Command(
                profile=profile.id,
                text=hub_command(entry, pack_id, latest, profile.id),
                pinned=create_command(entry, latest, profile.id),
            )
            for profile in latest.profiles
        ),
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
