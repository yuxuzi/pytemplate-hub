## Index change (listing or updating a pack)

- [ ] The entry was made with `pytemplate_hub add`, not edited by hand (a `yanked` reason is the only hand edit allowed).
- [ ] The tag is pushed, and it will not move.
- [ ] The pack repository has a license file at its root.
- [ ] This pull request does not add `reviewed_by`. Only a maintainer adds it.

## Code change

- [ ] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy pytemplate_hub` pass.
- [ ] Tests are added or updated, including the failure path.
