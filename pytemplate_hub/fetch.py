"""Fetch a pack at an exact tag, and compute what binds a listing to its contents."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pytemplate_hub.errors import FetchError

GIT_TIMEOUT_SECONDS = 300.0
SYMLINK_MODE = "120000"


def directory_digest(root: Path) -> str:
    """Return a SHA-256 over every file's relative path and bytes under ``root``.

    Uses the same framing as Quant App Factory's digest of a pack, but hashes every file. Symlinks
    are refused, since Copier would copy their targets into generated projects.
    """
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise FetchError(
                f"The pack contains a symlink, which is not allowed: {path.relative_to(root)}"
            )
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _remove_tree(root: Path) -> None:
    """Remove ``root``, including the read-only git objects Windows refuses to delete."""
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IWRITE)
    shutil.rmtree(root)


@dataclass(frozen=True)
class GitFetcher:
    """Fetches tags with git, ignoring the machine's git configuration and credentials.

    Ignoring the configuration keeps digests the same everywhere (``core.autocrlf`` would change
    file bytes), and only ``allowed_protocols`` may be used, so a URL cannot reach local files.
    """

    allowed_protocols: str = "https"
    clone_url: Callable[[str], str] = str

    def fetch(self, repository: str, tag: str, destination: Path) -> str:
        """Check out exactly ``refs/tags/<tag>`` into ``destination``; return its commit SHA.

        A tag is fetched by its full ref, so a branch with the same name cannot stand in for it.
        Submodules are not fetched. Symlinks are refused from git's own record, because a Windows
        checkout may write them as plain files. The ``.git`` directory is removed before returning.
        """
        url = self.clone_url(repository)
        destination.mkdir(parents=True)
        self._git(destination, "init", "--quiet")
        self._git(destination, "fetch", "--quiet", "--depth", "1", url, f"refs/tags/{tag}")
        self._refuse_symlinks(destination)
        self._git(destination, "checkout", "--quiet", "--detach", "FETCH_HEAD")
        commit = self._git(destination, "rev-parse", "HEAD").strip()
        _remove_tree(destination / ".git")
        return commit

    def _refuse_symlinks(self, directory: Path) -> None:
        listing = self._git(directory, "ls-tree", "-r", "-z", "FETCH_HEAD")
        for item in filter(None, listing.split("\0")):
            details, name = item.split("\t", 1)
            if details.startswith(SYMLINK_MODE):
                raise FetchError(f"The pack contains a symlink, which is not allowed: {name}")

    def _git(self, directory: Path, *arguments: str) -> str:
        git = shutil.which("git")
        if git is None:
            raise FetchError("git is required to fetch template packs; install git.")
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "GIT_ALLOW_PROTOCOL": self.allowed_protocols,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            completed = subprocess.run(
                [git, "-c", "core.hooksPath=" + os.devnull, *arguments],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise FetchError(f"git {arguments[0]} timed out.") from error
        if completed.returncode != 0:
            raise FetchError(f"git {arguments[0]} failed: {completed.stderr.strip()}")
        return completed.stdout
