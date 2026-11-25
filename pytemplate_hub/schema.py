"""The index entry format: one TOML file per pack, at ``index/<owner>/<pack-id>.toml``."""

from __future__ import annotations

import json
import re
import tomllib
from datetime import date
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
DEPENDENCY_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
KEYWORD = re.compile(r"^[a-z0-9][a-z0-9+#. -]{0,29}$")
CATEGORIES_FILE = Path(__file__).with_name("categories.toml")
NAME_MAX = 100
DESCRIPTION_MAX = 500
KEYWORDS_MAX = 12
SECURITY_POSTURE_MAX = 1000


def load_categories(path: Path = CATEGORIES_FILE) -> dict[str, str]:
    """Return the fixed category vocabulary: each id mapped to its label, in file order."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for identifier, table in data.items():
        label = table.get("label") if isinstance(table, dict) else None
        if not PACK_ID.match(identifier) or not isinstance(label, str) or not label:
            raise EntryError(f"{path}: each category needs an id and a label, got {identifier!r}.")
        labels[identifier] = label
    return labels


CATEGORIES = load_categories()


def check_categories(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Return ``values`` as a tuple, or raise naming the first category the vocabulary lacks."""
    for value in values:
        if value not in CATEGORIES:
            raise ValueError(
                f"unknown category {value!r}. Use one of: {', '.join(CATEGORIES)}. "
                "A new category is a change to pytemplate_hub/categories.toml."
            )
    if len(set(values)) != len(values):
        raise ValueError("each category may be listed only once")
    return tuple(values)


def check_keywords(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Return ``values`` as a tuple of short, lowercase search words, or raise."""
    if len(values) > KEYWORDS_MAX:
        raise ValueError(f"keywords: at most {KEYWORDS_MAX} are allowed, got {len(values)}.")
    for value in values:
        if not KEYWORD.match(value):
            raise ValueError(
                f"keyword {value!r} is not allowed. Use up to 30 lowercase letters, digits, "
                "spaces, or '+', '#', '.', '-', starting with a letter or digit."
            )
    if len(set(values)) != len(values):
        raise ValueError("each keyword may be listed only once")
    return tuple(values)


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


PythonVersion = Annotated[str, Field(pattern=r"^3\.[0-9]{1,2}$")]
DependencyName = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]


class ProfileCheck(_Strict):
    """A profile that planned with its default answers, and whether its lifecycle ran.

    The details come from the profile's own ``profile.toml``. ``dependencies`` holds names only,
    without version specifiers. A detail set to None is one the entry does not record (an entry
    written before it existed), and ``verify`` skips it; a recorded detail must still match.
    """

    id: Annotated[str, Field(pattern=PACK_ID.pattern)]
    lifecycle: Literal["passed", "not-run"]
    name: Annotated[str, Field(max_length=NAME_MAX)] | None = None
    description: Annotated[str, Field(max_length=DESCRIPTION_MAX)] | None = None
    kind: Literal["cli", "library", "service"] | None = None
    supported_python: tuple[PythonVersion, ...] | None = None
    dependencies: tuple[DependencyName, ...] | None = None
    security_posture: Annotated[str, Field(max_length=SECURITY_POSTURE_MAX)] | None = None


class Version(_Strict):
    """One listed version, bound to the exact commit and file contents that were checked."""

    tag: Tag
    commit: Commit
    digest: Digest
    pack_version: str
    license: License
    checked_with: str
    checked_on: date | None = None
    profiles: tuple[ProfileCheck, ...]
    reviewed_by: GitHubLogin | None = None
    yanked: str | None = None

    @property
    def tier(self) -> Literal["listed", "reviewed"]:
        """Return ``reviewed`` when a named maintainer reviewed this exact commit."""
        return "reviewed" if self.reviewed_by else "listed"


class Entry(_Strict):
    """A pack's source repository and its listed versions.

    ``categories`` must come from the fixed vocabulary in ``categories.toml``. ``keywords`` are
    search words. Both are copied from the pack's manifest by ``add`` and checked by ``verify``;
    None means the entry does not record them, and ``verify`` skips them.
    """

    format: Literal[1] = 1
    repository: str
    name: Annotated[str, Field(max_length=NAME_MAX)] = ""
    description: Annotated[str, Field(max_length=DESCRIPTION_MAX)] = ""
    categories: tuple[str, ...] | None = None
    keywords: tuple[str, ...] | None = None
    versions: tuple[Version, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Entry:
        match = GITHUB_URL.match(self.repository)
        if not match or self.repository.endswith(".git"):
            raise ValueError(
                f"repository must look like https://github.com/owner/repo, got {self.repository!r}"
            )
        if match.group(2) in (".", ".."):
            raise ValueError(
                f"repository name must not be '.' or '..', got {self.repository!r}. "
                "Use the repository's own name."
            )
        if self.categories is not None:
            check_categories(self.categories)
        if self.keywords is not None:
            check_keywords(self.keywords)
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
    if entry.categories is not None:
        lines.append(f"categories = {_array(entry.categories)}")
    if entry.keywords is not None:
        lines.append(f"keywords = {_array(entry.keywords)}")
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
        if version.checked_on is not None:
            lines.append(f"checked_on = {version.checked_on.isoformat()}")
        lines += [
            f"profiles = [{', '.join(_profile(profile) for profile in version.profiles)}]",
        ]
    return "\n".join(lines) + "\n"


def _text(value: str) -> str:
    # A JSON string is a valid TOML basic string, apart from a raw DEL. Keeping non-ASCII text raw
    # avoids surrogate pairs, which TOML rejects.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _array(values: tuple[str, ...]) -> str:
    return f"[{', '.join(_text(value) for value in values)}]"


def _profile(profile: ProfileCheck) -> str:
    fields: list[tuple[str, str | None]] = [
        ("id", _text(profile.id)),
        ("lifecycle", _text(profile.lifecycle)),
        ("name", None if profile.name is None else _text(profile.name)),
        ("description", None if profile.description is None else _text(profile.description)),
        ("kind", None if profile.kind is None else _text(profile.kind)),
        (
            "supported_python",
            None if profile.supported_python is None else _array(profile.supported_python),
        ),
        ("dependencies", None if profile.dependencies is None else _array(profile.dependencies)),
        (
            "security_posture",
            None if profile.security_posture is None else _text(profile.security_posture),
        ),
    ]
    return "{ " + ", ".join(f"{name} = {value}" for name, value in fields if value) + " }"


def dependency_name(requirement: str) -> str | None:
    """Return the project name in a requirement such as ``rich>=13.7``, or None if there is none."""
    match = DEPENDENCY_NAME.match(requirement)
    return match.group(1) if match else None
