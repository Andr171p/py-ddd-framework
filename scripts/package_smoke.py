"""Install the built wheel in a clean environment and import the public package."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PROBE = """
import importlib.resources as resources

import ddf.application
import ddf.domain
import ddf.ratelimit

for package, name in (
    ("ddf.ratelimit.redis", "scripts/token_bucket.lua"),
    ("ddf.infra.limits.concurrency.redis", "scripts/acquire.lua"),
):
    path = resources.files(package).joinpath(*name.split("/"))
    if not path.is_file():
        raise SystemExit(f"missing package data: {package}/{name}")

print("package smoke ok")
"""


def main() -> None:
    wheels = sorted(DIST.glob("*.whl"), key=lambda path: path.stat().st_mtime)
    if not wheels:
        raise SystemExit(f"no wheel found in {DIST}; run uv build first")

    wheel = wheels[-1]
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        subprocess.run(["uv", "venv", "--python", "3.14", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(["uv", "pip", "install", "--python", str(python), str(wheel)], check=True)
        completed = subprocess.run([str(python), "-c", PROBE], cwd=tmp, check=False)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)


if __name__ == "__main__":
    sys.exit(main())
