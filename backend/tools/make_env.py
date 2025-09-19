# tools/make_venv.py
import os, sys, subprocess, venv

VENV_DIR = os.path.join(os.path.dirname(__file__), "..", ".venv") if os.path.basename(os.getcwd()) == "tools" else ".venv"
venv.create(VENV_DIR, with_pip=True, clear=False)

pip_path = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin", "pip")
py_path  = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin", "python")

subprocess.check_call([pip_path, "install", "-U", "pip"])
req = "requirements.txt"
if os.path.exists(req):
    subprocess.check_call([pip_path, "install", "-r", req])

print("✅ Virtual env created at:", os.path.abspath(VENV_DIR))
print("→ Activate:")
if os.name == "nt":
    print(r"   .venv\Scripts\Activate.ps1   # PowerShell")
    print(r"   .venv\Scripts\activate.bat   # CMD")
else:
    print("   source .venv/bin/activate    # bash/zsh")
