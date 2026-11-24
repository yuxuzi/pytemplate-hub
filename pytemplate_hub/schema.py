"""The index entry format: one TOML file per pack, at ``index/<owner>/<pack-id>.toml``."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from pytemplate_hub.errors import EntryError

GITHUB_URL = re.compile(r"^https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)$")
PACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TAG_CHARACTERS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NAME_MAX = 100
DESCRIPTION_MAX = 500


def tag_problem(tag: str) -> str | None:
    """Return why git would refuse ``tag`` as a tag name, or None when the name is acceptable.

    Beyond the character pattern, git refuses a name that contains ``..`` or ``@{``, ends in
    ``.lock``, or ends in ``.`` or ``/``. Checking these before a fetch saves a late git error.
    """
    if not TAG_CHARACTERS.match(tag):
        return "it must start with a letter or digit and use only letters, digits, '.', '_', '-'"
    if ".." in tag:
        return "it contains '..'"
    if "@{" in tag:
        return "it contains '@{'"
    if tag.endswith(".lock"):
        return "it ends in '.lock'"
    if tag.endswith((".", "/")):
        return "it ends in '.' or '/'"
    return None


def _check_tag(tag: str) -> str:
    problem = tag_problem(tag)
    if problem is not None:
        raise ValueError(f"tag {tag!r} is not a valid git tag name: {problem}.")
    return tag


Tag = Annotated[str, Field(pattern=TAG_CHARACTERS.pattern), AfterValidator(_check_tag)]
Commit = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
License = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.+ ()-]*$")]
GitHubLogin = Annotated[str, Field(pattern=r"^[A-Za-z0-9-]+$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileCheck(_Strict):
    """A profile that planned with its default answers, and whether its lifecycle ran."""

    id: Annotated[str, Field(pattern=PACK_ID.pattern)]
    lifecycle: Literal["passed", "not-run"]


class Version(_Strict):
    """One listed version, bound to the exact commit and file contents that were checked."""

    tag: Tag
    commit: Commit
    digest: Digest
    pack_version: str
    license: License
    checked_with: str
    profiles: tuple[ProfileCheck, ...]
    reviewed_by: GitHubLogin | None = None
    yanked: str | None = None

    @property
    def tier(self) -> Literal["listed", "reviewed"]:
        """Return ``reviewed`` when a named maintainer reviewed this exact commit."""
        return "reviewed" if self.reviewed_by else "listed"


class Entry(_Strict):
    """A pack's source repository and its listed versions."""

    format: Literal[1] = 1
    repository: str
    name: Annotated[str, Field(max_length=NAME_MAX)] = ""
    description: Annotated[str, Field(max_length=DESCRIPTION_MAX)] = ""
    versions: tuple[Version, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Entry:
        if not GITHUB_URL.match(self.repository) or self.repository.endswith(".git"):
            raise ValueError(
                f"repository must look like https://github.com/owner/repo, got {self.repository!r}"
            )
        tags = [version.tag for version in self.versions]
        if len(tags) != len(set(tags)):
            raise ValueError("each tag may be listed only once")
        return self

    @property
    def owner(self) -> str:
        """Return the GitHub owner of the source repository."""
        match = GITHUB_URL.match(self.repository)
        assert match is not None  # guaranteed by the validator
        return match.group(1)

    @property
    def repository_name(self) -> str:
        """Return the name of the source repository."""
        match = GITHUB_URL.match(self.repository)
        assert match is not None  # guaranteed by the validator
        return match.group(2)

    @property
    def latest(self) -> Version | None:
        """Return the most recently listed version that is not yanked."""
        active = [version for version in self.versions if version.yanked is None]
        return active[-1] if active else None


def entry_path(index: Path, owner: str, pack_id: str) -> Path:
    """Return where the entry for ``owner``'s pack belongs."""
    return index / owner.lower() / f"{pack_id}.toml"


def load_entry(path: Path) -> Entry:
    """Read an entry, and check that its path names its repository's owner and a valid pack id."""
    try:
        entry = Entry.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise EntryError(f"{path}: {error}") from error
    if not PACK_ID.match(path.stem):
        raise EntryError(f"{path}: the file name must be a lowercase pack id.")
    if path.parent.name != entry.owner.lower():
        raise EntryError(
            f"{path}: the directory must be the repository owner, {entry.owner.lower()!r}."
        )
    return entry


def dump_entry(entry: Entry) -> str:
    """Return ``entry`` as TOML, with fields in a stable order so diffs stay reviewable."""
    lines = [f"format = {entry.format}", f"repository = {_text(entry.repository)}"]
    lines += [
        f"{name} = {_text(value)}"
        for name, value in (("name", entry.name), ("description", entry.description))
        if value
    ]
    for version in entry.versions:
        lines += ["", "[[versions]]"]
        lines += [
            f"{name} = {_text(value)}"
            for name, value in (
                ("tag", version.tag),
                ("commit", version.commit),
                ("digest", version.digest),
                ("pack_version", version.pack_version),
                ("license", version.license),
                ("checked_with", version.checked_with),
                ("reviewed_by", version.reviewed_by),
                ("yanked", version.yanked),
            )
            if value is not None
        ]
        lines += [
            f"profiles = [{', '.join(_profile(profile) for profile in version.profiles)}]",
        ]
    return "\n".join(lines) + "\n"


def _text(value: str) -> str:
    # A JSON string is a valid TOML basic string, apart from a raw DEL. Keeping non-ASCII text raw
    # avoids surrogate pairs, which TOML rejects.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _profile(profile: ProfileCheck) -> str:
    return f"{{ id = {_text(profile.id)}, lifecycle = {_text(profile.lifecycle)} }}"
