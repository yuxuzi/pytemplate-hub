"""Tests for the listing checks and for re-verifying listed versions."""

from pathlib import Path

import pytest

from pytemplate_hub.errors import FetchError, PackCheckError
from pytemplate_hub.fetch import GitFetcher
from pytemplate_hub.schema import Entry, dump_entry, load_entry
from pytemplate_hub.verify import add_version, check_pack, entry_files, verify_entry
from tests.conftest import REPOSITORY, commit_all, git


def _add(index: Path, fetcher: GitFetcher, tag: str = "v1.0.0") -> Path:
    return add_version(index, REPOSITORY, tag, "MIT", fetcher)


def test_sample_pack_passes_without_running_its_code(pack_dir: Path) -> None:
    def refuse(*_: object) -> tuple[bool, str]:
        raise AssertionError("no command may run")

    check = check_pack(pack_dir, runner=refuse)

    assert check.pack_id == "sample-pack"
    assert [(profile.id, profile.lifecycle) for profile in check.profiles] == [("tool", "not-run")]


def test_lifecycle_commands_run_with_no_credentials(
    pack_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    calls: list[tuple[list[str], dict[str, str]]] = []

    def record(command: list[str], _: Path, environment: dict[str, str]) -> tuple[bool, str]:
        calls.append((command, environment))
        return True, ""

    check = check_pack(pack_dir, run_lifecycle=True, runner=record)

    assert [command for command, _ in calls] == [["uv", "sync"], ["uv", "run", "pytest"]]
    assert check.profiles[0].lifecycle == "passed"
    for _, environment in calls:
        assert "GITHUB_TOKEN" not in environment
        assert environment["HOME"] != str(Path.home())


def test_failing_lifecycle_command_fails_the_check(pack_dir: Path) -> None:
    with pytest.raises(PackCheckError, match=r"uv sync.*failed"):
        check_pack(pack_dir, run_lifecycle=True, runner=lambda *_: (False, "boom"))


def test_lifecycle_command_outside_the_allowlist_is_refused(pack_dir: Path) -> None:
    profile = pack_dir / "tool" / "profile.toml"
    text = profile.read_text(encoding="utf-8")
    profile.write_text(text.replace('"uv sync"', '"curl https://example.com"'), encoding="utf-8")

    with pytest.raises(PackCheckError, match="disallowed command"):
        check_pack(pack_dir, run_lifecycle=True, runner=lambda *_: (True, ""))


@pytest.mark.parametrize("setting", ["_tasks", "_migrations", "_jinja_extensions"])
def test_pack_declaring_code_running_settings_is_rejected(pack_dir: Path, setting: str) -> None:
    config = pack_dir / "copier.yml"
    config.write_text(f"{setting}: []\n{config.read_text(encoding='utf-8')}", encoding="utf-8")

    with pytest.raises(PackCheckError, match=setting):
        check_pack(pack_dir)


def test_pack_with_a_symlink_is_rejected(pack_dir: Path) -> None:
    (pack_dir / "tool" / "template" / "stolen").symlink_to("/etc/hosts")

    with pytest.raises(PackCheckError, match="symlink"):
        check_pack(pack_dir)


def test_invalid_manifest_is_rejected(pack_dir: Path) -> None:
    (pack_dir / "pytemplate-pack.toml").write_text("contract = 99\n", encoding="utf-8")

    with pytest.raises(PackCheckError, match="contract"):
        check_pack(pack_dir)


def test_missing_license_is_rejected(pack_dir: Path) -> None:
    (pack_dir / "LICENSE").unlink()

    with pytest.raises(PackCheckError, match="no license"):
        check_pack(pack_dir)


def test_symlink_is_rejected_when_adding(source: Path, fetcher: GitFetcher, tmp_path: Path) -> None:
    (source / "stolen").symlink_to("/etc/hosts")
    commit_all(source)
    git(source, "tag", "v2.0.0")

    with pytest.raises(FetchError, match="symlink"):
        _add(tmp_path / "index", fetcher, "v2.0.0")


def test_add_records_commit_digest_and_results(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    path = _add(tmp_path / "index", fetcher)

    assert path == tmp_path / "index" / "acme" / "sample-pack.toml"
    version = load_entry(path).versions[0]
    assert version.commit == git(source, "rev-parse", "v1.0.0")
    assert len(version.digest) == 64
    assert version.pack_version == "1.0.0"
    assert version.tier == "listed"
    assert version.profiles[0].lifecycle == "not-run"
    assert version.checked_with.startswith("pytemplate-uv==")


def test_add_appends_new_versions_and_refuses_a_duplicate(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    index = tmp_path / "index"
    _add(index, fetcher)
    commit_all(source)
    git(source, "tag", "v1.1.0")

    path = _add(index, fetcher, "v1.1.0")

    assert [version.tag for version in load_entry(path).versions] == ["v1.0.0", "v1.1.0"]
    with pytest.raises(PackCheckError, match="already lists"):
        _add(index, fetcher, "v1.1.0")


def test_a_different_repository_cannot_take_over_an_entry(
    fetcher: GitFetcher, tmp_path: Path
) -> None:
    index = tmp_path / "index"
    _add(index, fetcher)

    with pytest.raises(PackCheckError, match="already lists this pack"):
        add_version(index, "https://github.com/acme/other", "v1.0.0", "MIT", fetcher)


def test_add_refuses_a_non_github_repository(fetcher: GitFetcher, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository must look like"):
        add_version(tmp_path, "https://gitlab.com/acme/pack", "v1.0.0", "MIT", fetcher)


def test_verify_passes_for_an_unchanged_tag(fetcher: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", fetcher)

    assert verify_entry(path, fetcher) == []


def test_verify_reports_a_moved_tag(source: Path, fetcher: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", fetcher)
    (source / "README.md").write_text("changed\n", encoding="utf-8")
    commit_all(source)
    git(source, "tag", "--force", "v1.0.0")

    problems = verify_entry(path, fetcher)

    assert any("the commit changed" in problem for problem in problems)
    assert any("the digest changed" in problem for problem in problems)


def test_verify_reports_a_deleted_tag(source: Path, fetcher: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", fetcher)
    git(source, "tag", "--delete", "v1.0.0")

    assert any("v1.0.0" in problem for problem in verify_entry(path, fetcher))


def test_verify_skips_a_yanked_version(source: Path, fetcher: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", fetcher)
    entry = load_entry(path)
    yanked = entry.versions[0].model_copy(update={"yanked": "A bad release"})
    path.write_text(
        dump_entry(Entry(repository=entry.repository, versions=(yanked,))), encoding="utf-8"
    )
    git(source, "tag", "--delete", "v1.0.0")

    assert verify_entry(path, fetcher) == []


def test_verify_reports_a_malformed_entry(fetcher: GitFetcher, tmp_path: Path) -> None:
    path = tmp_path / "acme" / "pack.toml"
    path.parent.mkdir()
    path.write_text("not toml =", encoding="utf-8")

    assert len(verify_entry(path, fetcher)) == 1


def test_entry_files_lists_only_entries(fetcher: GitFetcher, tmp_path: Path) -> None:
    index = tmp_path / "index"
    path = _add(index, fetcher)
    (index / "README.md").write_text("notes\n", encoding="utf-8")

    assert entry_files(index) == [path]
