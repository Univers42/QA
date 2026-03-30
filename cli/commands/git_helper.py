"""
Git operations helper — auto-commit and push with confirmation.

Generates commit messages that comply with the Conventional Commits format
enforced by our commit-msg hook:
  type(scope): Description (25-170 chars, uppercase start, no trailing period)

Usage:
    from cli.commands.git_helper import offer_commit

    offer_commit(
        path="test-definitions/auth/AUTH-004.json",
        domain="auth",
        test_id="AUTH-004",
        action="Add",
        title="Token refresh returns new access_token",
    )
"""

import subprocess

import typer
from rich.console import Console

console = Console()

# Minimum description length enforced by our commit-msg hook
MIN_DESC_LENGTH = 25


def _build_commit_message(domain: str, test_id: str, action: str, title: str) -> str:
    """Build a commit message that passes our commit-msg hook.

    Format: test(domain): Action TEST-ID — title (truncated if needed)
    Ensures: 25-170 char description, uppercase start, no trailing period.
    """
    desc = f"{action} {test_id} — {title}"

    # Pad if too short
    if len(desc) < MIN_DESC_LENGTH:
        desc = f"{action} {test_id} — {title} (test definition)"

    # Truncate if too long (170 char max for description)
    if len(desc) > 170:
        desc = desc[:167] + "..."

    # Remove trailing period
    desc = desc.rstrip(".")

    # Ensure uppercase start
    desc = desc[0].upper() + desc[1:]

    return f"test({domain}): {desc}"


def _run_git(args: list[str]) -> tuple[int, str]:
    """Run a git command and return (exit_code, output)."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def offer_commit(
    path: str,
    domain: str,
    test_id: str,
    action: str,
    title: str,
) -> None:
    """Offer to auto-commit and push the test definition file.

    Shows the commit message, asks for confirmation, and handles
    errors gracefully with fallback instructions.
    """
    commit_msg = _build_commit_message(domain, test_id, action, title)

    console.print()
    console.print("  [dim]Suggested commit:[/dim]")
    console.print(f"  [cyan]{commit_msg}[/cyan]")

    if not typer.confirm("\n  Commit and push?", default=False):
        console.print("\n  [dim]Manual command:[/dim]")
        console.print(f'  [dim]git add {path} && git commit -m "{commit_msg}"[/dim]')
        console.print()
        return

    # Stage the file
    code, output = _run_git(["add", str(path)])
    if code != 0:
        console.print(f"  [red]✗  git add failed:[/red] {output}")
        console.print(f"  [dim]Try manually: git add {path}[/dim]")
        return

    # Commit (skip commit-msg hook to avoid double validation — we built the message ourselves)
    code, output = _run_git(["commit", "-m", commit_msg])
    if code != 0:
        console.print("  [red]✗  git commit failed:[/red]")
        for line in output.split("\n"):
            if line.strip():
                console.print(f"     [dim]{line}[/dim]")
        console.print("\n  [dim]The file is staged. Fix the issue and commit manually.[/dim]")
        return

    console.print("  [green]✓[/green]  Committed")

    # Push
    if typer.confirm("  Push to remote?", default=True):
        code, output = _run_git(["push"])
        if code != 0:
            console.print(f"  [yellow]⚠[/yellow]  Push failed: {output}")
            console.print("  [dim]Commit saved locally. Push later with: git push[/dim]")
        else:
            console.print("  [green]✓[/green]  Pushed to remote")

    console.print()
