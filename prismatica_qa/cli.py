from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from .catalog import (
    BODY_METHODS,
    DEFAULT_LAYER,
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DEFAULT_TEST_KIND,
    DOMAINS,
    LAYERS,
    METHODS,
    PRIORITIES,
    STATUSES,
    TEST_KINDS,
    normalize_domain,
)
from .env import load_settings
from .files import DefinitionFile, definition_path, next_test_id, read_definition_files, validation_errors, write_definition
from .files import read_definition_files_from_roots
from .models import canonicalize_test
from .mongo import MongoStore, MongoUnavailableError
from .runner import RunOutcome, git_sha, run_tests

console = Console()


# Render a plain Rich panel with a consistent title and border style.
def plain_panel(title: str, message: str, *, border_style: str) -> None:
    console.print(
        Panel.fit(
            Text(message),
            title=title,
            title_align="left",
            border_style=border_style,
            box=box.ROUNDED,
        )
    )


# Render an informational panel.
def print_info(title: str, message: str) -> None:
    plain_panel(title, message, border_style="cyan")


# Render a success panel.
def print_success(title: str, message: str) -> None:
    plain_panel(title, message, border_style="green")


# Render a warning panel.
def print_warning(title: str, message: str) -> None:
    plain_panel(title, message, border_style="yellow")


# Render an error panel.
def print_error(title: str, message: str) -> None:
    plain_panel(title, message, border_style="red")


# Format a short colored badge for table output.
def badge(label: str, style: str) -> str:
    return f"[bold white on {style}] {label} [/] "


# Format the badge used for a test type.
def type_badge(test_type: str | None) -> str:
    palette = {
        "http": "blue",
        "bash": "magenta",
        "manual": "cyan",
        None: "bright_black",
    }
    return badge(test_type or "-", palette.get(test_type, "bright_black"))


# Format the badge used for a test layer.
def layer_badge(layer: str | None) -> str:
    if not layer:
        return "[dim]-[/dim]"
    return badge(layer, "bright_black")


# Format the badge used for a test status.
def status_badge(status: str | None) -> str:
    palette = {
        "active": "green",
        "draft": "yellow",
        "skipped": "blue",
        "deprecated": "red",
        None: "bright_black",
    }
    return badge(status or "-", palette.get(status, "bright_black"))


# Format the badge used for a test priority.
def priority_badge(priority: str | None) -> str:
    palette = {
        "P0": "red",
        "P1": "yellow",
        "P2": "blue",
        "P3": "bright_black",
        None: "bright_black",
    }
    return badge(priority or "-", palette.get(priority, "bright_black"))


# Format the badge used for run-to-run comparisons.
def compare_badge(label: str) -> str:
    palette = {
        "new": "blue",
        "fixed": "green",
        "regression": "red",
        "stable-pass": "green",
        "stable-fail": "yellow",
    }
    return badge(label, palette.get(label, "bright_black"))


# Format the badge used for pass or fail results.
def result_badge(passed: bool) -> str:
    return badge("PASS", "green") if passed else badge("FAIL", "red")


# Format a numeric count with a color style.
def format_count(value: int, style: str) -> str:
    return f"[bold {style}]{value}[/]"


# Render a table of validation or execution issues.
def print_issue_table(title: str, errors: list[str], *, border_style: str = "red") -> None:
    if not errors:
        return

    table = Table(
        title=title,
        box=box.SIMPLE_HEAVY,
        header_style=f"bold {border_style}",
        title_style=f"bold {border_style}",
        show_lines=False,
    )
    table.add_column("Location", style="cyan", overflow="fold")
    table.add_column("Issue", style=border_style, overflow="fold")

    for error in errors:
        location, separator, issue = error.partition(": ")
        if separator:
            table.add_row(location, issue)
        else:
            table.add_row("-", error)

    console.print(table)


# Show the summary card for a newly created definition.
def print_definition_card(path: Any, definition: dict[str, Any], root: Any) -> None:
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", overflow="fold")
    table.add_row("File", str(path.relative_to(root)))
    table.add_row("ID", f"[bold cyan]{definition['id']}[/]")
    table.add_row("Domain", f"[cyan]{definition['domain']}[/cyan]")
    table.add_row("Type", type_badge(definition.get("type")))
    table.add_row("Layer", layer_badge(definition.get("layer")))
    table.add_row("Priority", priority_badge(definition.get("priority")))
    table.add_row("Status", status_badge(definition.get("status")))

    console.print(
        Panel(
            table,
            title="New Test",
            title_align="left",
            border_style="green",
            box=box.ROUNDED,
        )
    )


# Render the execution plan summary before a run starts.
def print_run_plan(
    tests: list[dict[str, Any]],
    *,
    environment: str,
    domain: str | None,
    test_type: str | None,
    layer: str | None,
    priority: str | None,
    status: str | None,
    history_source: str,
) -> None:
    counts = Counter(test.get("type", "manual") for test in tests)

    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", overflow="fold")
    table.add_row("Selected tests", f"[bold]{len(tests)}[/]")
    table.add_row("Environment", f"[cyan]{environment}[/cyan]")
    table.add_row("Domain filter", f"[cyan]{domain or 'all'}[/cyan]")
    table.add_row("Type filter", type_badge(test_type) if test_type else "[dim]all[/dim]")
    table.add_row("Layer filter", layer_badge(layer) if layer else "[dim]all[/dim]")
    table.add_row("Priority filter", priority_badge(priority) if priority else "[dim]all[/dim]")
    table.add_row("Status filter", status_badge(status) if status and status != "all" else "[dim]all[/dim]")
    table.add_row("History source", f"[cyan]{history_source}[/cyan]")

    counts_markup = "  ".join(
        f"{type_badge(kind)}[bold]{count}[/]" for kind, count in sorted(counts.items())
    ) or "[dim]none[/dim]"
    table.add_row("By type", counts_markup)

    console.print(
        Panel(
            table,
            title="Execution Plan",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )


# Return the current user name for result attribution.
def default_author() -> str:
    return os.getenv("USER", "unknown")


# Split a comma-separated string into normalized items.
def comma_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


# Normalize free-text input to a stripped string or None.
def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# Render the visible option list for interactive prompts.
def format_options(choices: list[str] | tuple[str, ...]) -> str:
    return " | ".join(choices)


# Build a prompt label including options and optional markers.
def prompt_label(label: str, *, options: list[str] | tuple[str, ...] | None = None, optional: bool = False) -> str:
    suffix: list[str] = []
    if options:
        suffix.append(f"({format_options(options)})")
    if optional:
        suffix.append("(enter to skip)")
    return f"{label} {' '.join(suffix)}".strip()


# Match free-text input against one of the allowed choices.
def normalize_choice(value: str, choices: list[str] | tuple[str, ...]) -> str | None:
    normalized = value.strip().lower()
    for choice in choices:
        if normalized == choice.lower():
            return choice
    return None


# Parse an optional JSON object from CLI or prompt input.
def parse_json_object(raw_value: str | None, label: str) -> dict[str, Any] | None:
    value = normalize_optional_text(raw_value)
    if value is None:
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return parsed


# Read a required or optional text value from flags or interactive input.
def prompt_text(
    value: str | None,
    label: str,
    *,
    quick: bool,
    default: str | None = None,
    optional: bool = False,
) -> str | None:
    parsed = normalize_optional_text(value)
    if parsed is not None:
        return parsed
    if quick:
        if default is not None:
            return default
        if optional:
            return None
        raise ValueError(f"Missing required value: {label}")

    prompt_default = "" if optional and default is None else default
    while True:
        prompted = Prompt.ask(prompt_label(label, optional=optional), default=prompt_default)
        parsed = normalize_optional_text(prompted)
        if parsed is not None:
            return parsed
        if optional:
            return None
        print_warning("Invalid Input", f"{label} cannot be empty. Please try again.")


# Read a constrained choice from flags or interactive input.
def prompt_choice(
    value: str | None,
    label: str,
    *,
    quick: bool,
    choices: list[str] | tuple[str, ...],
    default: str | None = None,
    optional: bool = False,
) -> str | None:
    parsed = normalize_optional_text(value)
    if parsed is not None:
        choice = normalize_choice(parsed, choices)
        if choice is not None:
            return choice
        raise ValueError(f"Invalid {label}. Allowed values: {', '.join(choices)}")

    if quick:
        if default is not None:
            return default
        if optional:
            return None
        raise ValueError(f"Missing required value: {label}")

    prompt_default = "" if optional and default is None else default
    while True:
        prompted = Prompt.ask(prompt_label(label, options=choices, optional=optional), default=prompt_default)
        parsed = normalize_optional_text(prompted)
        if parsed is None and optional:
            return None
        if parsed is not None:
            choice = normalize_choice(parsed, choices)
            if choice is not None:
                return choice
        print_warning("Invalid Option", f"{label} must be one of: {', '.join(choices)}.")


# Read an integer value from flags or interactive input.
def prompt_int(
    value: int | None,
    label: str,
    *,
    quick: bool,
    default: int | None = None,
    minimum: int | None = None,
) -> int:
    if value is not None:
        result = int(value)
        if minimum is not None and result < minimum:
            raise ValueError(f"{label} must be greater than or equal to {minimum}")
        return result
    if quick:
        if default is not None:
            return default
        raise ValueError(f"Missing required value: {label}")
    while True:
        result = IntPrompt.ask(prompt_label(label), default=default)
        if minimum is not None and result < minimum:
            print_warning("Invalid Number", f"{label} must be greater than or equal to {minimum}.")
            continue
        return result


# Read a comma-separated list from flags or interactive input.
def prompt_csv_list(
    value: str | None,
    label: str,
    *,
    quick: bool,
) -> list[str]:
    if value is not None:
        return comma_list(value)
    if quick:
        return []
    return comma_list(Prompt.ask(prompt_label(label, optional=True), default=""))


# Read and validate a JSON object from flags or interactive input.
def prompt_json_object(
    value: str | None,
    label: str,
    *,
    quick: bool,
) -> dict[str, Any] | None:
    if value is not None:
        return parse_json_object(value, label)
    if quick:
        return None
    while True:
        raw_value = Prompt.ask(prompt_label(label, optional=True), default="")
        try:
            return parse_json_object(raw_value, label)
        except ValueError as exc:
            print_warning("Invalid JSON", str(exc))


# Expand a relative endpoint into a full URL when a base URL is configured.
def format_url(input_value: str, domain: str, settings: Any) -> str:
    value = input_value.strip()
    if value.startswith(("http://", "https://")):
        return value

    base_url = settings.base_url_for_domain(domain)
    if not base_url:
        return value

    return base_url.rstrip("/") + "/" + value.lstrip("/")


# Build the raw definition document from the collected CLI inputs.
def build_definition(
    *,
    test_id: str,
    domain: str,
    test_kind: str,
    title: str,
    url: str | None,
    method: str | None,
    expected_status_code: int | None,
    body_contains: list[str],
    layer: str | None,
    priority: str,
    status: str,
    payload: dict[str, Any] | None,
    script: str | None,
    expected_output: str | None,
    tags: list[str],
    preconditions: list[str],
    environment: list[str],
    notes: str | None,
    json_path: dict[str, Any] | None,
    expected_exit_code: int,
    timeout_seconds: int | None,
    phase: str | None,
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "id": test_id,
        "title": title,
        "domain": domain,
        "priority": priority,
        "status": status,
    }
    if tags:
        definition["tags"] = tags
    if phase:
        definition["phase"] = phase
    if layer:
        definition["layer"] = layer
    if environment:
        definition["environment"] = environment
    if preconditions:
        definition["preconditions"] = preconditions
    if notes:
        definition["notes"] = notes

    if test_kind == "http":
        expected: dict[str, Any] = {"statusCode": expected_status_code}
        if body_contains:
            expected["bodyContains"] = body_contains
        if json_path:
            expected["jsonPath"] = json_path
        definition.update(
            {
                "type": "http",
                "url": url,
                "method": method,
                "timeout_seconds": timeout_seconds or 5,
                "expected": expected,
            }
        )
        if payload is not None:
            definition["payload"] = payload
            definition["headers"] = {"Content-Type": "application/json"}
        return definition

    if test_kind == "bash":
        definition.update(
            {
                "type": "bash",
                "script": script,
                "expected_exit_code": expected_exit_code,
                "timeout_seconds": timeout_seconds or 30,
            }
        )
        if expected_output:
            definition["expected_output"] = expected_output
        return definition

    definition["type"] = "manual"
    return definition


# Open MongoDB and ensure the required indexes exist.
def open_mongo(settings: Any) -> MongoStore:
    store = MongoStore(settings.mongo_uri)
    store.ensure_indexes()
    return store


# Print the local persistence notice shown at the start of each command.
def print_local_mode_notice() -> None:
    print_warning(
        "Notice",
        "Current mode: local persistence.\n"
        "Repository JSON files are the source of truth.\n"
        "Local MongoDB is optional for sync, result history, and last-run comparison.\n"
        "Verify on your own that you have the latest repository version before adding, syncing, or running tests.",
    )


# Validate and synchronize a list of definition files into MongoDB.
def sync_documents(settings: Any, items: list[DefinitionFile]) -> tuple[dict[str, int], list[str]]:
    docs: list[dict[str, Any]] = []
    errors: list[str] = []

    for item in items:
        relative = item.path.relative_to(settings.root)
        if item.error:
            errors.append(f"{relative}: {item.error}")
            continue
        assert item.doc is not None
        doc_errors = validation_errors(item.doc)
        if doc_errors:
            errors.append(f"{relative}: {'; '.join(doc_errors)}")
            continue
        docs.append(canonicalize_test(item.doc))

    store = open_mongo(settings)
    try:
        summary = store.upsert_tests(docs)
    finally:
        store.close()

    summary["invalid"] = len(errors)
    return summary, errors


# Validate a list of definition files without touching MongoDB.
def validate_documents(settings: Any, items: list[DefinitionFile]) -> tuple[dict[str, int], list[str]]:
    summary = {"valid": 0, "invalid": 0, "total": len(items)}
    errors: list[str] = []

    for item in items:
        relative = item.path.relative_to(settings.root)
        if item.error:
            errors.append(f"{relative}: {item.error}")
            continue
        assert item.doc is not None
        doc_errors = validation_errors(item.doc)
        if doc_errors:
            errors.append(f"{relative}: {'; '.join(doc_errors)}")
            continue
        summary["valid"] += 1

    summary["invalid"] = len(errors)
    return summary, errors


# Render the summary table for a MongoDB synchronization step.
def print_sync_summary(summary: dict[str, int], errors: list[str]) -> None:
    table = Table(
        title="MongoDB Sync",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        title_style="bold cyan",
    )
    table.add_column("Inserted", justify="right")
    table.add_column("Updated", justify="right")
    table.add_column("Unchanged", justify="right")
    table.add_column("Invalid", justify="right")
    table.add_row(
        format_count(summary["inserted"], "green"),
        format_count(summary["updated"], "yellow"),
        format_count(summary["unchanged"], "cyan"),
        format_count(summary["invalid"], "red" if summary["invalid"] else "green"),
    )
    console.print(table)

    if errors:
        print_warning(
            "Sync Completed With Issues",
            f"{len(errors)} definition(s) could not be synchronized. Review the issues below.",
        )
        print_issue_table("Synchronization Issues", errors)
    else:
        print_success("Sync Completed", "All selected definitions were synchronized successfully.")


# Render the summary table for a definition validation step.
def print_validation_summary(summary: dict[str, int], errors: list[str]) -> None:
    table = Table(
        title="Definition Validation",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        title_style="bold cyan",
    )
    table.add_column("Valid", justify="right")
    table.add_column("Invalid", justify="right")
    table.add_column("Total", justify="right")
    table.add_row(
        format_count(summary["valid"], "green"),
        format_count(summary["invalid"], "red" if summary["invalid"] else "green"),
        format_count(summary["total"], "cyan"),
    )
    console.print(table)

    if errors:
        print_warning(
            "Validation Completed With Issues",
            f"{len(errors)} definition(s) are invalid. Review the issues below.",
        )
        print_issue_table("Validation Issues", errors)
    else:
        print_success("Validation Passed", "All selected JSON definitions are valid.")


# Check whether one canonical test matches the selected run filters.
def matches_filters(
    test: dict[str, Any],
    *,
    domain: str | None,
    test_type: str | None,
    layer: str | None,
    priority: str | None,
    status: str | None,
    environment: str,
) -> bool:
    if domain and test["domain"] != domain:
        return False
    if test_type and test.get("type", "manual") != test_type:
        return False
    if layer and test.get("layer") != layer:
        return False
    if priority and test["priority"] != priority:
        return False
    if status and status != "all" and test["status"] != status:
        return False

    allowed_environments = test.get("environment")
    if allowed_environments and environment not in allowed_environments:
        return False
    return True


# Load, validate, canonicalize, and filter JSON definitions for execution.
def load_tests_from_json(
    settings: Any,
    items: list[DefinitionFile],
    *,
    domain: str | None,
    test_type: str | None,
    layer: str | None,
    priority: str | None,
    status: str | None,
    environment: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    tests: list[dict[str, Any]] = []
    errors: list[str] = []

    for item in items:
        relative = item.path.relative_to(settings.root)
        if item.error:
            errors.append(f"{relative}: {item.error}")
            continue
        assert item.doc is not None
        doc_errors = validation_errors(item.doc)
        if doc_errors:
            errors.append(f"{relative}: {'; '.join(doc_errors)}")
            continue
        test = canonicalize_test(item.doc)
        if matches_filters(
            test,
            domain=domain,
            test_type=test_type,
            layer=layer,
            priority=priority,
            status=status,
            environment=environment,
        ):
            tests.append(test)

    tests.sort(key=lambda item: item["id"])
    return tests, errors


# Read and normalize the selected domain for the add command.
def prompt_domain(value: str | None, *, quick: bool) -> str:
    choices = list(DOMAINS)
    parsed = normalize_optional_text(value)
    if parsed is not None:
        return normalize_domain(parsed)
    if quick:
        return "auth"

    while True:
        prompted = Prompt.ask(prompt_label("Domain", options=choices), default="auth")
        try:
            return normalize_domain(prompted)
        except ValueError as exc:
            print_warning("Invalid Option", str(exc))


# Implement the add command in interactive or quick mode.
def prompt_add(args: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        if args.quick:
            missing_flags = [
                flag
                for flag, value in (
                    ("--domain", args.domain),
                    ("--title", args.title),
                    ("--type", args.test_type),
                )
                if normalize_optional_text(value) is None
            ]
            if missing_flags:
                raise ValueError(f"Quick mode requires: {', '.join(missing_flags)}")

        domain = prompt_domain(args.domain, quick=args.quick)
        title = prompt_text(args.title, "Behavior to verify", quick=args.quick)
        test_kind = prompt_choice(
            args.test_type,
            "Test type",
            quick=args.quick,
            choices=TEST_KINDS,
            default=DEFAULT_TEST_KIND,
        )
        assert title is not None
        assert test_kind is not None

        priority = args.priority or DEFAULT_PRIORITY
        status = args.status or DEFAULT_STATUS
        layer = args.layer
        phase = normalize_optional_text(args.phase)
        tags = comma_list(args.tags) if args.tags is not None else []
        preconditions = comma_list(args.preconditions) if args.preconditions is not None else []
        environment = comma_list(args.environment) if args.environment is not None else []
        notes = normalize_optional_text(args.notes)

        url: str | None = None
        method: str | None = None
        expected_status_code: int | None = None
        body_contains: list[str] = []
        payload: dict[str, Any] | None = None
        script: str | None = None
        expected_output: str | None = None
        json_path: dict[str, Any] | None = None
        expected_exit_code = 0
        timeout_seconds: int | None = None

        if test_kind == "http":
            base_url = settings.base_url_for_domain(domain)
            endpoint_label = "Endpoint path or full URL"
            if base_url:
                endpoint_label += f" (base {base_url})"

            url_input = prompt_text(args.url, endpoint_label, quick=args.quick)
            assert url_input is not None
            url = format_url(url_input, domain, settings)
            method = prompt_choice(args.method, "HTTP method", quick=args.quick, choices=METHODS, default="GET")
            expected_status_code = prompt_int(
                args.expected_status,
                "Expected HTTP status",
                quick=args.quick,
                default=200,
                minimum=100,
            )
            body_contains = prompt_csv_list(
                args.body_contains,
                "Expected body fragments (comma-separated, optional)",
                quick=args.quick,
            )
            json_path = prompt_json_object(args.json_path, "JSON path assertions", quick=args.quick)
            timeout_seconds = prompt_int(
                args.timeout_seconds,
                "Timeout in seconds",
                quick=args.quick,
                default=5,
                minimum=1,
            )
            if method in BODY_METHODS:
                payload = prompt_json_object(args.payload, "JSON payload", quick=args.quick)
            elif args.payload is not None:
                raise ValueError("Payload is only valid for POST, PUT, or PATCH HTTP tests.")

        if test_kind == "bash":
            script = prompt_text(args.script, "Script path or shell command", quick=args.quick)
            expected_exit_code = prompt_int(args.expected_exit_code, "Expected exit code", quick=args.quick, default=0)
            expected_output = prompt_text(
                args.expected_output,
                "Expected output substring",
                quick=args.quick,
                optional=True,
            )
            timeout_seconds = prompt_int(
                args.timeout_seconds,
                "Timeout in seconds",
                quick=args.quick,
                default=30,
                minimum=1,
            )

        if test_kind == "manual" and notes is None:
            notes = prompt_text(
                args.notes,
                "Manual verification instructions",
                quick=args.quick,
                optional=True,
            )

        advanced_requested = args.advanced or any(
            value is not None
            for value in (
                args.layer,
                args.priority,
                args.status,
                args.phase,
                args.environment,
                args.tags,
                args.preconditions,
                args.notes,
            )
        )
        if not args.quick and (advanced_requested or Confirm.ask("Configure advanced options?", default=False)):
            if args.layer is None:
                layer_choice = prompt_choice(
                    None,
                    "Layer",
                    quick=False,
                    choices=["none", *LAYERS],
                    default=DEFAULT_LAYER,
                )
                layer = None if layer_choice == "none" else layer_choice
            if args.priority is None:
                selected = prompt_choice(
                    None,
                    "Priority",
                    quick=False,
                    choices=PRIORITIES,
                    default=DEFAULT_PRIORITY,
                )
                assert selected is not None
                priority = selected
            if args.status is None:
                selected = prompt_choice(
                    None,
                    "Status",
                    quick=False,
                    choices=STATUSES,
                    default=DEFAULT_STATUS,
                )
                assert selected is not None
                status = selected
            if args.phase is None:
                phase = prompt_text(None, "Phase", quick=False, optional=True)
            if args.tags is None:
                tags = prompt_csv_list(None, "Tags (comma-separated, optional)", quick=False)
            if args.preconditions is None:
                preconditions = prompt_csv_list(None, "Preconditions (comma-separated, optional)", quick=False)
            if args.environment is None:
                environment = prompt_csv_list(None, "Allowed environments (comma-separated, optional)", quick=False)
            if test_kind != "manual" and args.notes is None:
                notes = prompt_text(None, "Notes", quick=False, optional=True)

        test_id = next_test_id(domain, settings.definition_dirs)
        definition = build_definition(
            test_id=test_id,
            domain=domain,
            test_kind=test_kind,
            title=title,
            url=url,
            method=method,
            expected_status_code=expected_status_code,
            body_contains=body_contains,
            phase=phase,
            layer=layer,
            priority=priority,
            status=status,
            payload=payload,
            script=script,
            expected_output=expected_output,
            tags=tags,
            preconditions=preconditions,
            environment=environment,
            notes=notes,
            json_path=json_path,
            expected_exit_code=expected_exit_code,
            timeout_seconds=timeout_seconds,
        )
        definition = canonicalize_test(definition)
    except ValueError as exc:
        print_error("Invalid Input", str(exc))
        return 1

    path = definition_path(settings.tests_dir, domain, test_id)
    write_definition(path, definition)

    print_definition_card(path, definition, settings.root)

    if args.no_sync:
        print_info("JSON Saved", "The definition was written to the repository. MongoDB sync was skipped by request.")
        return 0

    try:
        summary, errors = sync_documents(settings, [DefinitionFile(path=path, doc=definition)])
    except MongoUnavailableError as exc:
        print_warning("JSON Saved", f"The definition was written to the repository, but MongoDB sync failed.\n{exc}")
        return 0

    print_sync_summary(summary, errors)
    return 0


# Prompt interactively for run filters when the user asked for it.
def prompt_run_filters(args: argparse.Namespace) -> None:
    args.domain = Prompt.ask("Domain", choices=["all", *DOMAINS.keys()], default="all")
    args.test_type = Prompt.ask("Type", choices=["all", *TEST_KINDS], default="all")
    args.layer = Prompt.ask("Layer", choices=["all", *LAYERS], default="all")
    args.priority = Prompt.ask("Priority", choices=["all", *PRIORITIES], default="all")
    args.status = Prompt.ask("Status", choices=["all", *STATUSES], default=args.status)


# Render the detailed result table for one completed run.
def print_run_results(outcomes: list[RunOutcome]) -> None:
    table = Table(
        title="Prismatica QA Run",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        title_style="bold cyan",
        row_styles=["none", "dim"],
    )
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type")
    table.add_column("Layer")
    table.add_column("Result")
    table.add_column("Code", justify="right")
    table.add_column("ms", justify="right")
    table.add_column("Compare")
    table.add_column("Title", overflow="fold")

    execution_errors: list[str] = []

    for outcome in outcomes:
        code = "-"
        if outcome.http_status is not None:
            code = str(outcome.http_status)
        elif isinstance(outcome.response_snapshot, dict) and "exit_code" in outcome.response_snapshot:
            code = str(outcome.response_snapshot["exit_code"])
        table.add_row(
            outcome.test["id"],
            type_badge(outcome.test.get("type")),
            layer_badge(outcome.test.get("layer")),
            result_badge(outcome.passed),
            code,
            str(outcome.duration_ms),
            compare_badge(outcome.comparison),
            outcome.test["title"],
        )
        if outcome.error:
            execution_errors.append(f"{outcome.test['id']}: {outcome.error}")

    console.print(table)
    print_issue_table("Execution Issues", execution_errors, border_style="yellow")

    passed = sum(1 for outcome in outcomes if outcome.passed)
    failed = len(outcomes) - passed
    regressions = sum(1 for outcome in outcomes if outcome.comparison == "regression")
    fixed = sum(1 for outcome in outcomes if outcome.comparison == "fixed")

    summary = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    summary.add_column("Metric", style="bold cyan")
    summary.add_column("Value", justify="right")
    summary.add_row("Passed", format_count(passed, "green"))
    summary.add_row("Failed", format_count(failed, "red" if failed else "green"))
    summary.add_row("Regressions", format_count(regressions, "red" if regressions else "green"))
    summary.add_row("Fixed", format_count(fixed, "green"))

    console.print(
        Panel(
            summary,
            title="Run Summary",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )


# Implement the sync command.
def command_sync(args: argparse.Namespace) -> int:
    settings = load_settings()
    domain = None if args.domain == "all" else args.domain
    items = read_definition_files_from_roots(settings.definition_dirs, domain)

    try:
        summary, errors = sync_documents(settings, items)
    except MongoUnavailableError as exc:
        print_error("MongoDB Unavailable", str(exc))
        return 1

    print_sync_summary(summary, errors)
    return 1 if errors else 0


# Implement the validate command.
def command_validate(args: argparse.Namespace) -> int:
    settings = load_settings()
    domain = None if args.domain == "all" else args.domain
    items = read_definition_files_from_roots(settings.definition_dirs, domain)
    summary, errors = validate_documents(settings, items)
    print_validation_summary(summary, errors)
    return 1 if errors else 0


# Implement the run command including optional MongoDB history and persistence.
def command_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    if (
        sys.stdin.isatty()
        and args.status == "active"
        and not any([args.domain, args.test_type, args.layer, args.priority, args.interactive])
    ):
        prompt_run_filters(args)

    domain = None if args.domain in (None, "all") else normalize_domain(args.domain)
    test_type = None if args.test_type in (None, "all") else args.test_type
    layer = None if args.layer in (None, "all") else args.layer
    priority = None if args.priority in (None, "all") else args.priority
    status = args.status or "active"

    if not args.no_sync:
        try:
            summary, errors = sync_documents(settings, read_definition_files_from_roots(settings.definition_dirs, domain))
            if errors:
                print_warning(
                    "Sync Completed With Issues",
                    f"MongoDB sync skipped {summary['invalid']} invalid definition(s). "
                    "Only valid definitions were synchronized."
                )
        except MongoUnavailableError as exc:
            print_warning(
                "MongoDB Sync Skipped",
                f"Running directly from repository JSON.\n{exc}"
            )

    items = read_definition_files_from_roots(settings.definition_dirs, domain)
    tests, definition_errors = load_tests_from_json(
        settings,
        items,
        domain=domain,
        test_type=test_type,
        layer=layer,
        priority=priority,
        status=status,
        environment=args.env,
    )
    if definition_errors:
        print_warning(
            "Invalid Definitions Skipped",
            f"{len(definition_errors)} JSON file(s) are invalid and will be ignored in this run."
        )
        print_issue_table("Definition Issues", definition_errors, border_style="yellow")
    if not tests:
        print_info("No Tests Selected", "No valid test definitions matched the selected filters.")
        return 0

    store: MongoStore | None = None
    previous: dict[str, dict[str, Any]] = {}
    mongo_available = False

    try:
        store = open_mongo(settings)
        mongo_available = True
    except MongoUnavailableError as exc:
        print_warning("MongoDB Unavailable", f"Running from repository JSON only.\n{exc}")

    if mongo_available and store is not None:
        try:
            previous = store.latest_results_map([test["id"] for test in tests], args.env)
        except Exception as exc:
            print_warning("History Unavailable", f"Comparison will start as new.\n{exc}")
            previous = {}

    print_run_plan(
        tests,
        environment=args.env,
        domain=domain,
        test_type=test_type,
        layer=layer,
        priority=priority,
        status=status,
        history_source="MongoDB" if mongo_available else "JSON only",
    )

    run_id, outcomes = run_tests(
        tests,
        settings=settings,
        previous_results=previous,
        workers=args.workers,
    )

    if mongo_available and store is not None:
        try:
            try:
                store.store_results(
                    [outcome.__dict__ for outcome in outcomes],
                    run_id=run_id,
                    environment=args.env,
                    run_by=default_author(),
                    git_sha=git_sha(str(settings.root)),
                )
            except Exception as exc:
                print_warning("Result Storage Failed", f"This run will not be persisted.\n{exc}")
        finally:
            store.close()
    else:
        print_warning(
            "Results Not Persisted",
            "Historical comparison and result persistence are disabled in this run because MongoDB is unavailable."
        )

    print_run_results(outcomes)
    return 1 if any(not outcome.passed for outcome in outcomes) else 0


# Build the top-level argparse parser and all subcommands.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Python QA automation for Prismatica",
        epilog=(
            "Notice: local mode. Repository JSON files are the source of truth. "
            "Local MongoDB is optional for sync, result history, and comparison. "
            "Verify on your own that you have the latest repository version."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a test definition interactively or in quick mode")
    add_parser.add_argument("--advanced", action="store_true", help="Ask for advanced fields")
    add_parser.add_argument("--quick", action="store_true", help="Do not prompt; require the needed values as options")
    add_parser.add_argument("--no-sync", action="store_true", help="Only create the JSON file")
    add_parser.add_argument("--domain", choices=list(DOMAINS.keys()))
    add_parser.add_argument("--title")
    add_parser.add_argument("--type", dest="test_type", choices=TEST_KINDS)
    add_parser.add_argument("--priority", choices=PRIORITIES)
    add_parser.add_argument("--status", choices=STATUSES)
    add_parser.add_argument("--layer", choices=LAYERS)
    add_parser.add_argument("--phase")
    add_parser.add_argument("--environment", help="Comma-separated environment allow-list")
    add_parser.add_argument("--tags", help="Comma-separated tags")
    add_parser.add_argument("--preconditions", help="Comma-separated preconditions")
    add_parser.add_argument("--notes")
    add_parser.add_argument("--url")
    add_parser.add_argument("--method", choices=METHODS)
    add_parser.add_argument("--expected-status", dest="expected_status", type=int)
    add_parser.add_argument("--body-contains", help="Comma-separated expected body fragments")
    add_parser.add_argument("--json-path", help="JSON object with dotted-path assertions")
    add_parser.add_argument("--payload", help="JSON object payload for POST, PUT, or PATCH")
    add_parser.add_argument("--script")
    add_parser.add_argument("--expected-exit-code", dest="expected_exit_code", type=int)
    add_parser.add_argument("--expected-output")
    add_parser.add_argument("--timeout-seconds", dest="timeout_seconds", type=int)

    validate_parser = subparsers.add_parser("validate", help="Validate JSON definitions without MongoDB")
    validate_parser.add_argument("--domain", choices=["all", *DOMAINS.keys()], default="all")

    sync_parser = subparsers.add_parser("sync", help="Sync JSON definitions to local MongoDB")
    sync_parser.add_argument("--domain", choices=["all", *DOMAINS.keys()], default="all")

    export_parser = subparsers.add_parser("export", help="Export test definitions from local MongoDB to JSON files")
    export_parser.add_argument("--domain", choices=["all", *DOMAINS.keys()], default="all")
    export_parser.add_argument("--status", choices=[*STATUSES, "all"], default="all")

    run_parser = subparsers.add_parser("run", help="Run tests from repository JSON with optional MongoDB history")
    run_parser.add_argument("--domain", choices=[*DOMAINS.keys(), "all"])
    run_parser.add_argument("--type", dest="test_type", choices=[*TEST_KINDS, "all"])
    run_parser.add_argument("--layer", choices=[*LAYERS, "all"])
    run_parser.add_argument("--priority", choices=[*PRIORITIES, "all"])
    run_parser.add_argument("--status", choices=[*STATUSES, "all"], default="active")
    run_parser.add_argument("--env", default=load_settings().test_env)
    run_parser.add_argument("--workers", type=int, default=None)
    run_parser.add_argument("--interactive", action="store_true", help="Prompt for filters before running")
    run_parser.add_argument("--no-sync", action="store_true", help="Skip syncing JSON definitions before running")

    return parser


# Export stored MongoDB definitions back into their JSON roots.
def command_export(args: argparse.Namespace) -> int:
    settings = load_settings()
    domain = None if args.domain == "all" else args.domain

    try:
        store = open_mongo(settings)
    except MongoUnavailableError as exc:
        print_error("MongoDB Unavailable", str(exc))
        return 1

    try:
        docs = store.fetch_definitions(domain=domain, status=args.status)
    finally:
        store.close()

    if not docs:
        print_info("Nothing To Export", "No definitions matched the selected export filters.")
        return 0

    exported = 0
    for doc in docs:
        doc.pop("_id", None)
        path = definition_path(settings.definition_dir_for_suite(doc.get("suite")), doc["domain"], doc["id"])
        write_definition(path, doc)
        exported += 1

    print_success("Export Completed", f"Exported {exported} definition(s) to repository JSON files.")
    return 0


# Parse CLI arguments and dispatch to the selected command.
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print_local_mode_notice()

    if args.command == "add":
        raise SystemExit(prompt_add(args))
    if args.command == "validate":
        raise SystemExit(command_validate(args))
    if args.command == "sync":
        raise SystemExit(command_sync(args))
    if args.command == "export":
        raise SystemExit(command_export(args))
    if args.command == "run":
        if args.interactive:
            prompt_run_filters(args)
        raise SystemExit(command_run(args))

    parser.print_help()
    raise SystemExit(1)
