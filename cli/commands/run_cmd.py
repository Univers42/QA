"""
pqa test run — execute active tests and display results.

Uses the registry executor to dispatch by runner type (bash/http/jest/pytest).
Talks directly to Atlas (not through the API).
"""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from core.db import disconnect, get_db
from runner.registry_executor import execute_registered_test
from runner.results import persist_result

console = Console()


async def _run(
    domain: str | None,
    priority: str | None,
    test_id: str | None,
    repo: str | None,
    layer: str | None,
    repo_root: str = ".",
) -> list[dict]:
    """Fetch active tests from Atlas and execute them."""
    db = get_db()
    query: dict = {"status": "active"}
    if domain:
        query["domain"] = domain
    if priority:
        query["priority"] = priority
    if test_id:
        query["id"] = test_id
    if repo:
        query["repo"] = repo
    if layer:
        query["layer"] = layer

    tests = list(db["tests"].find(query, {"_id": 0}))

    if not tests:
        console.print("\n  [yellow]No active tests found matching filters.[/yellow]\n")
        return []

    console.print(f"\n  Running [bold]{len(tests)}[/bold] test(s)...\n")

    results = []
    for t in tests:
        # Determine runner from the registry entry or fall back to legacy 'type'
        runner = t.get("runner") or t.get("type", "http")
        entry = {**t, "runner": runner}

        result = await execute_registered_test(entry, repo_root=repo_root)
        persist_result(result, run_by="cli", repo=t.get("repo"))
        results.append(result)

    return results


def run_tests(
    domain: str | None = typer.Option(None, "--domain", "-d", help="Filter by domain"),
    priority: str | None = typer.Option(None, "--priority", "-p", help="Filter by priority"),
    test_id: str | None = typer.Option(None, "--id", help="Run a single test by ID"),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Filter by repository"),
    layer: str | None = typer.Option(None, "--layer", "-l", help="Filter by layer"),
    repo_root: str = typer.Option(
        ".", "--repo-root", help="Path to the repo root (for script-based tests)"
    ),
):
    """Execute all matching active tests and display results."""
    try:
        results = asyncio.run(_run(domain, priority, test_id, repo, layer, repo_root))

        if not results:
            raise typer.Exit(0)

        # Build results table
        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("ID", style="cyan", width=16)
        table.add_column("Status", width=8)
        table.add_column("ms", justify="right", width=6)
        table.add_column("Checks", width=8)
        table.add_column("Error")

        for r in results:
            if r["passed"] is True:
                icon = "[green]✓[/green]"
            elif r["passed"] is False:
                icon = "[red]✗[/red]"
            else:
                icon = "[dim]—[/dim]"

            # Show sub-test counts if available
            tp = r.get("tests_passed", 0)
            tf = r.get("tests_failed", 0)
            checks = f"{tp}/{tp + tf}" if (tp + tf) > 0 else ""

            table.add_row(
                r["test_id"],
                icon,
                str(r["duration_ms"]),
                checks,
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
