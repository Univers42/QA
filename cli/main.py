"""
Prismatica QA CLI — pqa command.

Usage:
    pqa test list
    pqa test run --domain auth --priority P0
    pqa test add
    pqa test add --quick --id AUTH-004 --title "..." --domain auth --priority P1
    pqa test edit AUTH-003
    pqa test delete AUTH-003
    pqa test export
"""

import typer

from cli.commands import add_cmd, delete_cmd, edit_cmd, export_cmd, list_cmd, register_cmd, run_cmd

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
test_app.command("add")(add_cmd.add_test)
test_app.command("edit")(edit_cmd.edit_test)
test_app.command("delete")(delete_cmd.delete_test)
test_app.command("export")(export_cmd.export_tests)
test_app.command("register")(register_cmd.register_tests)

app.add_typer(test_app, name="test")


if __name__ == "__main__":
    app()
