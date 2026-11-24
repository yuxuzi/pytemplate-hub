"""The checks a pack must pass to be listed, and the verification of listed versions."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version as installed_version
from pathlib import Path

from pytemplate import api

from pytemplate_hub.errors import FetchError, HubError, PackCheckError
from pytemplate_hub.fetch import GitFetcher, directory_digest
from pytemplate_hub.schema import (
    GITHUB_URL,
    PACK_ID,
    Entry,
    ProfileCheck,
    Version,
    dump_entry,
    entry_path,
    load_entry,
    tag_problem,
)

CHECK_PROJECT = "hub-check"
PACK_MANIFEST = "pytemplate-pack.toml"
LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
LIFECYCLE_TIMEOUT_SECONDS = 600.0
# Programs a pack's lifecycle commands may start. `uv run` still runs the pack's own code, so
# lifecycle checks belong on an isolated machine with no credentials.
ALLOWED_PROGRAMS = frozenset({"uv"})
_PACK_ERRORS = (
    api.PackError,
    api.RenderError,
    api.RequestError,
    api.ConfigurationError,
    api.ManifestError,
)

Runner = Callable[[list[str], Path, dict[str, str]], tuple[bool, str]]


@dataclass(frozen=True)
class PackCheck:
    """The computed facts about a pack that passed its checks."""

    pack_id: str
    pack_version: str
    name: str
    description: str
    profiles: tuple[ProfileCheck, ...]


@dataclass(frozen=True)
class Inspected:
    """A fetched and checked version, with the pack's own name and description."""

    pack_id: str
    name: str
    description: str
    version: Version


def run_program(
    command: list[str], directory: Path, environment: dict[str, str]
) -> tuple[bool, str]:
    """Run one lifecycle command; return whether it succeeded and its combined output."""
    try:
        completed = subprocess.run(
            command,
            cwd=directory,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=LIFECYCLE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    return completed.returncode == 0, completed.stdout


def check_pack(
    root: Path, *, run_lifecycle: bool = False, runner: Runner = run_program
) -> PackCheck:
    """Check a pack directory: its license, manifests, and every profile with default answers.

    Without ``run_lifecycle`` no pack code runs, because rendering uses Copier's ``unsafe=False``.
    With it, each profile is rendered and its lifecycle commands run, which executes the pack's
    code. Raises `PackCheckError` naming the first problem.
    """
    if not any((root / name).is_file() for name in LICENSE_FILES):
        raise PackCheckError(f"The pack has no license file ({', '.join(LICENSE_FILES)}).")
    try:
        with api.open_catalog(str(root)) as (catalog, source, _):
            identifiers = [profile.identifier for profile in catalog.profiles]
        if not identifiers:
            raise PackCheckError("The pack has no profiles.")
        checks = tuple(_check_profile(root, name, run_lifecycle, runner) for name in identifiers)
    except _PACK_ERRORS as error:
        raise PackCheckError(f"The pack failed its checks: {error}") from error
    assert source.pack_id is not None and source.pack_version is not None  # set for every pack
    manifest = tomllib.loads((root / PACK_MANIFEST).read_text(encoding="utf-8"))
    return PackCheck(
        source.pack_id, source.pack_version, manifest["name"], manifest["description"], checks
    )


def _check_profile(root: Path, profile: str, run_lifecycle: bool, runner: Runner) -> ProfileCheck:
    with tempfile.TemporaryDirectory(prefix="pytemplate-hub-") as scratch:
        request = api.RenderRequest(
            profile_id=profile,
            project_name=CHECK_PROJECT,
            output_dir=Path(scratch),
            no_input=True,
            template=str(root),
        )
        plan = api.plan(request)
        if not run_lifecycle:
            return ProfileCheck(id=profile, lifecycle="not-run")
        result = api.render(request)
        home = Path(scratch) / "home"
        home.mkdir()
        environment = _lifecycle_environment(home)
        for line in result.resolution.lifecycle_commands:
            command = shlex.split(line.replace("{package}", plan.package_name))
            if not command or command[0] not in ALLOWED_PROGRAMS:
                raise PackCheckError(f"Profile {profile!r} declares a disallowed command: {line}")
            succeeded, output = runner(command, result.project_path, environment)
            if not succeeded:
                raise PackCheckError(f"Profile {profile!r}: `{line}` failed:\n{output[-1500:]}")
    return ProfileCheck(id=profile, lifecycle="passed")


def _lifecycle_environment(home: Path) -> dict[str, str]:
    """Return an environment holding no credentials, with an empty home directory."""
    passed = {name: os.environ[name] for name in ("PATH", "SYSTEMROOT") if name in os.environ}
    return {**passed, "HOME": str(home), "USERPROFILE": str(home), "UV_CACHE_DIR": str(home / "uv")}


def inspect_version(
    repository: str,
    tag: str,
    license_name: str,
    fetcher: GitFetcher,
    *,
    run_lifecycle: bool = False,
) -> Inspected:
    """Fetch and check ``tag``; return the pack's details and the version record bound to it."""
    with tempfile.TemporaryDirectory(prefix="pytemplate-hub-") as scratch:
        root = Path(scratch) / "pack"
        commit = fetcher.fetch(repository, tag, root)
        digest = directory_digest(root)
        check = check_pack(root, run_lifecycle=run_lifecycle)
    version = Version(
        tag=tag,
        commit=commit,
        digest=digest,
        pack_version=check.pack_version,
        license=license_name,
        checked_with=f"pytemplate-uv=={installed_version('pytemplate-uv')}",
        profiles=check.profiles,
    )
    return Inspected(check.pack_id, check.name, check.description, version)


def add_version(
    index: Path,
    repository: str,
    tag: str,
    license_name: str,
    fetcher: GitFetcher,
    *,
    run_lifecycle: bool = False,
) -> Path:
    """Check ``tag`` and record it in the pack's entry, creating the entry if needed.

    A tag git would refuse is reported before anything is fetched.
    """
    match = GITHUB_URL.match(repository)
    owner = match.group(1) if match else ""
    entry = Entry(repository=repository)
    problem = tag_problem(tag)
    if problem is not None:
        raise FetchError(f"Tag {tag!r} cannot be fetched: {problem}. Use a tag name git accepts.")
    found = inspect_version(repository, tag, license_name, fetcher, run_lifecycle=run_lifecycle)
    if not PACK_ID.fullmatch(found.pack_id):
        raise PackCheckError(
            f"The manifest's pack id {found.pack_id!r} is not allowed. A pack id must match "
            f"{PACK_ID.pattern}: lowercase letters, digits, and hyphens. Rename the pack in "
            f"{PACK_MANIFEST} and tag again."
        )
    path = entry_path(index, owner, found.pack_id)
    if path.exists():
        entry = load_entry(path)
        if entry.repository != repository:
            raise PackCheckError(f"{path} already lists this pack from {entry.repository}.")
        if any(listed.tag == tag for listed in entry.versions):
            raise PackCheckError(f"{path} already lists {tag}.")
    updated = Entry(
        repository=repository,
        name=found.name,
        description=found.description,
        versions=(*entry.versions, found.version),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_entry(updated), encoding="utf-8")
    return path


def verify_entry(path: Path, fetcher: GitFetcher, *, run_lifecycle: bool = False) -> list[str]:
    """Return the problems found by re-checking every version that is not yanked.

    A moved tag, a changed file, a renamed pack, or a pack that stopped passing is a problem.
    """
    try:
        entry = load_entry(path)
    except HubError as error:
        return [str(error)]
    problems: list[str] = []
    for listed in entry.versions:
        if listed.yanked is None:
            try:
                problems += _verify_version(path, entry, listed, fetcher, run_lifecycle)
            except (FetchError, PackCheckError) as error:
                problems.append(f"{path} {listed.tag}: {error}")
    return problems


def _verify_version(
    path: Path, entry: Entry, listed: Version, fetcher: GitFetcher, run_lifecycle: bool
) -> list[str]:
    found = inspect_version(
        entry.repository, listed.tag, listed.license, fetcher, run_lifecycle=run_lifecycle
    )
    current = found.version
    expected = [
        ("commit", listed.commit, current.commit),
        ("digest", listed.digest, current.digest),
        ("pack version", listed.pack_version, current.pack_version),
        ("pack id", path.stem, found.pack_id),
        (
            "profiles",
            sorted(profile.id for profile in listed.profiles),
            sorted(profile.id for profile in current.profiles),
        ),
    ]
    if listed == entry.latest:
        expected += [
            ("name", entry.name, found.name),
            ("description", entry.description, found.description),
        ]
    return [
        f"{path} {listed.tag}: the {name} changed: listed {was}, found {now}."
        for name, was, now in expected
        if was != now
    ]


def entry_files(index: Path) -> list[Path]:
    """Return every entry file in the index, in a stable order."""
    return sorted(index.glob("*/*.toml"))


def changed_claims(base: Path, index: Path) -> list[str]:
    """Return changes that need a maintainer, comparing the index with its base.

    Reported: an added review claim; a changed fact of a listed version; a listed version that the
    index removes (yank it instead); and an entry file that the index deletes from the base.
    Only ``reviewed_by`` and ``yanked`` may change on a listed version. Any added review claim is
    reported, so a maintainer recording a real review overrides this check deliberately.
    """
    problems: list[str] = []
    present = {path.relative_to(index) for path in entry_files(index)}
    for path in entry_files(base):
        relative = path.relative_to(base)
        if relative not in present:
            problems.append(f"{relative}: deletes a whole entry; yank its versions instead.")
    for path in entry_files(index):
        relative = path.relative_to(index)
        before = load_entry(base / relative) if (base / relative).is_file() else None
        listed = {version.tag: version for version in before.versions} if before else {}
        versions = load_entry(path).versions
        after = {version.tag for version in versions}
        for tag in listed:
            if tag not in after:
                problems.append(f"{relative} {tag}: removes a listed version; yank it instead.")
        for version in versions:
            old = listed.get(version.tag)
            if version.reviewed_by and (old is None or old.reviewed_by != version.reviewed_by):
                problems.append(f"{relative} {version.tag}: adds a review claim.")
            if old and _facts(old) != _facts(version):
                problems.append(f"{relative} {version.tag}: changes a listed version's facts.")
    return problems


def _facts(version: Version) -> Version:
    return version.model_copy(update={"reviewed_by": None, "yanked": None})
