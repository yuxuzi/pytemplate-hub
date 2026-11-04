# CLAUDE.md

Guidance for Claude Code and other coding agents working in `pytemplate-hub`.

## Project

A static, verified index of pytemplate-uv template packs. A typed Python 3.11+ package (`pytemplate_hub`) with a Typer CLI. `uv` is the only required tool: never use pip, virtualenv activation, or make.

## Commands

- Install or refresh the environment: `uv sync`
- Test: `uv run pytest`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .` (check only: `uv run ruff format --check .`)
- Type-check: `uv run mypy pytemplate_hub`
- Run the CLI: `uv run pytemplate_hub --help` (`--run-lifecycle` executes pack code; use only the sample pack locally)
- One-off tools without installing them: `uvx <tool>` (for example `uvx pre-commit run --all-files`)

## Layout

- `pytemplate_hub/schema.py` — the index entry format.
- `pytemplate_hub/fetch.py` — fetching a tag; the commit and digest. Uses git only.
- `pytemplate_hub/verify.py` — listing checks, re-verification, and protected-field checks.
- `pytemplate_hub/site.py` — the static site. Entry text is untrusted: escape it, and never build HTML in the page's script.
- `pytemplate_hub/cli.py` — Typer entry point; a thin layer over `verify` and `site`.
- `examples/sample-pack/` — a trusted pack used by the tests.
- `index/` — the entries, one per pack.
- `tests/` — pytest suite, one test module per source module.

## Rules specific to this project

- Import pytemplate-uv only through `pytemplate.api`.
- The hub stores references, never template files, and has no accounts or server.
- Never add self-declared quality fields. Quality signals are computed, or name a reviewer.
- `.github/workflows/verify-index.yml` runs untrusted code: never give it secrets or write access.
- The hub is generic and independent, like pytemplate-uv. It never imports, depends on, or names a
  publisher or consumer, and gives none special treatment. Index entries are the only exception,
  because they are data.

## Conventions

- Type-annotate everything; mypy runs in strict mode and must stay clean.
- Ruff owns formatting and import order; do not hand-format.
- Add runtime dependencies with `uv add <package>` and tools with `uv add --dev <package>`; never edit `uv.lock` by hand.
- Keep business logic out of the CLI so it can be tested without invoking Typer.

## Testing

- Add or update tests with every behavior change, including the failure path.
- Before reporting work as done, run the test, lint, format, and type-check commands above and report the real results.
- Tests must not use the network or real credentials.

## Safety

- Never read, print, or commit `.env` files, tokens, or other secrets.
- Do not change CI workflows, release configuration, or dependency version bounds without asking first.
- Prefer small, reviewable diffs; explain any change that touches more than one module.
