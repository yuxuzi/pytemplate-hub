"""Command-line interface for pytemplate-hub."""

from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from pytemplate_hub.errors import HubError
from pytemplate_hub.fetch import GitFetcher
from pytemplate_hub.site import build_site, github_stars, no_stars
from pytemplate_hub.verify import (
    add_version,
    changed_claims,
    entry_files,
    verify_entry,
    yank_version,
)

app = typer.Typer(
    help="Check template packs and maintain the pytemplate-hub index.",
    no_args_is_help=True,
)
console = Console()
errors = Console(stderr=True)
fetcher = GitFetcher()

IndexOption = Annotated[Path, typer.Option(help="The index directory.")]
LifecycleOption = Annotated[
    bool,
    typer.Option(
        "--run-lifecycle",
        help="Also run each profile's lifecycle commands. This EXECUTES THE PACK'S CODE: use it "
        "only on an isolated machine with no credentials.",
    ),
]


@app.command()
def add(
    repository: Annotated[str, typer.Argument(help="https://github.com/owner/repo")],
    tag: Annotated[str, typer.Option(help="The git tag to list.")],
    license_name: Annotated[str, typer.Option("--license", help="SPDX license of the pack.")],
    index: IndexOption = Path("index"),
    run_lifecycle: LifecycleOption = False,
) -> None:
    """Check a tagged pack and record its commit, digest, and results in the index."""
    try:
        path = add_version(
            index, repository, tag, license_name, fetcher, run_lifecycle=run_lifecycle
        )
    except (HubError, ValueError) as error:
        errors.print(str(error), markup=False, soft_wrap=True)
        raise typer.Exit(1) from error
    console.print(f"Recorded {tag} in {path}", markup=False, soft_wrap=True)


@app.command()
def yank(
    entry: Annotated[str, typer.Argument(help="The pack as OWNER/PACK, for example acme/sample.")],
    tag: Annotated[str, typer.Argument(help="The listed tag to yank.")],
    reason: Annotated[str, typer.Option(help="Why the version is yanked, shown to users.")],
    index: IndexOption = Path("index"),
) -> None:
    """Yank a listed version: hide it from the site and stop re-checking it."""
    owner, separator, pack_id = entry.partition("/")
    if not separator or "/" in pack_id:
        errors.print(
            f"{entry!r} is not OWNER/PACK. Give the owner and the pack id, separated by one slash.",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(1)
    try:
        path = yank_version(index, owner, pack_id, tag, reason)
    except (HubError, ValueError) as error:
        errors.print(str(error), markup=False, soft_wrap=True)
        raise typer.Exit(1) from error
    console.print(f"Yanked {tag} of {owner}/{pack_id} in {path}", markup=False, soft_wrap=True)


@app.command("check-claims")
def check_claims(
    base: Annotated[Path, typer.Option(help="The index before the change.")],
    index: IndexOption = Path("index"),
) -> None:
    """Fail if a change adds a review claim or alters a listed version's recorded facts."""
    try:
        problems = changed_claims(base, index)
    except HubError as error:
        errors.print(str(error), markup=False, soft_wrap=True)
        raise typer.Exit(1) from error
    for problem in problems:
        errors.print(problem, markup=False, soft_wrap=True)
    if problems:
        raise typer.Exit(1)
    console.print("No protected fields changed.", markup=False, soft_wrap=True)


@app.command()
def verify(
    index: IndexOption = Path("index"),
    run_lifecycle: LifecycleOption = False,
) -> None:
    """Re-check every listed version; fail if a tag moved or a pack stopped passing."""
    if not index.is_dir():
        errors.print(f"{index} is not a directory.", markup=False, soft_wrap=True)
        raise typer.Exit(1)
    files = entry_files(index)
    problems = [
        problem
        for path in files
        for problem in verify_entry(path, fetcher, run_lifecycle=run_lifecycle)
    ]
    for problem in problems:
        errors.print(problem, markup=False, soft_wrap=True)
    if problems:
        raise typer.Exit(1)
    console.print(f"Verified {len(files)} entries.", markup=False, soft_wrap=True)


@app.command()
def site(
    index: IndexOption = Path("index"),
    output: Annotated[Path, typer.Option(help="Where to write the site.")] = Path("site"),
    stars: Annotated[
        bool, typer.Option("--stars/--no-stars", help="Fetch star counts from GitHub.")
    ] = True,
) -> None:
    """Build the static site from the index."""
    if not index.is_dir():
        errors.print(f"{index} is not a directory.", markup=False, soft_wrap=True)
        raise typer.Exit(1)
    try:
        shown = build_site(
            index,
            output,
            stars=github_stars if stars else no_stars,
            built_on=date.today().isoformat(),
        )
    except HubError as error:
        errors.print(str(error), markup=False, soft_wrap=True)
        raise typer.Exit(1) from error
    console.print(f"Built {output} with {shown} packs.", markup=False, soft_wrap=True)


def main() -> None:
    """Run the command-line interface."""
    app()


if __name__ == "__main__":
    main()
