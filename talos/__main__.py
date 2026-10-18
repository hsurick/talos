"""Talos entry point.

  python -m talos                   watch the camera and run bound actions
  python -m talos --debug           same, with the debug window (q or Esc to quit)
  python -m talos --record F.jsonl.gz   also save the tracked points to a file
  python -m talos --dry-run         print the actions instead of running them
  python -m talos replay F.jsonl.gz print the events a recording produces and the actions they'd run
  python -m talos action NAME [ARG] run one action now
  python -m talos app               the menu-bar app: camera on/off, event popup, misfire log
  python -m talos collect [GESTURE ...] [--count 10] [--slot 2] [--auto]
                                    guided session: do each prompted gesture; labeled clips go to tests/data
"""
import argparse
import random
import shutil
import signal
import time
from pathlib import Path

import cv2

from talos import ROOT, actions, features, recognizers, state
from talos.arbiter import Arbiter
from talos.bindings import Bindings
from talos.events import Event

# Your settings, outside the app so updates keep them; starts as a copy of the defaults (config.yaml in the source).
CONFIG = Path.home() / "Library" / "Application Support" / "Talos" / "config.yaml"
if not CONFIG.exists():
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "config.yaml", CONFIG)


def process(frames, bindings, on_frame=None):
    """The pipeline: frames -> features -> recognizers -> tiebreaker -> bound actions."""
    found = recognizers.build(bindings.settings)
    arbiter = Arbiter()
    log = []
    for n, frame in enumerate(frames):
        settings = bindings.settings
        if n % 30 == 0 and bindings.reload_if_changed() and bindings.settings != settings:
            # New recognizers drop gestures in progress: end the ongoing ones, so a held key is released.
            for gesture, side in arbiter.active:
                bindings.handle(Event(gesture, "end", frame.t, side))
            arbiter.active.clear()
            found = recognizers.build(bindings.settings)
        f = features.compute(frame)
        for e in arbiter.push([e for r in found for e in r.update(f)], f.t):
            line = f"{e} -> {', '.join(bindings.describe(e)) or 'nothing bound'}"
            print(line)
            log.append(line)
            bindings.handle(e)
        if on_frame and on_frame(frame, f, found, log) is False:
            break
    return log


def stop_on_ctrl_c():
    """Ctrl+C stops the loop after the current frame instead of raising inside a MediaPipe call: that left a model
    half-closed, and closing it again at exit crashed. A second Ctrl+C interrupts right away."""
    stop = []

    def handler(*_):
        stop.append(True)
        signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGINT, handler)
    return stop


def live(args):
    from talos import debug, vision
    from talos.actions import overview
    bindings = Bindings(CONFIG, run=dry if args.dry_run else actions.submit)
    recorder = None
    if args.record:
        from talos.record import Recorder
        recorder = Recorder(args.record)
    stats, stop = debug.Stats(), stop_on_ctrl_c()

    def on_frame(frame, f, found, log):
        if stop:
            return False
        if recorder:
            recorder.write(frame)
        text = stats.tick()
        overview.draw()
        if args.debug:
            return debug.show(frame, f, found, log, text)
        cv2.waitKey(1)  # lets the overview window draw

    frames = vision.frames()
    try:
        process(frames, bindings, on_frame)
    except KeyboardInterrupt:
        pass
    finally:
        frames.close()  # shut the camera and models down now, not during Python's exit
        cv2.destroyAllWindows()
        if recorder:
            recorder.close()
            print(f"saved {args.record}")


DATA = ROOT / "tests" / "data"
# What `collect` can prompt, with the one-line reminder shown under the name (full descriptions: SPEC.md).
# Left out: Walk Away (15s gone), Ear Hold (a long hold).
HINTS = {
    "twist_1": "1 finger up, thumb tucked: roll the hand and back",
    "twist_2": "2 fingers up, thumb tucked: roll the hand and back",
    "twist_3": "3 fingers up, thumb tucked: roll the hand and back",
    "twist_4": "4 fingers up, thumb tucked: roll the hand and back",
    "swipe_left": "hand edge-on, fingers up: lean fingers left",
    "swipe_right": "hand edge-on, fingers up: lean fingers right",
    "swipe_up": "palm flat, fingers sideways: flip fingers up",
    "point": "aim your hand that way, then pinch thumb and index",
    "flick": "1 finger: snap that way and back",
    "burst": "fist, palm to camera: open to 5 fingers",
    "unburst": "5 fingers, palm to camera: close to a fist",
    "hand_swipe": "sweep a hand across the camera",
    "lens_wipe": "slide a hand across the lens",
    "ear_tap": "point at your ear, then take the hand away",
    "ear_up": "point at your ear, then leave upward",
    "ear_down": "point at your ear a moment, then move down",
    "brush_off": "open palm toward you: flick the fingers away",
    "nothing": "no gesture: sit normally, hands anywhere",
}
NEGATIVES = ("nothing",)  # clips where no gesture may fire
# Window selection is prompted with a direction ("point@135" = up-left, angles as in the overview: 0 = right,
# 90 = up). These only work with the overview open, so it counts as open during their clips.
SELECT = ("point", "flick")
DIRECTIONS = {0: "RIGHT", 45: "UP-RIGHT", 90: "UP", 135: "UP-LEFT", 180: "LEFT", 225: "DOWN-LEFT", 270: "DOWN",
              315: "DOWN-RIGHT"}
READY = 1.0  # seconds showing the next prompt before GO
CHUNK = 3    # prompts per file (~9s), so an interruption or a crash loses at most one file
KEYS_WAITING = "SPACE = start    A = autoplay {}    X = redo this file    Q = quit"
KEYS_RUNNING = "SPACE = stop (throws this clip away)    A = autoplay {}    X = redo this file    Q = quit"


# `collect sequences`: open Mission Control, then pick a window, as in real use (steps joined by "+"; the pick gets a
# direction). Scored as a whole: each step must fire, and nothing else that has an effect. Plain open/close flows
# were dropped: the selection is what needs testing (the user, 2026-10-18). Swipe Up no longer opens it (it zooms),
# so recorded swipe_up+ flows are skipped when scoring (tools/eval.py, OBSOLETE).
SEQUENCES = ("burst+point",)
SEQ_SLOT = 5.0  # seconds to do a sequence


def _aimed(g, rnd):
    return f"{g}@{rnd.choice(list(DIRECTIONS))}" if g in SELECT else g


def prompts(gestures, count, rnd=random, negatives=0.0):
    """Random prompts from gestures; with negatives, that share of them is "nothing". Selection gestures get a
    random direction; "sequences" gives random flows from SEQUENCES."""
    if list(gestures) == ["sequences"]:
        return ["+".join(_aimed(g, rnd) for g in rnd.choice(SEQUENCES).split("+")) for _ in range(count)]
    out = [rnd.choice(NEGATIVES) if rnd.random() < negatives else rnd.choice(gestures) for _ in range(count)]
    return [_aimed(g, rnd) for g in out]


def step_name(step):
    """'point@135' -> 'POINT UP-LEFT, then PINCH': aiming and choosing are two moves, so both show."""
    g, _, angle = step.partition("@")
    name = g.replace("_", " ").upper() + (f" {DIRECTIONS[int(angle)]}" if angle else "")
    return name + {"point": ", then PINCH", "flick": " AND BACK"}.get(g, "")


def overview_only(prompt):
    """Single-gesture prompts that need the overview open (it's counted as open for their whole clip)."""
    return prompt.partition("@")[0] in SELECT


def simulate(name, event, arg):
    """A dry run that still opens and closes the overview the way the real actions do (state only, nothing on
    screen), so collect sessions and replays of sequences behave like live use. Returns False when the action would
    have done nothing, e.g. Unburst with nothing open: a harmless misfire."""
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


def collect(args):
    """Guided session: show a prompt, record what the user does, save labeled clips in tests/data, one file
    per CHUNK prompts. Manual: SPACE starts each clip. Autoplay (A, or --auto): the next clip starts by itself.
    A clip only gets its label once it's finished, so frames of a dropped clip stay unlabeled."""
    from talos import debug, vision
    from talos.record import Recorder
    seq = "sequences" in args.target  # optionally with point or flick: which one picks the window
    if unknown := set(args.target) - (set(SELECT) if seq else set(HINTS)) - {"sequences"}:
        raise SystemExit(f"unknown gesture {', '.join(unknown)}; pick from {', '.join(HINTS)}, or: sequences [flick]")
    # Named gestures: only those. A mixed session (no names) adds "nothing" 1 in 4 to catch false triggers.
    bindings, stats, stop = Bindings(CONFIG, run=simulate), debug.Stats(), stop_on_ctrl_c()
    # Flick and Point never run together (setting select_with): record the one prompted, else the one set.
    asked = {"point", "flick"} & set(args.target)
    if len(asked) > 1:
        raise SystemExit("collect point and flick separately: only one of them runs at a time")
    chosen = bindings.settings["select_with"] = asked.pop() if asked else bindings.settings.get("select_with", "point")
    other = {"point": "flick", "flick": "point"}[chosen]
    todo = prompts(["sequences"] if seq else args.target, args.count) if args.target else \
        prompts([g for g in HINTS if g not in (*NEGATIVES, other)], args.count, negatives=0.25)
    todo = [p.replace("point", chosen) for p in todo]  # sequences pick windows the way you set
    chunks = [todo[i:i + CHUNK] for i in range(0, len(todo), CHUNK)]
    DATA.mkdir(parents=True, exist_ok=True)
    base = DATA / f"{time.strftime('%Y%m%d-%H%M%S')}{'_' + '-'.join(args.target) if args.target else ''}"
    # chunk, clip in chunk, clip start (None = waiting for SPACE), autoplay, (message, until), finished files,
    # the clip the overview state was last reset for
    c, i, t0, auto, note, kept, clip = 0, 0, None, args.auto, None, [], None
    path = Path(f"{base}_01.jsonl.gz")
    rec = Recorder(path)

    def new_chunk():
        nonlocal rec, path
        path = Path(f"{base}_{c + 1:02d}.jsonl.gz")
        rec = Recorder(path)

    def on_frame(frame, f, found, log):
        nonlocal c, i, t0, auto, note, rec, clip
        if stop:
            return False
        if t0 is not None:  # a clip is running
            rec.write(frame)
            slot = SEQ_SLOT if "+" in chunks[c][i] else args.slot
            if frame.t - t0 >= READY + slot:
                rec.label(chunks[c][i], t0 + READY, t0 + READY + slot)
                i, t0 = i + 1, frame.t if auto else None
                if i == len(chunks[c]):
                    rec.close()
                    kept.append(path)
                    c, i, rec = c + 1, 0, None
                    if c == len(chunks):
                        return False
                    new_chunk()
        prompt, n = chunks[c][i], c * CHUNK + i + 1
        # The overview: closed between clips and at the start of each one (a sequence opens it itself, through the
        # simulated actions); counted as open for a whole single Point/Flick clip.
        if t0 is None or overview_only(prompt) or clip != (c, i, t0):
            state.overview_open = t0 is not None and overview_only(prompt)
            clip = (c, i, t0)
        name = ", then ".join(step_name(s) for s in prompt.split("+"))
        hint = f"in order, within {SEQ_SLOT:.0f}s" if "+" in prompt else HINTS[prompt.partition("@")[0]]
        if t0 is None:
            banner = [(f"next: {name}", debug.WHITE, 1.6 if "+" not in prompt else 1.1), (hint, debug.WHITE, 0.9),
                      ("press SPACE when ready", debug.GREEN, 0.9)]
        else:
            go = frame.t - t0 >= READY
            banner = [(f"{'GO' if go else 'get ready'}: {name}", debug.GREEN if go else debug.GREY,
                       1.6 if "+" not in prompt else 1.1), (hint, debug.WHITE, 0.9)]
        banner.append((f"prompt {n} of {len(todo)}   (file {c + 1} of {len(chunks)})   "
                       f"autoplay {'ON' if auto else 'off'}", debug.GREY, 0.7))
        if note and frame.t < note[1]:
            banner.append((note[0], debug.YELLOW, 0.8))
        keys = (KEYS_WAITING if t0 is None else KEYS_RUNNING).format("off" if auto else "on")
        key = debug.show(frame, f, found, log, stats.tick(), banner, keys)
        if key is False:
            return False
        if key == ord(" "):
            if t0 is None:
                t0 = frame.t
            else:  # stop: this prompt comes back, and autoplay stops so you can recover
                t0, auto, note = None, False, ("clip thrown away", frame.t + 3)
        elif key in (ord("a"), ord("A")):
            auto = not auto
            t0 = frame.t if auto and t0 is None else t0
        elif key in (ord("x"), ord("X")):
            rec.close()
            path.unlink()
            new_chunk()
            i, t0, note = 0, frame.t if auto else None, (f"file {c + 1} thrown away: redoing it", frame.t + 3)

    frames = vision.frames()
    try:
        process(frames, bindings, on_frame)
    except KeyboardInterrupt:
        pass
    finally:
        state.overview_open = False
        frames.close()
        cv2.destroyAllWindows()
        if rec:  # quit mid-file: keep its finished clips, or delete it if there are none
            rec.close()
            if i:
                kept.append(path)
            else:
                path.unlink()
        print(f"saved {len(kept)} files, {c * CHUNK + i if rec else len(todo)} clips:")
        for p in kept:
            print(f"  {p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p}")


def dry(name, event, arg):
    pass  # process() already printed what would run


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", choices=["replay", "action", "collect", "app"])
    p.add_argument("target", nargs="*")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--record")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--count", type=int, default=10, help="collect: number of prompts (10 x 3s = 30s)")
    p.add_argument("--slot", type=float, default=2.0, help="collect: seconds to do each prompt")
    p.add_argument("--auto", action="store_true", help="collect: start with autoplay on (A toggles it)")
    args = p.parse_args()
    if args.command == "collect":
        collect(args)
    elif args.command == "app":
        from talos.app import run
        run(CONFIG, process)
    elif args.command == "replay":
        from talos.record import read
        process(read(args.target[0]), Bindings(CONFIG, run=dry))
    elif args.command == "action":
        actions.load()
        Bindings(CONFIG, run=dry)  # loads settings
        name, arg = args.target[0], " ".join(args.target[1:]) or None
        fn, phases = actions.REGISTRY[name]
        if "end" in phases:  # ongoing action, e.g. hold_key: hold for 3 seconds, then release
            fn(Event(name, "begin", 0), arg)
            time.sleep(3)
            fn(Event(name, "end", 3), arg)
        else:
            fn(Event(name, "once", 0), arg)
    else:
        live(args)


if __name__ == "__main__":
    main()
