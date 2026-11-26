# pytemplate-hub

A verified index of [pytemplate-uv](https://github.com/yuxuzi/pytemplate-uv) template packs, built
as a static website that also holds the documentation for both projects.

**Website: <https://yuxuzi.github.io/pytemplate-hub/>.** Browse the packs, copy the command that
creates a project from one, and read the tutorial and guides. This README is about the repository
itself; all user documentation is on the website.

## Find a template

Browse the packs on the [website](https://yuxuzi.github.io/pytemplate-hub/), or the entries in
[`index/`](index), one file per pack. Each listing gives a short command; pytemplate-uv 3.5 or
later reads the commit and digest the hub checked for that tag, and refuses the pack if anything
changed since:

```bash
uvx pytemplate-uv@latest create my-app -h <owner>/<pack>@<tag> -p <profile> -y
```

The hub stores references, not templates: authors keep their packs in their own GitHub
repositories, and each entry binds a tag to the exact commit and file contents that were checked.
**A listed pack is not a reviewed or safe pack**, and a generated project's dependencies, build
backend, and tests still run code when you use them.

## Documentation

| Page | For |
| --- | --- |
| [Tutorial](https://yuxuzi.github.io/pytemplate-hub/learn/tutorial/) | Your first project, a pack from the hub, and a pack of your own, listed |
| [Using pytemplate-uv](https://yuxuzi.github.io/pytemplate-hub/learn/guide/) | Every command and option of the generator |
| [Template packs](https://yuxuzi.github.io/pytemplate-hub/learn/packs/) | Using, writing, and pinning packs |
| [Publish a pack](https://yuxuzi.github.io/pytemplate-hub/publish/) | Listing your pack: requirements, the entry, the pull request, and CI |
| [What the checks mean](https://yuxuzi.github.io/pytemplate-hub/learn/trust/) | What a listing proves, the security model, and the limits |
| [Compatibility and versioning](https://yuxuzi.github.io/pytemplate-hub/learn/compatibility/) | What each pytemplate-uv release keeps stable |

The pages are built from the Markdown in
[`pytemplate_hub/site/learn/`](pytemplate_hub/site/learn); edit them there.

## Working on the hub

The hub is a uv project. Clone it and run `uv sync`; nothing needs pip, virtualenv activation, or
make, and the tests run offline.

```bash
uv run pytemplate_hub add https://github.com/acme/sample-pack --tag v1.0.0 --license MIT
uv run pytemplate_hub verify                     # fail if a tag moved or a pack stopped passing
uv run pytemplate_hub check-claims --base OLD    # fail if a change claims a review
uv run pytemplate_hub site --no-stars            # build the website into site/, offline
```

`--run-lifecycle` also runs each profile's lifecycle commands. **That executes the pack's code**, so
use it only on an isolated machine with no credentials.

`site` writes the home page, the catalog (`templates/`, with search, filters, and sorting), a page
per pack with a command builder, the Learn pages, `index.json` (the same data for tools),
`index.schema.json`, and the static files. Each push to `main` publishes it through
[`.github/workflows/pages.yml`](.github/workflows/pages.yml), which runs no pack code.

| Task | Command |
| --- | --- |
| Test (offline) | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type-check | `uv run mypy pytemplate_hub` |

- To list a pack, follow [Publish a pack](https://yuxuzi.github.io/pytemplate-hub/publish/).
- To change the hub itself, read [CONTRIBUTING.md](CONTRIBUTING.md), and open an issue to discuss a
  larger change first.
- Maintainer documents (the launch plan, the audit, the website's plan and design) are in
  [`docs/`](docs).

## License

MIT. See [LICENSE](LICENSE).
