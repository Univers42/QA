from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from .catalog import (
    BODY_METHODS,
    DEFAULT_PHASE,
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DEFAULT_TYPE,
    DOMAINS,
    METHODS,
    PRIORITIES,
    STATUSES,
    TEST_TYPES,
    normalize_domain,
)
from .env import load_settings
from .files import DefinitionFile, definition_path, next_test_id, read_definition_files, validation_errors, write_definition
from .mongo import MongoStore, MongoUnavailableError
from .runner import RunOutcome, git_sha, run_tests

console = Console()


def default_author() -> str:
    return os.getenv("USER", "unknown")


def comma_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def format_url(input_value: str, domain: str, settings: Any) -> str:
    value = input_value.strip()
    if value.startswith(("http://", "https://")):
        return value

    base_url = settings.base_url_for_domain(domain)
    if not base_url:
        return value

    return base_url.rstrip("/") + "/" + value.lstrip("/")


def build_definition(
    *,
    test_id: str,
    domain: str,
    title: str,
    url: str,
    method: str,
    status_code: int,
    body_contains: list[str],
    author: str,
    phase: str,
    test_type: str,
    priority: str,
    status: str,
    payload: dict[str, Any] | None,
    tags: list[str],
    preconditions: list[str],
    environment: str,
) -> dict[str, Any]:
    spec = DOMAINS[domain]
    description = f"{method} {url} should return HTTP {status_code} for {title.lower()}."
    expected: dict[str, Any] = {"statusCode": status_code}
    if body_contains:
        expected["bodyContains"] = body_contains

    definition: dict[str, Any] = {
        "id": test_id,
        "title": title,
        "description": description,
        "domain": domain,
        "type": test_type,
        "layer": spec.layer,
        "priority": priority,
        "tags": tags,
        "service": spec.service,
        "environment": [environment],
        "preconditions": preconditions,
        "expected": expected,
        "url": url,
        "method": method,
        "author": author,
        "phase": phase,
        "status": status,
    }

    if payload is not None:
        definition["payload"] = payload
        definition["headers"] = {"Content-Type": "application/json"}

    return definition


def open_mongo(settings: Any) -> MongoStore:
    store = MongoStore(settings.mongo_uri)
    store.ensure_indexes()
    return store


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
        docs.append(item.doc)

    store = open_mongo(settings)
    try:
        summary = store.upsert_tests(docs)
    finally:
        store.close()

    summary["invalid"] = len(errors)
    return summary, errors


def print_sync_summary(summary: dict[str, int], errors: list[str]) -> None:
    table = Table(title="MongoDB sync")
    table.add_column("Inserted", justify="right")
    table.add_column("Updated", justify="right")
    table.add_column("Unchanged", justify="right")
    table.add_column("Invalid", justify="right")
    table.add_row(
        str(summary["inserted"]),
        str(summary["updated"]),
        str(summary["unchanged"]),
        str(summary["invalid"]),
    )
    console.print(table)

    if errors:
        for error in errors:
            console.print(f"[red]-[/red] {error}")


def prompt_domain() -> str:
    choices = list(DOMAINS)
    return normalize_domain(Prompt.ask("Dominio", choices=choices, default="auth"))


def prompt_add(args: argparse.Namespace) -> int:
    settings = load_settings()
    domain = prompt_domain()
    title = Prompt.ask("Comportamiento a comprobar")

    base_url = settings.base_url_for_domain(domain)
    endpoint_label = "Endpoint path o URL completa"
    if base_url:
        endpoint_label += f" (base {base_url})"

    url = format_url(Prompt.ask(endpoint_label), domain, settings)
    method = Prompt.ask("Metodo HTTP", choices=METHODS, default="GET")
    status_code = IntPrompt.ask("HTTP status esperado", default=200)
    body_contains = comma_list(Prompt.ask("Fragmentos esperados en body (coma, opcional)", default=""))

    payload = None
    if method in BODY_METHODS:
        payload_input = Prompt.ask("Payload JSON (opcional)", default="")
        if payload_input:
            try:
                payload = json.loads(payload_input)
            except json.JSONDecodeError as exc:
                console.print(f"[red]Payload JSON invalido:[/red] {exc}")
                return 1

    advanced = args.advanced or Confirm.ask("¿Configurar opciones avanzadas?", default=False)
    author = default_author()
    phase = DEFAULT_PHASE
    test_type = DEFAULT_TYPE
    priority = DEFAULT_PRIORITY
    status = DEFAULT_STATUS
    tags: list[str] = []
    preconditions: list[str] = []

    if advanced:
        test_type = Prompt.ask("Tipo de test", choices=TEST_TYPES, default=DEFAULT_TYPE)
        priority = Prompt.ask("Prioridad", choices=PRIORITIES, default=DEFAULT_PRIORITY)
        phase = Prompt.ask("Fase", default=DEFAULT_PHASE)
        status = Prompt.ask("Estado", choices=STATUSES, default=DEFAULT_STATUS)
        author = Prompt.ask("Autor", default=author)
        tags = comma_list(Prompt.ask("Tags (coma, opcional)", default=""))
        preconditions = comma_list(Prompt.ask("Precondiciones (coma, opcional)", default=""))

    test_id = next_test_id(domain, settings.tests_dir)
    definition = build_definition(
        test_id=test_id,
        domain=domain,
        title=title,
        url=url,
        method=method,
        status_code=status_code,
        body_contains=body_contains,
        author=author,
        phase=phase,
        test_type=test_type,
        priority=priority,
        status=status,
        payload=payload,
        tags=tags,
        preconditions=preconditions,
        environment=settings.test_env,
    )
    path = definition_path(settings.tests_dir, domain, test_id)
    write_definition(path, definition)

    console.print(
        Panel.fit(
            f"JSON creado en [bold]{path.relative_to(settings.root)}[/bold]\n"
            f"ID: [cyan]{test_id}[/cyan]\n"
            f"Dominio: [cyan]{domain}[/cyan]\n"
            f"Tipo: [cyan]{test_type}[/cyan]\n"
            f"Estado: [cyan]{status}[/cyan]",
            title="Nuevo test",
        )
    )

    if args.no_sync:
        return 0

    try:
        summary, errors = sync_documents(settings, [DefinitionFile(path=path, doc=definition)])
    except MongoUnavailableError as exc:
        console.print(f"[yellow]JSON guardado, pero no se pudo sincronizar con MongoDB:[/yellow] {exc}")
        return 0

    print_sync_summary(summary, errors)
    return 0


def prompt_run_filters(args: argparse.Namespace) -> None:
    args.domain = Prompt.ask("Dominio", choices=["all", *DOMAINS.keys()], default="all")
    args.test_type = Prompt.ask("Tipo", choices=["all", *TEST_TYPES], default="all")
    args.priority = Prompt.ask("Prioridad", choices=["all", *PRIORITIES], default="all")
    args.status = Prompt.ask("Estado", choices=["all", *STATUSES], default=args.status)


def outcome_style(outcome: RunOutcome) -> str:
    if outcome.comparison == "regression":
        return "bold red"
    if outcome.comparison == "fixed":
        return "bold green"
    if outcome.passed:
        return "green"
    return "yellow"


def print_run_results(outcomes: list[RunOutcome]) -> None:
    table = Table(title="Prismatica QA run")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type")
    table.add_column("HTTP", justify="right")
    table.add_column("ms", justify="right")
    table.add_column("Compare")
    table.add_column("Title", overflow="fold")

    for outcome in outcomes:
        status_code = str(outcome.http_status) if outcome.http_status is not None else "-"
        table.add_row(
            outcome.test["id"],
            outcome.test.get("type", "-"),
            status_code,
            str(outcome.duration_ms),
            f"[{outcome_style(outcome)}]{outcome.comparison}[/]",
            outcome.test["title"],
        )
        if outcome.error:
            table.add_row("", "", "", "", "[red]error[/red]", outcome.error)

    console.print(table)

    passed = sum(1 for outcome in outcomes if outcome.passed)
    failed = len(outcomes) - passed
    regressions = sum(1 for outcome in outcomes if outcome.comparison == "regression")
    fixed = sum(1 for outcome in outcomes if outcome.comparison == "fixed")

    console.print(
        Panel.fit(
            f"Passed: [green]{passed}[/green]\n"
            f"Failed: [red]{failed}[/red]\n"
            f"Regressions: [red]{regressions}[/red]\n"
            f"Fixed: [green]{fixed}[/green]",
            title="Summary",
        )
    )


def command_sync(args: argparse.Namespace) -> int:
    settings = load_settings()
    domain = None if args.domain == "all" else args.domain
    items = read_definition_files(settings.tests_dir, domain)

    try:
        summary, errors = sync_documents(settings, items)
    except MongoUnavailableError as exc:
        console.print(f"[red]No se pudo abrir MongoDB:[/red] {exc}")
        return 1

    print_sync_summary(summary, errors)
    return 1 if errors else 0


def command_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    if (
        sys.stdin.isatty()
        and args.status == "active"
        and not any([args.domain, args.test_type, args.priority, args.interactive])
    ):
        prompt_run_filters(args)

    if not args.no_sync:
        try:
            summary, errors = sync_documents(settings, read_definition_files(settings.tests_dir))
            if errors:
                console.print(
                    f"[yellow]El pre-sync detecto {summary['invalid']} definicion(es) invalida(s). "
                    "Se ejecutaran solo las definiciones validas sincronizadas.[/yellow]"
                )
        except MongoUnavailableError:
            pass

    domain = None if args.domain in (None, "all") else normalize_domain(args.domain)
    test_type = None if args.test_type in (None, "all") else args.test_type
    priority = None if args.priority in (None, "all") else args.priority
    status = args.status or "active"

    try:
        store = open_mongo(settings)
    except MongoUnavailableError as exc:
        console.print(f"[red]No se pudo abrir MongoDB:[/red] {exc}")
        return 1

    try:
        tests = store.fetch_tests(
            domain=domain,
            test_type=test_type,
            priority=priority,
            status=status,
            environment=args.env,
        )
        if not tests:
            console.print("[yellow]No hay tests para los filtros indicados.[/yellow]")
            return 0

        previous = store.latest_results_map([test["id"] for test in tests], args.env)
        run_id, outcomes = run_tests(
            tests,
            settings=settings,
            previous_results=previous,
            workers=args.workers,
        )
        store.store_results(
            [outcome.__dict__ for outcome in outcomes],
            run_id=run_id,
            environment=args.env,
            run_by=default_author(),
            git_sha=git_sha(str(settings.root)),
        )
    finally:
        store.close()

    print_run_results(outcomes)
    return 1 if any(not outcome.passed for outcome in outcomes) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python QA automation for Prismatica")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a test definition interactively")
    add_parser.add_argument("--advanced", action="store_true", help="Ask for advanced fields")
    add_parser.add_argument("--no-sync", action="store_true", help="Only create the JSON file")

    sync_parser = subparsers.add_parser("sync", help="Sync JSON definitions to MongoDB")
    sync_parser.add_argument("--domain", choices=["all", *DOMAINS.keys()], default="all")

    run_parser = subparsers.add_parser("run", help="Run tests from MongoDB")
    run_parser.add_argument("--domain", choices=[*DOMAINS.keys(), "all"])
    run_parser.add_argument("--type", dest="test_type", choices=[*TEST_TYPES, "all"])
    run_parser.add_argument("--priority", choices=[*PRIORITIES, "all"])
    run_parser.add_argument("--status", choices=[*STATUSES, "all"], default="active")
    run_parser.add_argument("--env", default=load_settings().test_env)
    run_parser.add_argument("--workers", type=int, default=None)
    run_parser.add_argument("--interactive", action="store_true", help="Prompt for filters before running")
    run_parser.add_argument("--no-sync", action="store_true", help="Skip syncing JSON definitions before running")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "add":
        raise SystemExit(prompt_add(args))
    if args.command == "sync":
        raise SystemExit(command_sync(args))
    if args.command == "run":
        if args.interactive:
            prompt_run_filters(args)
        raise SystemExit(command_run(args))

    parser.print_help()
    raise SystemExit(1)
