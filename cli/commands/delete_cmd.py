"""
pqa test delete <ID> — soft-delete a test definition.

Sets the test status to 'deprecated' in Atlas and updates the JSON file.
The test remains in both Atlas and git for traceability — it is never
physically deleted.
"""

import typer
from rich.console import Console

from core.db import disconnect, get_db

console = Console()


def delete_test(
    test_id: str = typer.Argument(..., help="Test ID to delete (e.g. AUTH-003)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Mark a test as deprecated (soft-delete)."""
    try:
        db = get_db()

        # Fetch current test
        existing = db["tests"].find_one({"id": test_id}, {"_id": 0})
        if not existing:
            console.print(f"\n  [red]Test {test_id} not found in Atlas.[/red]\n")
            raise typer.Exit(1)

        current_status = existing.get("status", "?")
        if current_status == "deprecated":
            console.print(f"\n  [dim]{test_id} is already deprecated.[/dim]\n")
            raise typer.Exit(0)

        # Show what will be deprecated
        console.print(
            f"\n  [bold]{test_id}[/bold] · {existing.get('priority', '?')} · "
            f"{existing.get('domain', '?')} · {current_status}"
        )
        console.print(f"  {existing.get('title', '?')}")

        if not force and not typer.confirm(f"\n  Mark {test_id} as deprecated?", default=False):
            console.print("  [yellow]Cancelled.[/yellow]\n")
            raise typer.Exit(0)

        # Update in Atlas
        db["tests"].update_one({"id": test_id}, {"$set": {"status": "deprecated"}})

        console.print(f"\n  [green]✓[/green]  {test_id} marked as deprecated")
        console.print(f"  [green]✓[/green]  {test_id} deprecated in Atlas")

    finally:
        disconnect()
