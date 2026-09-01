from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    ".gitignore",
    "CONTRIBUTING.md",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "docs/ARCHITECTURE.md",
    "docs/adr",
    "pyproject.toml",
    "src/howedo",
    "tests",
)

FORBIDDEN_DIRECTORY_NAMES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

FORBIDDEN_FILE_NAMES = {
    ".DS_Store",
}


def tracked_paths() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(path for path in result.stdout.split("\0") if path)


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            errors.append(f"missing required path: {relative}")

    for relative in tracked_paths():
        path = Path(relative)
        if path.name in FORBIDDEN_FILE_NAMES:
            errors.append(f"tracked generated/local file: {relative}")
        if path.suffix == ".pyc":
            errors.append(f"tracked bytecode file: {relative}")
        if any(part in FORBIDDEN_DIRECTORY_NAMES for part in path.parts):
            errors.append(f"tracked generated/local directory content: {relative}")

    if errors:
        print("repository hygiene: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"repository hygiene: PASS ({len(tracked_paths())} tracked paths inspected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
