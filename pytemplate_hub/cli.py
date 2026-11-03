"""Command-line interface for pytemplate-hub."""

from importlib.metadata import metadata
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pytemplate_hub.core import greet

app = typer.Typer(
    help="Command-line interface for pytemplate-hub.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def hello(
    name: Annotated[str, typer.Option(help="Name to greet.")] = "World",
    formal: Annotated[bool, typer.Option("--formal", "-f", help="Use a formal greeting.")] = False,
) -> None:
    """Greet someone."""
    console.print(greet(name, formal=formal), style="bold green")


@app.command()
def info() -> None:
    """Show project information."""
    table = Table(title="Project Information")
    table.add_column("Attribute", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Name", "pytemplate-hub")
    table.add_row("Package", "pytemplate_hub")
    table.add_row(
        "Description",
        metadata("pytemplate-hub")["Summary"],
    )
    console.print(table)


def main() -> None:
    """Run the command-line interface."""
    app()


if __name__ == "__main__":
    main()
