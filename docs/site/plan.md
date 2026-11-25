# Website plan (pytemplate-web, now the hub's `site` command)

> **Moved.** The website now lives in pytemplate-hub: `uv run pytemplate_hub site` renders the
> page with Jinja2 from the index, and `.github/workflows/pages.yml` publishes it. The separate
> pytemplate-web repository is retired. Superseded here: section 8's repository layout, the
> `data/hub-index.json` snapshot, `sync-index`, and the hosting paragraph (the hub's Pages workflow
> replaces them), and the W1-W7 work steps that name a separate repository. The design, the site
> map, the search and ranking rules, and the posts plan still apply.

Status: draft for review, 2026-11-24. Nothing is built, deployed, or published yet. The design is
in [`design/prototype.html`](design/prototype.html), a clickable prototype that uses the hub's
real listings (also as a private page: <https://claude.ai/artifact/T3SLTtrLqG3pvYQLqbkAnb>).

## 1. Goal

A public website for the pytemplate ecosystem: **pytemplate-uv** (the generator),
**pytemplate-hub** (the verified index), and the **template packs** listed on it. It has four jobs,
in this order:

1. **Find** a template for what you want to build: browse by category, search, filter, rank.
2. **Copy** a ready command, pinned to the commit and digest the hub checked, and a link to share.
3. **Learn**: a tutorial path from the first generated project to your own pack.
4. **Grow the community**: posts on new features and packs, adopter stories, and a short path to
   publishing a pack.

Readers: Python developers who use uv (first visit: "what is this, and can I try it in a
minute?"), team leads who want one standard project layout, and pack authors.

## 2. What exists

- The hub's `site` command (`pytemplate_hub/site.py`) builds one page with search and a
  reviewed-only filter, plus `index.json` (`format: 1`). It escapes all entry text, and its script
  never builds HTML from entry text. The new site keeps both rules.
- The hub lists 8 packs (all by the maintainer, owner `yuxuzi`): 5 starter packs
  (`pytemplate-starters`, `fastapi-service`, `mcp-server`, `data-pipeline`, `background-worker`)
  and 3 Quant-Agent-OS packs (`quant-apps`, `quant-baseline`, `quant-agent-tool`). None are
  reviewed yet, and all have 0 stars.
- `docs/tutorial.md`, `docs/authors.md`, and `docs/trust.md` in the hub, and pytemplate-uv's
  CHANGELOG (3.1 pins, 3.2 `-y`, 3.3 hub search) are the source material for Learn and Posts.
- The hub's release plan already decides some of this: categories come from the pack (D1), and a
  Pages deploy runs no pack code (D3). Copy leads with "Generate once. Own your code." and makes no
  adoption claims (D-3).

## 3. Competitors and what to take from them

| Site | What works | Take | Avoid |
| --- | --- | --- | --- |
| [Vercel Templates](https://vercel.com/templates) | Facets by use case, framework, database, auth, with counts; one primary action per card | Use-case categories plus a "stack" facet (FastAPI, SQLAlchemy, Polars…) with counts | Screenshot-led cards: a CLI template has no screenshot, so show the files and the command instead |
| [Astro Themes](https://astro.build/themes) | Official and community themes side by side, author pages, catalog refreshed daily | Disclose the maintainer's own packs with a label; author pages; scheduled rebuild | Accounts and a submission portal: the hub has no accounts by design, and listing is a pull request |
| [Spring Initializr](https://start.spring.io) | Pick options, get the project; a shareable URL pre-fills the form; "Explore" shows the files before download | **The command builder**: project name, profile, `-y`, live command, copy link that restores the choice; a "Preview first" tab with `plan` | Too many knobs at once: show the defaults and keep the rest folded |
| [Terraform Registry](https://registry.terraform.io) | Tiers (official, partner, community, archived), a version picker, a usage snippet pinned to a version | Tiers as words, not stars: Listed / Reviewed; a versions table; yanked versions hidden but kept in JSON | Paid tiers or partner badges |
| [Hugo Themes](https://themes.gohugo.io) | Metadata (tags, license, features) lives in the theme's own file; submission is a pull request | Categories and keywords read from `pytemplate-pack.toml`, checked by `verify` (D1) | Free-form tags that drift: use a fixed category list |
| [Yeoman generators](https://yeoman.io/generators/) | Anything with the `yeoman-generator` keyword is listed, sortable by stars | Sorting by stars and recency | Listing without checks: thousands of entries, many abandoned. The hub's checks are the difference |
| Cookiecutter and Copier | Large template ecosystems | Nothing to copy: neither has a central index, so people find templates through GitHub search and awesome lists, with no trust signal. **This is the gap pytemplate fills.** | |
| [Scientific Python cookie](https://learn.scientific-python.org/development/) | A template, a guide that explains each choice, and a checker, linked to each other | Learn content that explains *why* a pack makes each choice; posts and packs link to each other | |
| [shadcn/ui](https://ui.shadcn.com) | "You own the code" positioning; a copy-the-command flow | The same promise, which pytemplate already makes: a generated project is yours from the first commit | |

The positioning that follows: **the only Python template index where every listing is pinned to a
checked commit and digest, and where the generator refuses anything that changed.** Every page
should make that visible without a lecture: the pin label on each listing, and the refusal shown on
the home page.

## 4. Site map

| Route | Page | Main parts |
| --- | --- | --- |
| `/` | Home | Rotating spotlight hero (§6), "What do you want to build?" category tiles with counts, how the pin works, featured packs, latest posts, the trust table, the publish band |
| `/templates/` | Catalog | Search, category and stack facets, trust and Python filters, sort, results with a copy button |
| `/templates/<owner>/<pack>/` | Pack | Profiles, the command builder, Preview first (`plan`), versions, checks, security posture, source and issues links, related posts, similar packs |
| `/posts/` | Posts | Featured post, filter by kind, list, RSS/Atom feed |
| `/posts/<slug>/` | Post | Article, related packs, next post |
| `/learn/` | Learn | The tutorial path, guides, and reference (trust, authors) |
| `/publish/` | Publish a pack | Requirements, steps, the CI checks, the README badge |
| `/authors/<owner>/` | Author | The owner's packs |
| `/index.json`, `/llms.txt`, `/feed.xml` | Data | The hub's JSON for tools; a summary for coding agents; the posts feed |

Permalinks: `/templates/<owner>/<pack>/?profile=<id>&name=<project>` restores the builder, which is
what **Copy link** copies. The prototype uses `#pack-<id>--<profile>`, because an Artifact page
passes only the hash.

## 5. Finding a template: categories, search, ranking

### Categories and facets

Categories come from the pack, never from a free-text field in the index (hub decision D1). The
plan is a fixed list in the hub, `categories.toml`, which `verify` checks:

| id | Label |
| --- | --- |
| `cli` | Command-line apps |
| `library` | Libraries |
| `web` | Web services and APIs |
| `worker` | Background workers |
| `data` | Data pipelines |
| `ai` | AI tools and MCP |
| `quant` | Quant research |

A pack declares `categories = [...]` (from that list) and `keywords = [...]` (free words, for
search only) in `pytemplate-pack.toml`. Other facets come from each profile's own file: **stack**
(from `dependencies`, mapped to display names such as FastAPI or Polars), **kind** (`cli`,
`library`, `service`), **Python** (`supported_python`), plus **trust tier** and **license** from the
index. Counts show next to each option, and an option with no packs is hidden, not disabled.

### Search

Phase 1 is lexical and runs in the browser over the built JSON, with no library:

- Fields are weighted: pack name 5, pack id 4, categories, keywords, stack and profile names 3,
  descriptions 1.
- Prefix matching, and one typo allowed in words of five letters or more.
- A small synonym list, kept in the repo and tested: `rest`, `api`, `http` → web, FastAPI;
  `etl`, `dataframe` → data, DuckDB, Polars; `queue`, `job`, `celery` → worker, Redis;
  `agent`, `llm`, `claude` → MCP; `backtest`, `alpha`, `risk` → quant; `db`, `sql`, `postgres` →
  SQLAlchemy. The page says what it expanded ("rest also matched: web, FastAPI").
- When a query matches a profile, the result shows that profile's command, not the pack's first.
- No results: suggest the closest category and link to "Request a template" (a hub issue form).

**Semantic search, later and measured.** With 8 packs, embeddings add weight and no benefit: the
synonym list covers the vocabulary. Plan it as phase 6, behind a measurement:

1. A golden query set in the repo (`tests/search_queries.toml`: query → packs expected in the top
   3), run in CI against the built index. Report recall@3 for each change to search.
2. When the hub passes about 100 packs, or recall@3 drops below an agreed level, add build-time
   embeddings (a small open model run by the build, in Python) for **Similar packs** on each pack
   page. That needs no model in the browser.
3. Only if that is not enough: query embeddings in the browser with a small quantized model
   (tens of MB), loaded on demand behind a "Search by meaning" toggle, with lexical search as the
   default. No hosted embedding API: the site stays static and sends no queries anywhere.

### Ranking

The default sort is **Recommended**, with a published formula; the other sorts are Most stars,
Recently checked, and Name. Nobody can pay for rank, and the maintainer's packs get no boost.

```
recommended = 0.4 * trust + 0.3 * freshness + 0.3 * popularity
  trust      = 1.0 reviewed | 0.6 listed, every profile's lifecycle passed | 0.3 otherwise
  freshness  = 1.0 if checked in the last 30 days, falling linearly to 0 at 365 days
  popularity = min(1, log10(1 + stars) / 3)          # 1000 stars = 1.0
with a query: score = relevance / max relevance * (0.7 + 0.3 * recommended)
ties: name
```

The catalog's "How ranking works" panel shows this. Usage counts (copies, creates) would be a
better signal, but they need analytics, which is decision W5.

## 6. Design

Direction: **the catalog as a manifest**. Each listing is a ruled row with a *pin label*
(tag · commit · digest), drawn as a luggage tag because a git tag is what it is. The hero pairs a
terminal running the pinned command with a seal whose digest resolves character by character to
"matches the hub's check". Quiet everywhere else.

- **Type**: Martian Mono for display (wordmark, headlines, labels; CLI-native and wide), Schibsted
  Grotesk for text, JetBrains Mono for commands. Fonts are self-hosted on the real site, so a visit
  makes no third-party requests.
- **Color**: cool paper with a green bias, deep ink, and one accent, tag amber, used for pins,
  primary buttons, and the active state. Pass green and review blue are semantic, not accents. A
  full dark theme.
- **Hero**: a rotating spotlight of up to four slides: the thesis, the newest release post, new
  packs, and an adopter or Quant-Agent-OS story. It advances every 8 seconds with a progress bar,
  pauses on hover and focus, has a pause button and named tabs, and never auto-rotates with
  `prefers-reduced-motion`. The first slide is complete with no motion, so a link preview and a
  screenshot show it.
- **Commands**: shown on several lines with `\` continuations, copied as one line. Every copy
  button confirms with a toast and falls back to selecting the text.
- **Accessibility**: WCAG 2.2 AA contrast in both themes, visible focus, keyboard-only flows, and
  no information carried by color alone.

## 7. Posts

A Posts section to promote the ecosystem, from Markdown files in this repo
(`content/posts/YYYY-MM-DD-slug.md`) with front matter:

```yaml
title: "pytemplate-uv 3.3 finds packs on the hub"
date: 2026-11-24
kind: release            # release | hub | packs | guide | adopters | quant-agent-os
summary: "The skill searches the hub, and inspection commands take the pins."
packs: [yuxuzi/pytemplate-starters]   # pack pages link back to the post
featured: true
author: Leo Liu
```

- **Kinds**: pytemplate-uv releases, hub news, new packs, guides, adopter stories, and
  Quant-Agent-OS. The filter chips use these.
- **"Hot"**: without analytics, the featured posts (set by the editor) come first, then the
  newest. With analytics (W5), "most read this month" can be added.
- **Honesty rules**: an adopter story is published only with the adopter's permission, sent as a
  pull request or an approved draft; never an invented user, quote, or number. Posts about the
  maintainer's own projects (Quant-Agent-OS, the starter packs) carry a "From the maintainer"
  label. The hub itself stays generic: Quant-Agent-OS appears only in posts and in its own index
  entries.
- **Launch drafts** (all from real releases): pytemplate-uv 3.3 (the hub in the skill, pinned
  inspection), 3.2 (`-y`, `library` profile, `status`), "Why every command carries a commit and a
  digest" (3.1 pins), "Five starter packs to begin with", "Quant-Agent-OS 1.0 publishes its
  application packs on the hub", and "From cookiecutter to a pack" (the hub's planned migration
  guide, D-1). The prototype lists them as drafts.
- An RSS/Atom feed, and each post gets an Open Graph image built at build time.

## 8. Technology

**Recommendation: a small Python static build, plain HTML/CSS, and vanilla JavaScript. No Node,
no front-end framework.**

| Option | For | Against |
| --- | --- | --- |
| **Python build (Jinja2 + Markdown) + vanilla JS** (recommended) | Only `uv`, like every other project here; testable with pytest; one page per pack and post, good for search engines; no npm dependency tree on a site whose message is a checked supply chain | We write a little navigation and table-of-contents code ourselves |
| Plain hand-written HTML + JS | No build at all | Per-pack pages, posts, and shared header and footer would be copied by hand |
| Astro (+ Starlight) | The best tooling for content sites; Pagefind search | Brings Node and hundreds of npm packages into a uv-only ecosystem |
| MkDocs Material | Python, strong for docs | Weak for a faceted catalog; its authors are moving to a successor project, so check its status before relying on it |
| Next.js or another SPA | Rich interaction | Needs a server or a heavy client for a static catalog |

Shape of the repo (scaffolded with pytemplate-uv's own `python` profile, so the site uses the
generator it promotes):

```
pytemplate-web/
  pytemplate_web/      build.py (data → pages), search.py (synonyms, index), cli.py (build, serve)
  templates/           Jinja2 layouts and components
  content/posts/       Markdown posts
  content/learn/       Markdown lessons
  static/              css/, js/ (search, filters, builder, copy, spotlight), fonts/
  data/hub-index.json  a committed snapshot of the hub's index.json
  tests/               pages build offline; links resolve; untrusted entry text is escaped;
                       golden search queries; every page has a title and description
```

Dependencies to approve: `jinja2`, `markdown-it-py` (with `mdit-py-plugins`), `pygments` for code
highlighting. The JS is written here, with no CDN at run time.

**Data flow.** The build reads only `data/hub-index.json`, so builds are offline and reproducible.
`uv run pytemplate-web sync-index` refreshes it from a local hub checkout now, and from the hub's
published `index.json` once the hub is public. A scheduled job can open the refresh as a pull
request later (workflow edit, W4).

**Hosting.** GitHub Pages from this repository, with the custom domain added later through a
`CNAME` file. Cloudflare Pages is the alternative if you want its analytics or previews per pull
request. A private repository cannot run Actions right now (billing), so either the repository is
public at launch or the first deploys are made by hand.

## 9. What the hub must add

The website can only show what the hub's JSON carries. Today each profile is an id and a lifecycle
result. These hub pull requests come first (additive under `format: 1`, each with tests and a
JSON Schema; hub plan B2):

- **H1** Profile details, read from the pack at the listed commit and checked by `verify` like
  `name` and `description`: name, description, kind, `supported_python`, dependency names, and
  security posture. Per version, `checked_on` (date).
- **H2** `categories` and `keywords` from `pytemplate-pack.toml`, the fixed list in
  `categories.toml`, and an error for an unknown category (D1).
- **H3** Publish `index.json` and its schema at a stable URL when the hub goes public.

Until H1 and H2 merge, the prototype's category, stack, and profile details are taken from the
packs' own files by hand.

## 10. Growing the community

- **A one-minute first run**: the home page leads with one bundled command and the copy button.
- **Author funnel**: `/publish/` with requirements and steps; a "Listed on pytemplate hub" README
  badge (an SVG built per pack); author pages; a "Request a template" issue form whose requests
  become the list of packs we want.
- **Posts and the launch plan**: the drafts above; the hub plan's Show HN post, DEV article, and
  LinkedIn post (D-4) link to posts on the site.
- **For coding agents**: `llms.txt` and `index.json`, so an agent with the `pytemplate` skill finds
  the same packs.
- **Where people talk**: GitHub Discussions on the hub, linked from every page. The site has no
  accounts and no comments of its own.
- **Measures**, all public numbers: packs listed by someone other than the maintainer (0 today),
  pull requests from new contributors, pytemplate-uv's PyPI downloads and stars (28 today), and,
  if W5 allows, copies per pack.

## 11. Phases

Each phase is one pull request; the user merges. CI on intermediate pull requests runs Python 3.12
only, and the last pull request gets the full matrix.

Cheaper `worker` subagents write the code, one written brief per phase in `docs/briefs/`, each in
its own worktree. A brief names the files, the tests, the design tokens and components to reuse
from `design/prototype.html`, and the checks to run (`uv run pytest`, `ruff check`,
`ruff format --check`, `mypy`). The main session writes the briefs, reviews each diff against the
plan and the prototype, and runs the checks again before opening the pull request.

| Phase | Scope | Needs |
| --- | --- | --- |
| P0 | This plan and the prototype | Review |
| P1 | Scaffold with pytemplate-uv; `build` and `serve`; layout, tokens, home page with static data; tests | W1, W2 |
| H1-H2 | Hub pull requests for profile details, categories, keywords | Hub review |
| P2 | Catalog, pack pages, command builder, copy link, search, facets, ranking, golden queries | H1, H2 |
| P3 | Posts (Markdown, feed, Open Graph images) and the launch drafts | W6 |
| P4 | Learn (tutorial path, ported from the hub's docs), Publish, author pages, badge, `llms.txt` | W3 |
| P5 | Deploy workflow, domain, analytics choice, accessibility and performance check; launch with the hub's wave E | W4, W5, domain |
| P6 | Semantic search and similar packs, only when §5's measurement asks for it | Measurement |

## 12. Decisions for you

- **W1 Technology**: the Python static build with vanilla JS (recommended), or Astro.
- **W2 Repository**: create `yuxuzi/pytemplate-web` on GitHub now (private) or at launch; public at
  launch so Pages and Actions work. The local repository exists; nothing is pushed.
- **W3 Where the tutorial lives**: the website owns the user tutorial and the hub's README links to
  it (recommended), or the hub keeps it and the site renders a copy.
- **W4 Automation**: a Pages deploy workflow on push to `main`, and a scheduled index refresh that
  opens a pull request.
- **W5 Analytics**: none (recommended at launch, and the footer says so), or a privacy-friendly
  counter (no cookies) to rank posts and packs by use.
- **W6 Posts**: which launch drafts to write, who signs them, and whether Quant-Agent-OS posts
  appear at launch or later.
- **W7 Name and domain**: the names are provisional; nothing is registered.

## 13. Risks

- **An empty-looking catalog.** Eight packs from one author. Mitigation: lead with categories and
  the command, not the count; label the maintainer's packs; invite authors before launch.
- **Trust words read as endorsement.** Keep "Listed does not mean safe" on the catalog and pack
  pages, with the trust table one click away.
- **Stale data.** Show "Index as of <date>" in the footer and on every pack page.
- **A rotating hero hides content.** The first slide stands alone, motion stops on hover, focus,
  and reduced motion, and every slide's content is also on the page below.
