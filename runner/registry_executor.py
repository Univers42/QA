"""
Registry executor — dispatches test execution by runner type.

Main function:
    execute_registered_test(entry, repo_root)
    
Supported runners:
    - http    → REST API testing (httpx async client)
    - bash    → Shell script execution (subprocess)
    - jest    → JavaScript testing via npx jest
    - pytest  → Python testing via pytest
    - manual  → Specification/manual test (skipped)

Result format (all runners return):
    {
        "test_id": str,           # Test identifier (e.g., "AUTH-001")
        "passed": bool | None,    # True=pass, False=fail, None=skipped
        "exit_code": int | None,  # Process exit code (0=success)
        "duration_ms": int,       # Execution time in milliseconds
        "error": str | None,      # Error message if failed
        "tests_passed": int,      # Sub-test passes (for frameworks)
        "tests_failed": int,      # Sub-test failures (for frameworks)
        "http_status": int | None,  # HTTP status code (for HTTP tests)
        "stdout_tail": str | None,  # Last 2000 chars of stdout
        "stderr_tail": str | None,  # Last 500 chars of stderr
    }

Dependencies:
    - core/logging: Structured logging for debugging
    - httpx: Async HTTP client for HTTP tests
    - subprocess: Shell execution for bash/jest/pytest tests
"""

import os
import re
import subprocess
import time

import httpx


async def execute_registered_test(entry: dict, repo_root: str = ".") -> dict:
    """
    Execute a registered test and capture results.
    
    Dispatches to appropriate executor based on runner type.
    Each runner has its own validation and error handling.

    Args:
        entry: Test definition dict from database with keys:
            - id (required): Test identifier
            - runner: Type of runner (http, bash, jest, pytest, manual)
            - script: Path to script (for bash/jest/pytest)
            - method, url, payload: HTTP test configuration
            - timeout_ms: Timeout for HTTP tests (default: 5000)
            - timeout_seconds: Timeout for scripts (default: 120)
            - env_vars: Environment variables to inject
            
        repo_root: Base directory for script resolution (default: current directory)

    Returns:
        Dictionary with test results (see module docstring for format)
    """
    runner = entry.get("runner", "http")

    # Dispatch to appropriate executor
    if runner == "http":
        return await _execute_http_test(entry)
    elif runner == "bash":
        return await _execute_script_test(entry, repo_root, shell_cmd=["bash"])
    elif runner == "jest":
        script = entry.get("script", "")
        return await _execute_script_test(
            entry,
            repo_root,
            shell_cmd=["npx", "jest", "--testPathPattern", script, "--forceExit"],
        )
    elif runner == "pytest":
        script = entry.get("script", "")
        return await _execute_script_test(
            entry,
            repo_root,
            shell_cmd=["python", "-m", "pytest", script, "-v"],
        )
    elif runner == "manual":
        # Manual tests are not automatically executed — return skipped
        return {
            "test_id": entry["id"],
            "passed": None,
            "exit_code": None,
            "duration_ms": 0,
            "error": "Manual test — skipped (requires manual execution)",
            "tests_passed": 0,
            "tests_failed": 0,
        }
    else:
        # Unknown runner type
        return {
            "test_id": entry["id"],
            "passed": False,
            "exit_code": None,
            "duration_ms": 0,
            "error": f"Unknown runner type: {runner}",
            "tests_passed": 0,
            "tests_failed": 0,
        }


# ─── HTTP Test Executor ───────────────────────────────────────────────


async def _execute_http_test(entry: dict) -> dict:
    """
    Execute an HTTP REST API test.
    
    Validates:
    - Response status code matches expected value
    - Response body contains all expected strings
    
    Args:
        entry: Test entry with http configuration (url, method, headers, payload, expected)
        
    Returns:
        Result dict with passed boolean, http_status, and error message
        
    Timeout handling:
    - Applies httpx.AsyncClient(timeout=timeout_ms/1000)
    - Returns error on timeout
    """
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

            # Validate expected status code
            expected_status = expected.get("statusCode")
            if expected_status is not None and response.status_code != expected_status:
                error = f"Expected status {expected_status}, got {response.status_code}"
            # Validate expected response body content
            elif expected.get("bodyContains"):
                missing = [s for s in expected["bodyContains"] if s not in body]
                if missing:
                    error = f"Body missing expected strings: {missing}"

            if not error:
                passed = True

    except httpx.TimeoutException:
        error = f"HTTP timeout after {timeout_ms}ms"
    except httpx.ConnectError:
        error = f"Connection refused: {url}"
    except Exception as e:
        error = f"HTTP execution error: {str(e)}"

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


# ─── Script Test Executor (Bash, Jest, Pytest) ──────────────────────────


async def _execute_script_test(
    entry: dict,
    repo_root: str,
    shell_cmd: list[str],
) -> dict:
    """
    Execute a script-based test (bash, jest, or pytest).

    Handles:
    - Script path resolution relative to repo_root
    - Environment variable injection
    - Timeout enforcement
    - Output capture and parsing
    
    Args:
        entry: Test entry with script path and env_vars
        repo_root: Base directory for script resolution
        shell_cmd: Command array (e.g., ["bash"], ["npx", "jest", ...])
        
    Returns:
        Result dict with exit_code, passed boolean, and error message
        
    Timeout handling:
    - Uses subprocess.run(timeout=timeout_seconds)
    - Raises TimeoutExpired if exceeded (caught and returned in error)
    """
    script = entry.get("script", "")
    env_vars = entry.get("env_vars") or {}
    timeout_sec = entry.get("timeout_seconds", 120)

    # Build the full command
    if shell_cmd == ["bash"]:
        # For bash runner: resolve script path and append to command
        full_path = os.path.join(repo_root, script)
        if not os.path.isfile(full_path):
            return {
                "test_id": entry["id"],
                "passed": False,
                "exit_code": -1,
                "duration_ms": 0,
                "error": f"Script not found: {full_path}",
                "tests_passed": 0,
                "tests_failed": 0,
            }
        cmd = ["bash", full_path]
    else:
        # For jest/pytest: command is complete, just use it
        cmd = shell_cmd

    # Merge environment variables (preserve existing + add test-specific)
    env = {**os.environ, **env_vars}

    start = time.perf_counter()
    error = None
    passed = False
    stdout_text = ""
    stderr_text = ""
    exit_code = -1

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
        exit_code = result.returncode
        passed = result.returncode == 0

        if not passed:
            error = f"Exit code {result.returncode}"

    except subprocess.TimeoutExpired:
        error = f"Script timeout after {timeout_sec}s"
        exit_code = -1
    except FileNotFoundError:
        error = f"Command not found: {cmd[0]}"
        exit_code = -1
    except Exception as e:
        error = f"Script execution error: {str(e)}"
        exit_code = -1

    duration_ms = round((time.perf_counter() - start) * 1000)

    # Parse sub-test counts from output (e.g., from test-ui.sh)
    tests_passed, tests_failed = _parse_test_counts(stdout_text)

    return {
        "test_id": entry["id"],
        "passed": passed,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_tail": stdout_text[-2000:] if stdout_text else None,
        "stderr_tail": stderr_text[-500:] if stderr_text else None,
        "error": error,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }


# ─── Output Parsing Helper ────────────────────────────────────────────


def _parse_test_counts(stdout: str) -> tuple[int, int]:
    """
    Extract sub-test pass/fail counts from script output.
    
    Recognizes test-ui.sh summary format:
        ✔ Passed: 13
        ✖ Failed: 0
        
    Also matches lines like:
        "Passed: 13 Failed: 0"
        
    Falls back to (0, 0) if format not recognized.
    
    Args:
        stdout: Complete stdout from script execution
        
    Returns:
        Tuple of (tests_passed, tests_failed) integers
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
