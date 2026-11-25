"""The repository's documents: relative links resolve, and user guides live on the website.

The tutorial and the guides are Learn pages, built from ``pytemplate_hub/site/learn``; the
repository keeps a README that links to them, plus maintainer documents in ``docs/``. No network
is used.
"""

import re
from pathlib import Path

import pytest

from pytemplate_hub.site.learn import PAGES, SITE_URL

ROOT = Path(__file__).parent.parent
DOCUMENTS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").rglob("*.md"))]
# Inline links: [text](target). The target stops at the first space or closing parenthesis.
LINK = re.compile(r"\]\(([^)\s]+)")


def _relative_targets(document: Path) -> list[str]:
    targets = LINK.findall(document.read_text(encoding="utf-8"))
    return [target for target in targets if not re.match(r"^[a-z][a-z0-9+.-]*:", target)]


def test_the_documents_are_found() -> None:
    assert any(_relative_targets(document) for document in DOCUMENTS)


def test_user_guides_are_not_kept_in_docs() -> None:
    kept = {path.relative_to(ROOT / "docs").as_posix() for path in (ROOT / "docs").rglob("*.md")}

    assert not kept & {f"{page.slug}.md" for page in PAGES}
    assert not kept & {"tutorial.md", "authors.md", "trust.md"}


def test_the_readme_links_every_learn_page() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert SITE_URL in readme
    for page in PAGES:
        assert page.url in readme, page.url


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_relative_links_point_to_existing_files(document: Path) -> None:
    broken = []
    for target in _relative_targets(document):
        path = target.split("#", 1)[0]
        if not path:
            continue  # a same-page anchor
        if not (document.parent / path).resolve().exists():
            broken.append(target)

    assert broken == []
