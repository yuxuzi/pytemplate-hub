"""Tests for the static site."""

import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from pytemplate_hub.errors import EntryError
from pytemplate_hub.schema import Entry, ProfileCheck, Version, dump_entry, load_entry
from pytemplate_hub.site import _card, build_site, create_command, github_stars, no_stars

ATTACK = '<script>alert(1)</script>" onmouseover="alert(2)'


def _version(tag: str = "v1.0.0", **changes: object) -> Version:
    fields: dict[str, object] = {
        "tag": tag,
        "commit": "a" * 40,
        "digest": "b" * 64,
        "pack_version": "1.0.0",
        "license": "MIT",
        "checked_with": "pytemplate-uv==3.0.0",
        "profiles": (ProfileCheck(id="tool", lifecycle="passed"),),
    }
    return Version.model_validate({**fields, **changes})


def _index(tmp_path: Path, *versions: Version, **fields: str) -> Path:
    index = tmp_path / "index"
    (index / "acme").mkdir(parents=True)
    entry = Entry(repository="https://github.com/acme/repo", versions=versions, **fields)
    (index / "acme" / "tools.toml").write_text(dump_entry(entry), encoding="utf-8")
    return index


def _build(index: Path, tmp_path: Path, stars: Any = no_stars) -> tuple[int, str, dict[str, Any]]:
    output = tmp_path / "site"
    shown = build_site(index, output, stars=stars, built_on="2026-11-04")
    page = (output / "index.html").read_text(encoding="utf-8")
    return shown, page, json.loads((output / "index.json").read_text(encoding="utf-8"))


def test_page_shows_the_pack_and_its_exact_command(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(), name="Tools", description="Useful tools")

    shown, page, data = _build(index, tmp_path, stars=lambda _: 7)

    assert shown == 1
    assert "Useful tools" in page
    assert "7 stars" in page
    assert "--template gh:acme/repo --template-ref v1.0.0" in page
    assert "https://github.com/acme/repo/issues" in page
    assert data["packs"][0]["id"] == "tools"
    assert data["packs"][0]["versions"][0]["commit"] == "a" * 40


def test_commands_wrap_so_the_pinned_tag_stays_visible(tmp_path: Path) -> None:
    _, page, _ = _build(_index(tmp_path, _version()), tmp_path)

    assert "white-space: pre-wrap" in page
    assert "overflow-x: auto" not in page


def test_page_says_listed_does_not_mean_safe(tmp_path: Path) -> None:
    _, page, _ = _build(_index(tmp_path, _version()), tmp_path)

    assert "Listed does not mean safe." in page


def test_untrusted_text_is_escaped(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(yanked=None), name=ATTACK, description=ATTACK)

    _, page, _ = _build(index, tmp_path)

    assert "<script>alert" not in page
    assert '" onmouseover="' not in page
    assert page.count("<script>") == 1


def test_commit_in_the_title_attribute_is_escaped() -> None:
    # model_copy skips validation, so the commit can hold a quote that a real entry never could.
    hostile = _version().model_copy(update={"commit": 'x" onmouseover="alert(3)'})
    entry = Entry(repository="https://github.com/acme/repo", versions=(hostile,))

    card = _card(entry, {"id": "tools", "stars": None})

    assert 'onmouseover="' not in card
    assert "x&quot; onmouseover=&quot;alert(3)" in card


def test_page_script_never_builds_html(tmp_path: Path) -> None:
    _, page, _ = _build(_index(tmp_path, _version()), tmp_path)

    assert "innerHTML" not in page
    assert "document.write" not in page


def test_page_loads_nothing_from_other_sites(tmp_path: Path) -> None:
    _, page, _ = _build(_index(tmp_path, _version()), tmp_path)

    assert "src=" not in page
    assert "stylesheet" not in page


def test_unknown_stars_are_labelled_rather_than_zero(tmp_path: Path) -> None:
    _, page, data = _build(_index(tmp_path, _version()), tmp_path)

    assert "stars unavailable" in page
    assert data["packs"][0]["stars"] is None


def test_yanked_latest_falls_back_to_the_previous_version(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(), _version("v2.0.0", yanked="Broken"))

    shown, page, data = _build(index, tmp_path)

    assert shown == 1
    assert "--template-ref v1.0.0" in page
    assert "v2.0.0" not in page
    assert data["packs"][0]["latest"] == "v1.0.0"
    assert [version["tag"] for version in data["packs"][0]["versions"]] == ["v1.0.0", "v2.0.0"]


def test_fully_yanked_pack_leaves_the_page_but_stays_in_the_data(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(yanked="Broken"), name="Gone")

    shown, page, data = _build(index, tmp_path)

    assert shown == 0
    assert "Gone" not in page
    assert "No packs are listed yet." in page
    assert data["packs"][0]["latest"] is None


def test_reviewed_pack_names_its_reviewer(tmp_path: Path) -> None:
    _, page, data = _build(_index(tmp_path, _version(reviewed_by="octocat")), tmp_path)

    assert "Reviewed by octocat" in page
    assert data["packs"][0]["versions"][0]["tier"] == "reviewed"


def test_malformed_entry_fails_the_build(tmp_path: Path) -> None:
    index = _index(tmp_path, _version())
    (index / "acme" / "tools.toml").write_text("not toml =", encoding="utf-8")

    with pytest.raises(EntryError):
        build_site(index, tmp_path / "site", stars=no_stars, built_on="2026-11-04")


@pytest.mark.parametrize("profile", ["x; rm -rf ~", "$(whoami)", "x y", "`id`", "-p"])
def test_profile_ids_cannot_inject_into_the_copied_command(profile: str) -> None:
    with pytest.raises(ValueError, match="id"):
        ProfileCheck(id=profile, lifecycle="passed")


def test_create_command_is_exact() -> None:
    entry = Entry(repository="https://github.com/Acme/repo")

    command = create_command(entry, _version(), "tool")

    assert command == (
        "uvx pytemplate-uv@latest create my-project -p tool "
        "--template gh:Acme/repo --template-ref v1.0.0 "
        f"--template-commit {'a' * 40} --template-digest {'b' * 64} -y"
    )


def test_non_ascii_text_round_trips(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(), description='Données 📈 \x7f "quoted"\nline')

    assert load_entry(index / "acme" / "tools.toml").description.startswith("Données 📈")


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def test_github_stars_reads_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(request: urllib.request.Request, timeout: float) -> _Response:
        seen.append(request.full_url)
        return _Response(b'{"stargazers_count": 28}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)

    assert github_stars(Entry(repository="https://github.com/acme/repo")) == 28
    assert seen == ["https://api.github.com/repos/acme/repo"]


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"stargazers_count": "many"}', b"{}"])
def test_github_stars_is_none_for_a_bad_response(
    body: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_, **__: _Response(body))

    assert github_stars(Entry(repository="https://github.com/acme/repo")) is None


def test_github_stars_is_none_when_github_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object, **__: object) -> None:
        raise OSError("no network")

    monkeypatch.setattr(urllib.request, "urlopen", fail)

    assert github_stars(Entry(repository="https://github.com/acme/repo")) is None
