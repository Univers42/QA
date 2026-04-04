"""
Registry executor — dispatches test execution by runner type.

Supports:
  - runner=http   → httpx async (legacy DDA behavior)
  - runner=bash   → subprocess with script path
  - runner=jest   → npx jest --testPathPattern=<script>
  - runner=pytest → python -m pytest <script>

For registered tests (scripts in external repos), the executor needs
the repo_root path to resolve the script location.

Usage:
    from runner.registry_executor import execute_registered_test

    result = await execute_registered_test(entry, repo_root="/path/to/repo")
"""

import os
import re
import subprocess
import time

import httpx


async def execute_registered_test(entry: dict, repo_root: str = ".") -> dict:
    """Execute a registered test and capture results.

    Args:
        entry: Registry entry dict from Atlas (id, runner, script, env_vars, etc.)
        repo_root: Path to the repository root where the script lives.

    Returns:
        Dict with test_id, passed, exit_code, duration_ms, stdout_tail, stderr_tail,
        tests_passed, tests_failed.
    """
    runner = entry.get("runner", "http")

    if runner == "http":
        return await _execute_http(entry)
    elif runner == "bash":
        return await _execute_script(entry, repo_root, shell_cmd=["bash"])
    elif runner == "jest":
        script = entry.get("script", "")
        return await _execute_script(
            entry,
            repo_root,
            shell_cmd=["npx", "jest", "--testPathPattern", script, "--forceExit"],
        )
    elif runner == "pytest":
        script = entry.get("script", "")
        return await _execute_script(
            entry,
            repo_root,
            shell_cmd=["python", "-m", "pytest", script, "-v"],
        )
    elif runner == "manual":
        return {
            "test_id": entry["id"],
            "passed": None,
            "exit_code": None,
            "duration_ms": 0,
            "error": "manual — skipped",
            "tests_passed": 0,
            "tests_failed": 0,
        }
    else:
        return {
            "test_id": entry["id"],
            "passed": False,
            "exit_code": None,
            "duration_ms": 0,
            "error": f"unknown runner: {runner}",
            "tests_passed": 0,
            "tests_failed": 0,
        }


async def _execute_http(entry: dict) -> dict:
    """Execute an HTTP test (legacy DDA behavior)."""
    expected = entry.get("expected", {})
    timeout_ms = entry.get("timeout_ms", 5000)
    method = entry.get("method", "GET")
    url = entry.get("url", "")
    headers = entry.get("headers") or {}
    payload = entry.get("payload")

    start = time.perf_counter()
    error = None
    passed = False
    status_code = None

    try:
        async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=payload if method in ("POST", "PUT", "PATCH") else None,
            )
            status_code = response.status_code
            body = response.text

            expected_status = expected.get("statusCode")
            if expected_status is not None and response.status_code != expected_status:
                error = f"expected status {expected_status}, got {response.status_code}"
            elif expected.get("bodyContains"):
                missing = [s for s in expected["bodyContains"] if s not in body]
                if missing:
                    error = f"body missing: {missing}"

            if not error:
                passed = True

    except httpx.TimeoutException:
        error = f"timeout after {timeout_ms}ms"
    except httpx.ConnectError:
        error = f"connection refused: {url}"
    except Exception as e:
        error = str(e)

    duration_ms = round((time.perf_counter() - start) * 1000)

    return {
        "test_id": entry["id"],
        "passed": passed,
        "exit_code": 0 if passed else 1,
        "duration_ms": duration_ms,
        "http_status": status_code,
        "error": error,
        "tests_passed": 1 if passed else 0,
        "tests_failed": 0 if passed else 1,
    }


async def _execute_script(
    entry: dict,
    repo_root: str,
    shell_cmd: list[str],
) -> dict:
    """Execute a script-based test (bash, jest, pytest).

    For bash runner, shell_cmd = ["bash"] and the script path is appended.
    For jest/pytest, shell_cmd already contains the full command.
    """
    script = entry.get("script", "")
    env_vars = entry.get("env_vars") or {}
    timeout_sec = entry.get("timeout_seconds", 120)

    # Build the command
    if shell_cmd == ["bash"]:
        full_path = os.path.join(repo_root, script)
        if not os.path.isfile(full_path):
            return {
                "test_id": entry["id"],
                "passed": False,
                "exit_code": -1,
                "duration_ms": 0,
                "error": f"script not found: {full_path}",
                "tests_passed": 0,
                "tests_failed": 0,
            }
        cmd = ["bash", full_path]
    else:
        cmd = shell_cmd

    # Merge environment variables
    env = {**os.environ, **env_vars}

    start = time.perf_counter()
    error = None
    passed = False
    stdout_text = ""
    stderr_text = ""

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
            cwd=repo_root,
        )

        stdout_text = result.stdout
        stderr_text = result.stderr
        passed = result.returncode == 0

        if not passed:
            error = f"exit code {result.returncode}"

    except subprocess.TimeoutExpired:
        error = f"timeout after {timeout_sec}s"
    except FileNotFoundError:
        error = f"command not found: {cmd[0]}"
    except Exception as e:
        error = str(e)

    duration_ms = round((time.perf_counter() - start) * 1000)

    # Parse test counts from stdout (test-ui.sh format)
    tests_passed, tests_failed = _parse_test_counts(stdout_text)

    return {
        "test_id": entry["id"],
        "passed": passed,
        "exit_code": result.returncode if "result" in dir() else -1,
        "duration_ms": duration_ms,
        "stdout_tail": stdout_text[-2000:] if stdout_text else None,
        "stderr_tail": stderr_text[-500:] if stderr_text else None,
        "error": error,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }


def _parse_test_counts(stdout: str) -> tuple[int, int]:
    """Extract test passed/failed counts from stdout.

    Recognizes the test-ui.sh summary format:
        ✔ Passed: 13
        ✖ Failed: 0

    Falls back to (0, 0) if the format is not found.
    """
    passed = 0
    failed = 0

    # Match patterns like "Passed: 13" or "✔ Passed: 13"
    passed_match = re.search(r"Passed:\s*(\d+)", stdout)
    failed_match = re.search(r"Failed:\s*(\d+)", stdout)

    if passed_match:
        passed = int(passed_match.group(1))
    if failed_match:
        failed = int(failed_match.group(1))

    return passed, failed
