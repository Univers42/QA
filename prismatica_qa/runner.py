from __future__ import annotations

import base64
import json
import math
import subprocess
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


@dataclass(frozen=True)
class RunOutcome:
    test: dict[str, Any]
    passed: bool
    http_status: int | None
    duration_ms: int
    error: str | None
    response_snapshot: dict[str, Any]
    comparison: str


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


def resolve_url(test: dict[str, Any], settings: Settings) -> str:
    raw_url = str(test.get("url", "")).strip()
    if raw_url.startswith(("http://", "https://")):
        return raw_url

    base_url = settings.base_url_for_domain(test["domain"])
    if not base_url:
        raise ValueError(f"Domain '{test['domain']}' requires a full URL because it has no base URL configured.")

    return urllib.parse.urljoin(base_url.rstrip("/") + "/", raw_url.lstrip("/"))


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT token")

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
    return json.loads(decoded)


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

    return errors


def execute_test(test: dict[str, Any], settings: Settings, previous: dict[str, Any] | None) -> RunOutcome:
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
    timeout_seconds = max(1, int(test.get("timeout_ms", 5000)) // 1000)

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
            "body_preview": body_text[:1000],
        },
        comparison=comparison_label(previous, passed),
    )


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

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(execute_test, test, settings, previous_results.get(test["id"])): test
            for test in tests
        }

        for future in as_completed(future_map):
            outcomes.append(future.result())

    outcomes.sort(key=lambda item: item.test["id"])
    return run_id, outcomes
