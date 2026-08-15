"""Tracked points -> shared facts about each hand. Every recognizer reads these and never the raw points."""
import math
from dataclasses import dataclass

EXTENDED = 1.1      # fingertip this much farther from the wrist than its middle joint = finger extended
THUMB_TUCKED = 0.5  # thumb tip within this many hand sizes of the middle knuckle = tucked (tucked: ~0.2-0.35,
                    # alongside the hand: ~0.75)
NEAR_EAR = 0.4      # index tip within this many shoulder widths of an ear = near the ear
RAISED = 0.8        # wrist above shoulder line + this many shoulder widths = raised above keyboard level
# A hand level with your face measures about 0.6 of your ear-to-ear width; bigger means it's closer to the camera.
# shortcut: one guessed number for everyone; replace with a per-user calibration (hand held beside the head).
IN_FRONT = 0.75

WRIST, THUMB_TIP, INDEX_MCP, MIDDLE_MCP, PINKY_MCP, INDEX_TIP, MIDDLE_TIP = 0, 4, 5, 9, 17, 8, 12
FINGERS = ((6, 8), (10, 12), (14, 16), (18, 20))  # (middle joint, tip): index, middle, ring, pinky
PALM = (0, 5, 9, 13, 17)
NOSE, LEFT_EAR, RIGHT_EAR, LEFT_SHOULDER, RIGHT_SHOULDER = 0, 7, 8, 11, 12


@dataclass
class Hand:
    side: str
    fingers: tuple          # extended? (index, middle, ring, pinky); thumb is separate
    thumb_tucked: bool
    palm: tuple             # unit vector out of the palm: +x your right, +y down, +z away from the camera
    facing: str             # where the palm points: camera | user | left | right | down | up
    roll: float             # degrees; knuckle-line angle seen from above, i.e. roll around the finger axis
    tilt: float             # degrees the hand leans in the image: 0 = fingers straight up, + = toward your right
    center: tuple           # palm center (x, y); x is scaled so both axes use the same units
    tip: tuple              # index fingertip (x, y)
    size: float             # wrist to middle knuckle; motion thresholds are in hand sizes
    raised: bool            # above keyboard level
    ear_dist: float | None  # index tip to the nearest ear, in shoulder widths (None without a body)
    shoulder: float | None  # shoulder width; a steadier unit than hand size for small moves near the face
    depth_ratio: float | None  # how big the hand looks next to the head; None without a body
    wrist: tuple = (0.0, 0.0)  # wrist (x, y); stays put in wrist gestures even when the palm swings
    # Where the index finger points, as the camera sees it: knuckle to tip in hand sizes (x right, y down). Short
    # when it points at the screen (neutral for Point), ~0.8 long when it points straight up, down or sideways.
    aim: tuple = (0.0, 0.0)
    pinch: float = 1.0  # thumb tip to index tip, in hand sizes (3D)
    index_reach: float = 1.0  # index tip to its knuckle, in hand sizes (3D): folded into a fist ~0.36, pinching ~0.6

    @property
    def fingers_up(self):
        return sum(self.fingers)

    @property
    def in_front(self):
        """Hand clearly in front of the face, not touching it or in your hair. Unknown (no body) counts as in front."""
        return self.depth_ratio is None or self.depth_ratio >= IN_FRONT

    @property
    def near_ear(self):
        # The ear check is 2D, so a hand in front of the face overlaps the ear in the image; require head depth.
        return self.ear_dist is not None and self.ear_dist < NEAR_EAR and not self.in_front


@dataclass
class Features:
    t: float
    hands: dict          # side -> Hand
    body_present: bool   # a person is in frame (both shoulders visible)
    idle: float          # seconds since keyboard or mouse input
    motion: tuple        # (changed fraction, x of the change) for Hand Swipe and Lens Wipe


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


_dist = math.dist


def _hand(side, raw, aspect, body):
    p = [(x * aspect, y, z * aspect) for x, y, z in raw]  # same units on every axis
    wrist = p[WRIST]
    size = _dist(wrist, p[MIDDLE_MCP]) or 1e-6
    fingers = tuple(_dist(p[tip], wrist) > EXTENDED * _dist(p[pip], wrist) for pip, tip in FINGERS)

    a, b = _sub(p[INDEX_MCP], wrist), _sub(p[PINKY_MCP], wrist)
    n = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    sign = -1 if side == "Right" else 1  # the cross product points the opposite way for the two hands
    length = math.hypot(*n) or 1e-6
    palm = tuple(sign * c / length for c in n)
    axis = max(range(3), key=lambda i: abs(palm[i]))
    facing = (("left", "right"), ("up", "down"), ("camera", "user"))[axis][palm[axis] > 0]

    knuckles = _sub(p[PINKY_MCP], p[INDEX_MCP])
    roll = math.degrees(math.atan2(knuckles[2], knuckles[0]))
    # To the fingertip, not the knuckle: the knuckle line shows only about half of a lean.
    lean = _sub(p[MIDDLE_TIP], wrist)
    tilt = math.degrees(math.atan2(lean[0], -lean[1]))  # image y points down
    center = tuple(sum(p[i][k] for i in PALM) / len(PALM) for k in (0, 1))

    raised, ear_dist, width, depth_ratio = wrist[1] < 0.9, None, None, None
    if body:
        q = [(x * aspect, y) for x, y, *_ in body]
        width = _dist(q[LEFT_SHOULDER], q[RIGHT_SHOULDER]) or 1e-6
        shoulder_y = (q[LEFT_SHOULDER][1] + q[RIGHT_SHOULDER][1]) / 2
        raised = wrist[1] < shoulder_y + RAISED * width
        ear = min((q[LEFT_EAR], q[RIGHT_EAR]), key=lambda e: _dist(e, p[INDEX_TIP][:2]))
        ear_dist = _dist(ear, p[INDEX_TIP][:2]) / width
        # Sizes as seen in the image (no depth). The larger of hand length and knuckle width stays steady when
        # the hand turns edge-on or points at the camera.
        hand_seen = max(_dist(wrist[:2], p[MIDDLE_MCP][:2]), _dist(p[INDEX_MCP][:2], p[PINKY_MCP][:2]))
        depth_ratio = hand_seen / (_dist(q[LEFT_EAR], q[RIGHT_EAR]) or 1e-6)

    aim = tuple((p[INDEX_TIP][k] - p[INDEX_MCP][k]) / size for k in (0, 1))
    return Hand(side, fingers, _dist(p[THUMB_TIP], p[MIDDLE_MCP]) < THUMB_TUCKED * size, palm, facing, roll,
                tilt, center, p[INDEX_TIP][:2], size, raised, ear_dist, width, depth_ratio, wrist[:2], aim,
                _dist(p[THUMB_TIP], p[INDEX_TIP]) / size, _dist(p[INDEX_TIP], p[INDEX_MCP]) / size)


def compute(frame):
    body = frame.body
    present = bool(body) and body[LEFT_SHOULDER][3] > 0.5 and body[RIGHT_SHOULDER][3] > 0.5
    hands = {h["side"]: _hand(h["side"], h["pts"], frame.aspect, body if present else None) for h in frame.hands}
    return Features(frame.t, hands, present, frame.idle, tuple(frame.motion))
