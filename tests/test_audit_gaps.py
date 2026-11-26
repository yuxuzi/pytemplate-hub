"""Gaps found by the launch audit (docs/audit.md).

Each test states the behaviour the hub has once a gap is fixed. Gaps the maintainer decided to
accept (the executable bit) have no test here; see docs/audit.md, Resolution (2026-11-25).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytemplate_hub import verify
from pytemplate_hub.errors import HubError
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


def test_removing_a_listed_version_is_reported(tmp_path: Path) -> None:
    base = tmp_path / "base"
    head = tmp_path / "head"
    listed = Entry(repository=REPOSITORY, versions=(_version(),))
    for root, entry in ((base, listed), (head, Entry(repository=REPOSITORY))):
        path = root / "acme" / "tools.toml"
        path.parent.mkdir(parents=True)
        path.write_text(dump_entry(entry), encoding="utf-8")

    assert changed_claims(base, head) != []
