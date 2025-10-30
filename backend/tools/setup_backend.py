#!/usr/bin/env python3
"""
Provision and verify the backend runtime environment.

This script makes sure core tooling is available, the backend virtualenv
exists, and Python dependencies are installed. It reuses the existing
make_env.py helper to stay consistent with the repo's setup story.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Tuple


TOOLS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TOOLS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
VENV_DIR = BACKEND_DIR / ".venv"
MAKE_ENV = TOOLS_DIR / "make_env.py"


def find_missing(commands: Iterable[str]) -> Tuple[str, ...]:
    """Return commands that are not present in PATH."""
    missing = []
    for cmd in commands:
        if shutil.which(cmd) is None:
            missing.append(cmd)
    return tuple(missing)


def run_checked(cmd: Iterable[str], *, cwd: Path | None = None) -> None:
    """Run command and raise a helpful error when it fails."""
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:
        display = " ".join(cmd)
        raise SystemExit(f"Command failed ({exc.returncode}): {display}") from exc


def ensure_docker() -> None:
    """Make sure Docker CLI is available and the daemon responds."""
    missing = find_missing(("docker",))
    if missing:
        raise SystemExit(
            "Docker CLI not found. Install Docker Desktop or the Docker Engine first."
        )

    try:
        subprocess.run(
            ("docker", "info"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Docker is installed but the daemon is not responding. "
            "Start Docker Desktop or ensure the engine is running."
        ) from exc


def ensure_virtualenv(force: bool) -> None:
    """Create/refresh the backend virtualenv using the repo helper."""
    if not MAKE_ENV.exists():
        raise SystemExit(f"Missing helper script: {MAKE_ENV}")

    if force or not VENV_DIR.exists():
        print("Creating backend virtualenv via make_env.py")
        run_checked((sys.executable, str(MAKE_ENV)))
    else:
        print("Updating backend dependencies via make_env.py")
        run_checked((sys.executable, str(MAKE_ENV)))


def ensure_node_tooling() -> None:
    """Warn when Node tooling needed for frontend is absent."""
    missing = find_missing(("node", "npm"))
    if missing:
        print(
            "Node/npm not detected. Backend runs without it, but the frontend "
            "will need Node.js from https://nodejs.org/.",
            file=sys.stderr,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure backend dependencies (Docker, virtualenv, requirements) are ready."
    )
    parser.add_argument(
        "--force-venv",
        action="store_true",
        help="Recreate the virtualenv even if it already exists.",
    )
    return parser.parse_args()


def main() -> None:
    os.chdir(REPO_ROOT)
    args = parse_args()

    print("→ Checking Docker installation")
    ensure_docker()

    print("→ Ensuring backend virtualenv and requirements")
    ensure_virtualenv(force=args.force_venv)

    ensure_node_tooling()

    python_bin = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "python"
    print(f"Backend ready. Activate the venv with:\n   source {python_bin.parent}/activate")


if __name__ == "__main__":
    main()
