from __future__ import annotations

import base64
import json
import math
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .catalog import BODY_METHODS
from .env import Settings
from .models import detect_test_type
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


@dataclass(frozen=True)
class RunOutcome:
    test: dict[str, Any]
    passed: bool
    http_status: int | None
    duration_ms: int
    error: str | None
    response_snapshot: dict[str, Any]
    comparison: str


# Return the current repository short SHA for result traceability.
def git_sha(root: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


# Resolve a test URL, expanding relative paths from the configured domain base URL.
def resolve_url(test: dict[str, Any], settings: Settings) -> str:
    raw_url = str(test.get("url", "")).strip()
    if raw_url.startswith(("http://", "https://")):
        return raw_url

    base_url = settings.base_url_for_domain(test["domain"])
    if not base_url:
        raise ValueError(f"Domain '{test['domain']}' requires a full URL because it has no base URL configured.")

    return urllib.parse.urljoin(base_url.rstrip("/") + "/", raw_url.lstrip("/"))


# Decode the payload section of a JWT token without external dependencies.
def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT token")

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
    return json.loads(decoded)


# Extract a JWT-like token from a JSON response body when present.
def extract_jwt_from_body(body_text: str) -> str | None:
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(body, dict):
        return None

    for key in ("access_token", "token", "jwt"):
        value = body.get(key)
        if isinstance(value, str):
            return value
    return None


# Classify the current result against the previous stored outcome.
def comparison_label(previous: dict[str, Any] | None, passed: bool) -> str:
    if not previous:
        return "new"

    previous_passed = bool(previous.get("passed"))
    if previous_passed and not passed:
        return "regression"
    if not previous_passed and passed:
        return "fixed"
    if passed:
        return "stable-pass"
    return "stable-fail"


# Evaluate HTTP expectations against the actual response data.
def evaluate_expected(test: dict[str, Any], status_code: int, body_text: str, headers: dict[str, str]) -> list[str]:
    expected = test.get("expected", {})
    errors: list[str] = []

    if "statusCode" in expected and status_code != expected["statusCode"]:
        errors.append(f"expected status {expected['statusCode']}, got {status_code}")

    for fragment in expected.get("bodyContains", []) or []:
        if fragment not in body_text:
            errors.append(f'body missing: "{fragment}"')

    cookie_name = expected.get("cookieSet")
    if cookie_name:
        cookie_header = headers.get("Set-Cookie", "")
        if cookie_name not in cookie_header:
            errors.append(f'missing cookie: "{cookie_name}"')

    jwt_claims = expected.get("jwtClaims")
    if jwt_claims:
        token = extract_jwt_from_body(body_text)
        if not token:
            errors.append("expected jwtClaims but no JWT found in response body")
        else:
            try:
                payload = decode_jwt_payload(token)
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"invalid JWT payload: {exc}")
            else:
                for key, expected_value in jwt_claims.items():
                    if key == "exp_offset_min":
                        exp = payload.get("exp")
                        if not isinstance(exp, (int, float)):
                            errors.append("JWT is missing numeric exp claim")
                            continue
                        delta = exp - time.time()
                        target = int(expected_value) * 60
                        if math.fabs(delta - target) > 300:
                            errors.append(f"jwt exp offset out of range: expected ~{target}s, got {int(delta)}s")
                        continue

                    if payload.get(key) != expected_value:
                        errors.append(f"jwt claim mismatch for {key}: expected {expected_value}, got {payload.get(key)}")

    json_path_assertions = expected.get("jsonPath")
    if json_path_assertions:
        try:
            body_json = json.loads(body_text)
        except json.JSONDecodeError:
            errors.append("expected jsonPath assertions but response body is not valid JSON")
        else:
            for path, expected_value in json_path_assertions.items():
                current = body_json
                for key in path.split("."):
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        current = None
                        break
                if current != expected_value:
                    errors.append(f"jsonPath mismatch for {path}: expected {expected_value}, got {current}")

    return errors


# Execute one HTTP test and collect its normalized outcome.
def execute_http_test(test: dict[str, Any], settings: Settings, previous: dict[str, Any] | None) -> RunOutcome:
    start = time.perf_counter()

    try:
        url = resolve_url(test, settings)
    except ValueError as exc:
        return RunOutcome(
            test=test,
            passed=False,
            http_status=None,
            duration_ms=0,
            error=str(exc),
            response_snapshot={"url": test.get("url")},
            comparison=comparison_label(previous, False),
        )

    headers = dict(test.get("headers") or {})
    data: bytes | None = None

    if test.get("method") in BODY_METHODS and test.get("payload") is not None:
        data = json.dumps(test["payload"]).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(
        url,
        method=test.get("method", "GET"),
        headers=headers,
        data=data,
    )
    timeout_seconds = test.get("timeout_seconds")
    if timeout_seconds is None and isinstance(test.get("timeout_ms"), int):
        timeout_seconds = max(1, int(test["timeout_ms"] / 1000))
    timeout_seconds = max(1, int(timeout_seconds or 5))

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            body_text = response.read().decode("utf-8", errors="replace")
            response_headers = dict(response.info())
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        body_text = exc.read().decode("utf-8", errors="replace")
        response_headers = dict(exc.headers.items())
    except urllib.error.URLError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return RunOutcome(
            test=test,
            passed=False,
            http_status=None,
            duration_ms=duration_ms,
            error=f"network error: {exc.reason}",
            response_snapshot={"url": url},
            comparison=comparison_label(previous, False),
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    errors = evaluate_expected(test, status_code, body_text, response_headers)
    passed = len(errors) == 0

    return RunOutcome(
        test=test,
        passed=passed,
        http_status=status_code,
        duration_ms=duration_ms,
        error=" | ".join(errors) if errors else None,
        response_snapshot={
            "url": url,
            "status_code": status_code,
            "headers": response_headers,
            "body_preview": body_text[:1000],
        },
        comparison=comparison_label(previous, passed),
    )


# Execute one bash/script test and collect its normalized outcome.
def execute_script_test(test: dict[str, Any], previous: dict[str, Any] | None) -> RunOutcome:
    start = time.perf_counter()
    command = str(test.get("script", "")).strip()
    if not command:
        return RunOutcome(
            test=test,
            passed=False,
            http_status=None,
            duration_ms=0,
            error="missing script command",
            response_snapshot={},
            comparison=comparison_label(previous, False),
        )

    timeout_seconds = max(1, int(test.get("timeout_seconds", 30)))

    try:
        result = subprocess.run(
            ["/bin/bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=test.get("working_dir"),
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return RunOutcome(
            test=test,
            passed=False,
            http_status=None,
            duration_ms=duration_ms,
            error=f"script timed out after {timeout_seconds}s",
            response_snapshot={"command": command},
            comparison=comparison_label(previous, False),
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    errors: list[str] = []
    expected_exit = int(test.get("expected_exit_code", 0))
    if result.returncode != expected_exit:
        errors.append(f"expected exit code {expected_exit}, got {result.returncode}")

    output = f"{result.stdout}\n{result.stderr}"
    expected_output = test.get("expected_output")
    if expected_output and expected_output not in output:
        errors.append(f'output missing: "{expected_output}"')

    passed = len(errors) == 0
    return RunOutcome(
        test=test,
        passed=passed,
        http_status=None,
        duration_ms=duration_ms,
        error=" | ".join(errors) if errors else None,
        response_snapshot={
            "command": command,
            "stdout_preview": result.stdout[:1000],
            "stderr_preview": result.stderr[:1000],
            "output_preview": output[:1000],
            "exit_code": result.returncode,
        },
        comparison=comparison_label(previous, passed),
    )


# Execute one manual test by asking the operator for confirmation.
def execute_manual_test(test: dict[str, Any], previous: dict[str, Any] | None) -> RunOutcome:
    start = time.perf_counter()

    if not sys.stdin.isatty():
        return RunOutcome(
            test=test,
            passed=False,
            http_status=None,
            duration_ms=0,
            error="manual tests require interactive confirmation",
            response_snapshot={},
            comparison=comparison_label(previous, False),
        )

    details = [test["title"]]
    if test.get("description"):
        details.append("")
        details.append(str(test["description"]))
    if test.get("preconditions"):
        details.append("")
        details.append("Preconditions:")
        details.extend(f"- {item}" for item in test["preconditions"])
    if test.get("notes"):
        details.append("")
        details.append(f"Notes: {test['notes']}")

    console.print(
        Panel.fit(
            "\n".join(details),
            title=f"Manual Test {test['id']}",
            border_style="cyan",
        )
    )
    passed = Confirm.ask("Did this manual test pass?", default=False)
    duration_ms = int((time.perf_counter() - start) * 1000)

    return RunOutcome(
        test=test,
        passed=passed,
        http_status=None,
        duration_ms=duration_ms,
        error=None if passed else "manual test marked as failed by operator",
        response_snapshot={"manual_confirmation": passed},
        comparison=comparison_label(previous, passed),
    )


# Dispatch one test to the matching executor based on its type.
def execute_test(test: dict[str, Any], settings: Settings, previous: dict[str, Any] | None) -> RunOutcome:
    test_type = detect_test_type(test)
    if test_type == "http":
        return execute_http_test(test, settings, previous)
    if test_type == "bash":
        return execute_script_test(test, previous)
    if test_type == "manual":
        return execute_manual_test(test, previous)

    return RunOutcome(
        test=test,
        passed=False,
        http_status=None,
        duration_ms=0,
        error=f"unsupported test type: {test_type}",
        response_snapshot={},
        comparison=comparison_label(previous, False),
    )


# Run a batch of tests, parallelizing automated ones and serializing manual ones.
def run_tests(
    tests: list[dict[str, Any]],
    *,
    settings: Settings,
    previous_results: dict[str, dict[str, Any]],
    workers: int | None,
) -> tuple[str, list[RunOutcome]]:
    run_id = uuid4().hex
    if not tests:
        return run_id, []

    max_workers = max(1, workers or min(8, max(1, len(tests))))
    outcomes: list[RunOutcome] = []
    automated_tests = [test for test in tests if detect_test_type(test) != "manual"]
    manual_tests = [test for test in tests if detect_test_type(test) == "manual"]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(execute_test, test, settings, previous_results.get(test["id"])): test
            for test in automated_tests
        }

        for future in as_completed(future_map):
            outcomes.append(future.result())

    for test in manual_tests:
        outcomes.append(execute_test(test, settings, previous_results.get(test["id"])))

    outcomes.sort(key=lambda item: item.test["id"])
    return run_id, outcomes
