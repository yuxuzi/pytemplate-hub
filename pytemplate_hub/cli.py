"""Command-line interface for pytemplate-hub."""

import typer

app = typer.Typer(
    help="Command-line interface for pytemplate-hub.",
    no_args_is_help=True,
)


def main() -> None:
    """Run the command-line interface."""
    app()


if __name__ == "__main__":
    main()
