"""Tests for the command-line interface."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pytemplate_hub import cli
from pytemplate_hub.fetch import GitFetcher
from pytemplate_hub.schema import Entry, dump_entry, load_entry
from tests.conftest import REPOSITORY, commit_all, git

runner = CliRunner()


@pytest.fixture(autouse=True)
def _local_fetcher(fetcher: GitFetcher, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "fetcher", fetcher)


def _add(index: Path) -> int:
    arguments = ["add", REPOSITORY, "--tag", "v1.0.0", "--license", "MIT", "--index", str(index)]
    return runner.invoke(cli.app, arguments).exit_code


def test_add_then_verify(tmp_path: Path) -> None:
    index = tmp_path / "index"

    assert _add(index) == 0
    result = runner.invoke(cli.app, ["verify", "--index", str(index)])

    assert result.exit_code == 0
    assert "Verified 1 entries" in result.output


def test_add_fails_for_a_missing_tag(tmp_path: Path) -> None:
    arguments = ["add", REPOSITORY, "--tag", "v9", "--license", "MIT", "--index", str(tmp_path)]

    result = runner.invoke(cli.app, arguments)

    assert result.exit_code == 1


def test_verify_fails_when_a_tag_moved(source: Path, tmp_path: Path) -> None:
    index = tmp_path / "index"
    assert _add(index) == 0
    (source / "README.md").write_text("changed\n", encoding="utf-8")
    commit_all(source)
    git(source, "tag", "--force", "v1.0.0")

    result = runner.invoke(cli.app, ["verify", "--index", str(index)])

    assert result.exit_code == 1
    assert "commit changed" in result.output


def test_verify_fails_for_a_missing_index(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["verify", "--index", str(tmp_path / "typo")])

    assert result.exit_code == 1
    assert "not a directory" in result.output


def test_check_claims_fails_when_a_submitter_claims_a_review(tmp_path: Path) -> None:
    index = tmp_path / "index"
    assert _add(index) == 0
    base = tmp_path / "base"
    shutil.copytree(index, base)
    path = index / "acme" / "sample-pack.toml"
    entry = load_entry(path)
    claimed = entry.versions[0].model_copy(update={"reviewed_by": "octocat"})
    path.write_text(
        dump_entry(Entry(repository=entry.repository, versions=(claimed,))), encoding="utf-8"
    )

    result = runner.invoke(cli.app, ["check-claims", "--base", str(base), "--index", str(index)])

    assert result.exit_code == 1
    assert "adds a review claim" in result.output


def test_check_claims_passes_for_a_new_unreviewed_entry(tmp_path: Path) -> None:
    index = tmp_path / "index"
    assert _add(index) == 0
    base = tmp_path / "base"
    base.mkdir()

    result = runner.invoke(cli.app, ["check-claims", "--base", str(base), "--index", str(index)])

    assert result.exit_code == 0


def test_check_claims_fails_when_a_listed_commit_is_rewritten(tmp_path: Path) -> None:
    index = tmp_path / "index"
    assert _add(index) == 0
    base = tmp_path / "base"
    shutil.copytree(index, base)
    path = index / "acme" / "sample-pack.toml"
    entry = load_entry(path)
    moved = entry.versions[0].model_copy(update={"commit": "f" * 40})
    path.write_text(
        dump_entry(Entry(repository=entry.repository, versions=(moved,))), encoding="utf-8"
    )

    result = runner.invoke(cli.app, ["check-claims", "--base", str(base), "--index", str(index)])

    assert result.exit_code == 1
    assert "facts" in result.output


def test_verify_of_an_empty_index_passes(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(cli.app, ["verify", "--index", str(empty)])

    assert result.exit_code == 0
    assert "Verified 0 entries" in result.output
