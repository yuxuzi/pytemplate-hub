"""Tests for the static site."""

import io
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from pytemplate_hub.errors import EntryError
from pytemplate_hub.schema import Entry, ProfileCheck, Version, dump_entry, load_entry
from pytemplate_hub.site import (
    MAX_STARS_BYTES,
    GitHubStars,
    build_site,
    create_command,
    github_stars,
    hub_command,
    no_stars,
)
from pytemplate_hub.site.render import STATIC_DIR

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
    # Every page the build wrote, so a test sees the home page, the catalog, and each pack's page.
    page = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(output.rglob("index.html"))
        if "learn" not in path.parts and "publish" not in path.parts
    )
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


def test_commands_wrap_so_the_pinned_tag_stays_visible() -> None:
    css = (STATIC_DIR / "css" / "site.css").read_text(encoding="utf-8")

    assert "white-space: pre-wrap" in css


def test_page_says_listed_does_not_mean_safe(tmp_path: Path) -> None:
    _, page, _ = _build(_index(tmp_path, _version()), tmp_path)

    assert "Listed does not mean safe." in page


def test_untrusted_text_is_escaped(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(yanked=None), name=ATTACK, description=ATTACK)

    _, page, _ = _build(index, tmp_path)

    assert "<script>alert" not in page
    assert '" onmouseover="' not in page


def test_page_script_never_builds_html() -> None:
    for script in (STATIC_DIR / "js").glob("*.js"):
        source = script.read_text(encoding="utf-8")
        assert "innerHTML" not in source, script.name
        assert "document.write" not in source, script.name


def test_page_loads_its_scripts_and_styles_from_the_site_only(tmp_path: Path) -> None:
    _, page, _ = _build(_index(tmp_path, _version()), tmp_path)

    assert 'src="static/js/spotlight.js"' in page
    assert 'src="../static/js/catalog.js"' in page
    assert 'src="../../../static/js/builder.js"' in page
    assert 'src="http' not in page
    assert 'href="static/css/site.css"' in page


def test_unknown_stars_are_labelled_rather_than_zero(tmp_path: Path) -> None:
    _, page, data = _build(_index(tmp_path, _version()), tmp_path)

    assert "stars unavailable" in page
    assert data["packs"][0]["stars"] is None


def test_yanked_latest_falls_back_to_the_previous_version(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(), _version("v2.0.0", yanked="Broken"))

    shown, page, data = _build(index, tmp_path)

    assert shown == 1
    assert "--template-ref v1.0.0" in page
    assert "@v2.0.0" not in page
    assert "--template-ref v2.0.0" not in page
    assert "Yanked: Broken" in page
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


def test_hub_command_is_exact() -> None:
    entry = Entry(repository="https://github.com/Acme/repo")

    command = hub_command(entry, "tools", _version(), "tool")

    assert command == "uvx pytemplate-uv@latest create my-project -h acme/tools@v1.0.0 -p tool -y"


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


def test_github_token_is_sent_as_a_bearer_header_only_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers: list[dict[str, str]] = []

    def fake(request: urllib.request.Request, timeout: float) -> _Response:
        headers.append({key.lower(): value for key, value in request.header_items()})
        return _Response(b'{"stargazers_count": 1}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    entry = Entry(repository="https://github.com/acme/repo")

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    GitHubStars()(entry)
    monkeypatch.setenv("GITHUB_TOKEN", "   ")
    GitHubStars()(entry)
    monkeypatch.delenv("GITHUB_TOKEN")
    GitHubStars()(entry)

    assert headers[0]["authorization"] == "Bearer ghp_secret"
    assert "authorization" not in headers[1]
    assert "authorization" not in headers[2]


def test_each_repository_is_requested_once_per_build(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(request: urllib.request.Request, timeout: float) -> _Response:
        seen.append(request.full_url)
        return _Response(b'{"stargazers_count": 9}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    stars = GitHubStars()
    first = stars(Entry(repository="https://github.com/acme/repo"))
    second = stars(Entry(repository="https://github.com/acme/repo"))

    assert (first, second) == (9, 9)
    assert seen == ["https://api.github.com/repos/acme/repo"]


def test_an_oversize_body_is_unavailable_and_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b'{"stargazers_count": 5, "pad": "' + b"a" * MAX_STARS_BYTES + b'"}'
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_, **__: _Response(body))
    stars = GitHubStars()

    assert stars(Entry(repository="https://github.com/acme/repo")) is None
    assert stars.failures == [f"response larger than {MAX_STARS_BYTES} bytes"]


def test_a_rate_limited_request_is_unavailable_and_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def limited(request: urllib.request.Request, timeout: float) -> None:
        raise urllib.error.HTTPError(request.full_url, 403, "rate limit exceeded", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", limited)
    stars = GitHubStars()
    stars(Entry(repository="https://github.com/acme/repo"))
    stars(Entry(repository="https://github.com/acme/other"))

    assert stars.failures == [
        "HTTP 403 rate limit exceeded",
        "HTTP 403 rate limit exceeded",
    ]
    assert stars.warning() == (
        "Star counts unavailable for 2 of 2 packs "
        "(GitHub API: HTTP 403 rate limit exceeded); set GITHUB_TOKEN or pass --no-stars."
    )


def test_no_warning_when_every_count_was_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_, **__: _Response(b"{}"))
    stars = GitHubStars()

    assert stars(Entry(repository="https://github.com/acme/repo")) is None
    assert stars.warning() is not None
    assert GitHubStars().warning() is None


_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def _violations(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Check ``instance`` against the JSON Schema keywords the hub's schema uses.

    The hub has no JSON Schema library as a dependency, so this covers the keywords the index
    schema uses: const, enum, type, format (date), properties, required, additionalProperties
    (false), and items. Any other keyword is an error, so the schema cannot quietly outgrow the
    check.
    """
    known = {
        "$schema",
        "title",
        "description",
        "const",
        "enum",
        "type",
        "format",
        "properties",
        "required",
        "additionalProperties",
        "items",
    }
    unknown = set(schema) - known
    assert not unknown, f"the checker does not know the keyword(s) {sorted(unknown)}"
    problems: list[str] = []
    if "const" in schema and instance != schema["const"]:
        problems.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        problems.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")
    if "type" in schema:
        allowed = [schema["type"]] if isinstance(schema["type"], str) else schema["type"]
        matches = any(
            isinstance(instance, _TYPES[name])
            and not (name == "integer" and isinstance(instance, bool))
            for name in allowed
        )
        if not matches:
            problems.append(f"{path}: expected {allowed}, got {type(instance).__name__}")
            return problems
    if schema.get("format") == "date" and isinstance(instance, str):
        try:
            date.fromisoformat(instance)
        except ValueError:
            problems.append(f"{path}: {instance!r} is not an ISO date")
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                problems.append(f"{path}: missing required key {key!r}")
        if schema.get("additionalProperties") is False:
            for key in set(instance) - set(properties):
                problems.append(f"{path}: unexpected key {key!r}")
        for key, value in instance.items():
            if key in properties:
                problems += _violations(value, properties[key], f"{path}.{key}")
    if isinstance(instance, list) and "items" in schema:
        for position, item in enumerate(instance):
            problems += _violations(item, schema["items"], f"{path}[{position}]")
    return problems


def _data_and_schema(index: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    build_site(index, output, stars=no_stars, built_on="2026-11-24")
    data = json.loads((output / "index.json").read_text(encoding="utf-8"))
    schema = json.loads((output / "index.schema.json").read_text(encoding="utf-8"))
    return data, schema


def _detailed_version() -> Version:
    profile = ProfileCheck(
        id="tool",
        lifecycle="passed",
        name="Tools",
        description="A tool.",
        kind="cli",
        supported_python=("3.12",),
        dependencies=("typer",),
        security_posture="No service is contacted.",
    )
    return _version(checked_on=date(2026, 11, 24), profiles=(profile,))


def test_index_json_carries_the_new_facts_and_validates_against_its_schema(
    tmp_path: Path,
) -> None:
    index = _index(
        tmp_path,
        _detailed_version(),
        name="Tools",
        description="Useful tools",
        categories=("cli", "ai"),
        keywords=("typer",),
    )

    data, schema = _data_and_schema(index, tmp_path / "site")

    pack = data["packs"][0]
    assert data["format"] == 1
    assert {"id": "cli", "label": "Command-line apps"} in data["categories"]
    assert pack["categories"] == ["cli", "ai"]
    assert pack["keywords"] == ["typer"]
    assert pack["versions"][0]["checked_on"] == "2026-11-24"
    assert pack["versions"][0]["profiles"][0]["dependencies"] == ["typer"]
    assert _violations(data, schema) == []


def test_index_schema_is_written_next_to_the_index(tmp_path: Path) -> None:
    index = _index(tmp_path, _version())

    _, schema = _data_and_schema(index, tmp_path / "site")

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["format"] == {"const": 1}


def test_old_entries_without_the_new_fields_still_validate(tmp_path: Path) -> None:
    index = _index(tmp_path, _version())

    data, schema = _data_and_schema(index, tmp_path / "site")

    assert data["packs"][0]["categories"] is None
    assert data["packs"][0]["versions"][0]["checked_on"] is None
    assert _violations(data, schema) == []


def test_the_checker_reports_a_missing_key_an_extra_key_and_a_bad_value(tmp_path: Path) -> None:
    index = _index(tmp_path, _detailed_version(), categories=("cli",))
    data, schema = _data_and_schema(index, tmp_path / "site")
    pack = data["packs"][0]
    del pack["keywords"]
    pack["surprise"] = True
    pack["categories"] = ["gardening"]
    pack["versions"][0]["profiles"][0]["kind"] = "plugin"

    problems = _violations(data, schema)

    assert "$.packs[0]: missing required key 'keywords'" in problems
    assert "$.packs[0]: unexpected key 'surprise'" in problems
    assert any("'gardening' is not one of" in problem for problem in problems)
    assert any("'plugin' is not one of" in problem for problem in problems)


def test_search_words_include_categories_and_keywords(tmp_path: Path) -> None:
    index = _index(tmp_path, _version(), categories=("quant",), keywords=("backtest",))

    _, page, _ = _build(index, tmp_path)

    tags = page.split('data-tags="', 1)[1].split('"', 1)[0]
    assert "quant" in tags.split()
    assert "backtest" in tags.split()
