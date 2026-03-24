"""
pqa test run — execute active tests and display results.

Talks directly to Atlas and the runner (not through the API)
so it works even when the API server is not running.
"""

import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from core.db import get_db, disconnect
from runner.executor import execute_http_test
from runner.bash_executor import execute_bash_test
from runner.results import persist_result


console = Console()


async def _run(domain: str | None, priority: str | None, test_id: str | None) -> list[dict]:
    """Fetch active tests from Atlas and execute them."""
    db = get_db()
    query: dict = {"status": "active"}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if test_id:
        query["id"] = test_id

    tests = list(db["tests"].find(query, {"_id": 0}))

    if not tests:
        console.print("\n  [yellow]No active tests found matching filters.[/yellow]\n")
        return []

    console.print(f"\n  Running [bold]{len(tests)}[/bold] test(s)...\n")

    results = []
    for t in tests:
        test_type = t.get("type", "http")

        if test_type == "bash":
            result = await execute_bash_test(t)
        elif test_type == "manual":
            result = {"test_id": t["id"], "passed": None, "duration_ms": 0, "error": "manual — skipped"}
        else:
            result = await execute_http_test(t)

        persist_result(result, run_by="cli")
        results.append(result)

    return results


def run_tests(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority"),
    test_id: Optional[str] = typer.Option(None, "--id", help="Run a single test by ID"),
):
    """Execute all matching active tests and display results."""
    try:
        results = asyncio.run(_run(domain, priority, test_id))

        if not results:
            raise typer.Exit(0)

        # Build results table
        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("ID", style="cyan", width=14)
        table.add_column("Status", width=8)
        table.add_column("ms", justify="right", width=6)
        table.add_column("Error")

        for r in results:
            if r["passed"] is True:
                icon = "[green]✓[/green]"
            elif r["passed"] is False:
                icon = "[red]✗[/red]"
            else:
                icon = "[dim]—[/dim]"

            table.add_row(
                r["test_id"],
                icon,
                str(r["duration_ms"]),
                r.get("error") or "",
            )

        console.print(table)

        passed = sum(1 for r in results if r["passed"] is True)
        failed = sum(1 for r in results if r["passed"] is False)
        total_ms = sum(r["duration_ms"] for r in results)

        summary_color = "green" if failed == 0 else "red"
        console.print(
            f"\n  [{summary_color}]{passed} passed[/{summary_color}] · "
            f"{'[red]' + str(failed) + ' failed[/red]' if failed else '0 failed'} · "
            f"{total_ms}ms total\n"
        )

        if failed > 0:
            raise typer.Exit(1)

    finally:
        disconnect()
