"""Shared pieces of the per-gesture state machines."""
import math

from talos.events import Event

START_FRAMES = 2   # a start pose must show for this many frames (~66ms); a check, not a hold
GRACE = 3          # frames a pose may drop out mid-gesture before the gesture resets
SETTLE = 0.05      # a hand moving less than this many hand sizes per frame counts as still
SETTLE_TIME = 0.3  # after firing, the hand must be still this long before the gesture can start again


class Recognizer:
    """One gesture's state machine for one hand (side) or for the whole frame (side None)."""
    name = ""

    def __init__(self, side=None):
        self.side = side
        self.reset()

    def reset(self):
        self.state = "idle"
        self.posed = 0
        self.lost = 0
        self.prev = None

    def hand(self, f):
        return f.hands.get(self.side)

    def event(self, f, phase="once", gesture=None, score=0, **data):
        return Event(gesture or self.name, phase, f.t, self.side, data, score, getattr(self, "began", f.t))

    def pose_ready(self, ok, f):
        """Count consecutive frames the start pose has shown; remember when it first appeared (tiebreaks)."""
        self.posed = self.posed + 1 if ok else 0
        if self.posed == 1:
            self.began = f.t
        return self.posed >= START_FRAMES

    def pose_lost(self, ok):
        """Mid-gesture: True once the pose has been gone longer than the grace period."""
        self.lost = 0 if ok else self.lost + 1
        return self.lost > GRACE

    def still(self, h):
        """True when the hand moved less than SETTLE sizes since the last frame (or is gone)."""
        if h is None:
            return True
        moved = self.prev is not None and math.dist(self.prev, h.center) > SETTLE * h.size
        self.prev = h.center
        return not moved

    def settle(self, f, h):
        """After firing: True once the hand has been still for SETTLE_TIME (or left), so the return motion is ignored."""
        if h is None:
            return True
        if not self.still(h):
            self.still_since = f.t
        return f.t - self.still_since >= SETTLE_TIME

    def fired(self, f, h):
        self.state, self.prev, self.still_since = "settle", h.center, f.t

    def update(self, f):
        raise NotImplementedError
