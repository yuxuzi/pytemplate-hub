# Template packs

A template pack is a directory or git repository with your own profiles and components. pytemplate-uv
renders it with the same composition logic and safety rules as its bundled templates. This page
covers using a pack, writing one, and pinning it to the files that were checked.

## Use a pack from the hub

The [hub](https://yuxuzi.github.io/pytemplate-hub/) lists packs that passed its checks. Each listed
version records the tag, commit, and digest that were checked. Name a listed pack with `-h`
(`--hub`), and pytemplate-uv 3.5 or later reads those pins from the hub's index:

```bash
uvx pytemplate-uv@latest list-profiles -h yuxuzi/pytemplate-starters@v1.0.0
uvx pytemplate-uv@latest plan --name my-app -h yuxuzi/pytemplate-starters@v1.0.0 -p cli
uvx pytemplate-uv@latest create my-app -h yuxuzi/pytemplate-starters@v1.0.0 -p cli -y
```

- Leave off `@v1.0.0` to take the newest version that is not yanked.
- Without `-p` in a terminal, `create` asks for the profile.
- `-h` alone, and `--help`, print help.
- A pack that does not match its pins is refused before anything is read, with exit code 1.
- In a request file, write `hub = "owner/pack@tag"`.
- `PYTEMPLATE_HUB_URL` points `-h` at another copy of the hub's index, such as an internal mirror.

Read a pack's repository before you use it: rendering is safe, but **a generated project runs code
when you use it**, through its build backend, dependencies, and tests. [What the checks
mean](trust.md) says what a listing proves.

**In CI and offline**, use the fully pinned form. It writes the pins into the command, so it never
reads the hub's index. Each listing on the hub gives this command too:

```bash
uvx pytemplate-uv@latest create my-app -p cli \
  --template gh:yuxuzi/pytemplate-starters --template-ref v1.0.0 \
  --template-commit 2886e570d1b964811e63b6aa93f3e0ede2e8e7d2 \
  --template-digest 9257161472cfe280e79c7452ff0e01618b278ea57b7d74280b882976969de924 -y
```

## Write a pack

A pack has the same layout as the bundled templates:

```text
my-pack/
  pytemplate-pack.toml       # contract = 1, id, name, description, version; categories, keywords
  copier.yml                 # _subdirectory: "{{ profile }}/template"; --- !include questions.yml
  questions.yml              # profile, project_name, package_name, components, ...
  <profile>/profile.toml     # the profile manifest (pytemplate schema profile)
  <profile>/template/...     # the project tree; only *.jinja files are rendered
  components/<id>.toml       # component manifests (pytemplate schema component)
```

Render it from a directory while you work, then from git once it is tagged:

```bash
pytemplate list-profiles --template ./my-pack
pytemplate create my-tool -p tool --template ./my-pack -y
pytemplate create my-tool -p tool --template gh:org/my-pack --template-ref v1.2.0 -y
```

The rules:

- Packs are selected explicitly for each request; nothing is discovered or installed.
- They render with Copier's `unsafe=False`. `_tasks`, `_migrations`, `_jinja_extensions`,
  `_external_data`, and symlinks are rejected, including in files a pack's `copier.yml` includes.
- Pack-generated projects record the pack's source and tag, and for a git pack its commit and
  digest too.
- `pytemplate-pack.toml` lists `categories` from a fixed list: `cli`, `library`, `web`, `worker`,
  `data`, `ai`, and `quant` (pytemplate-uv 3.7 or later refuses any other, with a suggestion). They
  are optional for a pack you only use yourself, and required to list it on the hub
  ([Publish a pack](publish.md#1-check-that-your-pack-can-be-listed)). `keywords` are free search
  words: at most 12 lowercase strings of 1 to 30 characters, with no spaces at either end.
- Each profile's `lifecycle_commands` are the checks a project rendered with default answers must
  pass; the hub runs them before listing a pack.
- `pytemplate schema pack`, `schema profile`, and `schema component` print the full formats. The
  hub's [example pack](https://github.com/yuxuzi/pytemplate-hub/tree/main/examples/sample-pack) is
  the smallest working one.

When your pack works, [publish it on the hub](publish.md) so others can find it with `-h`.

## Pin a pack

For a pack that is not listed, pin it yourself so that a changed pack is refused:

```bash
pytemplate create my-tool -p tool --template gh:org/my-pack --template-ref v1.2.0 \
  --template-commit <commit> --template-digest <digest> -y
```

- `--template-ref` also accepts a full commit hash.
- The discovery commands (`list-profiles`, `describe-profile`, `list-components`,
  `describe-component`) accept the same pins.
- A pack pinned to both a commit and a digest is cached under your user cache directory and checked
  against the digest on every use. A cached copy is not fetched again, so it always renders the
  pinned files, and a moved tag is only noticed on the next fetch. Pass `--no-cache` (or set
  `PYTEMPLATE_NO_CACHE=1`) to fetch it again; `PYTEMPLATE_CACHE_DIR` moves the cache.
- Git never prompts for credentials, and a clone stops after 120 seconds
  (`PYTEMPLATE_GIT_TIMEOUT`).

## The digest

The digest is a SHA-256 over every file in the pack's checkout, without `.git`, in order of their
path components compared as case-sensitive strings. For each file, it hashes the path with forward
slashes, a NUL byte, the file's bytes, and another NUL byte. pytemplate-uv and the hub compute it
the same way, so a digest the hub records is one pytemplate-uv can check. The format is stable:
see [Compatibility and versioning](compatibility.md#template-packs).
