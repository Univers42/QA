"""
pqa test list — display test definitions in a formatted table.

Talks directly to Atlas (not through the API) so it works
even when the API server is not running.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from core.db import get_db, disconnect


console = Console()


def list_tests(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """List all test definitions with optional filters."""
    try:
        db = get_db()
        query: dict = {}
        if domain:
            query["domain"] = domain
        if priority:
            query["priority"] = priority
        if status:
            query["status"] = status

        tests = list(db["tests"].find(query, {"_id": 0}).sort("id", 1))

        if not tests:
            console.print("\n  [yellow]No tests found matching filters.[/yellow]\n")
            return

        # Count by status
        active = sum(1 for t in tests if t.get("status") == "active")
        draft = sum(1 for t in tests if t.get("status") == "draft")
        skipped = sum(1 for t in tests if t.get("status") == "skipped")

        console.print(
            f"\n  Tests · [bold]{len(tests)}[/bold] total · "
            f"[green]{active} active[/green] · "
            f"[yellow]{draft} draft[/yellow] · "
            f"[dim]{skipped} skipped[/dim]\n"
        )

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("ID", style="cyan", width=14)
        table.add_column("Domain", width=10)
        table.add_column("Prio", width=4)
        table.add_column("Status", width=10)
        table.add_column("Title")

        status_colors = {
            "active": "green",
            "draft": "yellow",
            "skipped": "dim",
            "deprecated": "red",
        }

        for t in tests:
            s = t.get("status", "?")
            color = status_colors.get(s, "white")
            table.add_row(
                t.get("id", "?"),
                t.get("domain", "?"),
                t.get("priority", "?"),
                f"[{color}]{s}[/{color}]",
                t.get("title", "?"),
            )

        console.print(table)
        console.print()

    finally:
        disconnect()
