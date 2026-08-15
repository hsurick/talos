"""Score the recognizers on the labeled recordings: hits per expected gesture and anything that fired by mistake.
Each recording is also replayed mirrored (left hand; Swipe Left and Right swap), at 15 fps, and with extra
tracking jitter, to check the tuning isn't fragile.
Recordings: the hand-labeled ones below (if present) and every `talos collect` session in tests/data.

  python tools/eval.py [-v]
  python tools/eval.py --trace FILE         one line per clip: what was asked, what fired
  python tools/eval.py --trace FILE CLIP    the features and gesture states frame by frame for one clip
"""
import ast
import contextlib
import io
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from talos import state  # noqa: E402
from talos.__main__ import DATA, NEGATIVES, READY, SELECT, overview_only, process, simulate  # noqa: E402
from talos.bindings import Bindings  # noqa: E402
from talos.record import labels, read  # noqa: E402
from talos.recognizers.twist import _angle  # noqa: E402
from talos.vision import Frame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# (start, end, {gesture: expected count}) in recording time, labeled from the screen recordings frame by frame.
# None as a count = direction unknown, only check that nothing else fires there.
LABELS = {
    "swipeandpush": [(6, 12.4, {}),                      # Push attempts (arm strokes): no gesture any more
                     (12.4, 18.3, {"swipe_left": 8}),
                     (18.5, 22.5, {"swipe_right": 5}),   # approximate count
                     (25, 35.5, {"swipe_up": 11})],      # approximate; you said these were Swipe Ups
    "swipedemo": [(3.5, 12.3, {"swipe_left": 6}),
                  (12.8, 27, {"swipe_up": None})],  # flips, count unknown
    "demo1": [(0, 9, {}), (9, 20.5, {"twist_4": 10}), (20.5, 37, {})],
}
SWAP = {"swipe_left": "swipe_right", "swipe_right": "swipe_left"}
NEG = (*NEGATIVES, "fidget")  # "fidget" was a negative prompt in the first sessions (now dropped)
HARMLESS = {}  # path -> {(time, gesture)} of events that did nothing, filled by events()
# Recorded flows that no longer exist: Swipe Up opened Mission Control and Swipe Down closed it (now
# Swipe Up zooms, Burst/Unburst open and close). Their clips are left out of the scores.
OBSOLETE = ("swipe_up+",)


def recordings():
    """(name, path, windows, strict): the hand-labeled recordings that exist, then every collected session.
    strict = events outside the windows count as wrong. Not for sessions: between clips the user is getting
    ready, and a gesture finishing a bit late shouldn't count as both a miss and a mistake."""
    out = [(n, ROOT / f"{n}.jsonl.gz", w, True) for n, w in LABELS.items() if (ROOT / f"{n}.jsonl.gz").exists()]
    for p in sorted(DATA.glob("*.jsonl.gz")):
        windows = [(s, e, {} if g in NEG else dict(Counter(g.split("+")))) for s, e, g in labels(p)  # + = sequence
                   if not g.startswith(OBSOLETE)]
        if not windows:
            continue
        out.append((p.name.removesuffix(".jsonl.gz"), p, windows, False))
    return out


def mirrored_name(g):
    """What a gesture is called in the mirror: Swipe Left and Right swap, and a direction flips left/right."""
    base, _, angle = g.partition("@")
    return f"{base}@{(180 - int(angle)) % 360}" if angle else SWAP.get(g, g)


def mirrored(frames):
    for f in frames:
        hands = [{"side": "Left" if h["side"] == "Right" else "Right", "pts": [[1 - x, y, z] for x, y, z in h["pts"]]}
                 for h in f.hands]
        body = None if f.body is None else [[1 - x, y, z, v] for x, y, z, v in f.body]
        if body:  # left and right body points swap names too
            for a, b in ((1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16), (17, 18),
                         (19, 20), (21, 22), (23, 24), (25, 26), (27, 28), (29, 30), (31, 32)):
                body[a], body[b] = body[b], body[a]
        motion = (f.motion[0], None if f.motion[1] is None else 1 - f.motion[1])
        yield Frame(f.t, f.aspect, hands, body, f.idle, motion)


def half_rate(frames):
    """15 fps, as on a slow machine."""
    return (f for i, f in enumerate(frames) if i % 2 == 0)


def jittered(frames, sigma=0.004):
    """Heavier tracking noise than the camera gives today."""
    rnd = random.Random(1)
    for f in frames:
        hands = [{**h, "pts": [[c + rnd.gauss(0, sigma) for c in p] for p in h["pts"]]} for h in f.hands]
        yield Frame(f.t, f.aspect, hands, f.body, f.idle, f.motion)


VARIANTS = {"normal": lambda fr: fr, "mirrored = left hand": mirrored, "15 fps": half_rate, "jitter": jittered}


def bindings_for(path, run):
    """config.yaml's bindings, with the window picker the clips were recorded for (Flick or Point; one runs)."""
    b = Bindings(ROOT / "config.yaml", run=run)
    if any("flick" in g for *_, g in labels(path)):
        b.settings["select_with"] = "flick"
    elif any("point" in g for *_, g in labels(path)):
        b.settings["select_with"] = "point"
    return b


def overview_as_in_collect(path, then=None):
    """An on_frame for process() that sets the overview state as collect did: open for a whole single Point / Flick
    clip (from its "get ready"), closed at the start of every other clip and between clips; within a
    sequence the simulated actions open and close it. `then` is called after it, with the same arguments."""
    clips = [(s - READY, e, g) for s, e, g in labels(path)]
    current = [None]

    def on_frame(frame, f, found, log):
        clip = next((c for c in clips if c[0] <= f.t < c[1]), None)
        if clip is None or overview_only(clip[2]) or clip is not current[0]:
            state.overview_open = clip is not None and overview_only(clip[2])
        current[0] = clip
        return then(frame, f, found, log) if then else None
    return on_frame


def events(path, variant="normal"):
    """(time, gesture) per event. Window selection counts once, when it chooses, as "point@135": the direction it
    aimed at, rounded to the nearest of the 8 directions collect prompts. Ongoing gestures' other phases are left out.
    The actions are simulated as in collect, so the overview opens and closes as it would live; events whose actions
    did nothing (Unburst with nothing open) go in HARMLESS: they still count as hits, not as mistakes."""
    frames = VARIANTS[variant](read(path))
    did = {}  # (time text, gesture, phase) -> whether any of its actions had an effect
    harmless = HARMLESS.setdefault(path, set())  # (time, gesture) of events that did nothing

    def run(name, e, arg):
        key = (f"{e.t:7.2f}s".strip(), e.gesture, e.phase)
        did[key] = did.get(key, False) | simulate(name, e, arg)

    with contextlib.redirect_stdout(io.StringIO()):
        try:
            log = process(frames, bindings_for(path, run), overview_as_in_collect(path))
        finally:
            state.overview_open = False
    out, aim = [], {}
    for line in log:
        words = line.split()
        t, g, phase = float(words[0].rstrip("s")), words[1], words[2]
        if did.get((words[0], g, phase)) is False:
            harmless.add((t, g))
        data = ast.literal_eval(line[line.index("{"):line.index("}") + 1]) if "{" in line.split(" -> ")[0] else {}
        if g not in SELECT:
            if phase in ("once", "begin"):
                out.append((t, g))
        else:
            aim[g] = data.get("angle", aim.get(g))  # the end carries where Point aimed before the curl
            if phase == "end" and data.get("chosen") and aim[g] is not None:
                out.append((t, f"{g}@{round(aim[g] / 45) * 45 % 360}"))
    return out


def score(path, windows, strict=True, variant="normal"):
    mirror = variant.startswith("mirrored")
    evs = events(path, variant)
    harmless = HARMLESS.get(path, set())
    hits = misses = wrong = 0
    lines = []
    for start, end, want in windows:
        want = {mirrored_name(g) if mirror else g: n for g, n in want.items()}
        got = Counter(g for t, g in evs if start <= t < end)
        for g, n in want.items():
            if n is not None:
                hits += min(got[g], n)
                misses += max(n - got[g], 0)
        # Mistakes: events beyond what was asked for, not counting ones that did nothing.
        effective = Counter(g for t, g in evs if start <= t < end and (t, g) not in harmless)
        extra = {g: c - (want.get(g) or 0) for g, c in effective.items()
                 if g not in want or (want[g] is not None and c > want[g])}
        extra = {g: c for g, c in extra.items() if c > 0}
        wrong += sum(extra.values())
        lines.append(f"  {start:5.1f}-{end:5.1f}s  want {want or 'nothing'}  got {dict(got) or 'nothing'}"
                     + (f"  WRONG {extra}" if extra else ""))
    outside = [(t, g) for t, g in evs if not any(s <= t < e for s, e, _ in windows) and (t, g) not in harmless]
    wrong += len(outside) if strict else 0
    return hits, misses, wrong, lines + ([f"  outside labels: {outside}"] if outside else [])


def trace(path, clip=None):
    """No clip: one line per clip. With a clip: features and gesture states per frame, from READY before GO
    to 0.5s after the window (* = inside the window). Events print where they fire."""
    windows = labels(path)
    if clip is None:
        evs = events(path)
        for i, (s, e, g) in enumerate(windows, 1):
            got = [x for t, x in evs if s <= t < e]
            ok = got == ([] if g in NEG else g.split("+"))  # a sequence: its steps, in order, nothing else
            print(f"{i:3d}  {s:6.1f}s  {g:12s} got {', '.join(got) or 'nothing':24s} {'ok' if ok else 'WRONG'}")
        return
    start, end, gesture = windows[clip - 1]
    print(f"clip {clip}: {gesture}, window {start:.2f}-{end:.2f}s")

    def on_frame(frame, f, found, log):
        if f.t > end + 0.5:
            return False
        if f.t < start - READY:
            return
        cols = [f"{f.t:6.2f}{'*' if start <= f.t < end else ' '}"]
        for side, h in sorted(f.hands.items()):
            cols.append(f"{side[0]} {h.fingers_up}up thumb {'tucked' if h.thumb_tucked else 'out   '} "
                        f"{'front' if h.in_front else 'face '} {'raised' if h.raised else 'low   '} "
                        f"roll {h.roll:4.0f} tilt {h.tilt:4.0f} palm.x {h.palm[0]:5.2f}")
        for r in found:
            if r.state != "idle":
                h = f.hands.get(r.side)
                turn = f" turn {abs(_angle(h.roll, r.roll0)):.0f}" if hasattr(r, "roll0") and h else ""
                cols.append(f"{r.name}:{r.state}{turn}")
        print("  ".join(cols))

    try:
        process(read(path), bindings_for(path, lambda *a: None), overview_as_in_collect(path, on_frame))
    finally:
        state.overview_open = False


def main():
    if "--trace" in sys.argv:
        rest = sys.argv[sys.argv.index("--trace") + 1:]
        return trace(Path(rest[0]), int(rest[1]) if len(rest) > 1 else None)
    verbose = "-v" in sys.argv
    for variant in VARIANTS:
        total = Counter()
        for name, path, windows, strict in recordings():
            h, m, w, lines = score(path, windows, strict, variant)
            total.update(hits=h, misses=m, wrong=w)
            if verbose or w or m:
                print(f"  [{variant}] {name}: {h} hit, {m} missed, {w} wrong")
                print("\n".join(l for l in lines if verbose or "WRONG" in l or "outside" in l or "want {" in l))
        print(f"{variant:22s} {total['hits']} hit, {total['misses']} missed, {total['wrong']} wrong")


if __name__ == "__main__":
    main()
