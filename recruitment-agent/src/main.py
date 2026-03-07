"""Entry point for platforms expecting main.py (e.g. Nasiko standalone).
Defaults to port 5000 for standalone deployment."""
import os
import sys
import runpy

if "--port" not in sys.argv:
    sys.argv.extend(["--port", "5000"])

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "__main__.py"),
    run_name="__main__",
)
