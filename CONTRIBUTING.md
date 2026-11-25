# Contributing

## Listing a pack

If you want to list a pack, read [Publish a pack](https://yuxuzi.github.io/pytemplate-hub/publish/).
Make index entries with
`pytemplate_hub add`. Do not edit an entry by hand, except to add a `yanked` reason.

## Changing the hub

- Use `uv` only. Run `uv sync` to install. Do not use pip, a virtualenv, or make.
- Before you open a pull request, run these four checks:

  ```bash
  uv run pytest
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy pytemplate_hub
  ```

- Tests run offline. Use the local git fixture in `tests/conftest.py`. Do not use the network or real
  credentials.
- Keep one test module per source module. For example, `pytemplate_hub/verify.py` is tested in
  `tests/test_verify.py`.
- Add or update tests with every behavior change. Include the failure path.
- Entry text is untrusted. Names, descriptions, and repository fields come from pack authors. Escape
  them in any output. Do not build HTML in the site's page script.
- Never give `.github/workflows/verify-index.yml` secrets or write access. Never add a
  `pull_request_target` trigger to it. `tests/test_workflow.py` checks some of this.
- Changes to CI workflows, release configuration, or dependency version bounds need the maintainer's
  agreement first.
- Add runtime dependencies with `uv add <package>` and development tools with `uv add --dev <package>`.
  Do not edit `uv.lock` by hand.
- Keep the hub generic. Its code and documents must not name a publisher or a consumer.
  `tests/test_independence.py` checks this for some files.
- Read [What the checks mean](https://yuxuzi.github.io/pytemplate-hub/learn/trust/) before you change
  how a check works, and update that page with the change.
- User documentation lives on the website only. Edit its pages in `pytemplate_hub/site/learn/`, and
  do not add guides to `docs/`, which holds maintainer documents.
