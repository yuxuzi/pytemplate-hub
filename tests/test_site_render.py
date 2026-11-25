"""The rendered page: built offline, entry text escaped, links and assets present, titled."""

from __future__ import annotations

import json
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from pytemplate_hub.schema import Entry, ProfileCheck, Version, dump_entry
from pytemplate_hub.site import build_site, no_stars
from pytemplate_hub.site.render import STATIC_DIR, TEMPLATE_DIR

HOSTILE = "<script>alert('x')</script> & <img src=x onerror=alert(1)>"


class _Page(HTMLParser):
    """Collects the references, ids, and title text of one HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: set[str] = set()
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        for name, value in attrs:
            if value is None:
                continue
            if name in ("href", "src"):
                self.refs.append(value)
            if name == "id":
                self.ids.add(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _version(**changes: object) -> Version:
    fields: dict[str, object] = {
        "tag": "v1.0.0",
        "commit": "a" * 40,
        "digest": "b" * 64,
        "pack_version": "1.0.0",
        "license": "MIT",
        "checked_with": "pytemplate-uv==3.0.0",
        "profiles": (ProfileCheck(id="tool", lifecycle="passed"),),
    }
    return Version.model_validate({**fields, **changes})


def _index(root: Path, *packs: tuple[str, Entry]) -> Path:
    index = root / "index"
    for pack_id, entry in packs:
        folder = index / entry.owner if entry.owner else index / "acme"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{pack_id}.toml").write_text(dump_entry(entry), encoding="utf-8")
    return index


def _entry(*versions: Version, **fields: object) -> Entry:
    return Entry(repository="https://github.com/acme/repo", versions=versions, **fields)


def _build(index: Path, output: Path) -> str:
    build_site(index, output, stars=no_stars, built_on="2026-11-25")
    return (output / "index.html").read_text(encoding="utf-8")


def _parse(page: str) -> _Page:
    parser = _Page()
    parser.feed(page)
    return parser


def test_build_is_offline_and_writes_all_outputs(tmp_path: Path) -> None:
    index = _index(tmp_path, ("tools", _entry(_version(), name="Tools", description="Useful")))
    output = tmp_path / "site"

    shown = build_site(index, output, stars=no_stars, built_on="2026-11-25")

    assert shown == 1
    for name in ("index.html", "index.json", "index.schema.json"):
        assert (output / name).is_file(), name
    for asset in ("css/site.css", "js/copy.js", "js/spotlight.js", "js/filter.js"):
        assert (output / "static" / asset).is_file(), asset
    assert (output / "static" / "favicon.svg").is_file()
    assert (output / "static" / "logo.svg").is_file()


def test_entry_text_is_escaped_everywhere(tmp_path: Path) -> None:
    entry = _entry(_version(), name=HOSTILE, description=HOSTILE)
    page = _build(_index(tmp_path, ("tools", entry)), tmp_path / "site")

    assert "<img src=x" not in page
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;" in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page


def test_every_relative_link_and_asset_exists(tmp_path: Path) -> None:
    output = tmp_path / "site"
    index = _index(tmp_path, ("tools", _entry(_version(), name="Tools")))
    page = _parse(_build(index, output))

    assert page.refs
    for ref in page.refs:
        if ref.startswith(("http://", "https://", "mailto:", "//")):
            continue
        if ref.startswith("#"):
            assert ref[1:] in page.ids, f"fragment {ref} has no matching id"
            continue
        assert (output / ref).is_file(), f"{ref} is missing from the build"


def test_every_page_has_a_title(tmp_path: Path) -> None:
    page = _parse(_build(_index(tmp_path, ("tools", _entry(_version()))), tmp_path / "site"))

    assert page.title.strip() == "Pytemplate Hub"


def test_the_page_renders_the_empty_index(tmp_path: Path) -> None:
    empty = tmp_path / "index"
    empty.mkdir()
    page = _build(empty, tmp_path / "site")

    assert "No packs are listed yet." in page


def test_category_tiles_count_the_listed_packs(tmp_path: Path) -> None:
    index = _index(
        tmp_path,
        ("tools", _entry(_version(), categories=("cli", "ai"))),
        ("api", _entry(_version(), categories=("web",))),
        ("gone", _entry(_version(yanked="Broken"), categories=("cli",))),
    )
    page = _build(index, tmp_path / "site")

    assert 'data-category="cli"' in page
    cli_tile = page.split('data-category="cli"', 1)[1].split("</a>", 1)[0]
    assert "1 listed" in cli_tile
    ai_tile = page.split('data-category="ai"', 1)[1].split("</a>", 1)[0]
    assert "1 listed" in ai_tile
    web_tile = page.split('data-category="web"', 1)[1].split("</a>", 1)[0]
    assert "1 listed" in web_tile


def test_each_profile_has_a_short_command_and_a_pinned_one(tmp_path: Path) -> None:
    entry = _entry(_version(), name="Tools")
    page = _build(_index(tmp_path, ("tools", entry)), tmp_path / "site")

    short = "uvx pytemplate-uv@latest create my-project -h acme/tools@v1.0.0 -p tool -y"
    pinned = (
        "uvx pytemplate-uv@latest create my-project -p tool --template gh:acme/repo "
        "--template-ref v1.0.0 --template-commit "
        + "a" * 40
        + " --template-digest "
        + "b" * 64
        + " -y"
    )
    assert f'data-copy="{short}"' in page
    assert f"<pre><code>{short}</code></pre>" in page
    assert f'data-copy="{pinned}"' in page
    assert "Fully pinned (CI, offline)" in page


def test_the_pinned_command_sits_in_a_details_block(tmp_path: Path) -> None:
    page = _build(_index(tmp_path, ("tools", _entry(_version()))), tmp_path / "site")

    details = page.split('<details class="pinned">', 1)[1].split("</details>", 1)[0]
    assert "--template-digest" in details
    assert "-h " not in details


def test_the_hero_shows_the_short_command_of_the_first_pack(tmp_path: Path) -> None:
    page = _build(_index(tmp_path, ("tools", _entry(_version()))), tmp_path / "site")

    hero = page.split('id="slide-0"', 1)[1].split('id="slide-1"', 1)[0]
    assert "create my-project -h acme/tools@v1.0.0 -p tool -y" in hero


def test_scripts_only_show_and_hide_never_build_html() -> None:
    for script in (STATIC_DIR / "js").glob("*.js"):
        source = script.read_text(encoding="utf-8")
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            assert banned not in source, f"{script.name} uses {banned}"


def test_templates_never_mark_entry_data_safe() -> None:
    for template in TEMPLATE_DIR.rglob("*.html"):
        assert "|safe" not in template.read_text(encoding="utf-8"), template.name


def test_index_json_is_unchanged_in_shape(tmp_path: Path) -> None:
    output = tmp_path / "site"
    _build(_index(tmp_path, ("tools", _entry(_version(), name="Tools"))), output)

    data = json.loads((output / "index.json").read_text(encoding="utf-8"))

    assert data["format"] == 1
    assert data["built_on"] == "2026-11-25"
    assert data["packs"][0]["id"] == "tools"


def test_the_page_names_no_consumer_and_no_draft(tmp_path: Path) -> None:
    page = _build(_index(tmp_path, ("tools", _entry(_version(), name="Tools"))), tmp_path / "site")

    assert "Quant-Agent-OS" not in page
    assert "Draft" not in page
    assert "gh:yuxuzi" not in page


def test_the_spotlight_has_three_slides_labelled_in_order(tmp_path: Path) -> None:
    page = _build(_index(tmp_path, ("tools", _entry(_version()))), tmp_path / "site")

    assert page.count("data-slide") == 3
    assert "1 of 3:" in page and "2 of 3:" in page and "3 of 3:" in page


def test_newest_packs_are_the_most_recently_checked(tmp_path: Path) -> None:
    older = _entry(_version(checked_on=date(2026, 11, 1)), name="Older pack")
    newer = _entry(_version(checked_on=date(2026, 11, 20)), name="Newer pack")
    page = _build(_index(tmp_path, ("older", older), ("newer", newer)), tmp_path / "site")

    newest_block = page.split('aria-label="3 of 3', 1)[1].split("</section>", 1)[0]
    assert newest_block.index("Newer pack") < newest_block.index("Older pack")
