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


def test_long_messages_are_not_wrapped_on_a_narrow_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.errors, "_width", 20)
    missing = tmp_path / "a-long-directory-name-that-does-not-exist"

    result = runner.invoke(cli.app, ["verify", "--index", str(missing)])

    assert f"{missing} is not a directory." in result.output


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


def test_site_builds_without_network(tmp_path: Path) -> None:
    index = tmp_path / "index"
    assert _add(index) == 0
    output = tmp_path / "out"
    arguments = ["site", "--index", str(index), "--output", str(output), "--no-stars"]

    result = runner.invoke(cli.app, arguments)

    assert result.exit_code == 0
    assert "with 1 packs" in result.output
    assert "Sample pack" in (output / "index.html").read_text(encoding="utf-8")


def test_site_fails_for_a_missing_index(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["site", "--index", str(tmp_path / "typo"), "--no-stars"])

    assert result.exit_code == 1


def test_site_fails_for_a_malformed_entry(tmp_path: Path) -> None:
    index = tmp_path / "index"
    (index / "acme").mkdir(parents=True)
    (index / "acme" / "pack.toml").write_text("not toml =", encoding="utf-8")

    result = runner.invoke(cli.app, ["site", "--index", str(index), "--no-stars"])

    assert result.exit_code == 1


def test_verify_of_an_empty_index_passes(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(cli.app, ["verify", "--index", str(empty)])

    assert result.exit_code == 0
    assert "Verified 0 entries" in result.output


def test_yank_marks_the_version_and_names_the_file(tmp_path: Path) -> None:
    index = tmp_path / "index"
    assert _add(index) == 0

    result = runner.invoke(
        cli.app,
        ["yank", "acme/sample-pack", "v1.0.0", "--reason", "Broken", "--index", str(index)],
    )

    assert result.exit_code == 0
    assert "Yanked v1.0.0 of acme/sample-pack" in result.output
    assert load_entry(index / "acme" / "sample-pack.toml").versions[0].yanked == "Broken"


@pytest.mark.parametrize("entry", ["acme", "acme/sample/pack", "/sample-pack"])
def test_yank_reports_a_malformed_entry_without_a_traceback(tmp_path: Path, entry: str) -> None:
    result = runner.invoke(
        cli.app, ["yank", entry, "v1.0.0", "--reason", "Broken", "--index", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert "is not OWNER/PACK" in result.output or "not a valid entry" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
