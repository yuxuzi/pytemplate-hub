"""The catalog page, the pack pages, and the data behind their filters and ranking."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pytemplate_hub.schema import Entry, ProfileCheck, Version, dump_entry
from pytemplate_hub.site import build_site
from pytemplate_hub.site.data import recommended, stack_of

HOSTILE = "<script>alert('x')</script>\" onmouseover=\"alert(2)"


def _profile(profile_id: str = "tool", **details: object) -> ProfileCheck:
    return ProfileCheck.model_validate({"id": profile_id, "lifecycle": "passed", **details})


def _version(**changes: object) -> Version:
    fields: dict[str, object] = {
        "tag": "v1.0.0",
        "commit": "a" * 40,
        "digest": "b" * 64,
        "pack_version": "1.0.0",
        "license": "MIT",
        "checked_with": "pytemplate-uv==3.6.0",
        "checked_on": date(2026, 11, 20),
        "profiles": (_profile(),),
    }
    return Version.model_validate({**fields, **changes})


def _site(tmp_path: Path, *packs: tuple[str, str, Entry]) -> Path:
    index = tmp_path / "index"
    for owner, pack_id, entry in packs:
        (index / owner).mkdir(parents=True, exist_ok=True)
        (index / owner / f"{pack_id}.toml").write_text(dump_entry(entry), encoding="utf-8")
    index.mkdir(exist_ok=True)
    output = tmp_path / "site"
    build_site(index, output, stars=lambda _: 3, built_on="2026-11-25")
    return output


def _entry(owner: str = "acme", *versions: Version, **fields: object) -> Entry:
    return Entry(
        repository=f"https://github.com/{owner}/repo",
        versions=versions or (_version(),),
        **fields,  # type: ignore[arg-type]
    )


def _catalog(output: Path) -> str:
    return (output / "templates" / "index.html").read_text(encoding="utf-8")


def test_stack_comes_from_known_names_in_dependencies_and_keywords() -> None:
    assert stack_of(("fastapi", "SQLAlchemy", "pytest", "fastapi", "polars")) == (
        "FastAPI",
        "SQLAlchemy",
        "Polars",
    )
    assert stack_of(("unknown-thing",)) == ()


@pytest.mark.parametrize(
    ("changes", "stars", "expected"),
    [
        ({}, 0, 0.54),  # listed, every profile passed, fresh, no stars
        ({"reviewed_by": "octocat"}, 999, 1.0),
        ({"checked_on": date(2025, 11, 25)}, 0, 0.24),  # a year old: freshness 0
        ({"profiles": (ProfileCheck(id="tool", lifecycle="not-run"),)}, 0, 0.42),
        ({"checked_on": None}, 0, 0.24),
    ],
)
def test_recommended_follows_the_published_formula(
    changes: dict[str, object], stars: int, expected: float
) -> None:
    assert recommended(_version(**changes), stars, "2026-11-25") == pytest.approx(
        expected, abs=1e-3
    )


def test_the_catalog_lists_every_pack_with_its_filter_data(tmp_path: Path) -> None:
    detailed = _version(
        profiles=(_profile("api", kind="service", supported_python=("3.12", "3.13")),),
    )
    output = _site(
        tmp_path,
        ("acme", "web", _entry("acme", detailed, categories=("web",), keywords=("fastapi",))),
        ("other", "lib", _entry("other", categories=("library",))),
    )
    page = _catalog(output)

    assert page.count("data-pack ") == 2
    assert 'data-category="web"' in page
    assert 'data-kind="service"' in page
    assert 'data-stack="FastAPI"' in page
    assert 'data-python="3.12 3.13"' in page
    assert 'href="acme/web/index.html"' in page


def test_filters_show_only_values_some_pack_has_with_counts(tmp_path: Path) -> None:
    output = _site(
        tmp_path,
        ("acme", "one", _entry("acme", categories=("web", "cli"))),
        ("acme", "two", _entry("acme", categories=("web",))),
    )
    page = _catalog(output)

    web = page.split('data-facet="category" value="web"', 1)[1].split("</label>", 1)[0]
    assert '<span class="n" data-count>2</span>' in web
    assert 'value="cli"' in page
    assert 'value="quant"' not in page
    assert 'value="worker"' not in page


def test_each_pack_has_a_page_with_a_builder_and_both_commands(tmp_path: Path) -> None:
    output = _site(tmp_path, ("acme", "tools", _entry("acme", name="Tools", categories=("cli",))))
    page = (output / "templates" / "acme" / "tools" / "index.html").read_text(encoding="utf-8")

    assert "<title>Tools · Pytemplate Hub</title>" in page
    assert 'data-pack="acme/tools"' in page
    assert 'data-source="gh:acme/repo"' in page
    assert "create my-project -h acme/tools@v1.0.0 -p tool -y" in page
    assert "--template-digest " + "b" * 64 in page
    assert 'href="../../../templates/index.html?category=cli"' in page


def test_similar_packs_share_a_category(tmp_path: Path) -> None:
    output = _site(
        tmp_path,
        ("acme", "one", _entry("acme", name="One", categories=("data",))),
        ("acme", "two", _entry("acme", name="Two", categories=("data",))),
        ("acme", "three", _entry("acme", name="Three", categories=("web",))),
    )
    page = (output / "templates" / "acme" / "one" / "index.html").read_text(encoding="utf-8")

    similar = page.split("Similar packs", 1)[1]
    assert "Two" in similar
    assert "Three" not in similar


def test_entry_text_is_escaped_on_the_catalog_and_pack_pages(tmp_path: Path) -> None:
    output = _site(tmp_path, ("acme", "tools", _entry("acme", name=HOSTILE, description=HOSTILE)))

    for page in (_catalog(output), (output / "templates/acme/tools/index.html").read_text("utf-8")):
        assert "<script>alert" not in page
        assert '" onmouseover="' not in page


def test_home_tiles_and_search_lead_to_the_catalog(tmp_path: Path) -> None:
    output = _site(tmp_path, ("acme", "tools", _entry("acme", categories=("cli",))))
    home = (output / "index.html").read_text(encoding="utf-8")

    assert 'href="templates/index.html?category=cli"' in home
    assert 'action="templates/index.html"' in home
    assert "None yet" in home.split('data-category="quant"', 1)[1].split("</a>", 1)[0]


def test_the_catalog_says_so_when_nothing_is_listed(tmp_path: Path) -> None:
    output = _site(tmp_path)

    assert "No packs are listed yet." in _catalog(output)
