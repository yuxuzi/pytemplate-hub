# Launch audit (A1)

Scope: `pytemplate_hub/{schema,fetch,verify,site,cli}.py`, `.github/workflows/*.yml`, `tests/`, read at
`docs/launch-audit` from `origin/main`. Gap tests: `tests/test_audit_gaps.py` (all `xfail(strict=True)`).

## Summary

- The hub checks that an entry is well formed, that a tag resolves to one commit, that the pack's
  files hash to a recorded digest, that the pack's license file exists, and (optionally) that each
  profile renders and its lifecycle commands exit 0.
- It does not check that a license declaration matches the license file, that the code is safe, or
  that a reviewer is who the entry says. Lifecycle commands run pack code with network access.
- The "reviewed" tier is a claim in a TOML file. `check-claims` blocks a PR from adding one, but the
  PR's own copy of the hub code runs that check (see P0-1).
- Local probes of malformed input mostly fail closed. Two gaps are real: a manifest pack id can write
  outside the index, and a non-UTF-8 entry crashes with a raw exception.
- Nothing here is a security endorsement of any pack, and no passing check should be read that way.

## Area table

Severity: P0 blocks launch, P1 before launch, P2 after launch.

| Area | What exists (file:line) | Gap or risk | Severity | Proposed change |
| --- | --- | --- | --- | --- |
| Index schema and compatibility | `schema.py:27-28` forbids extra fields; `schema.py:60` `format: Literal[1]`; `schema.py:98-100` builds path from owner | Unknown fields and bad formats are refused (probed). No migration path for `format` 2. Stale hub reads newer entries as errors | P2 | Document `format` bump rule in `docs/trust.md` (A2) |
| Tag and commit validation | `schema.py:20-21` tag and commit regex; `verify.py:160` tag validated only after fetch and checks | Tags `v1..0` and `v1.0.0.lock` pass the regex; git rejects them later (`fetch.py:68`), with a late error. A bad tag costs a full fetch first | P2 | Validate with git's ref rules before fetching |
| Digest algorithm and canonicalization | `fetch.py:20-36` hashes relative path and bytes, sorted by parts | Executable bit and empty directories are not hashed (test gap). Path encoding uses `.encode()` (`fetch.py:34`), so non-UTF-8 names on Linux raise (unverified). `.gitattributes` `eol`/`text` still apply at checkout because `fetch.py:89` only clears global and system config; this can make digests differ across OSes (unverified, no Windows run) | P1 (EOL, unverified) / P2 (mode, empty dirs) | Hash git blob bytes or a normalized manifest; reject `.gitattributes` EOL rules; add a test for each |
| File path validation and symlinks | `fetch.py:75-80` refuses symlinks from `ls-tree`; `fetch.py:29-30` refuses them again in the digest; `tests/test_fetch.py:44`, `tests/test_fetch.py:89` | Good. Submodules (mode 160000) are not fetched and not refused, so the digest silently excludes them (unverified: not tested) | P2 | Refuse mode 160000 with a clear message |
| Copier rendering configuration | `verify.py:114-123` uses `api.plan`/`api.render`; `pytemplate-uv` renders with `unsafe=False` (`.venv/.../pytemplate/rendering.py:423`); `verify.py:97-98` requires a license file | Rendering protection depends on pytemplate-uv's setting, which the hub does not assert. The hub relies on pytemplate-uv refusing `_tasks` etc. (`tests/test_verify.py:62`) | P1 | Add a hub test that pins `unsafe=False` through `api.render`, so an upgrade cannot silently change it |
| Lifecycle execution and isolation | `verify.py:32-35` `ALLOWED_PROGRAMS = {"uv"}`; `verify.py:131-133` checks only `command[0]`; `verify.py:131` substitutes `{package}` before `shlex.split`; `verify.py:140-143` passes only PATH, SYSTEMROOT, and an empty HOME; `verify.py:136` 600 s timeout per command | The allow-list checks the program name only: `uv run <any program>` runs anything (code-read; not run). No network isolation (README "Limits"). `{package}` comes from the pack's manifest and is substituted before splitting (unverified whether `package_name` is validated). A timeout killed `sh` but its background child did not hold the pipe (probed; does not reproduce, so no test) | P1 | Say in the docs that the allow-list is a naming check, not a sandbox; run lifecycle in a disposable container without network; substitute `{package}` after splitting |
| Pull-request CI permissions and network | `verify-index.yml:12-13` `contents: read`; `verify-index.yml:22` `persist-credentials: false`; `verify-index.yml:17` runs on `ubuntu-latest`; `ci.yml:9` read only | Permissions and trigger are safe (`tests/test_workflow.py:13-28`). But `verify-index.yml:25` runs `uv sync --locked` and `verify-index.yml:34` and `:36` run the PR's own `pytemplate_hub`, and the job has network (`verify-index.yml:36`) | P0 | Install hub tooling from the base SHA and read the PR's `index/` as data only. Keep the job without secrets |
| License declaration and verification semantics | `verify.py:97-98` checks a file exists; `schema.py:23` free-form regex; `verify.py:243-250` re-checks name and description but not license | The declared SPDX string is never compared with the license file. A wrong declaration is never reported | P1 | Map the file to a known SPDX text, or require maintainer review of the declared license |
| Reviewed status and maintainer attestation | `schema.py:48` `reviewed_by` is any GitHub login; `verify.py:258-275` `changed_claims`; `cli.py:53-68`; no `CODEOWNERS` (`.github/` holds only two workflows) | `reviewed_by` is not checked against anyone. `changed_claims` only flags an added claim, not a removed one or a deleted version (see test). Since the check runs PR code (P0 row above), a PR can alter it. No CODEOWNERS on `index/` | P0 (with the CI row) / P1 (CODEOWNERS) | Run the base-branch checker; add `.github/CODEOWNERS` for `index/**` and `pytemplate_hub/**`; flag removed versions |
| Static site generation and JSON schema | `site.py:94-105` create command; `site.py:149` escapes it; `site.py:159-168` escapes name, description, links; `site.py:120-121` writes JSON with no schema; `site.py:186-188` has the "Listed does not mean safe" note | Escaping is consistent (`tests/test_site.py:73`). `site.py:164` puts the commit in a `title` attribute unescaped; safe only because `schema.py:21` is hex-only. The JSON has no schema file and no `format` test (planned in B2) | P2 | Escape every attribute anyway; add `site/index.schema.json` with a test (B2) |
| GitHub API rate limits and offline behaviour | `site.py:76-87` unauthenticated call per entry, `STARS_TIMEOUT_SECONDS=15`, every error becomes `None`; `cli.py:97-99` `--no-stars` | No token, no caching, no per-build limit. A failed call is indistinguishable from a missing repo, and no warning is printed. `json.load` reads an unbounded body (`site.py:84`) | P2 | Use `GITHUB_TOKEN` read-only and one request per repo (C3); warn on failure; cap the body |
| Error handling for malicious or malformed input | `schema.py:106-108` catches OSError, TOML, and validation errors; `verify.py:209-212`; `cli.py:47` catches `HubError` and `ValueError`; `cli.py:71-90` `verify` catches nothing itself | Non-UTF-8 entries raise `UnicodeDecodeError`, which `schema.py:107` does not catch, so `verify` and `check-claims` print a traceback (probed). `verify.py:108-110` reads the manifest and `manifest["name"]` outside the `try` (KeyError would escape; unverified: pytemplate-uv may validate it). A pack id from the manifest is used as a path before validation (`verify.py:186`) and writes outside the index (probed) | P1 | Catch `UnicodeDecodeError` in `load_entry`; validate `pack_id` with `PACK_ID` before `entry_path`; wrap manifest reads |

## Checks versus review versus lifecycle versus endorsement

These four are different facts. Keep them separate in every report and page.

- **Automated checks** (`listed`): the pack's files hash to the recorded digest at the recorded commit,
  its license file exists, and its profiles plan with default answers. They say what was checked, not
  whether the code is good.
- **Human review** (`reviewed`): a named login says they read this commit. It is an unsigned claim,
  and `check-claims` only guards its addition.
- **Lifecycle execution** (`lifecycle = "passed"`): commands exited 0 once, with default answers, on
  the machine that ran the check, with network. It does not cover other answers or later dependencies.
- **Endorsement**: none. The hub endorses nothing. A passing check is not evidence that a pack is safe.

## Malformed input probes

Local fixtures only (no network). Probe scripts were run from the scratchpad against the schema and
`load_entry`; the new tests are listed by name. Results are as observed.

| Input | Result | OK or gap |
| --- | --- | --- |
| Description of 501 characters | `ValidationError`, `String should have at most 500 characters` (`schema.py:18`, `:63`) | OK |
| Tag `..` | refused by pattern (`schema.py:20`) | OK |
| Tag `v1..0` | accepted; git refuses it later at `fetch.py:68` | gap (P2) |
| Tag `-x` | refused by pattern | OK |
| Tag `v1.0.0.lock` | accepted; git refuses it later | gap (P2) |
| Index file `Tools.toml` (uppercase) | `EntryError`, lowercase pack id (`schema.py:109-110`) | OK |
| Index file `..toml` | `EntryError`, lowercase pack id | OK |
| Non-UTF-8 entry bytes | raw `UnicodeDecodeError`, not `EntryError` (`schema.py:106-107`) | gap (P1); test `test_non_utf8_entry_is_reported_as_an_entry_error` |
| Entry in `impostor/` for owner `acme` | `EntryError`, directory must be the owner (`schema.py:111-114`) | OK |
| Duplicate tags | `ValidationError`, listed once (`schema.py:72-74`) | OK |
| Unknown field `stars` | `EntryError`, extra inputs not permitted (`schema.py:28`) | OK |
| Repository `https://github.com/acme/..` and `/.` | accepted (`schema.py:15`, `:68`) | gap (P2); test `test_repository_name_cannot_be_a_dot_segment` |
| Manifest pack id `../../escape` through `add_version` (inspection stubbed, local index) | returned a path outside the index, and `escape.toml` was written (`verify.py:186`, `:199-200`) | gap (P1); test `test_manifest_pack_id_cannot_escape_the_index` |
| Deleting a listed version in a PR (`changed_claims`) | no problem reported (`verify.py:258-275`) | gap (P1); test `test_removing_a_listed_version_is_reported` |
| Executable bit added to a file | digest unchanged (`fetch.py:28-36`) | gap (P2); test `test_digest_changes_when_a_file_becomes_executable` |
| Deep trees and large packs | not probed (no fixture size bound in the code; `fetch.py:16` 300 s git timeout only) | unverified |

## Prioritized issues

- **P0-1** PR-controlled checker (`verify-index.yml:25`, `:34`, `:36`). Fix: run hub tooling from the base SHA; read the PR's `index/` as data.
- **P1-1** Manifest pack id writes outside the index (`verify.py:186`). Fix: validate with `PACK_ID` before `entry_path`.
- **P1-2** Non-UTF-8 entry crashes instead of failing as `EntryError` (`schema.py:106-107`). Fix: catch `UnicodeDecodeError` in `load_entry`.
- **P1-3** Deleted listed versions pass `check-claims` (`verify.py:258-275`). Fix: flag any removed or altered listed version.
- **P1-4** Declared license never compared with the license file (`verify.py:97-98`, `:243-250`). Fix: check the declaration or require review.
- **P1-5** No CODEOWNERS on `index/` or hub code (`.github/`). Fix: add `CODEOWNERS`.
- **P1-6** Lifecycle allow-list is a naming check; `uv run` runs any program; no network isolation (`verify.py:131-133`, `:140-143`). Fix: document as not a sandbox; run in a no-network container.
- **P1-7** Pin `unsafe=False` through `api.render` with a test (`verify.py:114-126`). Fix: add the test.
- **P1-8** EOL and `.gitattributes` may change digests across OSes (`fetch.py:89`; unverified). Fix: verify on Windows; reject EOL attributes.
- **P2-1** Tags `v1..0` and `*.lock` accepted (`schema.py:20`). Fix: apply git ref rules before fetching.
- **P2-2** Dot-segment repository names accepted (`schema.py:15`). Fix: refuse `.` and `..` segments.
- **P2-3** Executable bit and empty directories not hashed (`fetch.py:28-36`). Fix: hash a manifest of modes and directories.
- **P2-4** Submodules silently excluded (`fetch.py:58-73`; unverified). Fix: refuse mode 160000.
- **P2-5** Stars: no token, no cache, silent failure, unbounded body (`site.py:76-87`). Fix: C3.
- **P2-6** JSON has no schema file (`site.py:120-121`). Fix: B2.
- **P2-7** Commit in a `title` attribute is unescaped (`site.py:164`). Fix: escape it.
- **P2-8** Yanking is unrestricted (`verify.py:258-275`). Fix: C2.
- **P2-9** `manifest["name"]` read outside `try` (`verify.py:108-110`; unverified). Fix: wrap it.
