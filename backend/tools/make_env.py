"""
Create or update the backend virtual environment and install requirements.
"""

from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = BACKEND_DIR / ".venv"
BIN_DIR = "Scripts" if os.name == "nt" else "bin"


def main() -> None:
    if not VENV_DIR.exists():
        builder = venv.EnvBuilder(with_pip=True, clear=False, symlinks=False)
        builder.create(VENV_DIR)
    else:
        print("  Existing virtualenv detected; skipping recreate.")

    pip_path = VENV_DIR / BIN_DIR / "pip"
    subprocess.check_call([str(pip_path), "install", "-U", "pip"])

    requirements = BACKEND_DIR / "requirements.txt"
    if requirements.exists():
        subprocess.check_call([str(pip_path), "install", "-r", str(requirements)])

    print(" Virtual env created at:", VENV_DIR)
    print("→ Activate:")
    if os.name == "nt":
        print(r"   .venv\Scripts\Activate.ps1   # PowerShell")
        print(r"   .venv\Scripts\activate.bat   # CMD")
    else:
        print("   source .venv/bin/activate    # bash/zsh")


if __name__ == "__main__":
    main()
