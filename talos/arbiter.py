"""Tiebreaker: when several gestures match the same motion, the one with the most points fires.
On a near-tie, the gesture whose start pose appeared clearly earlier wins (a 150-degree Twist-4 passes through
Brush Off's start pose halfway, so Brush Off starts late); otherwise nothing fires."""
from dataclasses import replace

WINDOW = 0.1  # seconds to collect competing matches; they don't finish on the same frame
MARGIN = 1    # the winner must lead the runner-up by this many points...
LEAD = 0.2    # ...or, on a near-tie, have started this many seconds before every close rival


def _began(e):
    return e.began if e.began is not None else e.t


class Arbiter:
    def __init__(self, window=WINDOW, margin=MARGIN):
        self.window, self.margin = window, margin
        self.pending = []     # once/begin events waiting for the window to close
        self.ended = {}       # (gesture, side) -> the end that arrived while its begin was still pending
        self.active = set()   # (gesture, side) of ongoing gestures that won

    def push(self, events, t):
        out = []
        for e in events:
            key = (e.gesture, e.side)
            waiting = any((p.gesture, p.side) == key for p in self.pending)
            if e.phase in ("once", "begin"):
                self.pending.append(e)
            elif key in self.active:
                out.append(e)
                if e.phase == "end":
                    self.active.discard(key)
            elif e.phase == "end" and waiting:
                self.ended[key] = e  # released before the decision; still send it (with its data) so no key sticks
            elif e.phase == "update" and not waiting:
                # Its begin lost a tiebreak, but the gesture goes on (Point keeps aiming): let it compete again.
                self.pending.append(replace(e, phase="begin"))
        if self.pending and t - self.pending[0].t >= self.window:
            out += self._decide()
        return out

    def _decide(self):
        best, *rest = sorted(self.pending, key=lambda e: e.score, reverse=True)
        close = [best] + [e for e in rest if e.gesture != best.gesture and best.score - e.score < self.margin]
        first = min(close, key=_began)
        # With no close rival, close is just [best] and it wins.
        best = first if all(_began(first) + LEAD <= _began(e) for e in close if e is not first) else None
        out = []
        if best:
            key = (best.gesture, best.side)
            out.append(best)
            if best.phase == "begin":
                if key in self.ended:
                    out.append(self.ended[key])
                else:
                    self.active.add(key)
        self.pending.clear()
        self.ended.clear()
        return out
