"""
pqa test export — export test definitions from Atlas to JSON files.

Writes each test to test-definitions/{domain}/{id}.json.
Shows a diff preview when a file already exists and content differs.
"""

import json
from pathlib import Path

import typer
from rich.console import Console

from core.db import disconnect, get_db
from core.git_export import DEFINITIONS_DIR, export_test

console = Console()


def _load_existing(path: Path) -> dict | None:
    """Load an existing JSON file for diff comparison."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def export_tests(
    domain: str | None = typer.Option(None, "--domain", "-d", help="Export only this domain"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite without confirmation"),
):
    """Export test definitions from Atlas to JSON files on disk."""
    try:
        db = get_db()
        query: dict = {}
        if domain:
            query["domain"] = domain

        tests = list(db["tests"].find(query, {"_id": 0}).sort("id", 1))

        if not tests:
            console.print("\n  [yellow]No tests found in Atlas.[/yellow]\n")
            raise typer.Exit(0)

        console.print(f"\n  Exporting [bold]{len(tests)}[/bold] test(s) to {DEFINITIONS_DIR}/\n")

        exported = 0
        skipped = 0
        unchanged = 0

        for test in tests:
            test_id = test.get("id", "?")
            test_domain = test.get("domain", "?")
            folder = DEFINITIONS_DIR / test_domain
            path = folder / f"{test_id}.json"

            # Clean MongoDB internal fields for comparison
            clean = {k: v for k, v in test.items() if not k.startswith("_")}
            new_content = json.dumps(clean, indent=2, ensure_ascii=False) + "\n"

            # Check if file exists and content is the same
            existing = _load_existing(path)
            if existing is not None:
                existing_content = json.dumps(existing, indent=2, ensure_ascii=False) + "\n"
                if existing_content == new_content:
                    console.print(f"  [dim]—  {test_id:<14} unchanged[/dim]")
                    unchanged += 1
                    continue

                # Content differs — show what changed
                if not force:
                    console.print(f"  [yellow]~  {test_id:<14} differs from disk[/yellow]")

                    # Show key differences
                    for key in set(list(clean.keys()) + list(existing.keys())):
                        old_val = existing.get(key)
                        new_val = clean.get(key)
                        if old_val != new_val:
                            if old_val is not None:
                                console.print(f"     [red]- {key}: {old_val}[/red]")
                            if new_val is not None:
                                console.print(f"     [green]+ {key}: {new_val}[/green]")

                    if not typer.confirm(f"     Overwrite {path}?", default=True):
                        console.print("     [dim]skipped[/dim]")
                        skipped += 1
                        continue

            # Write the file
            export_test(test)
            console.print(f"  [green]✓  {test_id:<14} → {path}[/green]")
            exported += 1

        console.print(f"\n  {'─' * 50}")
        console.print(f"  Exported  : {exported}")
        if unchanged:
            console.print(f"  Unchanged : {unchanged}")
        if skipped:
            console.print(f"  Skipped   : {skipped}")
        console.print(f"  {'─' * 50}")

        if exported > 0:
            console.print(
                '\n  [dim]↳  git add test-definitions/ && git commit -m "chore(tests): Export from Atlas"[/dim]'
            )
        console.print()

    finally:
        disconnect()
