# pytemplate-hub

A static, verified index of [pytemplate-uv](https://github.com/yuxuzi/pytemplate-uv) template packs.

**Status: phase 4.** The index format, its checks, the first listed packs, and a static site builder
exist, and the site's commands pin each pack to its checked commit and digest. The site is not
published, and this repository is private. The name is provisional.

## How it works

The hub stores references, not templates. Authors keep their packs in their own GitHub repositories,
and each index entry binds a tag to the exact commit and file contents that were checked:

```toml
# index/<github-owner>/<pack-id>.toml
format = 1
repository = "https://github.com/acme/sample-pack"
name = "Sample pack"
description = "From the pack's manifest; verify compares it with the latest version."

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
uv run pytemplate_hub site                       # build site/index.html and site/index.json
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

Details: [docs/trust.md](docs/trust.md), including what rendering and lifecycle commands do. **A
generated project's dependencies, build backend, and tests still run code when you use them.**

## Listing a pack

Read [docs/authors.md](docs/authors.md). It covers the pack requirements, tagging a release, adding
your entry with `pytemplate_hub add`, opening the pull request, and what the CI checks report.
Contributors to the hub's code should read [CONTRIBUTING.md](CONTRIBUTING.md).

## The site

`site` writes one page with search and a reviewed-only filter, plus the same data as JSON. Star counts
come from GitHub at build time, and comments link to the source repository's issues, so the hub has
no accounts. `--no-stars` builds without network access. Yanked versions stay in the JSON and leave the
page.

## Limits

- Star counts are only as fresh as the last build, and nothing rebuilds the site automatically yet.
- A pack's generated projects may install dependencies from moving sources, so a passing lifecycle
  result describes those sources as they were at check time.
- The site's commands pass the listed commit and digest, so pytemplate-uv 3.1 or later refuses a pack
  whose tag moved or whose files changed. A command typed without `--template-commit` and
  `--template-digest` still fetches by tag alone.
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
