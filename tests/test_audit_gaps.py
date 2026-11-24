"""Gaps found by the launch audit (docs/audit.md).

Each test states the behaviour the hub should have. Every test is xfail(strict=True): it fails
today, and its marker must be removed when the gap is fixed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytemplate_hub import verify
from pytemplate_hub.errors import HubError
from pytemplate_hub.fetch import directory_digest
from pytemplate_hub.schema import Entry, ProfileCheck, Version, dump_entry, load_entry
from pytemplate_hub.verify import Inspected, add_version, changed_claims

REPOSITORY = "https://github.com/acme/tools"


def _version(tag: str = "v1.0.0") -> Version:
    return Version(
        tag=tag,
        commit="a" * 40,
        digest="b" * 64,
        pack_version="1.0.0",
        license="MIT",
        checked_with="pytemplate-uv==3.0.0",
        profiles=(ProfileCheck(id="tool", lifecycle="not-run"),),
    )


def test_non_utf8_entry_is_reported_as_an_entry_error(tmp_path: Path) -> None:
    path = tmp_path / "acme" / "tools.toml"
    path.parent.mkdir()
    path.write_bytes(
        b'format = 1\nrepository = "' + REPOSITORY.encode() + b'"\ndescription = "\xff\xfe"\n'
    )

    from pytemplate_hub.errors import EntryError

    with pytest.raises(EntryError):
        load_entry(path)


@pytest.mark.xfail(
    strict=True,
    reason="audit tag and commit validation: a repository named '..' or '.' is accepted",
)
@pytest.mark.parametrize("repository", ["https://github.com/acme/..", "https://github.com/acme/."])
def test_repository_name_cannot_be_a_dot_segment(repository: str) -> None:
    with pytest.raises(ValueError):
        Entry(repository=repository)


def test_manifest_pack_id_cannot_escape_the_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hostile(*_: object, **__: object) -> Inspected:
        return Inspected("../../escape", "Tools", "", _version())

    monkeypatch.setattr(verify, "inspect_version", hostile)
    index = tmp_path / "index"

    with pytest.raises(HubError):
        add_version(index, REPOSITORY, "v1.0.0", "MIT", fetcher=None)  # type: ignore[arg-type]
    assert not (tmp_path / "escape.toml").exists()


@pytest.mark.xfail(
    strict=True,
    reason="audit reviewed status: a change that deletes a listed version passes check-claims",
)
def test_removing_a_listed_version_is_reported(tmp_path: Path) -> None:
    base = tmp_path / "base"
    head = tmp_path / "head"
    listed = Entry(repository=REPOSITORY, versions=(_version(),))
    for root, entry in ((base, listed), (head, Entry(repository=REPOSITORY))):
        path = root / "acme" / "tools.toml"
        path.parent.mkdir(parents=True)
        path.write_text(dump_entry(entry), encoding="utf-8")

    assert changed_claims(base, head) != []


@pytest.mark.xfail(
    strict=True,
    reason="audit digest: the executable bit is not hashed, so a mode change keeps the digest",
)
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_digest_changes_when_a_file_becomes_executable(tmp_path: Path) -> None:
    script = tmp_path / "run.sh"
    script.write_text("echo hi\n", encoding="utf-8")
    script.chmod(0o644)
    before = directory_digest(tmp_path)
    script.chmod(0o755)

    assert directory_digest(tmp_path) != before
