# What the checks mean

This page is the single source for what the hub's checks prove, what they do not prove, and what a
pack must provide.

## What the checks mean

| Signal | Means | Does not mean |
| --- | --- | --- |
| `listed` | The pack passed the automated checks at this commit | Safe, reviewed, or endorsed |
| `reviewed` | The named maintainer reviewed this exact commit | Safe or free of bugs |
| `lifecycle = "passed"` | The commands passed with default answers, at the time of the check | Other answers or components work |
| `license` | The submitter's declaration, and a license file exists | The hub checked the license text |

A passing check is not a safety review. It means the checks in this document ran and passed on the
day they ran.

## Verification policy

- `pytemplate_hub add` fetches one tag with git. It records the commit, a digest (SHA-256 over every
  file's path and bytes), the pack version, the license you declare, and the pytemplate-uv version
  that checked it. It renders each profile with default answers. It does not run lifecycle commands
  unless you pass `--run-lifecycle`.
- `pytemplate_hub verify` fetches every listed version that is not yanked, and fails when its commit,
  digest, pack version, pack id, or profile list no longer matches the entry. For the latest version,
  it also compares the name and description. With `--run-lifecycle`, it runs each profile's lifecycle
  commands.
- `pytemplate_hub check-claims --base OLD` fails when a change adds a `reviewed_by` value, or changes
  any recorded fact of a listed version. Only `reviewed_by` and `yanked` may change on a listed
  version.
- The verify CI job runs on pull requests that change `index/**`. It runs `check-claims` first, then
  `verify --run-lifecycle`. See [Publish a pack](publish.md#5-open-the-pull-request) for how to read its
  failures.

## Rendering and lifecycle commands

- Rendering runs with Copier's `unsafe=False`. `_tasks`, `_migrations`, `_jinja_extensions`, and
  symlinks are rejected. The hub's own code rejects symlinks in a fetched pack.
- That protection covers rendering only. **A generated project's dependencies, build backend, and
  tests still run code when you use them.** Read a pack before you run what it generates.
- Lifecycle commands must start with `uv`. Any other program is refused. This is a check on the
  program's name, not a sandbox: `uv run` can run any program the pack's code names.
- `uv run` still runs the pack's own code. `--run-lifecycle` therefore executes that code. Use it only
  on an isolated machine with no credentials.
- A lifecycle command runs with only `PATH` and `SYSTEMROOT` from the environment. `HOME` points to an
  empty directory. Each command has a 10-minute timeout.
- `lifecycle = "passed"` describes default answers at check time, and nothing more.

## Security model

- The verify CI job runs on `pull_request` only. It has no `pull_request_target` trigger and no
  secrets. Its token can only read, and checkout does not keep credentials. Do not add secrets, write
  permissions, or a privileged trigger to it.
- The `pull_request` CI job has network access, so it can fetch tags from GitHub.
- The hub stores references, never template files. It has no accounts and no server.
- `reviewed_by` has no signature behind it. The CI job refuses a submitter's claim. A maintainer must
  still read the diff, because a pull request can also change the hub's own code.
- A pack's generated projects can run code (see above). The hub does not sandbox them.

## License requirements

- A pack must have a license file at its repository root, named `LICENSE`, `LICENSE.md`,
  `LICENSE.txt`, or `COPYING`. The hub checks that the file exists.
- The `--license` value is your declaration. It is recorded as `license` and must match
  `^[A-Za-z0-9][A-Za-z0-9.+ ()-]*$`, for example `MIT` or `Apache-2.0`.
- The declared license is the submitter's claim. The hub does not read the license text, and it
  does not check that the declaration matches the file. A wrong declaration is not reported. Read
  the license file yourself before you rely on the `license` field.

## What the digest covers

- The digest is a SHA-256 over each regular file's path and bytes (see
  [Template packs](packs.md#the-digest)). It does not cover file modes, so a file that becomes
  executable keeps its digest, and it does not record empty directories.
- This is by decision, not an oversight: changing what the digest covers would change every digest
  already recorded and pinned, so every pinned command would stop matching. The files that run are
  still the files that were checked, but their executable bit is not part of what was checked.

## Limits

- Star counts are only as fresh as the last build. The Pages workflow rebuilds on each push to `main`, not on a schedule.
- A pack's generated projects may install dependencies from moving sources, so a passing lifecycle
  result describes those sources as they were at check time.
- The site's short commands (`-h`, pytemplate-uv 3.5 or later) read the listed commit and digest from
  the hub's index, and the fully pinned commands pass them directly, so pytemplate-uv 3.1 or later refuses a pack
  it fetches whose tag moved or whose files changed. A copy cached by an earlier pinned run is
  checked against the digest but not fetched again, so it still renders the listed files and notices
  a moved tag only on the next fetch (`--no-cache`). A command typed without `--template-commit` and
  `--template-digest` still fetches by tag alone.
- `reviewed_by` has no signature behind it. `check-claims` makes a submitter's claim fail CI, and a
  maintainer must still read the diff, because a pull request can also change the hub's own code.
- The `pull_request` CI job has no secrets, but it does have network access.
