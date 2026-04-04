"""
pqa test list — display test definitions in a formatted table.

Talks directly to Atlas (not through the API) so it works
even when the API server is not running.
"""

import os

import typer
from rich.console import Console
from rich.table import Table

from core.db import disconnect, get_db

console = Console()


def list_tests(
    domain: str | None = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    priority: str | None = typer.Option(None, "--priority", "-p", help="Filter by priority"),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Filter by repository"),
    layer: str | None = typer.Option(
        None, "--layer", "-l", help="Filter by layer (backend/frontend/infra)"
    ),
    author: str | None = typer.Option(None, "--author", help="Filter by author"),
    group: str | None = typer.Option(None, "--group", "-g", help="Filter by group"),
    mine: bool = typer.Option(False, "--mine", help="Show only my tests (uses PQA_USER)"),
    runner: str | None = typer.Option(
        None, "--runner", help="Filter by runner (http/bash/jest/pytest)"
    ),
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
        if repo:
            query["repo"] = repo
        if layer:
            query["layer"] = layer
        if group:
            query["group"] = group
        if runner:
            query["runner"] = runner

        # --mine uses PQA_USER env var
        if mine:
            pqa_user = os.getenv("PQA_USER", "")
            if not pqa_user:
                console.print(
                    "\n  [yellow]PQA_USER not set.[/yellow] "
                    "Set it to filter by your tests: export PQA_USER=your_42_login\n"
                )
                return
            query["author"] = pqa_user
        elif author:
            query["author"] = author

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
            f"[dim]{skipped} skipped[/dim]"
        )

        # Show active filters
        filters = []
        if repo:
            filters.append(f"repo={repo}")
        if layer:
            filters.append(f"layer={layer}")
        if mine:
            filters.append(f"author={os.getenv('PQA_USER', '?')}")
        elif author:
            filters.append(f"author={author}")
        if group:
            filters.append(f"group={group}")
        if filters:
            console.print(f"  [dim]Filters: {', '.join(filters)}[/dim]")

        console.print()

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("ID", style="cyan", width=16)
        table.add_column("Domain", width=10)
        table.add_column("Prio", width=4)
        table.add_column("Status", width=10)
        table.add_column("Runner", width=6)
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
            runner_val = t.get("runner") or t.get("type", "—")
            table.add_row(
                t.get("id", "?"),
                t.get("domain", "?"),
                t.get("priority", "?"),
                f"[{color}]{s}[/{color}]",
                runner_val,
                t.get("title", "?"),
            )

        console.print(table)
        console.print()

    finally:
        disconnect()
