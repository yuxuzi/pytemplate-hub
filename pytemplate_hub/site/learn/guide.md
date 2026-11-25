# Using pytemplate-uv

pytemplate-uv is a deterministic application factory that generates **uv-native** Python
projects: choose a profile (a typed CLI package, a library, or a FastAPI service), add components
(database, authentication, background jobs), and get a project that passes linting, formatting,
type-checking, and tests from its first commit. This page covers every command and option; the
[tutorial](tutorial.md) is the gentler start.

## Install

No installation is needed: `uvx` runs the latest release.

```bash
uvx pytemplate-uv --help
```

To install the `pytemplate` command:

```bash
uv tool install pytemplate-uv
```

It requires Python 3.11 to 3.15, and runs on Linux, macOS, and Windows. `pip install pytemplate-uv`
also works. The examples below write `pytemplate`; with `uvx`, write `uvx pytemplate-uv@latest`.

## Create a project

```bash
uvx pytemplate-uv@latest create my-api -p fastapi -c database -c auth-oidc -y
cd my-api
uv sync
uv run pytest
```

That gives a layered FastAPI service with a database, OIDC authentication, tests, a GitHub Actions
workflow, structured logging, and health checks. When it finishes, `create` prints the next steps:
the `cd` and the profile's own lifecycle commands.

More examples:

```bash
# A Python CLI tool
pytemplate create my-tool -p python -y

# A FastAPI service with background jobs
pytemplate create my-service -p fastapi -c worker -c database -y

# A containerized API with API key auth
pytemplate create my-api -p fastapi -c auth-api-key -c container -y

# A project from a pack listed on the hub
pytemplate create my-app -h yuxuzi/pytemplate-starters@v1.0.0 -p cli -y

# Preview before writing anything
pytemplate plan --name my-api -p fastapi -c database -c auth-oidc

# Validate a request (catches mistakes early)
pytemplate validate --name my-api -p fastapi -c auth
```

The last command fails with `Component 'auth' needs one of: auth-api-key, auth-oidc; add
--component auth-api-key.`

`create-project` is an optional shortcut with the same arguments and options as `pytemplate
create`:

```bash
uvx --from pytemplate-uv create-project pricing-api -p fastapi -y
```

## Profiles and components

Choose one profile:

- **`python`**: a typed package with a Typer CLI, for tools.
- **`library`**: a typed package with no CLI or console script, for code others import.
- **`fastapi`**: a layered REST API service with structured logging, health checks, and security.

Add any components:

| Component | Purpose | When to use |
| --- | --- | --- |
| `database` | SQLAlchemy 2.x ORM and Alembic migrations | When you need persistent data |
| `worker` | A task-queue port with an in-process adapter and job endpoints | For background work |
| `auth-api-key` | API key authentication with scopes | For service-to-service auth |
| `auth-oidc` | OpenID Connect (JWT) authentication | For user login through an identity provider |
| `container` | A Dockerfile and `.dockerignore` | For containerized deployment |
| `devcontainer` | A `.devcontainer/devcontainer.json` for VS Code and Codespaces with uv | For a one-click development environment |
| `release` | A trusted-publishing PyPI release workflow triggered by a `v*` tag (`python` and `library`) | To publish a package |
| `mcp` | An MCP server over stdio, with a typed tool, a test, and `.mcp.json` (`python` and `library`) | To give AI agents tools they can call |

The generator validates combinations and adds required components and dependencies.
`pytemplate list-profiles`, `list-components`, `describe-profile ID`, and `describe-component ID`
show the same details from the command line.

Every project generated from the bundled templates passes `ruff check`, `ruff format --check`,
strict `mypy`, and `pytest`, and CI checks every bundled component combination on every commit.
Projects from your own packs are not covered by these checks; test your pack the same way.

## Commands

| Command | What it does |
| --- | --- |
| `create NAME` | Generate a project |
| `plan` | Preview files and dependencies (writes nothing) |
| `validate` | Check a request for errors before rendering |
| `create-from-config FILE` | Render from a TOML request file |
| `status [PATH]` | List files changed, deleted, or added since generation (read-only) |
| `list-profiles` / `describe-profile ID` | Show profiles and their inputs |
| `list-components` / `describe-component ID` | Show components: requirements, conflicts, dependencies, files, settings |
| `schema NAME` | Print a JSON Schema (`profile`, `component`, `pack`, `request`, `manifest`) |
| `skill install` / `skill show` | Install or print the AI project-creation skill |

- Every command except `schema` (which already prints JSON) and `skill` accepts `--json`.
- `create`, `plan`, `validate`, and the list and describe commands accept a pack: `-h OWNER/PACK[@TAG]`
  for a pack listed on the hub, or `--template` for any other. See [Template packs](packs.md).
- Errors and warnings go to stderr; only `--json` output and results go to stdout. A misspelled
  profile, component, schema, or `--data` key gets a "Did you mean" suggestion.

Exit codes:

- `0`: success.
- `1`: an invalid request; nothing was written. With `--json`, the error is printed as
  `{"ok": false, "error": {...}}`.
- `2`: a valid request that failed while rendering or writing.

## Options of create

- `--profile`, `-p`: the profile (default `python`). With a pack and no `-p`, `create` asks for the
  profile in a terminal.
- `--component`, `-c`: add a component; repeat as needed. Profile defaults are always included,
  and required components are added automatically.
- `--output-dir`, `-o`: an existing parent directory (default `.`).
- `--data`, `-d KEY=VALUE`: answer a template question; repeat as needed. The inputs are
  `package_name`, `description`, `author`, `email`, `python_version` (3.11 to 3.15), and `license`
  (an SPDX expression).
- `--hub`, `-h OWNER/PACK[@TAG]`: render from a pack listed on the hub, pinned to the commit and
  digest it checked. `-h` alone, and `--help`, print help.
- `--template`, `-t SOURCE` and `--template-ref REF`: render from any template pack, with
  `--template-commit` and `--template-digest` to pin it (see [Template packs](packs.md)).
- `--yes`, `-y`: accept the template defaults instead of prompting. Without it, `create` prompts,
  and the picker below asks for optional components; when standard input is not a terminal it
  exits 1 before rendering and asks for `-y`. `--json` implies `-y`. `--no-input` still works but
  is deprecated: it prints a warning and goes away in 4.0.
- `--git`: after rendering, run `git init` and commit everything as "Initial commit from
  pytemplate-uv". `--lock`: run `uv lock` first, so the commit includes `uv.lock`. Neither is ever
  the default, and neither runs with `--dry-run`. If a step fails, the project stays and the exit
  code is 2, with a message saying what was created and what failed.
- `--dry-run`: validate and show the target without writing.
- `--force`, `-f`: replace an existing directory. The project is rendered into a staging directory
  and swapped in only after rendering succeeds, so no stale files remain.
- `--json`: print the result as JSON.

## Picker, completion, and status

- In a terminal, without `-y`, `--json`, or `-c`, `create` offers the profile's optional components
  as a multi-select list. Required components are still added, and conflicts still refused.
- `--profile` and `--component` complete in your shell (for the bundled catalog) once you run
  `pytemplate --install-completion`.
- `pytemplate status [PATH]` compares a generated project with the SHA-256 inventory in
  `.pytemplate.toml` and lists the files you changed, deleted, or added. It ignores `.git/`,
  `.venv/`, caches, `uv.lock`, and the manifest, never writes, accepts `--json`, and exits 1 when
  `PATH` has no valid manifest.

## Request files

A request file records a render so you can repeat it:

```toml
# pricing-api.toml
project_name = "pricing-api"
profile = "fastapi"
components = ["database", "auth-api-key"]
output_dir = "./projects"   # relative to this file

[data]
description = "Pricing service"
author = "Platform Team"
```

```bash
pytemplate validate pricing-api.toml
pytemplate plan pricing-api.toml --json
pytemplate create-from-config pricing-api.toml
```

For a pack listed on the hub, add `hub = "owner/pack@tag"`; its pins are read from the hub as with
`-h`. For any other git pack, use `template`, `template_ref`, `template_commit`, and
`template_digest`.

Each project records how it was generated, and neither file stores secrets or environment values:

- `.pytemplate.toml` records the generator, the template source, the profile and component versions
  (with why each component is present), the answers, and a SHA-256 hash and owner for every
  generated file;
- `.copier-answers.yml` records the Copier answers and the template source.

`pytemplate schema request` and `pytemplate schema manifest` describe the formats.

## Coding agents

Every generated project carries an `AGENTS.md`: its commands, layout, conventions, and safety
rules, for any agent that reads the [AGENTS.md](https://agents.md) format. `CLAUDE.md` is a one-line
import of it, so Claude Code reads the same text.

To build something an agent can call, add `mcp` to a `python` project:

```bash
pytemplate create pricing-tools --profile python --component mcp -y
cd pricing-tools && uv sync && uv run pytest
```

You get a [Model Context Protocol](https://modelcontextprotocol.io) server on the official SDK, a
`pricing-tools-mcp` command, a test that calls the tool through the server, and a `.mcp.json` that
registers it for agents working in the repository. Rendering it calls no model and needs no API
key.

pytemplate-uv also ships an agent skill (`SKILL.md`) that teaches an agent to discover profiles,
components, and packs on the hub; write a render request and check it with `plan`; **wait for your
confirmation**; and then create the project and run its checks:

```bash
uvx pytemplate-uv@latest skill install                  # ~/.claude/skills (all projects)
uvx pytemplate-uv@latest skill install --project        # ./.claude/skills (this repository)
uvx pytemplate-uv@latest skill install --agent agents   # ~/.agents/skills, for Codex and others
```

Then ask, for example, *"Create a FastAPI service called pricing-api with a database and OIDC
login"*. For other AI tools, give them the instructions from `uvx pytemplate-uv@latest skill show`.

## From Python and scripts

From Python, through the supported `pytemplate.api` module:

```python
from pathlib import Path
from pytemplate import api

request = api.RenderRequest("fastapi", "my-api", Path("."), components=("database",), no_input=True)
plan = api.plan(request)  # writes nothing
print(plan.resolution.dependencies)  # what will be added
print(plan.files)  # every generated file
api.render(request)  # or render the project
```

From scripts, CI, or other languages, use `--json` and the published schemas:

```bash
pytemplate plan --name my-api -p fastapi -c database --json | jq .
pytemplate validate request.toml --json
pytemplate schema request
```

## The FastAPI layout

```text
pricing-api/
  AGENTS.md  CLAUDE.md  README.md  pyproject.toml  .env.example  .copier-answers.yml  .pytemplate.toml
  pricing_api/
    api/             routers/, schemas, dependencies, errors, middleware, health
    application/     use cases
    domain/          entities, rules, errors, ports
    infrastructure/  memory adapter (database/ with -c database)
    bootstrap/       settings, logging, container, create_app()
    security/        with -c auth-api-key or -c auth-oidc
  migrations/  alembic.ini       with -c database
  SECURITY.md                    with authentication
  Dockerfile  .dockerignore      with -c container
  tests/unit/  tests/integration/
```

## Questions

**Can I use this in production?** The generated code is a starting point you own. Every `stable`
bundled component combination passes lint, format, strict type-checking, and its tests in CI.
Projects with authentication also get a `SECURITY.md` that lists what you still need to configure
for deployment; for others, review the generated `README.md` (and `.env.example` for FastAPI
services).

**How do I customize the templates?** Use a template pack: your own profiles and components, with
all of pytemplate-uv's composition logic. Look on the [hub](https://yuxuzi.github.io/pytemplate-hub/)
for a pack that already fits first; [Template packs](packs.md) covers writing one.

**How do I keep my project updated?** The generated project is yours from the first commit;
pytemplate-uv does not merge later template releases into it. Keep dependencies current with
`uv lock --upgrade` or a bot such as Dependabot. To see what a newer release changed, generate a
fresh project with the same answers and compare.

**Do I commit the generated code?** Yes: generate the project into a git repository and commit it.
`.pytemplate.toml` records how it was made.

**Is the generated code opinionated?** Yes, on purpose: async-first FastAPI with structured
logging, SQLAlchemy 2.x, a layered architecture (domain, application, infrastructure), and strict
mypy. Each generated project's `README.md` and `AGENTS.md` describe its layout and conventions.

**Can I generate projects offline?** Yes, with the bundled templates: rendering never touches the
network or reads your environment, and Copier runs with `unsafe=False`, so templates can't execute
code. Git template packs, `-h`, and the generated project's `uv sync` need network access.

See [Compatibility and versioning](compatibility.md) for what each release keeps stable, and
[pytemplate-uv's changelog](https://github.com/yuxuzi/pytemplate-uv/blob/main/CHANGELOG.md) for
what changed.
