import os
import sys
import subprocess
import platform
from pathlib import Path


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"
VENV_DIR = BASE_DIR / "venv"
REQUIREMENTS = APP_DIR / "requirements.txt"
MAIN = APP_DIR / "main.py"


# ------------------------------------------------------------
# Find Python inside the virtual environment
# ------------------------------------------------------------

if platform.system() == "Windows":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"


# ------------------------------------------------------------
# Create virtual environment if it doesn't exist
# ------------------------------------------------------------

if not VENV_PYTHON.exists():

    print("Virtual environment not found.")
    print("Creating virtual environment...")

    subprocess.check_call([
        sys.executable,
        "-m",
        "venv",
        str(VENV_DIR)
    ])

    print("Virtual environment created.")


# ------------------------------------------------------------
# Install/update requirements
# ------------------------------------------------------------

print()
print("Installing required packages...")

subprocess.check_call([
    str(VENV_PYTHON),
    "-m",
    "pip",
    "install",
    "-q",
    "-r",
    str(REQUIREMENTS)
])


# ------------------------------------------------------------
# Run main.py
# ------------------------------------------------------------

print()
print("=" * 60)
print("Starting UFC Fight Notifier...")
print("=" * 60)
print()

subprocess.call([
    str(VENV_PYTHON),
    str(MAIN)
])
