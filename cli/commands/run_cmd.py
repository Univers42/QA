"""
pqa test run — execute active tests and display results.

Executes tests locally using the registry executor to dispatch by runner type
(Bash, HTTP, Jest, Pytest). Connects directly to Atlas (not through the API),
enabling offline execution even if the dashboard API is unavailable.

Flow:
    1. Parse filters (domain, priority, layer, repo, test_id)
    2. Query Atlas for matching active tests
    3. Execute each test with appropriate runner
    4. Persist results to 'results' collection
    5. Display rich table with status, timing, and errors

Dependencies:
    - core.db: MongoDB connection
    - core.query_builder.QueryBuilder: Safe query construction
    - runner.registry_executor: Test execution dispatcher
    - runner.results: Result persistence
"""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from core.db import disconnect, get_db
from core.query_builder import QueryBuilder
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
    """
    Fetch active tests from Atlas and execute them.

    Args:
        domain: Filter by test domain
        priority: Filter by priority level
        test_id: Run a specific test by ID
        repo: Filter by repository
        layer: Filter by test layer
        repo_root: Base directory for script execution

    Returns:
        List of result dicts with {test_id, passed, error, duration_ms, ...}
    """
    db = get_db()

    # Build query for active tests only
    query = (
        QueryBuilder()
        .with_status("active")
        .with_domain(domain)
        .with_priority(priority)
        .with_test_id(test_id)
        .with_repo(repo)
        .with_layer(layer)
        .build()
    )

    tests = list(db["tests"].find(query, {"_id": 0}))

    if not tests:
        console.print("\n  [yellow]No active tests found matching filters.[/yellow]\n")
        return []

    console.print(f"\n  Running [bold]{len(tests)}[/bold] test(s)...\n")

    results = []
    for t in tests:
        # Determine runner from registry entry or legacy 'type' field
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
