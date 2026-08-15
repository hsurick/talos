"""The pipeline: frames -> features -> recognizers -> tiebreaker -> bound actions. Shared by live use, the app,
replay, collect and tools/eval.py."""
import shutil
import signal
from pathlib import Path

from talos import ROOT, features, recognizers, state
from talos.arbiter import Arbiter
from talos.events import Event

CONFIG = Path.home() / "Library" / "Application Support" / "Talos" / "config.yaml"


def user_config():
    """Your settings live outside the app so updates keep them; the first run copies the defaults there."""
    if not CONFIG.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "config.yaml", CONFIG)
    return CONFIG


def process(frames, bindings, on_frame=None):
    """Runs every frame through the pipeline until the frames end or on_frame returns False."""
    found = recognizers.build(bindings.settings)
    arbiter = Arbiter()
    log, t = [], 0.0

    def end_active():  # so a held key is released
        for gesture, side in arbiter.active:
            bindings.handle(Event(gesture, "end", t, side))
        arbiter.active.clear()

    try:
        for n, frame in enumerate(frames):
            t, settings = frame.t, bindings.settings
            if n % 30 == 0 and bindings.reload_if_changed() and bindings.settings != settings:
                end_active()  # new recognizers drop gestures in progress
                found = recognizers.build(bindings.settings)
            f = features.compute(frame)
            for e in arbiter.push([e for r in found for e in r.update(f)], f.t):
                line = f"{e} -> {', '.join(bindings.describe(e)) or 'nothing bound'}"
                print(line)
                log.append(line)
                bindings.handle(e)
            if on_frame and on_frame(frame, f, found, log) is False:
                break
    finally:  # camera off, quit or Ctrl+C mid-gesture
        end_active()
    return log


def simulate(name, event, arg):
    """A dry run that still tracks whether Mission Control is open, so replays of Burst-then-Point work.
    Returns False when the action would have done nothing (Unburst with nothing open)."""
    if name == "open_overview":
        state.overview_open = not state.overview_open  # opening it again closes it
    elif name == "close_overview":
        if not state.overview_open:
            return False
        state.overview_open = False
    elif name == "select_window":
        if not state.overview_open:
            return False
        if event.phase == "end" and event.data.get("chosen"):
            state.overview_open = False
    return True


def stop_on_ctrl_c():
    """Ctrl+C stops the loop after the current frame: raised inside MediaPipe, it left a model half-closed and
    crashed on exit. A second Ctrl+C interrupts right away."""
    stop = []

    def handler(*_):
        stop.append(True)
        signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGINT, handler)
    return stop
