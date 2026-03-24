"""
Bash test executor — runs a shell command and checks exit code / output.

Usage:
    from runner.bash_executor import execute_bash_test
    result = await execute_bash_test(test)
"""

import subprocess
import time


async def execute_bash_test(test: dict) -> dict:
    """Execute a single bash test and return the result dict.

    Args:
        test: A dict with at least script and expected_exit_code fields.

    Returns:
        Dict with test_id, passed, duration_ms, error.
    """
    script = test.get("script", "")
    expected_exit = test.get("expected_exit_code", 0)
    expected_output = test.get("expected_output")
    timeout_sec = test.get("timeout_seconds", 30)

    start = time.perf_counter()
    error = None
    passed = False

    try:
        result = subprocess.run(
            script,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

        if result.returncode != expected_exit:
            error = f"exit code: expected {expected_exit}, got {result.returncode}"
        elif expected_output and expected_output not in result.stdout:
            error = f"output missing: {expected_output}"
        else:
            passed = True

    except subprocess.TimeoutExpired:
        error = f"timeout after {timeout_sec}s"
    except Exception as e:
        error = str(e)

    duration_ms = round((time.perf_counter() - start) * 1000)

    return {
        "test_id": test["id"],
        "passed": passed,
        "duration_ms": duration_ms,
        "error": error,
    }
