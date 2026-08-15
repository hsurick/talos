"""Actions registered by name. Bindings run them on a worker thread so a slow action never stalls the camera."""
import importlib
import queue
import threading
import traceback

REGISTRY = {}  # name -> (function, phases it runs on)
MODULES = ("talos.actions.system", "talos.actions.media", "talos.actions.windows", "talos.actions.overview")


def action(name, phases=("once", "begin")):
    """Register fn(event, arg). Most actions run when a gesture fires; ongoing ones can ask for every phase."""
    def register(fn):
        REGISTRY[name] = (fn, phases)
        return fn
    return register


def load():
    for m in MODULES:
        importlib.import_module(m)


def call(name, event, arg=None):
    fn, phases = REGISTRY[name]
    if event.phase in phases:
        fn(event, arg)


_jobs = queue.Queue()


def _worker():
    while True:
        name, event, arg = _jobs.get()
        try:
            call(name, event, arg)
        except Exception:
            print(f"action {name} failed:\n{traceback.format_exc()}")


threading.Thread(target=_worker, daemon=True).start()


def submit(name, event, arg=None):
    _jobs.put((name, event, arg))  # one worker keeps order: a key's down always runs before its up
