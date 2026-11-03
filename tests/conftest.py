"""Shared fixtures: the sample pack as a local git repository with a tag."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pytemplate_hub.fetch import GitFetcher

SAMPLE_PACK = Path(__file__).parent.parent / "examples" / "sample-pack"
REPOSITORY = "https://github.com/acme/sample-pack"


def git(directory: Path, *arguments: str) -> str:
    """Run git with a fixed identity, ignoring the machine's configuration."""
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    return subprocess.run(
        ["git", *arguments],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def commit_all(repository: Path, message: str = "change") -> str:
    """Commit everything in ``repository`` and return the commit SHA."""
    git(repository, "add", "-A")
    git(repository, "commit", "--quiet", "--allow-empty", "-m", message)
    return git(repository, "rev-parse", "HEAD")


@pytest.fixture
def pack_dir(tmp_path: Path) -> Path:
    """Return a writable copy of the sample pack."""
    return Path(shutil.copytree(SAMPLE_PACK, tmp_path / "pack-copy"))


@pytest.fixture
def source(pack_dir: Path) -> Path:
    """Return the sample pack as a git repository tagged v1.0.0."""
    git(pack_dir, "init", "--quiet", "-b", "main")
    commit_all(pack_dir, "first")
    git(pack_dir, "tag", "v1.0.0")
    return pack_dir


@pytest.fixture
def fetcher(source: Path) -> GitFetcher:
    """Return a fetcher that resolves every repository to the local ``source``."""
    return GitFetcher(allowed_protocols="file", clone_url=lambda _: source.as_uri())
