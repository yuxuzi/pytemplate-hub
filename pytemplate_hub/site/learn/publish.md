# Publish a pack

This guide is for pack authors. It shows how to list a pack in the hub without help from the
maintainer. Read [What the checks mean](trust.md) for what the checks prove and what they do not.

## 1. Check that your pack can be listed

The pack format is defined by pytemplate-uv: read [Template packs](packs.md#write-a-pack) first.

A pack can be listed only when all of these are true:

- It is a contract 1 pytemplate pack, with `pytemplate-pack.toml` at the root of the repository. The
  manifest needs `contract = 1`, plus `name` and `description`.
- It lives in a public GitHub repository, and the URL looks like `https://github.com/<owner>/<repo>`
  with no `.git` suffix.
- It has a license file at the root: `LICENSE`, `LICENSE.md`, `LICENSE.txt`, or `COPYING`.
- It has at least one profile.
- It contains no symlinks.
- It does not use the Copier settings `_tasks`, `_migrations`, or `_jinja_extensions`. The checks
  refuse them.
- Its lifecycle commands start with `uv`, for example `uv sync` and `uv run pytest`. Other programs
  are refused.
- Each profile's `profile.toml` sets `name`, `description`, and `kind` (`cli`, `library`, or
  `service`). It may also set `supported_python`, `dependencies`, and `security_posture`. The hub
  records these and checks them on every `verify`. Dependencies are recorded by name only.
- `pytemplate-pack.toml` must set `categories`: one or two ids from this fixed list, which decide
  where the site files the pack. It may also set `keywords`: up to 12 search words of up to 30
  lowercase characters, for search only.

  ```toml
  categories = ["web"]
  keywords = ["fastapi", "rest", "api"]
  ```


  | id | Label |
  | --- | --- |
  | `cli` | Command-line apps |
  | `library` | Libraries |
  | `web` | Web services and APIs |
  | `worker` | Background workers |
  | `data` | Data pipelines |
  | `ai` | AI tools and MCP |
  | `quant` | Quant research |

  The list is fixed by pytemplate-uv, which refuses any other category while you write the pack
  (3.7 or later). A pack with no category cannot be listed: `add` refuses it and names the choices.
  New categories come in later pytemplate-uv releases.

  Packs that set `categories` or `keywords` need pytemplate-uv 3.4 or later. An older version
  refuses those keys, so `add` fails with `unknown key(s)`.

The hub's [example pack](https://github.com/yuxuzi/pytemplate-hub/tree/main/examples/sample-pack) is a minimal working pack. Use it as a reference for the layout:

```text
examples/sample-pack/
├── LICENSE
├── copier.yml
├── questions.yml
├── pytemplate-pack.toml
└── tool/
    ├── profile.toml
    └── template/
        ├── {{ _copier_conf.answers_file }}.jinja
        ├── README.md.jinja
        ├── pyproject.toml.jinja
        ├── tests/
        │   └── test_double.py.jinja
        └── {{ package_name }}/
            └── __init__.py
```

The profile `tool` is defined by `tool/profile.toml`, and its files live under `tool/template/`. The
example's `copier.yml` and `questions.yml` are pytemplate-uv's format, so check them against
[Template packs](packs.md#write-a-pack) when you write your own.

## 2. Tag a release

Tag the commit you want to list, then push the tag. The hub fetches the tag from GitHub.

```bash
git tag v1.0.0
git push origin v1.0.0
```

Never move a tag after you list it. The hub records the commit and a digest of the files. A moved tag
fails the next `verify`. Publish a new tag for a fix.

## 3. Add your pack to the index

Fork the hub repository on GitHub, then clone your fork. From the fork's root:

```bash
uv sync
uv run pytemplate_hub add https://github.com/<you>/<pack> --tag v1.0.0 --license MIT
```

Replace `<you>` and `<pack>` with your GitHub owner and repository name.

- `--tag` is required. It is the tag you pushed.
- `--license` is required. It is your declared SPDX license, such as `MIT`.
- `--index` is optional. It defaults to `index`, so the command writes
  `index/<you>/<pack-id>.toml`. The directory is your GitHub owner name in lowercase.

`add` checks the tag and writes the entry. Open the file and read it before you commit; the next
section says what each field means.

**Do not pass `--run-lifecycle` on your own machine.** That flag runs the pack's lifecycle commands,
which executes the pack's code. Use it only on an isolated machine with no credentials. Without the
flag, your entry records `lifecycle = "not-run"` for each profile. The verify CI job still runs the
lifecycle commands on your pull request, and the pull request fails if they fail, but it does not
change that recorded value.

To try `add` without touching your fork's `index/` folder, point `--index` at a scratch directory:

```bash
uv run pytemplate_hub add https://github.com/<you>/<pack> --tag v1.0.0 --license MIT --index "$(mktemp -d)/index"
```

## 4. Read the entry

The entry binds each tag to the exact commit and file contents that were checked. Everything in it
comes from your pack or from the check; you write none of it by hand:

```toml
# index/<github-owner>/<pack-id>.toml
format = 1
repository = "https://github.com/acme/sample-pack"
name = "Sample pack"                     # from pytemplate-pack.toml, latest version
description = "A small package."         # from pytemplate-pack.toml, latest version
categories = ["cli", "library"]          # from pytemplate-pack.toml; the table above only
keywords = ["starter", "tests"]          # from pytemplate-pack.toml; search words

[[versions]]
tag = "v1.0.0"
commit = "<40-character commit SHA>"
digest = "<SHA-256 over every file's path and bytes>"
pack_version = "1.0.0"
license = "MIT"                          # your --license declaration
checked_with = "pytemplate-uv==3.5.0"    # the pytemplate-uv that checked it
checked_on = 2026-11-24                  # the day add ran
profiles = [{ id = "tool", lifecycle = "not-run", name = "Sample tool", description = "A small package.", kind = "library", supported_python = ["3.11", "3.12"], dependencies = ["pytest"], security_posture = "Rendering contacts no service." }]
```

Each profile's details come from its own `profile.toml`, and `dependencies` holds names only.
Entries written before a field existed still load: `verify` skips a detail that an entry does not
record, and checks every detail that it does record. Once the pull request is merged, the pack's
users run `uvx pytemplate-uv@latest create my-app -h <you>/<pack>@v1.0.0 -y`.

## 5. Open the pull request

Commit only the new or changed entry file. Open a pull request against the hub's `main` branch. The
pull request template lists the checks to confirm.

The verify CI job runs on any pull request that changes `index/**`. It runs two steps:

1. `check-claims` compares your pull request with the base branch. It fails if your change adds a
   `reviewed_by` value, or if it changes a recorded fact of a listed version, such as the commit,
   digest, pack version, license, `checked_with`, or profiles.
2. `verify --run-lifecycle` re-checks every listed version that is not yanked, including versions
   other people listed. It fetches each tag, compares the recorded facts, and runs the lifecycle
   commands.

The job runs your pack's code. It has no secrets and only read access.

Reading the failures:

| Message contains | What it means | What to do |
| --- | --- | --- |
| `adds a review claim` | Your entry has a `reviewed_by` value | Remove it. Only a maintainer adds it. |
| `changes a listed version's facts` | You edited a recorded field | Revert the edit. For a change, publish a new tag. |
| `the commit changed` or `the digest changed` | The tag moved, or its files changed | Publish a new tag, and list it. Never move a listed tag. |
| `the pack version changed`, `the pack id changed`, or `the profiles changed` | The pack's manifest or profiles differ from the entry | Restore the tag's values, or publish a new tag and list it. |
| `the profile <id> <field> changed`, `the categories changed`, or `the keywords changed` | The profile's `profile.toml`, or the pack's categories or keywords, differ from the entry | Restore the tag's values, or publish a new tag and list it. verify skips a detail that the entry does not record. |
| `unknown category` | A category is not in the table in this guide | Use one of the listed ids. |
| `declares no categories` | `pytemplate-pack.toml` has no `categories` | Add one or two ids from the table, tag again, and list the new tag. |
| `unknown key(s) categories` or `unknown key(s) keywords` | The pytemplate-uv that `add` uses is older than 3.4 | Use pytemplate-uv 3.4 or later, then tag and list again. |
| `has no license file` | No license file at the root | Add the file, push a new tag, and list it. |
| `has no profiles` or `The pack failed its checks` | The pack does not render, or it is not a contract 1 pack | Fix the pack, push a new tag, and list it. |
| `failed:` followed by command output | A lifecycle command failed with default answers | Run the same command in an empty directory to reproduce it. |
| `already lists` | The tag is already in the entry | Use a new tag. |
| `lowercase pack id` or `the directory must be the repository owner` | The file path is wrong | Let `add` write the file. Do not rename it by hand. |

Run `uv run pytemplate_hub verify` locally to see the same problems, without `--run-lifecycle`.

## 6. Add a later version

Tag the new commit, for example `v1.1.0`, and push the tag. Then run `add` again with the new tag, and
open a new pull request:

```bash
uv run pytemplate_hub add https://github.com/<you>/<pack> --tag v1.1.0 --license MIT
```

Earlier versions stay as they are. The latest version that is not yanked is the one the name,
description, categories, and keywords come from. Each version records `checked_on`, the day `add`
ran.

## 7. Yank a version

Yanking hides a listed version from the site, and `verify` stops re-checking it. The version's
entry stays in the index with its reason, so the record of what was listed remains. The latest
version that is not yanked is the one the name, description, categories, and keywords come from.

To yank a version, run `yank` with the pack as `OWNER/PACK`, the tag, and the reason users will see:

```bash
uv run pytemplate_hub yank <you>/<pack> v1.0.0 --reason "Fails on Python 3.13. Use v1.0.1."
```

The command changes only the version's `yanked` field in its entry, so the change passes
`check-claims`. It refuses a tag the entry does not list, and a version that is already yanked.
Commit the entry file and open a pull request, as in step 5.

## 8. What "reviewed" means

`listed` means the automated checks passed at one commit. `reviewed` is a separate tier. It means a
named maintainer read the diff at that commit and recorded `reviewed_by`.

Authors cannot claim it. The check fails any pull request that adds `reviewed_by`, so a maintainer
adds it on purpose, after reading the code. A listed pack is not a reviewed pack, and neither tier
means the pack is safe. See [What the checks mean](trust.md).
