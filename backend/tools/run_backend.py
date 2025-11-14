#!/usr/bin/env python3
"""
Launch the Savery backend stack (API + Celery + supporting services).

This script ensures supporting Docker services are running, starts the FastAPI
app with uvicorn and the Celery worker, and records state so a subsequent run
can clean up stale processes. When it starts it automatically stops anything
left over from a previous invocation to avoid port conflicts.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

TOOLS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TOOLS_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
STATE_FILE = BACKEND_DIR / ".backend_runner_state.json"
RUN_LABEL = "backend-runner"

CONTAINERS = {
    "postgres": "savery-postgres",
    "rabbit": "savery-rabbit",
    "dragonfly": "savery-dragonfly",
}

POSTGRES_IMAGE = "savery/postgres-postgis-pgvector:local"
POSTGRES_DOCKERFILE = REPO_ROOT / "infra" / "docker" / "postgres-pgvector.Dockerfile"
POSTGRES_CONTEXT = REPO_ROOT / "infra" / "docker"


class RunnerError(RuntimeError):
    """Raised for critical runner errors."""


def load_state() -> Dict[str, object]:
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return {}
    return {}


def write_state(state: Dict[str, object]) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def kill_pid(pid: int, name: str) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        raise RunnerError(f"Unable to terminate {name} (pid={pid}): {exc}") from exc

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.5)

    # Final attempt with SIGKILL
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError as exc:
        raise RunnerError(f"Failed to kill {name} (pid={pid}): {exc}") from exc


def stop_processes(state: Dict[str, object]) -> None:
    pids = state.get("pids")
    if not isinstance(pids, dict):
        return
    for name, pid in pids.items():
        if isinstance(pid, int):
            print(f"→ Stopping {name} (pid {pid})")
            try:
                kill_pid(pid, name)
            except RunnerError as exc:
                print(f"  {exc}", file=sys.stderr)


def stop_containers(containers: Iterable[str]) -> None:
    for container in containers:
        subprocess.run(("docker", "stop", container), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_previous_invocation() -> None:
    state = load_state()
    if not state:
        return

    print("→ Cleaning up leftover processes/containers from previous run")
    stop_processes(state)

    containers = state.get("containers")
    if isinstance(containers, list):
        stop_containers([c for c in containers if isinstance(c, str)])

    clear_state()


def run_checked(cmd: Iterable[str], *, cwd: Optional[Path] = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def docker_inspect(name: str) -> bool:
    result = subprocess.run(
        ("docker", "inspect", name),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def docker_running(name: str) -> bool:
    result = subprocess.run(
        ("docker", "inspect", "-f", "{{.State.Running}}", name),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def ensure_postgres() -> None:
    if not docker_inspect(CONTAINERS["postgres"]):
        if not POSTGRES_DOCKERFILE.exists():
            raise RunnerError(f"Missing Dockerfile at {POSTGRES_DOCKERFILE}")
        print("→ Building local postgres image (first run only)")
        run_checked(
            (
                "docker",
                "build",
                "-t",
                POSTGRES_IMAGE,
                "-f",
                str(POSTGRES_DOCKERFILE),
                str(POSTGRES_CONTEXT),
            )
        )
        run_checked(
            (
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINERS["postgres"],
                "-p",
                "5432:5432",
                "-e",
                "POSTGRES_DB=savery",
                "-e",
                "POSTGRES_USER=postgres",
                "-e",
                "POSTGRES_PASSWORD=postgres",
                POSTGRES_IMAGE,
            )
        )
    elif not docker_running(CONTAINERS["postgres"]):
        run_checked(("docker", "start", CONTAINERS["postgres"]))


def ensure_rabbit() -> None:
    if not docker_inspect(CONTAINERS["rabbit"]):
        run_checked(
            (
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINERS["rabbit"],
                "-p",
                "5672:5672",
                "-p",
                "15672:15672",
                "rabbitmq:3-management",
            )
        )
    elif not docker_running(CONTAINERS["rabbit"]):
        run_checked(("docker", "start", CONTAINERS["rabbit"]))


def ensure_dragonfly() -> None:
    if not docker_inspect(CONTAINERS["dragonfly"]):
        run_checked(
            (
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINERS["dragonfly"],
                "-p",
                "6379:6379",
                "--ulimit",
                "memlock=-1",
                "docker.dragonflydb.io/dragonflydb/dragonfly",
                "--proactor_threads=2",
            )
        )
    elif not docker_running(CONTAINERS["dragonfly"]):
        run_checked(("docker", "start", CONTAINERS["dragonfly"]))


def load_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def get_python_bin() -> Path:
    venv = BACKEND_DIR / ".venv"
    if os.name == "nt":
        candidate = venv / "Scripts" / "python.exe"
    else:
        candidate = venv / "bin" / "python"
    if not candidate.exists():
        raise RunnerError("Backend virtualenv not found. Run setup_backend.py first.")
    return candidate


def start_processes(env: Dict[str, str]) -> Dict[str, subprocess.Popen]:
    python_exec = get_python_bin()
    processes: Dict[str, subprocess.Popen] = {}

    uvicorn_cmd = [
        str(python_exec),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    print("→ Starting uvicorn (API)")
    processes["uvicorn"] = subprocess.Popen(
        uvicorn_cmd,
        cwd=REPO_ROOT,
        env=env,
    )

    celery_cmd = [
        str(python_exec),
        "-m",
        "celery",
        "-A",
        "backend.workers.celery_app:celery_app",
        "worker",
        "-l",
        "info",
        "--pool",
        "solo",
    ]
    print("→ Starting Celery worker")
    processes["celery"] = subprocess.Popen(
        celery_cmd,
        cwd=REPO_ROOT,
        env=env,
    )

    return processes


def ensure_services() -> None:
    print("→ Ensuring Docker services are running")
    ensure_postgres()
    ensure_rabbit()
    ensure_dragonfly()


def build_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env_file = BACKEND_DIR / ".env"
    env.update(load_env_file(env_file))
    return env


def wait_for_processes(processes: Dict[str, subprocess.Popen]) -> int:
    names = list(processes.keys())
    while True:
        for name in names:
            proc = processes[name]
            code = proc.poll()
            if code is not None:
                print(f"  {name} exited with code {code}")
                return code
        time.sleep(0.5)


def shutdown(processes: Dict[str, subprocess.Popen]) -> None:
    for name, proc in processes.items():
        if proc.poll() is None:
            print(f"→ Terminating {name}")
            proc.terminate()
    deadline = time.time() + 10
    while time.time() < deadline:
        if all(proc.poll() is not None for proc in processes.values()):
            return
        time.sleep(0.5)
    for name, proc in processes.items():
        if proc.poll() is None:
            print(f"→ Killing {name}")
            proc.kill()


def main() -> None:
    stop_previous_invocation()

    env = build_env()

    ensure_services()

    processes = start_processes(env)
    write_state(
        {
            "pids": {name: proc.pid for name, proc in processes.items()},
            "containers": list(CONTAINERS.values()),
            "label": RUN_LABEL,
            "timestamp": time.time(),
        }
    )

    exit_code = 0

    def handle_signal(signum, frame):  # type: ignore[unused-argument]
        nonlocal exit_code
        print(f"\n→ Received signal {signum}, shutting down...")
        exit_code = 0
        shutdown(processes)
        stop_containers(CONTAINERS.values())
        clear_state()
        sys.exit(exit_code)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        exit_code = wait_for_processes(processes)
    except KeyboardInterrupt:
        exit_code = 0
    finally:
        shutdown(processes)
        stop_containers(CONTAINERS.values())
        clear_state()
    sys.exit(exit_code)


if __name__ == "__main__":
    if shutil.which("docker") is None:
        raise SystemExit("Docker CLI not found. Run setup_backend.py first.")

    main()
