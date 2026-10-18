"""Ear gestures. One finger at the ear: Ear Tap, Ear Up / Down. Two fingers in the tube pose: Ear Hold."""
from talos.recognizers.base import Recognizer

PRESS = 0.25      # Ear Hold: the fingertip closes this fraction of its distance to the ear
# Ear Tap / Up / Down, in shoulder widths (hand size shrinks when the hand is side-on at the ear) and seconds,
# tuned on the collected ear and nothing clips:
EAR_IN, EAR_OUT = 0.3, 0.45  # a visit starts within EAR_IN of an ear and ends beyond EAR_OUT
UP, DOWN = 0.2, 0.15         # leaving at least this far up / down (from where the visit started)
DOWN_STAY = 0.3              # Ear Down: stayed at least this long first
TAP_STAY = 0.8               # Ear Tap: any other visit up to this long
MIN_STAY = 0.15              # shorter visits are a hand passing by
MAX_STAY = 2.0               # longer is a hand resting on the head
MIN_POINTING = 0.5           # share of the visit's frames with 1-2 fingers up (0.4: 4 false taps in nothing)
UP_POINTING = 0.1            # ...for Ear Up
# Depth: the hand's size next to the head's (Hand.depth_ratio) over the visit, median. Collected ear visits: 0.55-0.85
# (36/37 under 0.9); hands overlapping the ear only in the image, in front of the face: median 1.16. The pose
# model's z didn't separate them at all. Replaced a share-of-frames-beside-the-head rule (2 more ear hits, no new
# misfires in the other clips).
AT_EAR_DEPTH = 0.9


class EarTapUpDown(Recognizer):
    """Ear Tap / Up / Down as one visit: a pointing fingertip comes to the ear and leaves again (the user's design:
    away, at the ear, away). Judged when it leaves: leaving upward is Ear Up; leaving downward after staying a
    while is Ear Down; any other short visit is Ear Tap.
    Collected clips (tools: ear visit measurements): the hand comes up from the lap, stays 0.2-1.8s, and the finger
    count flickers 0-2 at the ear (the index hides behind the head), so the pose is judged over the whole visit,
    not frame by frame. Lowering a hand after touching your head also leaves downward; what tells it apart is
    pointing through the visit."""
    name = "ear_tap"

    def reset(self):
        super().reset()
        self.visit = None  # {t0, tip0, shoulder, frames, pointing, depth} while a fingertip is at an ear
        self.resting = False  # stayed past MAX_STAY: no new visit until the hand leaves the ear

    def update(self, f):
        h = self.hand(f)
        v = self.visit
        if h is None or h.ear_dist is None:
            self.visit = None
            return self.judge(f, v, None) if v else []  # left the picture: judged like any exit
        if v is None:
            if self.resting:
                self.resting = h.ear_dist <= EAR_OUT  # after a rest, a new visit needs the hand to leave first
            elif h.ear_dist < EAR_IN:
                self.visit = {"t0": f.t, "tip0": h.tip, "shoulder": h.shoulder, "frames": 1,
                              "pointing": int(1 <= h.fingers_up <= 2),
                              "depth": [h.depth_ratio]}
            return []
        v["frames"] += 1
        v["pointing"] += 1 <= h.fingers_up <= 2
        v["depth"].append(h.depth_ratio)
        if h.ear_dist > EAR_OUT:
            self.visit = None
            return self.judge(f, v, h)
        if f.t - v["t0"] > MAX_STAY:
            self.visit, self.resting = None, True  # a hand resting on the head; lowering it isn't Ear Down
        return []

    def judge(self, f, v, h):
        stay, pointing = f.t - v["t0"], v["pointing"] / v["frames"]
        # The ear check is 2D, so a hand raised in front of the face overlaps the ear too (Twist-1 and Burst clips
        # fired Ear Up); a real visit's hand is at the head's depth (median, as depth flickers frame to frame).
        depth = sorted(v["depth"])[len(v["depth"]) // 2]
        if stay < MIN_STAY or depth >= AT_EAR_DEPTH:
            return []
        dy = None if h is None else (h.tip[1] - v["tip0"][1]) / v["shoulder"]
        # Leaving upward is rare by accident, so Ear Up asks less of the pose (its clips pointed only 13-20%).
        if dy is not None and dy <= -UP and pointing >= UP_POINTING:
            return [self.event(f, gesture="ear_up", score=5)]
        if pointing < MIN_POINTING:
            return []
        if dy is not None and dy >= DOWN and stay >= DOWN_STAY:
            return [self.event(f, gesture="ear_down", score=5)]
        if stay <= TAP_STAY:
            return [self.event(f, gesture="ear_tap", score=5)]
        return []


class EarHold(Recognizer):
    """Tube pose at the ear, then a press: key down on the press, key up on release."""
    name = "ear_hold"

    def __init__(self, side, delay=0):
        self.delay = delay
        super().__init__(side)

    def update(self, f):
        h = self.hand(f)
        ok = h is not None and h.fingers == (True, True, False, False) and h.near_ear
        if self.state == "idle":
            if self.pose_ready(ok, f):
                self.state, self.d0, self.t0 = "armed", h.ear_dist, f.t
            return []
        if self.state == "held":
            if self.pose_lost(ok):  # a hand missed for a frame or two (side-on at the ear) doesn't drop the key
                self.reset()
                return [self.event(f, "end", lost=h is None)]  # always end, so the key can't stick
            return []
        if self.pose_lost(ok):
            self.reset()
            return []
        if not ok:
            return []
        if self.state == "armed":
            if h.ear_dist <= self.d0 * (1 - PRESS):
                self.state, self.t0 = "pressed", f.t
            elif h.ear_dist > self.d0 or f.t - self.t0 > 0.5:
                self.d0, self.t0 = h.ear_dist, f.t
        if self.state == "pressed" and f.t - self.t0 >= self.delay:
            self.state = "held"
            return [self.event(f, "begin", score=6)]
        return []
