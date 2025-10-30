#!/usr/bin/env python3
"""
Stop all processes and services started by run_backend.py.
"""

from __future__ import annotations

from run_backend import (
    CONTAINERS,
    clear_state,
    load_state,
    stop_containers,
    stop_processes,
)


def main() -> None:
    state = load_state()
    if not state:
        print("No runner state found; nothing to stop.")
        return

    print("→ Stopping backend processes")
    stop_processes(state)

    print("→ Stopping backend services")
    stop_containers(CONTAINERS.values())

    clear_state()
    print("✅ Backend stopped.")


if __name__ == "__main__":
    main()
