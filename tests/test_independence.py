"""The hub is generic: its code and documents name no publisher or consumer."""

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FILES = [*sorted((ROOT / "pytemplate_hub").glob("*.py")), ROOT / "pyproject.toml"]
FILES += [ROOT / "README.md", ROOT / "CLAUDE.md"]
# Assembled so this file does not name them either.
PUBLISHERS = (
    "quant" + "-agent",
    "quant" + "_agent",
    "quant" + "-factory",
    "quant app" + " factory",
)


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_file_names_no_publisher(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()

    assert not [name for name in PUBLISHERS if name in text]
