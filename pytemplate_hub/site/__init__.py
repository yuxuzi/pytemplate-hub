"""The hub's static site: ``index.html`` (rendered by Jinja2), ``index.json``, and its schema.

``data`` holds the JSON and the schema, star counts, and the create command; ``render`` holds the
page. The page's templates and static files live beside this module, so they ship in the wheel.
"""

from pytemplate_hub.site.data import (
    INDEX_FILE,
    INDEX_FORMAT,
    INDEX_SCHEMA,
    SCHEMA_FILE,
    STARS_TIMEOUT_SECONDS,
    StarSource,
    build_site,
    create_command,
    github_stars,
    hub_command,
    no_stars,
)

__all__ = [
    "INDEX_FILE",
    "INDEX_FORMAT",
    "INDEX_SCHEMA",
    "SCHEMA_FILE",
    "STARS_TIMEOUT_SECONDS",
    "StarSource",
    "build_site",
    "create_command",
    "github_stars",
    "hub_command",
    "no_stars",
]
