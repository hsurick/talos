"""`python -m talos collect`: a guided recording session. Each prompt is saved as a labeled clip in tests/data, which
tests and tools/eval.py replay."""
import random
import time
from pathlib import Path

import cv2

from talos import ROOT, recognizers, state
from talos.bindings import Bindings
from talos.pipeline import process, simulate, stop_on_ctrl_c, user_config

DATA = ROOT / "tests" / "data"
NEGATIVES = ("nothing",)  # clips where no gesture may fire
HINTS = {**recognizers.HINTS, "nothing": "no gesture: sit normally, hands anywhere"}
# Window selection is prompted with a direction ("point@135" = up-left; 0 = right, 90 = up, as in the overview).
# It only works with the overview open, so the overview counts as open during these clips.
SELECT = ("point", "flick")
DIRECTIONS = {0: "RIGHT", 45: "UP-RIGHT", 90: "UP", 135: "UP-LEFT", 180: "LEFT", 225: "DOWN-LEFT", 270: "DOWN",
              315: "DOWN-RIGHT"}
READY = 1.0  # seconds showing the next prompt before GO
CHUNK = 3    # prompts per file, so a crash loses at most one file
KEYS_WAITING = "SPACE = start    A = autoplay {}    X = redo this file    Q = quit"
KEYS_RUNNING = "SPACE = stop (throws this clip away)    A = autoplay {}    X = redo this file    Q = quit"
# `collect sequences`: open Mission Control, then pick a window, as in real use. Steps are joined by "+" and scored
# as a whole: each step must fire, and nothing else that has an effect.
SEQUENCES = ("burst+point",)
SEQ_SLOT = 5.0  # seconds to do a sequence


def _aimed(g, rnd):
    return f"{g}@{rnd.choice(list(DIRECTIONS))}" if g in SELECT else g


def prompts(gestures, count, rnd=random, negatives=0.0):
    """Random prompts from gestures, that share of them "nothing". Selection gestures get a random direction;
    ["sequences"] gives random flows from SEQUENCES."""
    if list(gestures) == ["sequences"]:
        return ["+".join(_aimed(g, rnd) for g in rnd.choice(SEQUENCES).split("+")) for _ in range(count)]
    out = [rnd.choice(NEGATIVES) if rnd.random() < negatives else rnd.choice(gestures) for _ in range(count)]
    return [_aimed(g, rnd) for g in out]


def step_name(step, choose="pinch"):
    """'point@135' -> 'POINT UP-LEFT, then PINCH': aiming and choosing are two moves, so both show."""
    g, _, angle = step.partition("@")
    name = g.replace("_", " ").upper() + (f" {DIRECTIONS[int(angle)]}" if angle else "")
    return name + {"point": ", then PINKY UP" if choose == "pinky" else ", then PINCH", "flick": " AND BACK"}.get(g, "")


def overview_only(prompt):
    """Single-gesture prompts that need the overview open for their whole clip."""
    return prompt.partition("@")[0] in SELECT


def collect(args):
    """Show a prompt, record what you do, save labeled clips, CHUNK prompts per file. Manual: SPACE starts each clip.
    Autoplay (A, or --auto): the next clip starts by itself. A clip is labeled only once it's finished, so frames of
    a dropped clip stay unlabeled."""
    from talos import debug, vision
    from talos.record import Recorder
    seq = "sequences" in args.target
    pinky = "pinky" in args.target  # Point chooses by raising the pinky (setting choose_with)
    gestures = [g for g in args.target if g != "pinky"]
    if unknown := set(gestures) - (set(SELECT) if seq else set(HINTS)) - {"sequences"}:
        raise SystemExit(f"unknown gesture {', '.join(unknown)}; pick from {', '.join(HINTS)}, "
                         f"or: sequences [flick | pinky]")
    bindings, stats, stop = Bindings(user_config(), run=simulate), debug.Stats(), stop_on_ctrl_c()
    # Point and Flick never run together: record the one prompted, else the one set.
    asked = {"point", "flick"} & set(gestures) | ({"point"} if pinky else set())
    if len(asked) > 1:
        raise SystemExit("collect point and flick separately: only one of them runs at a time")
    chosen = bindings.settings["select_with"] = asked.pop() if asked else bindings.settings.get("select_with", "point")
    choose = bindings.settings["choose_with"] = "pinky" if pinky else bindings.settings.get("choose_with", "pinch")
    other = {"point": "flick", "flick": "point"}[chosen]
    # Named gestures: only those. A mixed session adds "nothing" 1 in 4 to catch false triggers.
    todo = prompts(["sequences"] if seq else gestures, args.count) if gestures else \
        prompts([g for g in HINTS if g not in (*NEGATIVES, other)], args.count, negatives=0.25)
    todo = [p.replace("point", chosen) for p in todo]
    chunks = [todo[i:i + CHUNK] for i in range(0, len(todo), CHUNK)]
    DATA.mkdir(parents=True, exist_ok=True)
    base = DATA / f"{time.strftime('%Y%m%d-%H%M%S')}{'_' + '-'.join(args.target) if args.target else ''}"
    # c: file, i: clip in file, t0: clip start (None = waiting for SPACE), note: (message, shown until),
    # kept: finished files, clip: the clip the overview was last reset for
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
        # The overview is closed between clips and at the start of each one (a sequence opens it itself), and
        # counts as open for a whole single Point / Flick clip.
        if t0 is None or overview_only(prompt) or clip != (c, i, t0):
            state.overview_open = t0 is not None and overview_only(prompt)
            clip = (c, i, t0)
        name = ", then ".join(step_name(s, choose) for s in prompt.split("+"))
        hint = f"in order, within {SEQ_SLOT:.0f}s" if "+" in prompt else HINTS[prompt.partition("@")[0]]
        if prompt.startswith("point") and choose == "pinky":
            hint = "point that way, then raise your pinky (middle and ring curled)"
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
