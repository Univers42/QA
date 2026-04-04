"""
pqa test register — register test scripts from external repos.

Two modes:
  - --scan <dir>:    auto-detect test scripts in a directory
  - --script <path>: register a single script manually

Detection rules for --scan:
  - *test*.sh, phase*-*.sh   → runner=bash
  - *.test.ts, *.test.tsx    → runner=jest
  - test_*.py, *_test.py     → runner=pytest
  - Skips: test-ui.sh, conftest.py, __pycache__

Usage:
    pqa test register --repo mini-baas-infra --scan scripts/
    pqa test register --repo mini-baas-infra --script scripts/phase1-smoke-test.sh
"""

import os
import re
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from core.db import disconnect, get_db

console = Console()

# ── Repository prefix mapping (for auto-generated IDs) ──
REPO_PREFIXES = {
    "mini-baas-infra": "BAAS",
    "transcendence": "FT",
    "qa": "QA",
}

# ── File patterns for runner detection ──
BASH_PATTERNS = [
    re.compile(r".*test.*\.sh$", re.IGNORECASE),
    re.compile(r"^phase\d+-.*\.sh$", re.IGNORECASE),
]
JEST_PATTERNS = [
    re.compile(r".*\.test\.(ts|tsx|js|jsx)$"),
    re.compile(r".*\.spec\.(ts|tsx|js|jsx)$"),
]
PYTEST_PATTERNS = [
    re.compile(r"^test[-_].*\.py$"),
    re.compile(r".*[-_]test\.py$"),
]

# ── Files to skip (helpers, not tests) ──
SKIP_FILES = {
    "test-ui.sh",
    "conftest.py",
    "jest.config.ts",
    "jest.config.js",
    "vitest.config.ts",
    "setup.ts",
    "setup.js",
}

SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".venv"}


def _detect_runner(filename: str) -> str | None:
    """Detect the runner type from the filename, or None if not a test."""
    if filename in SKIP_FILES:
        return None

    for pattern in BASH_PATTERNS:
        if pattern.match(filename):
            return "bash"
    for pattern in JEST_PATTERNS:
        if pattern.match(filename):
            return "jest"
    for pattern in PYTEST_PATTERNS:
        if pattern.match(filename):
            return "pytest"

    return None


def _generate_id(repo: str, filename: str) -> str:
    """Generate a test ID from the repo and filename.

    Examples:
        mini-baas-infra + phase8-token-lifecycle-test.sh → BAAS-PHASE08
        transcendence + auth.test.ts → FT-AUTH
    """
    prefix = REPO_PREFIXES.get(repo, repo[:4].upper())
    stem = Path(filename).stem  # Remove extension

    # Remove common suffixes
    for suffix in ["-test", "_test", ".test", ".spec", "-smoke"]:
        stem = stem.replace(suffix, "")

    # Extract phase number if present
    phase_match = re.match(r"^phase(\d+)", stem, re.IGNORECASE)
    if phase_match:
        num = phase_match.group(1).zfill(2)
        return f"{prefix}-PHASE{num}"

    # Fallback: clean up the stem
    clean = re.sub(r"[^a-zA-Z0-9]", "", stem).upper()
    if len(clean) > 20:
        clean = clean[:20]

    return f"{prefix}-{clean}"


def _generate_title(filename: str) -> str:
    """Generate a human-readable title from the filename."""
    stem = Path(filename).stem
    # Replace hyphens/underscores with spaces, title case
    title = re.sub(r"[-_]+", " ", stem)
    # Remove "test" suffix/prefix
    title = re.sub(r"\btest\b", "", title, flags=re.IGNORECASE).strip()
    title = " ".join(title.split())  # Normalize whitespace
    return title.title() if title else filename


def _guess_domain(filename: str) -> str:
    """Guess the domain from filename keywords."""
    lower = filename.lower()
    if any(k in lower for k in ["auth", "token", "jwt", "login", "signup"]):
        return "auth"
    if any(k in lower for k in ["cors", "rate-limit", "gateway", "kong"]):
        return "gateway"
    if any(k in lower for k in ["storage", "minio", "s3", "upload"]):
        return "storage"
    if any(k in lower for k in ["realtime", "websocket", "ws"]):
        return "realtime"
    if any(k in lower for k in ["db", "sql", "postgres", "query", "mutation"]):
        return "api"
    if any(k in lower for k in ["smoke", "health", "infra"]):
        return "infra"
    if any(k in lower for k in ["ui", "component", "render", "frontend"]):
        return "ui"
    return "infra"  # default


def _scan_directory(scan_path: str, repo: str) -> list[dict]:
    """Scan a directory for test files and build registry entries."""
    entries = []
    base = Path(scan_path)

    if not base.is_dir():
        console.print(f"\n  [red]Directory not found: {scan_path}[/red]\n")
        return []

    for item in sorted(base.rglob("*")):
        # Skip directories and hidden files
        if item.is_dir():
            continue
        if any(part in SKIP_DIRS for part in item.parts):
            continue

        runner = _detect_runner(item.name)
        if runner is None:
            console.print(f"  [dim]—  {item.name:<40} skipped (not a test)[/dim]")
            continue

        # Build relative path from repo root
        rel_path = str(item)

        test_id = _generate_id(repo, item.name)
        title = _generate_title(item.name)
        domain = _guess_domain(item.name)

        entry = {
            "id": test_id,
            "title": title,
            "domain": domain,
            "priority": "P1",
            "status": "active",
            "repo": repo,
            "runner": runner,
            "script": rel_path,
            "layer": "backend",
            "author": os.getenv("PQA_USER", ""),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        entries.append(entry)

    return entries


def register_tests(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository name (e.g. mini-baas-infra)"),
    scan: str | None = typer.Option(None, "--scan", help="Directory to scan for test scripts"),
    script: str | None = typer.Option(None, "--script", help="Single script to register"),
    layer: str | None = typer.Option(
        None, "--layer", "-l", help="Override layer for all registered tests"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be registered without writing to Atlas"
    ),
):
    """Register test scripts from an external repository.

    Auto-detects test files by naming convention and registers metadata in Atlas.
    The scripts themselves stay in their repo — QA only stores the catalog entry.
    """
    try:
        if not scan and not script:
            console.print("\n  [red]Provide --scan <dir> or --script <path>[/red]\n")
            raise typer.Exit(1)

        entries: list[dict] = []

        if scan:
            console.print(f"\n  Scanning [bold]{scan}[/bold] for test files...\n")
            entries = _scan_directory(scan, repo)
        elif script:
            runner = _detect_runner(Path(script).name)
            if not runner:
                runner = "bash"  # Default for single script
            entries = [
                {
                    "id": _generate_id(repo, Path(script).name),
                    "title": _generate_title(Path(script).name),
                    "domain": _guess_domain(Path(script).name),
                    "priority": "P1",
                    "status": "active",
                    "repo": repo,
                    "runner": runner,
                    "script": script,
                    "layer": layer or "backend",
                    "author": os.getenv("PQA_USER", ""),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]

        if not entries:
            console.print("  [yellow]No test files detected.[/yellow]\n")
            raise typer.Exit(0)

        # Apply layer override
        if layer:
            for e in entries:
                e["layer"] = layer

        if dry_run:
            console.print("  [dim]Dry run — nothing will be written to Atlas[/dim]\n")
            for e in entries:
                console.print(
                    f"  [cyan]{e['id']:<16}[/cyan] {e['script']:<45} runner={e['runner']}"
                )
            console.print(f"\n  Would register {len(entries)} test(s)\n")
            raise typer.Exit(0)

        # Write to Atlas
        db = get_db()
        new_count = 0
        updated_count = 0

        for entry in entries:
            existing = db["tests"].find_one({"id": entry["id"]})
            if existing:
                # Update — preserve author, created_at, status if already set
                entry["created_at"] = existing.get("created_at", entry["created_at"])
                entry["author"] = existing.get("author") or entry["author"]
                if existing.get("status") != "draft":
                    entry["status"] = existing["status"]
                db["tests"].update_one({"id": entry["id"]}, {"$set": entry})
                console.print(
                    f"  [yellow]~  {entry['id']:<16}[/yellow] {entry['script']:<45} (updated)"
                )
                updated_count += 1
            else:
                db["tests"].insert_one(entry)
                console.print(f"  [green]✓  {entry['id']:<16}[/green] {entry['script']:<45} (new)")
                new_count += 1

        console.print(f"\n  Registered {new_count} new · {updated_count} updated\n")

    finally:
        disconnect()
