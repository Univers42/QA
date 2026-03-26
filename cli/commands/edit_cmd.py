"""
pqa test edit <ID> — modify an existing test definition.

Loads the current test from Atlas, lets the user change fields interactively,
shows a diff preview, and saves on confirmation.
"""

import typer
from rich.console import Console
from rich.panel import Panel

from core.db import disconnect, get_db
from core.git_export import export_test
from core.schema import parse_test

console = Console()

EDITABLE_FIELDS = [
    "title",
    "priority",
    "status",
    "type",
    "url",
    "method",
    "notes",
    "author",
]


def _prompt_edit(field: str, current: str | None) -> str | None:
    """Prompt user to edit a field. Enter keeps current value, '-' clears it."""
    display = current if current is not None else "(empty)"
    value = typer.prompt(f"  {field}", default=display)

    if value == display:
        return current
    if value.strip() == "-":
        return None
    return value.strip()


def edit_test(
    test_id: str = typer.Argument(..., help="Test ID to edit (e.g. AUTH-003)"),
):
    """Modify an existing test definition."""
    try:
        db = get_db()

        # Fetch current test
        existing = db["tests"].find_one({"id": test_id}, {"_id": 0})
        if not existing:
            console.print(f"\n  [red]Test {test_id} not found in Atlas.[/red]\n")
            raise typer.Exit(1)

        console.print(f"\n  [bold]Editing {test_id}[/bold]")
        console.print(
            "  [dim]Press Enter to keep current value. Type '-' to clear a field.[/dim]\n"
        )

        # Create a mutable copy
        updated = {**existing}

        # Edit each field
        for field in EDITABLE_FIELDS:
            current = existing.get(field)
            if current is not None or field in ("title", "priority", "status"):
                new_value = _prompt_edit(field, str(current) if current is not None else None)
                if new_value is not None:
                    updated[field] = new_value
                elif field in updated:
                    del updated[field]

        # Edit expected status code for HTTP tests
        if updated.get("type") == "http":
            current_expected = existing.get("expected", {})
            current_status = current_expected.get("statusCode")
            new_status = typer.prompt("  expected.statusCode", default=str(current_status or 200))
            if "expected" not in updated:
                updated["expected"] = {}
            updated["expected"]["statusCode"] = int(new_status)

            current_body = current_expected.get("bodyContains")
            body_str = ", ".join(current_body) if current_body else ""
            new_body = typer.prompt("  expected.bodyContains (comma-separated)", default=body_str)
            if new_body.strip():
                updated["expected"]["bodyContains"] = [s.strip() for s in new_body.split(",")]
            elif "bodyContains" in updated.get("expected", {}):
                del updated["expected"]["bodyContains"]

        # Edit tags
        current_tags = existing.get("tags", [])
        tags_str = ", ".join(current_tags) if current_tags else ""
        new_tags = typer.prompt("  tags (comma-separated)", default=tags_str)
        if new_tags.strip():
            updated["tags"] = [t.strip() for t in new_tags.split(",")]
        elif "tags" in updated:
            del updated["tags"]

        # Show diff
        console.print()
        changes = []
        all_keys = set(list(existing.keys()) + list(updated.keys()))
        for key in sorted(all_keys):
            old_val = existing.get(key)
            new_val = updated.get(key)
            if old_val != new_val:
                changes.append((key, old_val, new_val))

        if not changes:
            console.print("  [dim]No changes detected.[/dim]\n")
            raise typer.Exit(0)

        diff_lines = []
        for key, old_val, new_val in changes:
            if old_val is not None:
                diff_lines.append(f"[red]- {key}: {old_val}[/red]")
            if new_val is not None:
                diff_lines.append(f"[green]+ {key}: {new_val}[/green]")

        console.print(Panel("\n".join(diff_lines), title="Changes", border_style="yellow"))

        if not typer.confirm("\n  Apply changes?", default=True):
            console.print("  [yellow]Cancelled.[/yellow]\n")
            raise typer.Exit(0)

        # Validate with Pydantic
        try:
            test = parse_test(updated)
        except Exception as e:
            console.print(f"\n  [red]Validation error:[/red] {e}\n")
            raise typer.Exit(1) from None

        # Save to Atlas
        doc = test.model_dump(exclude_none=False)
        db["tests"].update_one({"id": test_id}, {"$set": doc})

        # Export to JSON
        path = export_test(doc)

        console.print(f"\n  [green]✓[/green]  {test_id} updated in Atlas")
        console.print(f"  [green]✓[/green]  Exported to {path}")
        console.print(
            f"  [dim]↳  git add {path} && "
            f'git commit -m "test({test.domain}): Update {test_id}"[/dim]'
        )
        console.print()

    finally:
        disconnect()
