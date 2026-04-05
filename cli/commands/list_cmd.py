"""
pqa test list — display test definitions in a formatted table.

Lists all tests matching optional filters, displaying ID, title, domain, priority,
status, layer, and runner type. Connects directly to Atlas (not through API),
enabling offline operation.

Features:
    - Multiple filter options (domain, priority, status, repo, layer, etc.)
    - --mine flag: Show only tests authored by current user (PQA_USER env var)
    - Color-coded status indicators (green=active, yellow=draft, dim=skipped)
    - Sorted alphabetically by test ID
    - Summary line showing counts by status

Dependencies:
    - core.db: MongoDB connection
    - core.query_builder.QueryBuilder: Safe query construction
    - core.config.Settings: PQA_USER for --mine flag
"""

import os

import typer
from rich.console import Console
from rich.table import Table

from core.db import disconnect, get_db
from core.query_builder import QueryBuilder

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
    """
    List all test definitions with optional filters.

    Filters can be combined. Results are sorted by test ID.

    Examples:
        pqa test list                          # All tests
        pqa test list --domain auth            # Only auth tests
        pqa test list --status active          # Only active tests
        pqa test list --mine                   # Tests I authored (requires PQA_USER)
        pqa test list --domain auth --status active  # Combined filters
    """
    try:
        db = get_db()

        # Build query using centralized QueryBuilder
        builder = QueryBuilder()
        builder.with_domain(domain)
        builder.with_priority(priority)
        builder.with_status(status)
        builder.with_repo(repo)
        builder.with_layer(layer)
        builder.with_group(group)
        builder.with_runner(runner)

        # Handle --mine flag: filter by current user
        if mine:
            pqa_user = os.getenv("PQA_USER", "")
            if not pqa_user:
                console.print(
                    "\n  [yellow]PQA_USER not set.[/yellow] "
                    "Set it to filter by your tests: export PQA_USER=your_42_login\n"
                )
                return
            builder.with_author(pqa_user)
        elif author:
            builder.with_author(author)

        query = builder.build()
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
        if domain:
            filters.append(f"domain={domain}")
        if priority:
            filters.append(f"priority={priority}")
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
        if runner:
            filters.append(f"runner={runner}")
        if filters:
            console.print(f"  [dim]Filters: {', '.join(filters)}[/dim]")

        console.print()

        # Build and show table
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
