"""Swipes done with the wrist, the arm staying still (wrist position barely moves). Each has its own start pose:
Swipe Left / Right: hand EDGE-ON (palm sideways), fingers up, then it leans; direction is where the fingertips go.
Swipe Up: hand FLAT to the camera; it flips from flat (fingers sideways or pointing at the screen) to upright
(fingers up). No Swipe Down (dropped): every Swipe Up's prep looks like one, and it collided with
picking a window downward.
swipedemo recording: leans had |palm x| 0.65-0.90 (edge-on), flips 0.13-0.15 (flat), which keeps them apart."""
from talos import state
from talos.recognizers.base import GRACE, Recognizer

EDGE_ON = 0.6   # |palm x| at least this = hand seen edge-on (Swipe Left/Right)
# Thresholds below sit mid-way in the ranges that scored the same on all recordings (tools/eval.py):
FLAT = 0.3      # |palm x| under this mid-lean = the hand turned flat: a flip, so the lean is cancelled (0.25-0.4)
FLAT_POSE = 0.45  # |palm x| under this = hand facing the camera or the floor, Swipe Up (0.35-0.5)
UPRIGHT = 35    # fingers within this many degrees of straight up = upright
LEAN = 30       # leaning this far from the start is a sideways swipe (swipedemo leans: 33-56 degrees)
LYING = 60      # tilted past this (fingers sideways or pointing down) = the flat end of a flip
QUICK = 0.4     # seconds for the lean or the flip
STAY = 1.0      # the wrist may travel at most this many hand sizes; more means the arm moved
DWELL = 0.4     # Swipe Up: the most time the hand must stay upright after the flip before it counts.
                # In a run it's really "as long as it stayed flat" (~0.3s); the cap matters when
                # starting from a long rest (recordings: 0.3-0.6 all work).
HOME_TIME = 1.5 # Swipe Left/Right: for this long after a swipe, the other direction is measured from its start
REST_LEAN = 65   # Swipe Left/Right may start from a hand resting at up to this lean (collected rests: up to ~55)
STILL_TILT = 150  # ...holding still: the lean changing less than this many degrees per second (5 a frame at 30 fps)


def _moved(a, b, size):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 / size


class SwipeSideways(Recognizer):
    name = "swipe_sideways"

    def reset(self):
        super().reset()
        self.last_tilt = None  # (time, lean) on the previous idle frame

    def update(self, f):
        h = self.hand(f)
        if self.state == "idle":
            # Arms at whatever lean the hand rests at, as long as it's holding still: collected swipes start from
            # a rest already leaning ~40 degrees and flick ~45 degrees from there and back. Requiring upright missed
            # most of them, and armed mid-flick instead, counting the way back as the other direction. Leaning
            # back after a swipe is handled by `home` below.
            still = (self.last_tilt is not None and h is not None
                     and abs(h.tilt - self.last_tilt[1]) < STILL_TILT * (f.t - self.last_tilt[0]))
            self.last_tilt = (f.t, h.tilt) if h else None
            if still:
                self.rest = h.tilt
            start = (h is not None and h.raised and h.in_front and h.fingers_up == 4 and abs(h.tilt) < REST_LEAN
                     and abs(h.palm[0]) >= EDGE_ON and still)
            if self.pose_ready(start, f):
                self.state, self.recent, self.flat = "armed", [(f.t, h.tilt, h.wrist)], 0
            return []
        # Mid-swipe the hand must stay in front of the face with most fingers up (an edge-on hand hides one or two
        # from the camera). Collected "nothing" clips fired swipes on hands at the hair or face, fingers curling.
        ok = h is not None and h.in_front and h.fingers_up >= 3
        if self.pose_lost(ok):
            self.reset()
            return []
        if not ok:
            return []
        self.flat = self.flat + 1 if abs(h.palm[0]) < FLAT else 0
        if self.flat > GRACE:
            self.reset()  # the hand turned flat to the camera: a flip (Swipe Up/Down), not a lean
            return []
        # Leans start gradually, so measure from the most upright moment of the last QUICK seconds.
        self.recent = [r for r in self.recent if f.t - r[0] <= QUICK] + [(f.t, h.tilt, h.wrist)]
        if len(self.recent) > 1 and abs(h.tilt - self.recent[-2][1]) < STILL_TILT * (f.t - self.recent[-2][0]):
            self.rest = h.tilt  # where the hand last held still: where a swipe really starts
        most_right, most_left = max(self.recent, key=lambda r: r[1]), min(self.recent, key=lambda r: r[1])
        if most_right[1] - h.tilt >= h.tilt - most_left[1]:
            way, ref, lean = "swipe_left", most_right, most_right[1] - h.tilt
        else:
            way, ref, lean = "swipe_right", most_left, h.tilt - most_left[1]
        home = getattr(self, "home", None)  # (direction, tilt it started from, time) of the last swipe
        if home and f.t - home[2] > HOME_TIME:
            home = self.home = None
        if home and way != home[0]:
            # After a swipe the other direction counts from where that swipe started, so leaning back home
            # isn't a swipe the other way (at 15 fps the lean back took longer than any fixed time window).
            lean = home[1] - h.tilt if way == "swipe_left" else h.tilt - home[1]
        if lean >= LEAN and self.flat == 0:
            if _moved(h.wrist, ref[2], h.size) > STAY:
                self.recent = self.recent[-1:]  # the arm moved: not a wrist swipe
                return []
            self.reset()
            # From the rest, not the most extreme lean of the last QUICK seconds: back to back, that was the far end
            # of the previous swipe, so the next swipe the other way fell short and its way back fired instead.
            self.home = (way, getattr(self, "rest", ref[1]), f.t)  # kept across reset()
            # 5 points: edge-on start, upright, lean, wrist still, four fingers. A lean also nudges the roll,
            # so Twist-4 (4 points) can complete on the same motion (swipedemo 7.3s); the swipe should win.
            return [self.event(f, gesture=way, score=5)]
        return []


class SwipeVertical(Recognizer):
    name = "swipe_vertical"

    @staticmethod
    def position(h, engaged=False):
        """'upright' or 'flat' for a hand facing the camera or the floor; None when edge-on or unclear.
        The palm label flickers between camera and down here, so the fingers' tilt decides.
        In front is checked to start only (engaged): the flat hand is foreshortened and its hand/head ratio
        dips to ~0.78, right at the cutoff, which made frames drop out at random (swipeandpush flips)."""
        if h is None or not (h.raised and (engaged or h.in_front)) or abs(h.palm[0]) >= FLAT_POSE:
            return None
        if abs(h.tilt) < UPRIGHT and h.fingers_up >= 3:
            return "upright"
        if abs(h.tilt) > LYING or h.facing == "down":  # fingers pointing at the screen read as curled
            return "flat"
        return None

    def reset(self):
        super().reset()
        self.pos = self.since = self.left = self.pending = None

    def fire(self, f):
        if self.pending and f.t - self.since >= self.pending[1]:
            gesture, self.pending = self.pending[0], None
            if state.overview_open:  # picking a window in Mission Control flips the hand too (the user's rule)
                return []
            return [self.event(f, gesture=gesture, score=4)]
        return []

    def update(self, f):
        """A flip to upright counts once the hand has stayed upright as long as it stayed flat (capped): a real
        stroke lingers at its end, while a brief upright blip between flat moments doesn't."""
        h = self.hand(f)
        if self.pose_lost(h is not None):
            self.reset()
            return []
        pos = self.position(h, engaged=self.pos is not None)
        if pos is None:  # in between, edge-on, or unclear: keep the current position
            # Going on from the upright end straight into another pose (Point's finger) reads as neither (collected
            # sequences: 9 of 15 Swipe Ups were lost waiting for an upright hand). Not the brief upright blip of a
            # prep: that goes back to flat. So the time still counts.
            return self.fire(f) if self.pos == "upright" else []
        if pos == self.pos:
            self.left = f.t
            return self.fire(f)
        quick = self.left is not None and f.t - self.left <= QUICK
        wrist_flip = self.pos and quick and _moved(h.wrist, self.origin, h.size) <= STAY
        if wrist_flip and pos == "upright":
            self.pending = ("swipe_up", min(self.left - self.since, DWELL))
        else:
            self.pending = None  # first position seen, too slow, the arm moved, or a flip down
        self.pos, self.since, self.left, self.origin = pos, f.t, f.t, h.wrist
        return []
