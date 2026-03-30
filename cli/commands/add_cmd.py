"""
pqa test add — create a new test definition.

Two modes:
  - Interactive (default): guided prompts for each field
  - Quick (--quick): all fields via CLI flags in one line

Both modes validate with Pydantic, write to Atlas, and export JSON to disk.
"""

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.db import disconnect, get_db
from core.git_export import export_test
from core.schema import parse_test

console = Console()

# Domain prefixes for auto-generating the next available ID
DOMAIN_PREFIXES = {
    "auth": "AUTH",
    "gateway": "GW",
    "schema": "SCH",
    "api": "API",
    "realtime": "RT",
    "storage": "STG",
    "ui": "UI",
    "infra": "INFRA",
}

# Domain descriptions for the help table
DOMAIN_HELP = {
    "auth": "GoTrue — login, OAuth, JWT, sessions",
    "gateway": "Kong — routing, rate limiting, CORS",
    "schema": "schema-service — collections, fields, DDL",
    "api": "PostgREST or QA API — endpoints, filters, RLS",
    "realtime": "Supabase Realtime — WebSocket, subscriptions",
    "storage": "MinIO — file upload, presigned URLs",
    "ui": "React frontend — components, hooks, stores",
    "infra": "Docker, health checks, infrastructure, Atlas",
}

# Type descriptions
TYPE_HELP = {
    "http": "API call — check status code, body content (needs url + method + expected)",
    "bash": "Shell command — check exit code, stdout (needs script)",
    "manual": "Human verification — specification only, skipped by runner",
}

DOMAINS = list(DOMAIN_PREFIXES.keys())
PRIORITIES = ["P0", "P1", "P2", "P3"]
TYPES = ["http", "bash", "manual"]
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def _next_id(domain: str) -> str:
    """Query Atlas for the next available ID in a domain."""
    db = get_db()
    prefix = DOMAIN_PREFIXES.get(domain, domain.upper())
    existing = list(
        db["tests"].find({"domain": domain}, {"id": 1, "_id": 0}).sort("id", -1).limit(1)
    )
    if not existing:
        return f"{prefix}-001"

    last_id = existing[0]["id"]
    try:
        num = int(last_id.split("-")[-1])
        return f"{prefix}-{num + 1:03d}"
    except (ValueError, IndexError):
        return f"{prefix}-001"


def _show_domain_help() -> None:
    """Display the domain reference table."""
    table = Table(
        title="Test Domains",
        show_header=True,
        header_style="bold",
        padding=(0, 1),
        title_style="bold blue",
    )
    table.add_column("Domain", style="cyan", width=10)
    table.add_column("Prefix", width=8)
    table.add_column("What it tests", style="dim")

    for domain, desc in DOMAIN_HELP.items():
        prefix = DOMAIN_PREFIXES[domain]
        table.add_row(domain, f"{prefix}-", desc)

    console.print()
    console.print(table)
    console.print()


def _show_type_help() -> None:
    """Display the type reference."""
    table = Table(
        title="Test Types",
        show_header=True,
        header_style="bold",
        padding=(0, 1),
        title_style="bold blue",
    )
    table.add_column("Type", style="cyan", width=8)
    table.add_column("Description", style="dim")

    for t, desc in TYPE_HELP.items():
        table.add_row(t, desc)

    console.print()
    console.print(table)
    console.print()


def _prompt_choice(label: str, options: list[str], default: str | None = None) -> str:
    """Prompt user to pick from a list of options."""
    options_str = " / ".join(options)
    prompt = f"  {label} [{options_str}]"
    if default:
        prompt += f" ({default})"
    while True:
        value = typer.prompt(prompt, default=default or "")
        if value in options:
            return value
        console.print(f"  [red]Invalid choice.[/red] Options: {options_str}")


def _interactive_add() -> dict:
    """Walk the user through creating a test interactively."""
    console.print("\n  [bold]Create a new test definition[/bold]")

    # Show domain reference and prompt
    _show_domain_help()
    domain = _prompt_choice("Domain", DOMAINS)

    # Auto-suggest next ID
    suggested_id = _next_id(domain)
    test_id = typer.prompt("  ID", default=suggested_id)

    # Title
    title = typer.prompt("  Title (what should happen, min 5 chars)")

    # Show type reference and prompt
    _show_type_help()
    test_type = _prompt_choice("Type", TYPES, default="http")

    # Priority
    console.print()
    console.print(
        "  [dim]P0 = blocks merge | P1 = critical | P2 = warning | P3 = report only[/dim]"
    )
    priority = _prompt_choice("Priority", PRIORITIES, default="P1")

    # Build the test dict
    data: dict = {
        "id": test_id,
        "title": title,
        "domain": domain,
        "type": test_type,
        "priority": priority,
        "status": "draft",
    }

    # Type-specific fields
    if test_type == "http":
        console.print()
        console.print("  [dim]── HTTP test configuration ──[/dim]")
        data["url"] = typer.prompt("  URL")
        data["method"] = _prompt_choice("Method", METHODS, default="GET")

        status_code = typer.prompt("  Expected status code", default="200")
        data["expected"] = {"statusCode": int(status_code)}

        body_contains = typer.prompt(
            "  Expected body contains (comma-separated, empty to skip)", default=""
        )
        if body_contains.strip():
            data["expected"]["bodyContains"] = [s.strip() for s in body_contains.split(",")]

        add_headers = typer.confirm("  Add headers?", default=False)
        if add_headers:
            headers_raw = typer.prompt(
                '  Headers (JSON, e.g. {"Content-Type": "application/json"})'
            )
            try:
                data["headers"] = json.loads(headers_raw)
            except json.JSONDecodeError:
                console.print("  [yellow]Invalid JSON — skipping headers[/yellow]")

        add_payload = typer.confirm("  Add payload?", default=False)
        if add_payload:
            payload_raw = typer.prompt("  Payload (JSON)")
            try:
                data["payload"] = json.loads(payload_raw)
            except json.JSONDecodeError:
                console.print("  [yellow]Invalid JSON — skipping payload[/yellow]")

    elif test_type == "bash":
        console.print()
        console.print("  [dim]── Bash test configuration ──[/dim]")
        console.print("  [dim]Example: pg_isready -h localhost -p 5432[/dim]")
        data["script"] = typer.prompt("  Script (shell command)")
        exit_code = typer.prompt("  Expected exit code", default="0")
        data["expected_exit_code"] = int(exit_code)
        expected_output = typer.prompt("  Expected output in stdout (empty to skip)", default="")
        if expected_output.strip():
            data["expected_output"] = expected_output

    elif test_type == "manual":
        console.print()
        console.print("  [dim]── Manual test (skipped by runner, serves as specification) ──[/dim]")
        notes = typer.prompt("  Notes (what to verify manually)", default="")
        if notes.strip():
            data["notes"] = notes

    # Optional metadata
    console.print()
    console.print("  [dim]── Optional metadata (press Enter to skip) ──[/dim]")
    author = typer.prompt("  Author (your 42 login)", default="")
    if author.strip():
        data["author"] = author

    tags_raw = typer.prompt("  Tags (comma-separated)", default="")
    if tags_raw.strip():
        data["tags"] = [t.strip() for t in tags_raw.split(",")]

    return data


def _save_test(data: dict) -> None:
    """Validate, save to Atlas, and export JSON."""
    # Validate with Pydantic
    try:
        test = parse_test(data)
    except Exception as e:
        console.print(f"\n  [red]Validation error:[/red] {e}\n")
        raise typer.Exit(1) from None

    db = get_db()

    # Check uniqueness
    if db["tests"].find_one({"id": test.id}):
        console.print(f"\n  [red]Test {test.id} already exists in Atlas.[/red]\n")
        raise typer.Exit(1)

    # Write to Atlas
    doc = test.model_dump(exclude_none=False)
    db["tests"].insert_one(doc)

    # Export to JSON on disk
    path = export_test(doc)

    # Show summary
    console.print()
    console.print(
        Panel(
            f"[bold]{test.id}[/bold] · {test.priority} · {test.domain} · {data.get('type', 'manual')}\n"
            f"{test.title}",
            title="[green]Test created[/green]",
            border_style="green",
        )
    )
    console.print("  [green]✓[/green]  Saved to Atlas")
    console.print(f"  [green]✓[/green]  Exported to {path}")

    from cli.commands.git_helper import offer_commit

    offer_commit(str(path), str(test.domain), test.id, "Add", test.title)


def add_test(
    quick: bool = typer.Option(False, "--quick", "-q", help="Non-interactive mode (use flags)"),
    test_id: str | None = typer.Option(None, "--id", help="Test ID (e.g. AUTH-004)"),
    title: str | None = typer.Option(None, "--title", "-t", help="Test title (min 5 chars)"),
    domain: str | None = typer.Option(
        None, "--domain", "-d", help="Domain (auth/gateway/infra/...)"
    ),
    priority: str | None = typer.Option(None, "--priority", "-p", help="Priority (P0/P1/P2/P3)"),
    test_type: str | None = typer.Option(None, "--type", help="Test type (http/bash/manual)"),
    url: str | None = typer.Option(None, "--url", help="[http] URL to call"),
    method: str | None = typer.Option(None, "--method", "-m", help="[http] HTTP method"),
    expected_status: int | None = typer.Option(
        None, "--expected-status", help="[http] Expected status code"
    ),
    expected_body: str | None = typer.Option(
        None, "--expected-body", help="[http] Body contains (comma-separated)"
    ),
    script: str | None = typer.Option(None, "--script", help="[bash] Shell command to run"),
    author: str | None = typer.Option(None, "--author", help="Your 42 login"),
):
    """Create a new test definition.

    Interactive mode (default): guided prompts with domain/type reference tables.
    Quick mode (--quick): all fields via flags in one command.

    Examples:

        pqa test add                          # interactive

        pqa test add --quick \\
          --id AUTH-004 \\
          --title "Token refresh works" \\
          --domain auth --priority P1 \\
          --type http \\
          --url http://localhost:9999/token \\
          --method POST \\
          --expected-status 200 \\
          --expected-body access_token
    """
    try:
        if quick:
            # Validate required flags
            if not all([test_id, title, domain, priority]):
                console.print(
                    "\n  [red]Quick mode requires: --id, --title, --domain, --priority[/red]\n"
                )
                console.print("  [bold]Example:[/bold]")
                console.print(
                    "  [dim]pqa test add --quick --id AUTH-004 "
                    '--title "Token refresh works" --domain auth --priority P1 '
                    "--type http --url http://localhost:9999/token --method POST "
                    "--expected-status 200[/dim]\n"
                )
                raise typer.Exit(1)

            data: dict = {
                "id": test_id,
                "title": title,
                "domain": domain,
                "priority": priority,
                "type": test_type or "manual",
                "status": "draft",
            }

            if test_type == "http" and url:
                data["url"] = url
                data["method"] = method or "GET"
                data["expected"] = {"statusCode": expected_status or 200}
                if expected_body:
                    data["expected"]["bodyContains"] = [s.strip() for s in expected_body.split(",")]

            elif test_type == "bash" and script:
                data["script"] = script

            if author:
                data["author"] = author

            _save_test(data)
        else:
            data = _interactive_add()

            # Show preview and confirm
            console.print()
            console.print(
                Panel(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    title=f"[bold]{data['id']}[/bold] — preview",
                    border_style="blue",
                )
            )

            if not typer.confirm("\n  Save this test?", default=True):
                console.print("  [yellow]Cancelled.[/yellow]\n")
                raise typer.Exit(0)

            _save_test(data)
    finally:
        disconnect()
