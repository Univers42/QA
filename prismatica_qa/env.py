from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .catalog import DOMAINS


# Load simple dotenv-style key/value pairs without overriding existing values.
def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    root: Path
    tests_dir: Path
    definition_dirs: tuple[Path, ...]
    mongo_uri: str | None
    test_env: str

    # Resolve the base URL environment variable for a given test domain.
    def base_url_for_domain(self, domain: str) -> str | None:
        env_name = DOMAINS[domain].base_url_env
        return os.getenv(env_name) if env_name else None

    # Pick the JSON definition root that belongs to a given suite.
    def definition_dir_for_suite(self, suite: str | None) -> Path:
        if suite == "trascendence_testing":
            return self.root / "trascendence_testing" / "definitions"
        return self.tests_dir


# Build runtime settings from the repository layout and local environment.
def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.example")

    return Settings(
        root=root,
        tests_dir=root / "test-definitions",
        definition_dirs=(
            root / "test-definitions",
            root / "trascendence_testing" / "definitions",
        ),
        mongo_uri=os.getenv("MONGO_URI"),
        test_env=os.getenv("TEST_ENV", "local"),
    )
