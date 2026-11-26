"""Tests for the listing checks and for re-verifying listed versions."""

import dataclasses
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytemplate import api

from pytemplate_hub import verify
from pytemplate_hub.errors import EntryError, FetchError, PackCheckError
from pytemplate_hub.fetch import GitFetcher
from pytemplate_hub.schema import (
    Entry,
    ProfileCheck,
    Version,
    dump_entry,
    load_entry,
    tag_problem,
)
from pytemplate_hub.verify import (
    Inspected,
    add_version,
    changed_claims,
    check_pack,
    entry_files,
    verify_entry,
    yank_version,
)
from tests.conftest import REPOSITORY, commit_all, git


def _add(index: Path, fetcher: GitFetcher, tag: str = "v1.0.0") -> Path:
    return add_version(index, REPOSITORY, tag, "MIT", fetcher)


def _version() -> Version:
    return Version(
        tag="v1.0.0",
        commit="a" * 40,
        digest="b" * 64,
        pack_version="1.0.0",
        license="MIT",
        checked_with="pytemplate-uv==3.0.0",
        profiles=(ProfileCheck(id="tool", lifecycle="not-run"),),
    )


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


def test_package_name_is_one_argument_in_a_lifecycle_command(
    pack_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = pack_dir / "tool" / "profile.toml"
    text = profile.read_text(encoding="utf-8")
    profile.write_text(
        text.replace('"uv run pytest"', '"uv run --with {package} pytest"'), encoding="utf-8"
    )
    real_plan = api.plan

    def spaced(request: api.RenderRequest) -> api.RenderPlan:
        return dataclasses.replace(real_plan(request), package_name="one two")

    monkeypatch.setattr(verify.api, "plan", spaced)
    calls: list[list[str]] = []

    def record(command: list[str], _: Path, __: dict[str, str]) -> tuple[bool, str]:
        calls.append(command)
        return True, ""

    check_pack(pack_dir, run_lifecycle=True, runner=record)

    assert calls[1] == ["uv", "run", "--with", "one two", "pytest"]


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


def test_render_request_has_no_unsafe_option() -> None:
    """Rendering runs Copier with ``unsafe=False`` (pytemplate-uv, rendering.py). A request has no
    field that can turn it on, so a pack cannot opt out of that protection through the hub."""
    names = {field.name for field in dataclasses.fields(api.RenderRequest)}

    assert not any("unsafe" in name for name in names)


def test_pack_with_a_symlink_is_rejected(pack_dir: Path) -> None:
    (pack_dir / "tool" / "template" / "stolen").symlink_to("/etc/hosts")

    with pytest.raises(PackCheckError, match="symlink"):
        check_pack(pack_dir)


def test_invalid_manifest_is_rejected(pack_dir: Path) -> None:
    (pack_dir / "pytemplate-pack.toml").write_text("contract = 99\n", encoding="utf-8")

    with pytest.raises(PackCheckError, match="contract"):
        check_pack(pack_dir)


@pytest.mark.parametrize(
    "manifest",
    [
        'contract = 1\nid = "tools"\nversion = "1.0.0"\ndescription = "A pack"\n',
        'contract = 1\nid = "tools"\nversion = "1.0.0"\nname = "Tools"\n',
        'contract = 1\nid = "tools"\nversion = "1.0.0"\nname = 7\ndescription = "A pack"\n',
        'contract = 1\nid = "tools"\nversion = "1.0.0"\nname = "Tools" = bad\n',
    ],
    ids=["no-name", "no-description", "name-not-text", "bad-toml"],
)
def test_manifest_without_text_name_and_description_is_a_pack_error(
    pack_dir: Path, manifest: str
) -> None:
    (pack_dir / "pytemplate-pack.toml").write_text(manifest, encoding="utf-8")

    with pytest.raises(PackCheckError, match=r"pytemplate-pack\.toml"):
        check_pack(pack_dir)


@pytest.mark.parametrize(
    "manifest",
    ['description = "A pack"\n', 'name = "Tools"\n', "name = 7\ndescription = 'x'\n", "name = ["],
    ids=["missing-name", "missing-description", "not-text", "bad-toml"],
)
def test_manifest_reader_refuses_a_missing_or_bad_name(tmp_path: Path, manifest: str) -> None:
    (tmp_path / "pytemplate-pack.toml").write_text(manifest, encoding="utf-8")

    with pytest.raises(PackCheckError, match=r"pytemplate-pack\.toml"):
        verify._manifest(tmp_path)


def test_manifest_reader_returns_name_and_description(tmp_path: Path) -> None:
    (tmp_path / "pytemplate-pack.toml").write_text(
        'name = "T"\ndescription = "D"\n', encoding="utf-8"
    )

    assert verify._manifest(tmp_path) == ("T", "D", (), ())


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


@pytest.mark.parametrize("pack_id", ["../../escape", "Tools", "a/b", "-leading", "a\n"])
def test_add_refuses_a_manifest_pack_id_that_is_not_allowed(
    pack_id: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def hostile(*_: object, **__: object) -> Inspected:
        return Inspected(pack_id, "Tools", "", _version())

    monkeypatch.setattr(verify, "inspect_version", hostile)
    index = tmp_path / "index"

    with pytest.raises(PackCheckError, match=r"pack id .* is not allowed"):
        add_version(index, REPOSITORY, "v1.0.0", "MIT", fetcher=None)  # type: ignore[arg-type]
    assert not index.exists()


@pytest.mark.parametrize("tag", ["v1..0", "v1.0.0.lock", "v1.", "v1.0@{x", "v1..", "a..b.lock"])
def test_add_refuses_a_tag_git_would_refuse_before_fetching(
    tag: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_fetch(*_: object, **__: object) -> Inspected:
        raise AssertionError("a tag git refuses must not be fetched")

    monkeypatch.setattr(verify, "inspect_version", no_fetch)
    index = tmp_path / "index"

    with pytest.raises(FetchError, match=r"cannot be fetched: .*"):
        add_version(index, REPOSITORY, tag, "MIT", fetcher=None)  # type: ignore[arg-type]
    assert not index.exists()


@pytest.mark.parametrize("tag", ["v1..0", "v1.0.0.lock", "v1."])
def test_version_refuses_a_tag_git_would_refuse(tag: str) -> None:
    with pytest.raises(ValidationError, match="not a valid git tag name"):
        _version().model_validate({**_version().model_dump(), "tag": tag})


def test_tag_rule_accepts_ordinary_tags() -> None:
    assert tag_problem("v1.0.0") is None
    assert tag_problem("v1.0.0-rc.1") is None


def test_add_refuses_a_non_github_repository(fetcher: GitFetcher, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repository must look like"):
        add_version(tmp_path, "https://gitlab.com/acme/pack", "v1.0.0", "MIT", fetcher)


def test_verify_passes_for_an_unchanged_tag(fetcher: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", fetcher)

    assert verify_entry(path, fetcher) == []


def test_add_records_the_pack_name_and_description(fetcher: GitFetcher, tmp_path: Path) -> None:
    entry = load_entry(_add(tmp_path / "index", fetcher))

    assert entry.name == "Sample pack"
    assert entry.description.startswith("A minimal template pack")


def test_verify_reports_a_faked_description(fetcher: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", fetcher)
    entry = load_entry(path)
    faked = entry.model_copy(update={"description": "Trusted by everyone"})
    path.write_text(dump_entry(faked), encoding="utf-8")

    assert any("the description changed" in problem for problem in verify_entry(path, fetcher))


def test_verify_compares_the_description_only_with_the_latest_version(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    index = tmp_path / "index"
    _add(index, fetcher)
    manifest = source / "pytemplate-pack.toml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace("A minimal template pack", "A better pack"), encoding="utf-8")
    commit_all(source)
    git(source, "tag", "v1.1.0")

    path = _add(index, fetcher, "v1.1.0")

    assert load_entry(path).description.startswith("A better pack")
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


def _write_entry(root: Path, entry: Entry) -> None:
    path = root / "acme" / "tools.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_entry(entry), encoding="utf-8")


def test_removed_version_message_says_to_yank(tmp_path: Path) -> None:
    base, head = tmp_path / "base", tmp_path / "head"
    _write_entry(base, Entry(repository=REPOSITORY, versions=(_version(),)))
    _write_entry(head, Entry(repository=REPOSITORY))

    assert changed_claims(base, head) == [
        "acme/tools.toml v1.0.0: removes a listed version; yank it instead."
    ]


def test_deleted_entry_file_is_reported(tmp_path: Path) -> None:
    base, head = tmp_path / "base", tmp_path / "head"
    _write_entry(base, Entry(repository=REPOSITORY, versions=(_version(),)))
    head.mkdir()

    problems = changed_claims(base, head)

    assert problems == ["acme/tools.toml: deletes a whole entry; yank its versions instead."]


def test_yanking_a_version_is_not_reported(tmp_path: Path) -> None:
    base, head = tmp_path / "base", tmp_path / "head"
    _write_entry(base, Entry(repository=REPOSITORY, versions=(_version(),)))
    yanked = _version().model_copy(update={"yanked": "A bad release"})
    _write_entry(head, Entry(repository=REPOSITORY, versions=(yanked,)))

    assert changed_claims(base, head) == []


def _detail_pack(pack_dir: Path, dependencies: str = '"rich>=13.7", "typer[all]"') -> GitFetcher:
    """Give the sample profile details, tag the pack, and return a fetcher for it."""
    profile = pack_dir / "tool" / "profile.toml"
    details = (
        'supported_python = ["3.11", "3.12"]\n'
        f"dependencies = [{dependencies}]\n"
        'security_posture = "Rendering contacts no service."\n\n[dependency_groups]'
    )
    profile.write_text(
        profile.read_text(encoding="utf-8").replace("[dependency_groups]", details),
        encoding="utf-8",
    )
    git(pack_dir, "init", "--quiet", "-b", "main")
    commit_all(pack_dir, "first")
    git(pack_dir, "tag", "v1.0.0")
    return GitFetcher(allowed_protocols="file", clone_url=lambda _: pack_dir.as_uri())


@pytest.fixture
def detailed(pack_dir: Path) -> GitFetcher:
    return _detail_pack(pack_dir)


def test_add_records_profile_details_and_the_check_date(
    detailed: GitFetcher, tmp_path: Path
) -> None:
    path = _add(tmp_path / "index", detailed)

    profile = load_entry(path).versions[0].profiles[0]

    assert (profile.name, profile.kind) == ("Sample tool", "library")
    assert profile.supported_python == ("3.11", "3.12")
    assert profile.dependencies == ("rich", "typer")
    assert profile.security_posture == "Rendering contacts no service."
    assert load_entry(path).versions[0].checked_on == datetime.now(UTC).date()
    assert "checked_on = " in path.read_text(encoding="utf-8")


def test_verify_passes_right_after_add(detailed: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", detailed)

    assert verify_entry(path, detailed) == []


def test_verify_reports_a_changed_profile_detail(detailed: GitFetcher, tmp_path: Path) -> None:
    path = _add(tmp_path / "index", detailed)
    path.write_text(path.read_text(encoding="utf-8").replace('kind = "library"', 'kind = "cli"'))

    problems = verify_entry(path, detailed)

    assert problems == [f"{path} v1.0.0: the profile tool kind changed: listed cli, found library."]


def test_details_an_entry_does_not_record_are_not_checked(
    detailed: GitFetcher, tmp_path: Path
) -> None:
    path = _add(tmp_path / "index", detailed)
    entry = load_entry(path)
    bare = entry.model_copy(
        update={
            "categories": None,
            "keywords": None,
            "versions": (
                entry.versions[0].model_copy(
                    update={
                        "checked_on": None,
                        "profiles": (ProfileCheck(id="tool", lifecycle="not-run"),),
                    }
                ),
            ),
        }
    )
    path.write_text(dump_entry(bare), encoding="utf-8")

    assert verify_entry(path, detailed) == []


def test_recorded_detail_still_fails_when_others_are_not_recorded(
    detailed: GitFetcher, tmp_path: Path
) -> None:
    path = _add(tmp_path / "index", detailed)
    entry = load_entry(path)
    partly = entry.model_copy(
        update={
            "versions": (
                entry.versions[0].model_copy(
                    update={"profiles": (ProfileCheck(id="tool", lifecycle="passed", kind="cli"),)}
                ),
            ),
        }
    )
    path.write_text(dump_entry(partly), encoding="utf-8")

    problems = verify_entry(path, detailed)

    assert problems == [f"{path} v1.0.0: the profile tool kind changed: listed cli, found library."]


def test_categories_and_keywords_an_entry_does_not_record_are_not_checked(
    fetcher: GitFetcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _add(tmp_path / "index", fetcher)
    entry = load_entry(path)
    path.write_text(
        dump_entry(entry.model_copy(update={"categories": None, "keywords": None})),
        encoding="utf-8",
    )
    real = verify.inspect_version

    def with_categories(*args: object, **kwargs: object) -> Inspected:
        found = real(*args, **kwargs)  # type: ignore[arg-type]
        return dataclasses.replace(found, categories=("web",), keywords=("api",))

    monkeypatch.setattr(verify, "inspect_version", with_categories)

    assert verify_entry(path, fetcher) == []


def test_add_refuses_a_profile_dependency_with_no_name(tmp_path: Path, pack_dir: Path) -> None:
    fetcher = _detail_pack(pack_dir, dependencies='">=1.0"')

    with pytest.raises(PackCheckError, match="has no package name"):
        _add(tmp_path / "index", fetcher)


def test_add_copies_categories_and_keywords_from_the_pack(
    fetcher: GitFetcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = verify.inspect_version

    def with_categories(*args: object, **kwargs: object) -> Inspected:
        found = real(*args, **kwargs)  # type: ignore[arg-type]
        return dataclasses.replace(found, categories=("cli", "ai"), keywords=("polars",))

    monkeypatch.setattr(verify, "inspect_version", with_categories)
    path = _add(tmp_path / "index", fetcher)

    entry = load_entry(path)
    assert entry.categories == ("cli", "ai")
    assert entry.keywords == ("polars",)
    assert verify_entry(path, fetcher) == []


def test_verify_reports_categories_and_keywords_that_the_pack_no_longer_has(
    fetcher: GitFetcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _add(tmp_path / "index", fetcher)
    real = verify.inspect_version

    def changed(*args: object, **kwargs: object) -> Inspected:
        found = real(*args, **kwargs)  # type: ignore[arg-type]
        return dataclasses.replace(found, categories=("web",), keywords=("api",))

    monkeypatch.setattr(verify, "inspect_version", changed)

    problems = verify_entry(path, fetcher)

    assert (
        f"{path} v1.0.0: the categories changed: listed ('library',), found ('web',)." in problems
    )
    assert f"{path} v1.0.0: the keywords changed: listed (), found ('api',)." in problems


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ('categories = ["gardening"]\n', "unknown category 'gardening'. Use one of: cli"),
        ('categories = ["cli", "cli"]\n', "each category may be listed only once"),
        ('categories = "cli"\n', "`categories` must be a list of text strings"),
        ('keywords = ["Polars"]\n', "keyword 'Polars' is not allowed"),
    ],
)
def test_manifest_refuses_a_bad_category_or_keyword(
    tmp_path: Path, manifest: str, message: str
) -> None:
    (tmp_path / "pytemplate-pack.toml").write_text(
        'name = "T"\ndescription = "D"\n' + manifest, encoding="utf-8"
    )

    with pytest.raises(PackCheckError, match=re.escape(message)):
        verify._manifest(tmp_path)


def test_manifest_reads_categories_and_keywords(tmp_path: Path) -> None:
    (tmp_path / "pytemplate-pack.toml").write_text(
        'name = "T"\ndescription = "D"\ncategories = ["web", "ai"]\nkeywords = ["fastapi"]\n',
        encoding="utf-8",
    )

    assert verify._manifest(tmp_path) == ("T", "D", ("web", "ai"), ("fastapi",))


def test_add_refuses_a_pack_that_declares_no_category(
    fetcher: GitFetcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = verify.inspect_version

    def without(*args: object, **kwargs: object) -> Inspected:
        found = real(*args, **kwargs)  # type: ignore[arg-type]
        return dataclasses.replace(found, categories=())

    monkeypatch.setattr(verify, "inspect_version", without)

    with pytest.raises(
        PackCheckError, match=r"declares no categories.*one or two of: cli, library"
    ):
        _add(tmp_path / "index", fetcher)
    assert not (tmp_path / "index").exists()


def test_yank_sets_only_the_yanked_field(source: Path, fetcher: GitFetcher, tmp_path: Path) -> None:
    index = tmp_path / "index"
    base = tmp_path / "base"
    _add(index, fetcher)
    shutil.copytree(index, base)
    before = load_entry(index / "acme" / "sample-pack.toml")

    path = yank_version(index, "acme", "sample-pack", "v1.0.0", "  Fails on 3.13.  ")

    assert path == index / "acme" / "sample-pack.toml"
    after = load_entry(path)
    assert after.versions[0].yanked == "Fails on 3.13."
    assert after.versions[0].model_copy(update={"yanked": None}) == before.versions[0]
    assert after.model_copy(update={"versions": before.versions}) == before
    assert changed_claims(base, index) == []


def test_yank_refuses_an_unknown_entry(tmp_path: Path) -> None:
    with pytest.raises(EntryError, match="does not exist"):
        yank_version(tmp_path / "index", "acme", "sample-pack", "v1.0.0", "Broken")


def test_yank_refuses_an_unknown_tag_and_lists_the_tags(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    index = tmp_path / "index"
    _add(index, fetcher)

    with pytest.raises(EntryError, match=r"Listed tags: v1\.0\.0\."):
        yank_version(index, "acme", "sample-pack", "v9.9.9", "Broken")


def test_yank_refuses_a_version_already_yanked(
    source: Path, fetcher: GitFetcher, tmp_path: Path
) -> None:
    index = tmp_path / "index"
    _add(index, fetcher)
    yank_version(index, "acme", "sample-pack", "v1.0.0", "First reason")

    with pytest.raises(EntryError, match="First reason"):
        yank_version(index, "acme", "sample-pack", "v1.0.0", "Second reason")


@pytest.mark.parametrize("reason", ["", "   \n\t "])
def test_yank_refuses_an_empty_reason(
    source: Path, fetcher: GitFetcher, tmp_path: Path, reason: str
) -> None:
    index = tmp_path / "index"
    _add(index, fetcher)

    with pytest.raises(EntryError, match="needs a reason"):
        yank_version(index, "acme", "sample-pack", "v1.0.0", reason)
    assert load_entry(index / "acme" / "sample-pack.toml").versions[0].yanked is None


@pytest.mark.parametrize(("owner", "pack_id"), [("ac/me", "sample-pack"), ("acme", "Sample_Pack")])
def test_yank_validates_owner_and_pack_id_before_building_a_path(
    tmp_path: Path, owner: str, pack_id: str
) -> None:
    with pytest.raises(EntryError, match="not a valid entry"):
        yank_version(tmp_path / "index", owner, pack_id, "v1.0.0", "Broken")
    assert not (tmp_path / "index").exists()
