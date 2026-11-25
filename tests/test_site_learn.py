"""The Learn pages: one per Markdown source, links between them resolved, raw HTML shown as text."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pytemplate_hub.errors import SiteError
from pytemplate_hub.site import build_site, no_stars
from pytemplate_hub.site.learn import PAGES, SOURCE_DIR, render_markdown, root_of, slugify


def test_every_source_is_a_page_and_every_page_has_a_source() -> None:
    sources = {path.stem for path in SOURCE_DIR.glob("*.md")}

    assert sources == {page.slug for page in PAGES}


def test_the_build_writes_each_page_and_the_learn_index(tmp_path: Path) -> None:
    index = tmp_path / "index"
    index.mkdir()
    output = tmp_path / "site"

    build_site(index, output, stars=no_stars, built_on="2026-11-25")

    assert (output / "learn" / "index.html").is_file()
    for page in PAGES:
        html = (output / page.path / "index.html").read_text(encoding="utf-8")
        assert f"<title>{page.title} · Pytemplate Hub</title>" in html
        assert 'aria-current="page"' in html


@pytest.mark.parametrize(
    ("heading", "anchor"),
    [
        ("6. Share your pack on the hub", "6-share-your-pack-on-the-hub"),
        ("Options of create", "options-of-create"),
        ('What "reviewed" means', "what-reviewed-means"),
        ("Compatibility and versioning", "compatibility-and-versioning"),
    ],
)
def test_headings_get_githubs_anchors(heading: str, anchor: str) -> None:
    assert slugify(heading) == anchor


def test_repeated_headings_get_numbered_anchors() -> None:
    rendered = render_markdown("## Notes\n\n## Notes\n", "learn/guide/")

    assert [heading.anchor for heading in rendered.headings] == ["notes", "notes-1"]


def test_a_link_to_a_page_source_becomes_a_relative_link() -> None:
    html = render_markdown("[Publish](publish.md#2-tag-a-release)", "learn/tutorial/").html

    assert 'href="../../publish/index.html#2-tag-a-release"' in html


def test_a_link_to_an_unknown_page_fails_the_build() -> None:
    with pytest.raises(SiteError, match="names no Learn page"):
        render_markdown("[Gone](authors.md)", "learn/tutorial/")


def test_a_relative_path_to_a_repository_file_fails_the_build() -> None:
    with pytest.raises(SiteError, match="full URL"):
        render_markdown("[Read](../README.md)", "learn/tutorial/")


def test_full_urls_are_kept_even_when_they_end_in_md() -> None:
    html = render_markdown("[AGENTS.md](https://agents.md)", "learn/guide/").html

    assert 'href="https://agents.md"' in html


def test_raw_html_in_a_source_is_shown_as_text() -> None:
    html = render_markdown("<script>alert(1)</script>\n\n<b onclick=x>b</b>", "learn/").html

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b onclick" not in html


def test_shell_blocks_get_a_copy_button_with_escaped_text() -> None:
    source = '```bash\necho "<x>" && ls\n```\n\n```toml\na = 1\n```\n'
    html = render_markdown(source, "learn/").html

    assert html.count('class="copy"') == 1
    assert 'data-copy="echo &#34;&lt;x&gt;&#34; &amp;&amp; ls"' in html


def test_wide_tables_scroll_in_their_own_box() -> None:
    html = render_markdown("| a |\n| --- |\n| b |\n", "learn/").html

    assert '<div class="table"><table>' in html


def test_root_of_counts_the_directories() -> None:
    assert root_of("learn/") == "../"
    assert root_of("learn/tutorial/") == "../../"
    assert root_of("") == ""


def test_listed_packs_are_shown_with_the_short_hub_command() -> None:
    # A listed pack is named with -h; the fully pinned form is for CI and offline use only, and
    # always carries both pins.
    for page in PAGES:
        text = page.source.read_text(encoding="utf-8")
        commands = re.findall(r"uvx pytemplate-uv@latest [^\n]*(?:\\\n[^\n]*)*", text)
        for command in commands:
            if "--template gh:yuxuzi/" in command:
                assert "--template-commit" in command, (page.slug, command)
                assert "--template-digest" in command, (page.slug, command)
        assert "gh:yuxuzi/pytemplate-starters --template-ref v1.0.0\n" not in text, page.slug
