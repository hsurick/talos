"""Brush Off, Burst / Unburst, and Flick / Point (window selection inside the overview)."""
import math

from talos import state
from talos.recognizers.base import Recognizer

BRUSH_TURN = 50     # degrees the palm turns
BRUSH_OUT = 0.25    # hand sizes the fingertip travels outward; 0.5 missed wrist flips done in place (0.39)
BRUSH_TIME = 0.35
HOLD, HOLD_TURN = 0.25, 15  # the start pose must be held this many seconds, the palm turning less than this
# Palm's z (+ = toward you): above START_Z to start (held start poses in the collected clips: 0.07 to 0.6, edge-on
# to angled), below -TOWARD_CAMERA (palm to the camera) to fire.
START_Z, TOWARD_CAMERA = 0.05, 0.3  # -0.25 (edge-on starts) gained nothing and fired in a swipe_left clip
CHANGE_TIME = 0.4   # Burst / Unburst: seconds from one shape to the other
FIST_TILT, FIST_DOWN = 65, 0.4  # a fist leans less than this many degrees, palm y (+ = facing down) under this
FIST_HOLD = 4       # Unburst: frames the fist must show (~0.13s) before it counts
SNAP = 0.4          # Flick: hand sizes the palm moves out (collected flick sequences: 0.4 got 18/30 right, 0.5 15/30)
SNAP_TIME = 0.2
BACK = 0.35         # Flick: back within this many hand sizes of the start chooses the window (0.25: 1 more wrong pick)
BACK_TIME = 0.4
POINT_DEAD = 0.4    # Point: the finger seen shorter than this (hand sizes) points at the screen = neutral
                    # (straight up or sideways is ~0.8)
POINT_TURN = 10     # Point: degrees the direction must change before the highlight moves
# Point: thumb and index tips closer than PINCH_ON (hand sizes) is a pinch; apart past PINCH_OFF first, so a hand
# that's already pinched doesn't choose the moment it aims. Collected point sequences: 0.25 got 12/30, 0.3 18/30
# (pointing down shrinks the hand-size measure, so pinches there read 0.25-0.3), 0.35 19/30.
PINCH_ON, PINCH_OFF = 0.3, 0.4
# Also requiring the tips close in MediaPipe's 3D world landmarks (against tips that only overlap in the image) was
# tried: it lost real pinches (Burst+Point right picks 10/16 -> 7/16 at 4 cm, 5/16 at 3 cm).
# A fist's thumb lies near the index tip too (6% of fist frames under PINCH_ON), but its index tip is folded in:
# index tip to knuckle in fists ~0.36 (95% under 0.51), in pinches ~0.59. Pinches curl the other three fingers,
# so they can't tell it apart (that rule blocked every collected pinch). 0.55: no picks in any Burst/Unburst clip
# (0.45: 1), same hits.
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
        # Open palm = thumb out too; the tucked thumb of Twist-4 and of the swipe leans keeps them apart.
        # Palm partly toward you, not mostly: in the collected clips the hand starts angled (palm x -0.8, z +0.6),
        # which reads as facing "left".
        start_pose = (h is not None and h.raised and h.in_front and h.fingers_up == 4 and not h.thumb_tucked
                      and h.palm[2] > START_Z)
        if self.state == "idle":
            # Held, not passed through: a twist's roll turns the palm toward you for ~0.1s and back, which is
            # the same flip (collected twist_3/4 fired Brush Off 21 times). The real start pose is held ~1s.
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
        # Ends palm to the camera: the flip changes the hand's lean too, so Swipe Left/Right match the same motion,
        # but a swipe keeps the palm sideways. Scored above Swipe's 5 to win that tie.
        if turned >= BRUSH_TURN and _dist(h.tip, self.tip0) >= BRUSH_OUT * h.size and h.palm[2] < -TOWARD_CAMERA:
            self.fired(f, h)
            return [self.event(f, score=6)]
        if start_pose and turned < 10:
            self.palm0, self.tip0, self.t0 = h.palm, h.tip, f.t
        return []


class ShapeChange(Recognizer):
    """Burst (fist -> five fingers) and Unburst (five fingers -> fist), palm facing the camera throughout.
    The palm rule filters out relaxed hands, which open and close constantly but rarely face the camera."""

    def __init__(self, name, side, start, end):
        self.name, self.start_shape, self.end_shape = name, start, end  # "fist" or "open"
        super().__init__(side)

    def reset(self):
        super().reset()
        self.held = 0  # frames in a row the end shape has shown

    @staticmethod
    def shape(h):
        # An upright fist facing the camera. The flat hand of a Swipe Up/Down (fingers pointing sideways or at the
        # screen, palm down) also reads as zero fingers and fired Burst/Unburst on every flip in the old recordings:
        # those "fists" lean 55-150 degrees with palm y 0.4-0.7; real ones (60 collected) lean under 56, y under 0.35.
        if h.fingers_up == 0 and abs(h.tilt) < FIST_TILT and h.palm[1] < FIST_DOWN:
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
    """Inside the overview only: the open hand snaps toward a window (picks it) and back (chooses it). Flick or Point
    runs, not both (setting select_with). The whole hand, not one finger: the collected flick sequences were done
    with the open hand (4 fingers up in ~80% of frames), so a one-finger Flick never armed."""
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
    """Inside the overview only: the direction the index finger points picks the window, and a pinch chooses it
    (the user's design). Pointing at the screen is neutral; pointing up lights the top window, left the
    left one, wherever the finger started. The lit window stays lit through neutral. Pinching bends the finger, so
    the choice is where it pointed the last time thumb and index were still apart. (Aiming with the hand was tried:
    in the collected sequences the hand stayed upright and the finger did the aiming.)"""
    name = "point"

    def reset(self):
        super().reset()
        self.apart = False  # thumb and index were seen apart since aiming began; a pinch then chooses
        self.aimed = None  # direction while they were last apart: what the pinch chooses

    def update(self, f):
        h = self.hand(f)
        out = self.state == "out"
        if not state.overview_open:
            self.reset()
            return [self.event(f, "end", chosen=False)] if out else []
        ok = h is not None and h.raised and not h.near_ear  # any raised hand aims; a fist is Unburst's, see below
        if self.state == "idle":
            if self.pose_ready(ok, f):
                self.state = "aim"
            return []
        if self.pose_lost(ok):  # the hand went down or away: lit stays lit, nothing chosen
            self.reset()
            return [self.event(f, "end", chosen=False)] if out else []
        if not ok:
            return []
        if h.pinch < PINCH_ON and self.apart and out and h.index_reach > FIST_REACH:
            aimed = self.aimed
            self.reset()
            return [self.event(f, "end", chosen=True, **({"angle": round(aimed)} if aimed is not None else {}))]
        dx, dy = h.aim
        if not h.fingers[0] or math.hypot(dx, dy) < POINT_DEAD:
            return []  # index curled, or pointing at the screen: neutral
        angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0 = right, 90 = up, from your point of view
        if h.pinch > PINCH_OFF:
            self.apart, self.aimed = True, angle
        if not out:
            self.state, self.angle = "out", angle
            return [self.event(f, "begin", score=2, angle=round(angle))]
        if abs((angle - self.angle + 180) % 360 - 180) >= POINT_TURN:
            self.angle = angle
            return [self.event(f, "update", angle=round(angle))]
        return []
