"""Tests for fetching a tag and computing its digest."""

from pathlib import Path

import pytest

from pytemplate_hub.errors import FetchError
from pytemplate_hub.fetch import GitFetcher, directory_digest
from tests.conftest import REPOSITORY, git


def test_fetch_returns_the_tagged_commit_and_removes_git(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    destination = tmp_path / "out"

    commit = fetcher.fetch(REPOSITORY, "v1.0.0", destination)

    assert commit == git(source, "rev-list", "-n", "1", "v1.0.0")
    assert (destination / "pytemplate-pack.toml").is_file()
    assert not (destination / ".git").exists()


def test_annotated_tag_resolves_to_its_commit(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    git(source, "tag", "-a", "v2.0.0", "-m", "annotated")

    commit = fetcher.fetch(REPOSITORY, "v2.0.0", tmp_path / "out")

    assert commit == git(source, "rev-parse", "HEAD")


def test_a_branch_cannot_stand_in_for_a_tag(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    git(source, "branch", "v9.9.9")

    with pytest.raises(FetchError, match="fetch failed"):
        fetcher.fetch(REPOSITORY, "v9.9.9", tmp_path / "out")


def test_symlink_is_refused_before_checkout(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    (source / "stolen").symlink_to("/etc/hosts")
    git(source, "add", "-A")
    git(source, "commit", "--quiet", "-m", "link")
    git(source, "tag", "v3.0.0")

    with pytest.raises(FetchError, match=r"symlink.*stolen"):
        fetcher.fetch(REPOSITORY, "v3.0.0", tmp_path / "out")

    assert not (tmp_path / "out" / "pytemplate-pack.toml").exists()


def test_disallowed_protocol_is_refused(source: Path, tmp_path: Path) -> None:
    https_only = GitFetcher(clone_url=lambda _: source.as_uri())

    with pytest.raises(FetchError, match="fetch failed"):
        https_only.fetch(REPOSITORY, "v1.0.0", tmp_path / "out")


def test_digest_changes_with_contents_and_with_names(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    first = directory_digest(tmp_path)
    (tmp_path / "a.txt").write_text("two", encoding="utf-8")
    second = directory_digest(tmp_path)
    (tmp_path / "a.txt").rename(tmp_path / "b.txt")
    third = directory_digest(tmp_path)

    assert len({first, second, third}) == 3


def test_digest_refuses_symlinks(tmp_path: Path) -> None:
    (tmp_path / "link").symlink_to("/etc/hosts")

    with pytest.raises(FetchError, match="symlink"):
        directory_digest(tmp_path)


def test_digest_does_not_depend_on_where_the_pack_was_fetched(
    fetcher: GitFetcher, tmp_path: Path
) -> None:
    fetcher.fetch(REPOSITORY, "v1.0.0", tmp_path / "one")
    fetcher.fetch(REPOSITORY, "v1.0.0", tmp_path / "two")

    assert directory_digest(tmp_path / "one") == directory_digest(tmp_path / "two")
