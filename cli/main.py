"""
Prismatica QA CLI — pqa command.

Usage:
    pqa test list
    pqa test run --domain auth --priority P0
"""

import typer

from cli.commands import list_cmd, run_cmd

app = typer.Typer(
    name="pqa",
    help="Prismatica QA — Test Hub CLI",
    no_args_is_help=True,
)

# Group all test commands under 'pqa test'
test_app = typer.Typer(
    name="test",
    help="Manage and execute test definitions.",
    no_args_is_help=True,
)

test_app.command("list")(list_cmd.list_tests)
test_app.command("run")(run_cmd.run_tests)

app.add_typer(test_app, name="test")


if __name__ == "__main__":
    app()
