"""
HTTP test executor — makes an HTTP call and checks the response.

Supports assertions:
  - statusCode: expected HTTP status
  - bodyContains: list of strings that must appear in response body

Usage:
    from runner.executor import execute_http_test
    result = await execute_http_test(test)
"""

import time

import httpx


async def execute_http_test(test: dict) -> dict:
    """Execute a single HTTP test and return the result dict.

    Args:
        test: A dict with at least url, method, and expected fields.

    Returns:
        Dict with test_id, passed, duration_ms, http_status, error.
    """
    expected = test.get("expected", {})
    timeout_ms = test.get("timeout_ms", 5000)
    method = test.get("method", "GET")
    url = test.get("url", "")
    headers = test.get("headers") or {}
    payload = test.get("payload")

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

            # Check statusCode
            expected_status = expected.get("statusCode")
            if expected_status is not None and response.status_code != expected_status:
                error = f"expected status {expected_status}, got {response.status_code}"

            # Check bodyContains
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
        "test_id": test["id"],
        "passed": passed,
        "duration_ms": duration_ms,
        "http_status": status_code,
        "error": error,
    }
