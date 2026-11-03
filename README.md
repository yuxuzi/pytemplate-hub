# pytemplate-hub

A static, verified index of pytemplate-uv template packs

## Requirements

[uv](https://docs.astral.sh/uv/) is the only tool you need. It installs Python 3.11+
and every development tool on demand, on Windows, macOS, and Linux.

## Getting started

```bash
uv sync                      # create .venv and install the project with its dev group
uv lock                      # create uv.lock, then commit it for reproducible installs
uv run pytemplate_hub --help
uv run pytemplate_hub hello --name World
```

## Development

| Task | Command |
| --- | --- |
| Run tests with coverage | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type-check | `uv run mypy pytemplate_hub` |
| Build sdist and wheel | `uv build` |
| Install git hooks | `uvx pre-commit install` |

Add runtime dependencies with `uv add <package>` and development tools with
`uv add --dev <package>`.

## Project layout

```
pytemplate_hub/
  cli.py      # Typer command-line interface (thin layer)
  core.py     # business logic, testable without the CLI
  py.typed    # marks the package as typed
tests/        # pytest suite
```

## License

MIT — Leo Liu <yuxuzi@gmail.com>
