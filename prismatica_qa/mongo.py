from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MongoUnavailableError(RuntimeError):
    """Raised when MongoDB persistence cannot be used."""


class MongoStore:
    def __init__(self, mongo_uri: str | None) -> None:
        if not mongo_uri:
            raise MongoUnavailableError("MONGO_URI is not configured.")

        try:
            from pymongo import MongoClient, UpdateOne
            from pymongo.errors import ConfigurationError
        except ImportError as exc:
            raise MongoUnavailableError(
                "pymongo is not installed. Run `pip install -e .` or `pip install pymongo rich`."
            ) from exc

        self._UpdateOne = UpdateOne
        self._ConfigurationError = ConfigurationError
        self._client = MongoClient(mongo_uri)

        try:
            self._db = self._client.get_default_database()
        except ConfigurationError:
            self._db = self._client["test_hub"]

        self.tests = self._db["tests"]
        self.results = self._db["results"]
        self.suites = self._db["suites"]

    def close(self) -> None:
        self._client.close()

    def ensure_indexes(self) -> None:
        self.tests.create_index("id", unique=True)
        self.tests.create_index([("domain", 1), ("type", 1), ("priority", 1), ("status", 1)])
        self.results.create_index([("test_id", 1), ("environment", 1), ("executed_at", -1)])
        self.results.create_index("run_id")
        self.suites.create_index("name", unique=True)

    def upsert_tests(self, docs: Iterable[dict[str, Any]]) -> dict[str, int]:
        summary = {"inserted": 0, "updated": 0, "unchanged": 0}
        now = utc_now()

        for doc in docs:
            payload = {key: value for key, value in doc.items() if not key.startswith("_")}
            result = self.tests.update_one(
                {"id": payload["id"]},
                {
                    "$set": {**payload, "updated_at": now},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

            if result.upserted_id is not None:
                summary["inserted"] += 1
            elif result.modified_count > 0:
                summary["updated"] += 1
            else:
                summary["unchanged"] += 1

        return summary

    def fetch_tests(
        self,
        *,
        domain: str | None,
        test_type: str | None,
        priority: str | None,
        status: str | None,
        environment: str,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}

        if domain:
            query["domain"] = domain
        if test_type:
            query["type"] = test_type
        if priority:
            query["priority"] = priority
        if status and status != "all":
            query["status"] = status

        query["$or"] = [
            {"environment": {"$exists": False}},
            {"environment": {"$size": 0}},
            {"environment": environment},
        ]

        return list(self.tests.find(query).sort("id", 1))

    def latest_results_map(self, test_ids: list[str], environment: str) -> dict[str, dict[str, Any]]:
        if not test_ids:
            return {}

        pipeline = [
            {"$match": {"test_id": {"$in": test_ids}, "environment": environment}},
            {"$sort": {"test_id": 1, "executed_at": -1}},
            {"$group": {"_id": "$test_id", "doc": {"$first": "$$ROOT"}}},
        ]

        rows = self.results.aggregate(pipeline)
        return {row["_id"]: row["doc"] for row in rows}

    def store_results(
        self,
        outcomes: Iterable[dict[str, Any]],
        *,
        run_id: str,
        environment: str,
        run_by: str,
        git_sha: str | None,
    ) -> None:
        documents = []
        updates = []
        executed_at = utc_now()

        for outcome in outcomes:
            test = outcome["test"]
            document = {
                "run_id": run_id,
                "test_id": test["id"],
                "run_by": run_by,
                "environment": environment,
                "executed_at": executed_at,
                "passed": outcome["passed"],
                "duration_ms": outcome["duration_ms"],
                "http_status": outcome["http_status"],
                "response_snapshot": outcome["response_snapshot"],
                "error": outcome["error"],
                "comparison": outcome["comparison"],
                "git_sha": git_sha,
                "runner_version": "python-0.1.0",
            }
            documents.append(document)
            updates.append(
                self._UpdateOne(
                    {"id": test["id"]},
                    {
                        "$set": {
                            "last_run": {
                                "run_id": run_id,
                                "executed_at": executed_at,
                                "passed": outcome["passed"],
                                "duration_ms": outcome["duration_ms"],
                            }
                        }
                    },
                )
            )

        if documents:
            self.results.insert_many(documents)
            self.tests.bulk_write(updates, ordered=False)

