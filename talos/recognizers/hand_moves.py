"""Brush Off, Burst / Unburst, and Flick / Point (window selection inside the overview)."""
import math

from talos import state
from talos.recognizers.base import Recognizer

BRUSH_TURN = 50     # degrees the palm turns
BRUSH_OUT = 0.25    # hand sizes the fingertip travels outward (wrist flips done in place travel ~0.4)
BRUSH_TIME = 0.35
HOLD, HOLD_TURN = 0.25, 15  # the start pose must be held this many seconds, the palm turning less than this
START_Z, TOWARD_CAMERA = 0.05, 0.3  # palm z (+ = toward you): above START_Z to start, below -TOWARD_CAMERA to fire
CHANGE_TIME = 0.4   # Burst / Unburst: seconds from one shape to the other
FIST_TILT, FIST_DOWN = 65, 0.4  # a fist leans less than this many degrees, palm y (+ = facing down) under this
FIST_HOLD = 4       # Unburst: frames the fist must show (~0.13s) before it counts
SNAP = 0.4          # Flick: hand sizes the palm moves out
SNAP_TIME = 0.2
BACK = 0.35         # Flick: back within this many hand sizes of the start chooses the window
BACK_TIME = 0.4
POINT_DEAD = 0.4    # Point: a finger seen shorter than this (hand sizes) points at the screen = neutral
POINT_TURN = 10     # Point: degrees the direction must change before the highlight moves
# Point: thumb and index tips closer than PINCH_ON (hand sizes) is a pinch. They must be apart past PINCH_OFF first,
# so a hand that's already pinched doesn't choose the moment it aims. Pointing down shrinks the hand-size measure,
# so pinches there read up to 0.3.
PINCH_ON, PINCH_OFF = 0.3, 0.4
# Index tip to its knuckle: folded into a fist ~0.36, pinching ~0.6. Tells a pinch from a fist, whose thumb also
# lies near the index tip.
FIST_REACH = 0.55


def _dist(a, b):
    return math.dist(a[:2], b[:2])


def _turn(a, b):
    """Degrees between two palm directions."""
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))


class BrushOff(Recognizer):
    """Open palm facing you, then the wrist turns and the fingers flick outward."""
    name = "brush_off"

    def reset(self):
        super().reset()
        self.hold = None  # (palm, since when) while the start pose is held steady

    def update(self, f):
        h = self.hand(f)
        if self.state == "settle":
            if self.settle(f, h):
                self.reset()
            return []
        # Thumb out: the tucked thumb of Twist-4 and the swipes keeps them apart. Palm only partly toward you:
        # the start pose is usually angled.
        start_pose = (h is not None and h.raised and h.in_front and h.fingers_up == 4 and not h.thumb_tucked
                      and h.palm[2] > START_Z)
        if self.state == "idle":
            # Held, not passed through: a twist's roll turns the palm toward you for ~0.1s on the way.
            if not start_pose:
                self.hold = None
            elif self.hold is None or _turn(h.palm, self.hold[0]) > HOLD_TURN:
                self.hold = (h.palm, f.t)
            elif f.t - self.hold[1] >= HOLD:
                self.state, self.palm0, self.tip0, self.t0 = "armed", h.palm, h.tip, f.t
            return []
        if h is None or f.t - self.t0 > BRUSH_TIME:
            if h is None or not start_pose:
                self.reset()
            else:
                self.palm0, self.tip0, self.t0 = h.palm, h.tip, f.t
            return []
        turned = _turn(h.palm, self.palm0)
        # Ends palm to the camera, which a swipe on the same motion doesn't. Scored above Swipe's 5 to win that tie.
        if turned >= BRUSH_TURN and _dist(h.tip, self.tip0) >= BRUSH_OUT * h.size and h.palm[2] < -TOWARD_CAMERA:
            self.fired(f, h)
            return [self.event(f, score=6)]
        if start_pose and turned < 10:
            self.palm0, self.tip0, self.t0 = h.palm, h.tip, f.t
        return []


class ShapeChange(Recognizer):
    """Burst (fist -> five fingers) and Unburst (five fingers -> fist), palm facing the camera throughout.
    The palm rule filters out relaxed hands, which open and close constantly but rarely face the camera."""

    def __init__(self, name, side, start, end, pinch_safe=False):
        self.name, self.start_shape, self.end_shape = name, start, end  # "fist" or "open"
        self.pinch_safe = pinch_safe  # Point chooses with a pinch, so a pinch mustn't count as a fist
        super().__init__(side)

    def reset(self):
        super().reset()
        self.held = 0  # frames in a row the end shape has shown

    def shape(self, h):
        # An upright fist: a Swipe Up's flat hand also shows zero fingers, but leans far over or faces down.
        # With pinch choosing, the index must be folded in too, or opening the hand after a pinch fires Burst.
        if (h.fingers_up == 0 and abs(h.tilt) < FIST_TILT and h.palm[1] < FIST_DOWN
                and not (self.pinch_safe and h.index_reach >= FIST_REACH)):
            return "fist"
        if h.fingers_up == 4 and not h.thumb_tucked:  # five fingers; four with the thumb tucked is Twist-4's pose
            return "open"
        return None

    def update(self, f):
        h = self.hand(f)
        facing = h is not None and h.in_front and h.facing == "camera"
        if self.state == "idle":
            if self.pose_ready(facing and h.raised and self.shape(h) == self.start_shape, f):
                self.state, self.t0 = "armed", f.t
            return []
        if h is None or f.t - self.t0 > CHANGE_TIME:
            self.reset()
            return []
        if self.shape(h) == self.start_shape:
            self.t0, self.held = f.t, 0  # still in the start shape
        elif self.shape(h) == self.end_shape and facing:
            self.held += 1
            # Unburst's fist must hold: curling an open hand into a pointing finger passes through a fist.
            if self.end_shape != "fist" or self.held >= FIST_HOLD:
                self.reset()
                return [self.event(f, score=3)]
        else:
            self.held = 0
        return []


class Flick(Recognizer):
    """Inside the overview only: the open hand snaps toward a window (picks it) and back (chooses it).
    Flick or Point runs, not both (setting select_with)."""
    name = "flick"

    def update(self, f):
        h = self.hand(f)
        if not state.overview_open:
            if self.state == "out":
                self.reset()
                return [self.event(f, "end", chosen=False)]
            self.reset()
            return []
        ok = h is not None and h.raised and h.fingers_up >= 3 and not h.near_ear
        if self.state == "idle":
            if self.pose_ready(ok, f):
                self.state, self.tip0, self.t0 = "armed", h.center, f.t
            return []
        if self.state == "out":
            if h is None or f.t - self.t0 > BACK_TIME:
                self.reset()
                return [self.event(f, "end", chosen=False)]
            if _dist(h.center, self.tip0) <= BACK * h.size:
                self.reset()
                return [self.event(f, "end", chosen=True)]
            return []
        if self.pose_lost(ok):
            self.reset()
            return []
        if not ok:
            return []
        if f.t - self.t0 > SNAP_TIME or _dist(h.center, self.tip0) < 0.1 * h.size:
            self.tip0, self.t0 = h.center, f.t  # tip0: where the palm rested, not the fingertip
        elif _dist(h.center, self.tip0) >= SNAP * h.size:
            dx, dy = h.center[0] - self.tip0[0], h.center[1] - self.tip0[1]
            angle = math.degrees(math.atan2(-dy, dx))  # 0 = right, 90 = up, from your point of view
            self.state, self.t0 = "out", f.t
            return [self.event(f, "begin", score=3, angle=round(angle) % 360)]
        return []


class Point(Recognizer):
    """Inside the overview only: the direction the index finger points picks the window, and a pinch chooses it.
    Pointing at the screen is neutral, and the lit window stays lit through it. Pinching bends the finger, so the
    choice is where it pointed the last time thumb and index were still apart.
    choose="pinky" (setting choose_with): raising the pinky chooses instead, with middle and ring still curled
    (an open hand has the pinky up too). The camera sees a raised pinky more reliably than two touching tips."""
    name = "point"

    def __init__(self, side, choose="pinch"):
        self.choose = choose
        super().__init__(side)

    def reset(self):
        super().reset()
        self.apart = False  # thumb and index apart (pinky down) since aiming began
        self.aimed = None  # direction while they were last apart: what gets chosen

    def update(self, f):
        h = self.hand(f)
        out = self.state == "out"
        if not state.overview_open:
            self.reset()
            return [self.event(f, "end", chosen=False)] if out else []
        ok = h is not None and h.raised and not h.near_ear
        if self.state == "idle":
            if self.pose_ready(ok, f):
                self.state = "aim"
            return []
        if self.pose_lost(ok):  # the hand went down or away: the lit window stays lit, nothing chosen
            self.reset()
            return [self.event(f, "end", chosen=False)] if out else []
        if not ok:
            return []
        if self.choose == "pinky":
            chose, apart = h.fingers == (True, False, False, True), not h.fingers[3]
        else:
            chose, apart = h.pinch < PINCH_ON and h.index_reach > FIST_REACH, h.pinch > PINCH_OFF
        if chose and self.apart and out:
            aimed = self.aimed
            self.reset()
            return [self.event(f, "end", chosen=True, **({"angle": round(aimed)} if aimed is not None else {}))]
        dx, dy = h.aim
        if not h.fingers[0] or math.hypot(dx, dy) < POINT_DEAD:
            return []  # index curled, or pointing at the screen: neutral
        angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0 = right, 90 = up, from your point of view
        if apart:
            self.apart, self.aimed = True, angle
        if not out:
            self.state, self.angle = "out", angle
            return [self.event(f, "begin", score=2, angle=round(angle))]
        if abs((angle - self.angle + 180) % 360 - 180) >= POINT_TURN:
            self.angle = angle
            return [self.event(f, "update", angle=round(angle))]
        return []
