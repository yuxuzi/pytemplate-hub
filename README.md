# pytemplate-hub

A static, verified index of [pytemplate-uv](https://github.com/yuxuzi/pytemplate-uv) template packs.

**Status: phase 2.** The index format, its checks, and two listed packs exist. There is no site yet,
and this repository is private. The name is provisional.

## How it works

The hub stores references, not templates. Authors keep their packs in their own GitHub repositories,
and each index entry binds a tag to the exact commit and file contents that were checked:

```toml
# index/<github-owner>/<pack-id>.toml
format = 1
repository = "https://github.com/acme/sample-pack"

[[versions]]
tag = "v1.0.0"
commit = "<40-character commit SHA>"
digest = "<SHA-256 over every file's path and bytes>"
pack_version = "1.0.0"
license = "MIT"
checked_with = "pytemplate-uv==3.0.0"
profiles = [{ id = "tool", lifecycle = "passed" }]
```

Only contract 1 pytemplate packs at the root of a public GitHub repository can be listed.

## Usage

```bash
uv run pytemplate_hub add https://github.com/acme/sample-pack --tag v1.0.0 --license MIT
uv run pytemplate_hub verify                     # fail if a tag moved or a pack stopped passing
uv run pytemplate_hub check-claims --base OLD    # fail if a change claims a review
```

`--run-lifecycle` also runs each profile's lifecycle commands. **That executes the pack's code**, so
use it only on an isolated machine with no credentials.

## What the checks mean

| Signal | Means | Does not mean |
| --- | --- | --- |
| `listed` | The pack passed the automated checks at this commit | Safe, reviewed, or endorsed |
| `reviewed` | The named maintainer reviewed this exact commit | Safe or free of bugs |
| `lifecycle = "passed"` | The commands passed with default answers, at the time of the check | Other answers or components work |
| `license` | The submitter's declaration, and a license file exists | The hub checked the license text |

Rendering runs with Copier's `unsafe=False`, and `_tasks`, `_migrations`, `_jinja_extensions`, and
symlinks are rejected. That only protects rendering: **a generated project's dependencies, build
backend, and tests still run code when you use them.** Read a pack before you run what it generates.

## Limits

- Pack mirrors are made by hand so far. Their source is recorded in each mirror's README.
- `quant-agent-tool` and `quant-baseline` install quant-agent-os from its git default branch, so a
  passing lifecycle result applies to that branch as it was at check time, not to a fixed version.
- Consumers do not verify the commit or digest yet. pytemplate-uv fetches by tag, so a moved tag is
  only caught by the hub's own `verify`. Closing this gap is phase 4.
- `reviewed_by` has no signature behind it. `check-claims` makes a submitter's claim fail CI, and a
  maintainer must still read the diff, because a pull request can also change the hub's own code.
- The `pull_request` CI job has no secrets, but it does have network access.

## Development

| Task | Command |
| --- | --- |
| Test (offline) | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type-check | `uv run mypy pytemplate_hub` |
