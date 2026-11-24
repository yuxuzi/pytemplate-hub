"""The relative links in the documentation point to files that exist. No network is used."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DOCUMENTS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").glob("*.md"))]
# Inline links: [text](target). The target stops at the first space or closing parenthesis.
LINK = re.compile(r"\]\(([^)\s]+)")


def _relative_targets(document: Path) -> list[str]:
    targets = LINK.findall(document.read_text(encoding="utf-8"))
    return [target for target in targets if not re.match(r"^[a-z][a-z0-9+.-]*:", target)]


def test_the_documents_are_found() -> None:
    assert (ROOT / "docs" / "authors.md").is_file()
    assert any(_relative_targets(document) for document in DOCUMENTS)


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
