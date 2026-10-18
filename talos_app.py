"""Entry point for Talos.app (built by setup.py)."""
from talos.__main__ import CONFIG, process
from talos.app import run

run(CONFIG, process)
