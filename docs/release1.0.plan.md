# pytemplate-hub: Public Launch Readiness and Ecosystem Growth

## Objective

Prepare pytemplate-hub for its first public release as an open, community-driven index of verified
pytemplate-uv template packs.

The objective is not simply to publish a static website. It is to establish a trustworthy ecosystem
where independent developers can publish, maintain, discover, and use Python application template
packs.

## Product positioning

pytemplate-hub is a static, GitHub-native registry for discovering and verifying pytemplate-uv
template packs. It stores references rather than templates. Pack authors retain ownership of their
repositories.

Differentiators: version-specific commit and content-digest pinning; explicit verification and
lifecycle status; transparent trust and security boundaries; open contribution through GitHub pull
requests; a static website and machine-readable JSON index; integration with pytemplate-uv.

Preserve the product philosophy: **Generate once. Own your code.** Do not introduce automatic
template synchronization as a core requirement.

## Review of the original plan (2026-11-24)

The plan is sound in intent but was written as if starting from zero. Much of Phase 1 already
exists, and several items collide with the hub's own rules. Corrections:

1. **Start from what exists.** Already built and tested (~870 lines, 100 tests): commit + SHA-256
   digest binding (`fetch.py`), tag fetched by full ref, symlinks refused from git's tree, git run
   with no user config/credentials and https only, Copier `unsafe=False` with `_tasks`/
   `_migrations`/`_jinja_extensions` rejected, lifecycle limited to `uv` in a credential-free
   `HOME`, `check-claims` refusing review claims and rewritten facts, the isolated
   `verify-index.yml` (`pull_request`, read-only token, `persist-credentials: false`), and an
   escaped static site with JSON. The audit must report gaps against this, not re-specify it.
2. **No new self-declared quality fields** (CLAUDE.md). "Framework and application-type filters"
   need a category source. Descriptive categories are not quality signals, but they must come from
   the pack (its manifest or profile ids), never from a free-text index field. Decision D1.
3. **"Last verification date" cannot be written back by CI.** The verify workflow runs untrusted
   code and must never get write access. Verification time must come from a separate trusted job
   (scheduled verify on `main`, no pack code with write token in the same job) or from the site
   build, not from commits by the untrusted job. Decision D3.
4. **Workflow edits, Pages publishing, public repos, and the repo going public all need the user's
   approval** (CLAUDE.md "Safety"; memory: ask before public repos, mirrors, going public, names).
   The name is provisional: no domains, PyPI names, or trademarks.
5. **"First five reference packs" vs "do not fabricate authors".** Today the index lists three
   packs, all published by one author (yuxuzi), all from one ecosystem. Any new reference packs
   (FastAPI, CLI, data, worker, library) would also be the maintainer's own; the site and
   announcements must say so. pytemplate-uv's built-in templates (`fastapi`, …) could seed them,
   but publishing new repos is Decision D2.
6. **Hub independence.** The hub never names Quant-Agent-OS outside index entries. Launch copy
   must not lead with the quant packs.
7. **Announcements are drafts only**, kept out of the repository (it will be public before the
   announcement): `launch-drafts/` in this checkout, untracked.
8. **Missing prerequisites:** open PR #12 (`-y` in commands) should land first; the quant 1.0
   mirrors session will open a hub PR for quant-apps v2.3.0 etc. Work goes on branches from
   `origin/main` in separate worktrees; never in this checkout (it is on a stale branch and
   another session may use it).
9. **What "1.0" versions.** The hub is not published to PyPI. "Release" here means: repo public,
   site live, `format = 1` frozen and documented, tag `v1.0.0`. Tagging needs the user's word.

## Decisions for the user

| ID | Question | Recommendation |
| --- | --- | --- |
| D1 | Where categories for filters come from | Profile ids + an optional `keywords` list read from `pytemplate-pack.toml`, checked by verify like `name`/`description`; no index-only field |
| D2 | Create new public reference-pack repos (FastAPI, CLI, data, worker, library)? | Yes, as yuxuzi-owned packs derived from pytemplate-uv's built-ins, labelled as the maintainer's; two at launch (FastAPI, CLI), more later |
| D3 | Automation: scheduled verify + Pages deploy | Two new workflows: `verify-scheduled.yml` (cron weekly, read-only, opens no PRs; failure = red badge + issue via a separate step with `issues: write` that runs no pack code), and `pages.yml` (build site on push to `main`, `pages: write`, runs no pack code) |
| D4 | Go public: when and under what name | After waves A-C merge; name stays provisional until the user decides |

## Execution plan

Owners: **W** = a `worker` subagent (Haiku, low effort) in its own worktree from `origin/main`;
**M** = the main session (review, integration, PRs). One PR per wave item; the user merges.
Every worker runs: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy pytemplate_hub`, and commits locally. M reviews the diff, reruns the checks from a
fresh clone of the commit, then pushes and opens the PR.

### Wave A: audit and contributor docs (no decisions needed; parallel)

- **A1 (W) Architecture and security audit** → `docs/audit.md`, branch `docs/launch-audit`.
  For each of the 12 review areas below: what exists (file:line), the gap, severity (P0 blocks
  launch, P1 before launch, P2 after), and the proposed change. Plus "Malformed and malicious
  inputs" tried against the CLI with local fixtures (oversized description, odd tags, huge pack,
  path traversal in index file names, non-UTF-8, deep trees). No code changes except new tests
  that demonstrate a gap (marked `xfail` with the audit item id).
  Areas: index schema and compatibility; tag and commit validation; digest algorithm and
  canonicalization; path validation and symlinks; Copier rendering configuration; lifecycle
  execution and isolation; PR CI permissions and network; license semantics; reviewed status and
  attestation; site generation and JSON schema; GitHub API rate limits and offline behavior; error
  handling. Keep separate: automated checks, human review, lifecycle execution, security
  endorsement. Never imply a passing check means safe.
- **A2 (W) Contributor experience** → branch `docs/contributors`:
  `CONTRIBUTING.md` (hub code changes), `docs/authors.md` (quickstart: make a pack from
  pytemplate-uv's contract, tag it, run `pytemplate_hub add` locally without `--run-lifecycle`,
  open the index PR; what CI does), `docs/trust.md` (verification policy, security model, license
  requirements: one source of truth for the README's "What the checks mean" table, which then
  links to it), `.github/pull_request_template.md` (index PR checklist). Pack-contract details
  link to pytemplate-uv's docs rather than copying them. Success test: M follows `docs/authors.md`
  literally against `examples/sample-pack` in a temp dir.
- **A3 (M)** Review PR #12 with the user; note the quant mirrors hub PR when it appears.

### Wave B: fixes and discovery (after A1 is reviewed)

- **B1 (W) P0/P1 audit fixes**, one commit per item, each with a failure-path test.
  Do not weaken any validation.
- **B2 (W) Site discovery**, branch `feat/site-discovery`: all non-yanked versions per pack with
  their pinned commands (a version picker or list), maintainer (GitHub owner link), license,
  `checked_with`, lifecycle per profile, profile filter, D1 category filter, "built on" date and
  (after D3) "last verified" date. JSON gains these fields under `format: 1` additively and gets a
  JSON Schema file (`site/index.schema.json`) with a test that the output validates. Keep: no
  backend, no accounts, page script never builds HTML.
- **B3 (W) Starter pack**: extend `examples/sample-pack` into a documented minimal pack that
  `docs/authors.md` uses; publishing it as its own repo waits for D2.

### Wave C: automation (needs D3; workflow edits need approval)

- **C1 (M+W)** `verify-scheduled.yml` and `pages.yml` as drafted in D3, in one PR flagged as a
  workflow change. `tests/test_workflow.py` extended to assert: no `pull_request_target`, no
  secrets in jobs that run pack code, write permissions only in jobs that run no pack code.
- **C2 (W)** Yanked-version handling end to end: `pytemplate_hub yank <entry> <tag> --reason`,
  `check-claims` allows only that change, site and JSON reflect it.
- **C3 (W)** Rate limits: stars use `GITHUB_TOKEN` when present (read-only), degrade to "stars
  unavailable"; one request per repo per build.

### Wave D: ecosystem and launch package (drafts; nothing is published)

- **D-1 (W)** `docs/migrating.md`: turn an existing Copier/cookiecutter template into a
  pytemplate pack.
- **D-2 (W)** Architecture diagram (Mermaid in `docs/architecture.md`): author repo → index PR →
  verify CI → maintainer review → merge → site/JSON → `uvx pytemplate-uv create --template-commit
  --template-digest`.
- **D-3 (M)** README and site landing copy for a public reader; lead with "Generate once. Own your
  code." and the trust table; no adoption claims.
- **D-4 (W)** Untracked `launch-drafts/`: invitation message for pack authors, target categories
  (FastAPI apps, CLIs, data engineering, workers, libraries) with criteria for a good first pack,
  Show HN post, DEV article outline, LinkedIn post, demo script (search → pick version → pinned
  create → tag moved → refused). No invented users, quotes, or endorsements.
- **D-5 (W, after D2)** Reference packs from pytemplate-uv built-ins, in new repos the user
  approves, listed through a normal index PR.

### Wave E: launch (user's word only)

Public-launch checklist: all P0/P1 audit items closed; waves A-C merged; CI green on all OS/Python;
`verify --run-lifecycle` green on `main`; site builds offline (`--no-stars`) and online; a
first-time-author dry run done by someone other than the author (or a fresh agent with only the
docs); README limits section current; D4 decided; then make the repo public, enable Pages, tag
`v1.0.0`, and post the announcements the user approves.

## Constraints

- Preserve existing working functionality; avoid unnecessary architectural redesign.
- Do not weaken validation to make more packs pass.
- Do not claim security guarantees that have not been established.
- Do not fabricate external users, authors, endorsements, or adoption.
- Do not publish, announce, make public, tag, or create repositories without explicit approval.
- Keep pytemplate-hub independent from Quant-Agent-OS; pytemplate-uv stays the generation engine
  and never names the hub.
- Ask before CI workflow changes, dependency additions, or version bounds (hub CLAUDE.md).

## Deliverables (where each lands)

1. Architecture and security audit — `docs/audit.md` (A1).
2. Prioritized issues — the audit's table, P0/P1/P2 (A1).
3. Proposed changes — the audit's table, then B1/C PRs.
4. Contributor experience assessment — A2 PR body, plus M's dry-run notes.
5. Public-launch checklist — Wave E above, tracked in the final PR.
6. Ecosystem growth recommendations — `launch-drafts/` (D-4).
7. Tests and verification results — each PR body.
8. Changed-file list — each PR body.
9. Remaining risks and limitations — README "Limits" and `docs/trust.md`.

## Status

- 2026-11-24: plan reviewed and expanded; A1 and A2 started (worktrees `../pytemplate-hub-audit`,
  `../pytemplate-hub-docs`).
- 2026-11-24: A2 → PR #13 (105 passed). A1 → PR #14 (P0-1 PR-controlled checker; P1-1..P1-8).
  B1 started on `fix/audit-p1` (worktree `../pytemplate-hub-fix`, stacked on #14): P1-1, P1-2,
  P1-3, P1-7, P2-1, P2-2, P2-7, P2-9. P0-1 and P1-5 (workflow, CODEOWNERS) await approval;
  P1-4 (license check) and P1-6 (sandboxing) need a decision.
- 2026-11-24: B1 → PR #15 (stacked on #14; 134 passed, 1 xfailed).
- 2026-11-24: D2 decided by the user: "create founder provided templates as starter and pillar, to
  attract users". Five packs, built locally in `/Users/yuxuz/projects/packs/<repo>` (shared brief
  `packs/BRIEF.md`, checker `packs/check_pack.py`), labelled as the maintainer's own:
  starter `pytemplate-starters` (script, cli, library); pillars `fastapi-service` (service,
  service-sql), `mcp-server` (tools, tools-http), `data-pipeline`, `background-worker`.
  First three in progress. Creating the GitHub repos and pushing tags await the user's word.
- 2026-11-24: all five packs built, each a local repo with one commit and a local tag v1.0.0; the
  main session reran `check_pack.py` on each: every profile `lifecycle passed`
  (starters: script, cli, library; fastapi-service: service, service-sql; mcp-server (mcp 2.3):
  tools, tools-http; data-pipeline (duckdb 2.0.1, polars 2.1.0, also tested on 3.11): etl,
  etl-polars; background-worker (redis 8.2, fakeredis 2.41): worker, worker-redis).
  Unverified: Docker build, PostgreSQL, real Redis, real MCP clients, Linux/Windows.
  Before publishing: unify commit author (3 commits carry `yuxuz@mac.mynetworksettings.com`).
  Next on the user's word: create 5 public repos under yuxuzi, push main + v1.0.0, then a hub PR
  listing them with `pytemplate_hub add --run-lifecycle` (on this machine, trusted own packs).
- 2026-11-24: user approved publishing. Authors unified (Leo Liu <yuxuzi@gmail.com>); five public
  repos yuxuzi/<pack> with v1.0.0 pushed; hub PR #16 lists them (verify: 8 entries).
