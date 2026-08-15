"""Whole-frame gestures with no start pose: Walk Away, and Hand Swipe / Lens Wipe from whole-image motion.
Sweeps are too fast (blur) or too close for hand tracking, and a hand at the lens isn't dark in a lit room."""
from talos.recognizers.base import Recognizer

MOVING = 0.12     # at least this fraction of the image changing between frames = something is sweeping
                  # (wrist swipes change ~0.07)
LENS = 0.5        # a sweep this big at its peak is a hand at the lens (Lens Wipe); smaller is a Hand Swipe
SWEEP = 0.35      # the moving area's center travels this fraction of the image width...
SWEEP_TIME = 0.6  # ...within this many seconds
GAP = 2           # frames the motion may drop out mid-sweep
QUIET = 5         # still frames needed after a sweep before the next one
# shortcut: anything big crossing the frame counts, e.g. a person walking behind you.


class WalkAway(Recognizer):
    """No person in frame and no keyboard or mouse input for `seconds`. Fires once per absence."""
    name = "walk_away"

    def __init__(self, seconds=15):
        self.seconds = seconds
        super().__init__()

    def update(self, f):
        if f.body_present:
            self.state = "idle"  # back in frame: the timer resets
            return []
        if self.state == "fired":
            return []
        if self.state == "idle":
            self.state, self.gone_since = "gone", f.t
        if f.t - self.gone_since >= self.seconds and f.idle >= self.seconds:
            self.state = "fired"
            return [self.event(f, score=1)]
        return []


class MotionSweep(Recognizer):
    """A big moving area crosses the image: Lens Wipe if it covered most of the image, else Hand Swipe."""
    name = "hand_swipe"

    def reset(self):
        super().reset()
        self.gap = self.quiet = 0

    def update(self, f):
        frac, x = f.motion
        moving = frac >= MOVING and x is not None
        if self.state == "fired":
            self.quiet = 0 if moving else self.quiet + 1
            if self.quiet >= QUIET:
                self.reset()
            return []
        if not moving:
            self.gap += 1
            if self.gap > GAP:
                self.reset()
            return []
        self.gap = 0
        if self.state == "idle" or f.t - self.t0 > SWEEP_TIME:
            self.state, self.x0, self.t0, self.peak = "moving", x, f.t, frac
            return []
        self.peak = max(self.peak, frac)
        if abs(x - self.x0) >= SWEEP:
            self.state, self.quiet = "fired", 0
            return [self.event(f, gesture="lens_wipe" if self.peak >= LENS else "hand_swipe", score=3)]
        return []
