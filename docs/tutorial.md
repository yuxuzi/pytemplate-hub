# Tutorial: pytemplate-uv and pytemplate-hub

This tutorial takes you from your first generated project to a template pack of your own, listed
on the hub for others to use. It takes about 30 minutes.

Two projects work together:

- **[pytemplate-uv](https://github.com/yuxuzi/pytemplate-uv)** generates Python projects. It
  bundles a few profiles (a typed package with a CLI, a library, a FastAPI service) and renders
  *template packs*: directories or git repositories with profiles of their own.
- **pytemplate-hub** (this repository) is where you find template packs. It stores references,
  not files: each pack stays in its author's GitHub repository, and each listed version records
  the tag, commit, and file digest that passed the hub's checks.

## What you need

- [uv](https://docs.astral.sh/uv/). Nothing else: no pip, no virtualenv activation, no make.
- git, and a GitHub account for parts 5 and 6.

You never install pytemplate-uv to use it: `uvx pytemplate-uv@latest` runs the latest release.
If you prefer a `pytemplate` command, run `uv tool install pytemplate-uv`.

## 1. Generate a project from the bundled templates

```bash
uvx pytemplate-uv@latest create my-tool -y
cd my-tool
uv sync
uv run pytest
uv run my_tool --help
```

`create` used the default `python` profile, and `-y` accepted the defaults instead of asking. The
project comes with ruff, strict mypy, pytest, a GitHub Actions workflow, and an `AGENTS.md` for
coding agents. When `create` finishes, it prints the project's own check commands.

Run `uvx pytemplate-uv@latest list-profiles` and `list-components` to see what is bundled. When the
bundled profiles don't fit, look on the hub.

## 2. Find a pack on the hub

Every pack on the hub has a file in [`index/`](../index), named `index/<github-owner>/<pack-id>.toml`.
The hub's site, <https://yuxuzi.github.io/pytemplate-hub/>, lists the same entries with search and a
ready command. Here is a listed entry:

```toml
repository = "https://github.com/yuxuzi/pytemplate-starters"
name = "Python starters"

[[versions]]
tag = "v1.0.0"
commit = "2886e570d1b964811e63b6aa93f3e0ede2e8e7d2"
digest = "9257161472cfe280e79c7452ff0e01618b278ea57b7d74280b882976969de924"
license = "MIT"
checked_with = "pytemplate-uv==3.2.0"
profiles = [{ id = "cli", lifecycle = "passed" }, { id = "library", lifecycle = "passed" }, { id = "script", lifecycle = "passed" }]
```

`lifecycle = "passed"` means the hub rendered that profile with default answers and its own
commands (`uv sync`, lint, type-check, tests) passed when it was checked. It does not mean the pack
is reviewed or safe: [What the checks mean](../README.md#what-the-checks-mean) has the details.

## 3. Look before you render

Read the pack's repository first. Rendering is safe (Copier runs with `unsafe=False`, and the hub
refuses packs with tasks, migrations, Jinja extensions, or symlinks), but **the generated project
runs code when you use it**: its build backend, dependencies, and tests.

Then ask pytemplate-uv what the pack offers and what it would write. Pass the listing's commit
and digest here too (pytemplate-uv 3.3 or later), so you inspect exactly the files the hub checked.
Neither command writes anything:

```bash
uvx pytemplate-uv@latest list-profiles \
  --template gh:yuxuzi/pytemplate-starters --template-ref v1.0.0 \
  --template-commit 2886e570d1b964811e63b6aa93f3e0ede2e8e7d2 \
  --template-digest 9257161472cfe280e79c7452ff0e01618b278ea57b7d74280b882976969de924

uvx pytemplate-uv@latest plan --name hello-cli -p cli \
  --template gh:yuxuzi/pytemplate-starters --template-ref v1.0.0 \
  --template-commit 2886e570d1b964811e63b6aa93f3e0ede2e8e7d2 \
  --template-digest 9257161472cfe280e79c7452ff0e01618b278ea57b7d74280b882976969de924
```

`plan` lists the files and the dependencies the project would get.

## 4. Create a project from the listing

Use the short command from the listing. It names the pack and tag, and pytemplate-uv 3.5 or later
reads the commit and digest the hub checked from the hub's index, then refuses the pack if they
no longer match:

```bash
uvx pytemplate-uv@latest create hello-cli -h yuxuzi/pytemplate-starters@v1.0.0 -p cli -y
```

`-h` is `--hub`, and `--help` prints help. Without `-p` in a terminal, pytemplate-uv asks for the
profile. For CI or offline use, the listing's fully pinned command gives the commit and digest
yourself, and needs no index:

```bash
uvx pytemplate-uv@latest create hello-cli -p cli \
  --template gh:yuxuzi/pytemplate-starters --template-ref v1.0.0 \
  --template-commit 2886e570d1b964811e63b6aa93f3e0ede2e8e7d2 \
  --template-digest 9257161472cfe280e79c7452ff0e01618b278ea57b7d74280b882976969de924 -y
cd hello-cli
uv sync
uv run pytest
```

With the pins, pytemplate-uv refuses a fetched pack if the tag was moved or any file changed since
the hub checked it, and writes nothing:

```text
Error: Template pack 'gh:yuxuzi/pytemplate-starters' at v1.0.0 has digest 9257…, not the pinned
0000…. Nothing was rendered.
```

A command with only `--template-ref` fetches whatever the tag points to today. Keep the pins.
A pinned pack is cached after the first fetch and checked against the digest on every use, so it
always renders the listed files; pass `--no-cache` to fetch it again and check the tag too.

The project is yours from the first commit. `.pytemplate.toml` records the pack, its commit, your
answers, and a hash of every generated file, so `uvx pytemplate-uv@latest status` later lists the
files you changed.

## 5. Make your own pack

A pack has the same layout as pytemplate-uv's bundled templates. The smallest working one is this
repository's [`examples/sample-pack`](../examples/sample-pack):

```
my-pack/
  pytemplate-pack.toml       # contract = 1, id, name, description, version
  copier.yml                 # _subdirectory: "{{ profile }}/template"; --- !include questions.yml
  questions.yml              # the questions every profile can ask
  LICENSE
  tool/profile.toml          # the profile: id, questions, dependencies, lifecycle_commands
  tool/template/...          # the project tree; only *.jinja files are rendered
```

Start from a copy, give it your own `id` and `name` in `pytemplate-pack.toml`, and render it from
the directory while you work:

```bash
cp -R pytemplate-hub/examples/sample-pack my-pack
uvx pytemplate-uv@latest list-profiles --template ./my-pack
uvx pytemplate-uv@latest create try-it -p tool --template ./my-pack -y
cd try-it && uv sync && uv run pytest
```

Each profile's `lifecycle_commands` are the commands the hub runs on a project rendered with
default answers, so run them yourself before you publish. `uvx pytemplate-uv@latest schema pack`,
`schema profile`, and `schema component` print the full formats, and pytemplate-uv's
[Template packs](https://github.com/yuxuzi/pytemplate-uv#template-packs) section lists the rules.

When the generated project passes, push the pack to the root of a public GitHub repository and tag
it:

```bash
git tag v1.0.0
git push origin main v1.0.0
```

Anyone can now use it with `--template gh:you/my-pack --template-ref v1.0.0`, listed or not.

## 6. Share your pack on the hub

Listing makes your pack easy to find, and gives its users a command pinned to what was checked.
You keep the repository; the hub keeps a reference to each tag you submit.

A pack can be listed when:

- it is a contract 1 pytemplate pack at the root of a public GitHub repository;
- the version is a tag, and the repository has a license file;
- every profile renders, and the rendering rules above hold.

To list it, fork this repository and run:

```bash
git clone https://github.com/<you>/pytemplate-hub
cd pytemplate-hub
uv sync
uv run pytemplate_hub add https://github.com/<you>/my-pack --tag v1.0.0 --license MIT
uv run pytest
```

`add` fetches the tag, checks the pack, and writes `index/<you>/my-pack.toml` with the commit and
digest. Commit that one file and open a pull request. The hub's CI checks it again; a maintainer
reads the diff and merges it. For a later version, tag it and run `add` again: it appends a
version to the same file.

`--run-lifecycle` also runs each profile's lifecycle commands, which **executes the pack's code**.
Use it only on an isolated machine with no credentials.

[List your pack](authors.md) has the details: what CI reports, later versions, yanking, and what
"reviewed" means.

## 7. Work with a coding agent

pytemplate-uv ships a skill that teaches Claude Code and other agents to choose a profile, check
the request with `plan`, wait for your confirmation, and then create the project:

```bash
uvx pytemplate-uv@latest skill install
```

Ask, for example, *"Create a command-line app called hello-cli from the pytemplate-starters pack
on the hub, pinned to its listed commit"*. Projects from the bundled templates, and many packs,
include an `AGENTS.md` that tells the agent the project's commands and rules.

## Where next

- [pytemplate-uv's README](https://github.com/yuxuzi/pytemplate-uv#readme): every command and option.
- [What the checks mean](../README.md#what-the-checks-mean), before you rely on a listing.
- [List your pack](authors.md): the full guide for pack authors.
- [Contributing](../CONTRIBUTING.md): improve the hub itself.
