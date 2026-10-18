"""Twist-N: N fingers up (Twist-4 also needs the thumb tucked), then a quick roll and back (recorded twists
turn ~150 degrees)."""
from talos.recognizers.base import Recognizer

ROLL_OUT = 35    # degrees away from the starting angle; 20 let tracking jitter on an edge-on hand fake a twist
ROLL_BACK = 15   # within this many degrees of the start counts as back (roll reads jitter ~±7°)
STEADY = 5       # rolling less than this keeps resetting the starting angle (slow drift isn't a twist)
QUICK = 0.6      # seconds allowed for each half of the roll; 0.4 missed most real twists
DRIFT = 1.0      # the hand may move at most this many hand sizes; more means a swipe, not a twist
UPRIGHT = 25     # ...and lean at most this many degrees while rolling (swipeandpush: leans read as Twist-4)
STILL_ROLL = 150  # a twist arms only while the roll changes less than this many degrees per second (5 a frame)
LEAN_FRAMES = 2 # ...for this many frames in a row
MID_SLACK = 1   # mid-roll, the finger count may be off by this many (the start pose must be exact)


def _angle(a, b):
    return (a - b + 180) % 360 - 180


class Twist(Recognizer):
    def __init__(self, n, side):
        self.n = n
        self.name = f"twist_{n}"
        super().__init__(side)

    def reset(self):
        super().reset()
        self.leaning = 0  # frames in a row the hand has leaned past UPRIGHT
        self.last_roll = None  # (time, roll) on the previous idle frame

    def update(self, f):
        h = self.hand(f)
        if self.state == "idle":
            # The thumb only matters for Twist-4: four fingers with the thumb out is an open palm (Brush Off,
            # Burst). For 1-3 it rejected real poses (thumb resting on the curled fingers, or hidden edge-on).
            # Holding still: arming mid-roll (after a reset) counted the way back as a twist (collected twist_2).
            # Not "palm to the camera": the twist_1 sessions start edge-on.
            still = (h is not None and self.last_roll is not None
                     and abs(_angle(h.roll, self.last_roll[1])) < STILL_ROLL * (f.t - self.last_roll[0]))
            self.last_roll = (f.t, h.roll) if h else None
            start = (h is not None and h.raised and h.in_front and h.fingers_up == self.n
                     and (h.thumb_tucked or self.n < 4)
                     and still
                     and not h.near_ear)  # fingers at the ear belong to the Ear gestures
            if self.pose_ready(start, f):
                self.state, self.roll0, self.t0, self.origin, self.tilt0 = "armed", h.roll, f.t, h.center, h.tilt
            return []
        # Mid-roll only the finger count must hold, give or take one: turning the hand hides the thumb (reset half
        # the twists in the twist1 recording), and edge-on a curled finger reads as up for a few frames, exactly
        # the frames the roll happens in (collected twist_3: 3 fingers read as 4 at the peak of the roll).
        # Only up: allowing one fewer let Twist-2 steal Twist-1's rolls after a brief 2-finger reading.
        ok = h is not None and self.n <= h.fingers_up <= self.n + MID_SLACK
        if self.pose_lost(ok):
            self.reset()
            return []
        if not ok:
            return []
        turned = abs(_angle(h.roll, self.roll0))
        # The hand leaning sideways is Swipe Left/Right, but only if it lasts: edge-on mid-roll, the lean reads
        # wildly off for single frames (-86 degrees in a collected twist_2).
        self.leaning = self.leaning + 1 if abs(h.tilt - self.tilt0) > UPRIGHT else 0
        if (abs(h.center[0] - self.origin[0]) + abs(h.center[1] - self.origin[1]) > DRIFT * h.size
                or self.leaning >= LEAN_FRAMES):
            self.reset()
        elif self.state == "armed":
            if turned < STEADY:
                self.roll0, self.t0, self.origin = h.roll, f.t, h.center
            elif turned >= ROLL_OUT:
                if f.t - self.t0 <= QUICK:
                    self.state, self.t0, self.way = "out", f.t, 1 if _angle(h.roll, self.roll0) > 0 else -1
                else:
                    self.roll0, self.t0 = h.roll, f.t
        elif self.state == "out":
            if turned <= ROLL_BACK:
                self.state = "idle"
                self.posed = 0
                return [self.event(f, score=4, direction=self.way)]
            if f.t - self.t0 > QUICK:
                self.state, self.roll0, self.t0 = "armed", h.roll, f.t
        return []
