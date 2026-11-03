"""Tests for the index entry format."""

from pathlib import Path

import pytest

from pytemplate_hub.errors import EntryError
from pytemplate_hub.schema import Entry, ProfileCheck, Version, dump_entry, load_entry


def _version(tag: str = "v1.0.0", **changes: str) -> Version:
    fields: dict[str, object] = {
        "tag": tag,
        "commit": "a" * 40,
        "digest": "b" * 64,
        "pack_version": "1.0.0",
        "license": "MIT",
        "checked_with": "pytemplate-uv==3.0.0",
        "profiles": (ProfileCheck(id="tool", lifecycle="not-run"),),
    }
    return Version.model_validate({**fields, **changes})


def _write(tmp_path: Path, entry: Entry, owner: str = "acme", name: str = "tools") -> Path:
    path = tmp_path / owner / f"{name}.toml"
    path.parent.mkdir(parents=True)
    path.write_text(dump_entry(entry), encoding="utf-8")
    return path


def test_round_trip(tmp_path: Path) -> None:
    entry = Entry(repository="https://github.com/Acme/tools", versions=(_version(),))

    assert load_entry(_write(tmp_path, entry)) == entry


def test_round_trip_keeps_review_and_yank(tmp_path: Path) -> None:
    version = _version(reviewed_by="octocat", yanked='a "bad" release')
    entry = Entry(repository="https://github.com/acme/tools", versions=(version,))

    loaded = load_entry(_write(tmp_path, entry))

    assert loaded == entry
    assert loaded.versions[0].tier == "reviewed"


def test_unreviewed_version_is_listed() -> None:
    assert _version().tier == "listed"


def test_self_declared_quality_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "acme" / "tools.toml"
    path.parent.mkdir()
    path.write_text(
        'repository = "https://github.com/acme/tools"\n[quality]\ntests = true\n', encoding="utf-8"
    )

    with pytest.raises(EntryError, match="quality"):
        load_entry(path)


@pytest.mark.parametrize(
    "repository",
    [
        "http://github.com/acme/tools",
        "https://gitlab.com/acme/tools",
        "https://github.com/acme/tools.git",
        "https://github.com/acme/tools/../other",
        "file:///etc/acme/tools",
    ],
)
def test_only_github_https_repositories_are_accepted(repository: str) -> None:
    with pytest.raises(ValueError, match="repository must look like"):
        Entry(repository=repository)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tag", "--upload-pack=evil"),
        ("tag", "refs/heads/main"),
        ("commit", "v1.0.0"),
        ("digest", "short"),
        ("license", ""),
    ],
)
def test_malformed_version_fields_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        _version(**{field: value})


def test_duplicate_tags_are_rejected() -> None:
    with pytest.raises(ValueError, match="only once"):
        Entry(repository="https://github.com/acme/tools", versions=(_version(), _version()))


def test_directory_must_match_the_repository_owner(tmp_path: Path) -> None:
    entry = Entry(repository="https://github.com/acme/tools")

    with pytest.raises(EntryError, match="repository owner"):
        load_entry(_write(tmp_path, entry, owner="impostor"))


def test_file_name_must_be_a_pack_id(tmp_path: Path) -> None:
    entry = Entry(repository="https://github.com/acme/tools")

    with pytest.raises(EntryError, match="pack id"):
        load_entry(_write(tmp_path, entry, name="Not_A_Slug"))
