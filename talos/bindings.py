"""Reads config.yaml and runs the actions bound to each gesture. Reloads the config on save."""
from pathlib import Path

import yaml

from talos import actions


def parse(spec):
    """'lock_screen' -> ('lock_screen', None); {'focus_app': 'Claude'} -> ('focus_app', 'Claude')."""
    if isinstance(spec, str):
        return spec, None
    if isinstance(spec, dict) and len(spec) == 1:
        return next(iter(spec.items()))
    raise ValueError(f"bad action entry: {spec!r}")


def specs(entry):
    """A gesture's actions as a list; one action may be written on its own (`walk_away: lock_screen`)."""
    return [entry] if isinstance(entry, (str, dict)) else entry or []


class Bindings:
    def __init__(self, path, run=actions.submit):
        self.path, self.run = Path(path), run
        actions.load()
        self.load()

    def load(self):
        self.mtime = self.path.stat().st_mtime
        data = yaml.safe_load(self.path.read_text()) or {}
        table = {}
        for gesture, entry in (data.get("bindings") or {}).items():
            table[gesture] = [parse(s) for s in specs(entry)]
            for name, _ in table[gesture]:
                if name not in actions.REGISTRY:
                    raise ValueError(f"{gesture}: unknown action {name!r}")
        self.table, self.settings = table, data.get("settings") or {}

    def reload_if_changed(self):
        """Returns True after a successful reload. A broken file keeps the last good config running."""
        try:
            if self.path.stat().st_mtime == self.mtime:
                return False
            self.mtime = self.path.stat().st_mtime  # a broken file isn't retried until the next save
            self.load()
            print("config reloaded")
            return True
        except Exception as e:  # also a deleted file
            print(f"config not reloaded, keeping the previous one: {e}")
            return False

    def handle(self, event):
        for name, arg in self.table.get(event.gesture, []):
            self.run(name, event, arg)

    def describe(self, event):
        return [name if arg is None else f"{name}: {arg}" for name, arg in self.table.get(event.gesture, [])]
