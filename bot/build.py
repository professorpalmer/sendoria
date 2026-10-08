"""Build SendoriaBot.exe and SendoriaBot_Silent.exe with PyInstaller (run on Windows)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(name: str, windowed: bool) -> None:
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--onefile", "--noconfirm", "--clean",
        "--name", name, "--noconsole" if windowed else "--console",
        "--distpath", str(HERE / "dist"), "--workpath", str(HERE / "build"),
        "--specpath", str(HERE / "build"),
        str(HERE / "run_bot.py"),
    ], check=True, cwd=HERE)


if __name__ == "__main__":
    build("SendoriaBot", windowed=False)
    build("SendoriaBot_Silent", windowed=True)
    print(f"Built into {HERE / 'dist'}")
