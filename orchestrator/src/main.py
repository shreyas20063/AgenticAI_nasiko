"""Entry point for platforms expecting main.py (e.g. Nasiko standalone)."""
import os
import runpy

runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "__main__.py"),
    run_name="__main__",
)
