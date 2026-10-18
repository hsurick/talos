"""Builds one recognizer per gesture (per hand where the gesture uses a hand)."""
from talos.recognizers.ear import EarHold, EarTapUpDown
from talos.recognizers.frame import MotionSweep, WalkAway
from talos.recognizers.hand_moves import BrushOff, Flick, Point, ShapeChange
from talos.recognizers.twist import Twist
from talos.recognizers.wrist import SwipeSideways, SwipeVertical

# Every gesture name the recognizers below can fire, in the order the settings window lists them.
GESTURES = ("twist_1", "twist_2", "twist_3", "twist_4", "swipe_left", "swipe_right", "swipe_up",
            "burst", "unburst",
            "flick", "point", "ear_tap", "ear_up", "ear_down", "ear_hold", "brush_off", "hand_swipe", "lens_wipe",
            "walk_away")


def build(settings):
    out = [WalkAway(settings.get("walk_away_seconds", 15)), MotionSweep()]
    for side in ("Left", "Right"):
        out += [Twist(n, side) for n in range(1, 5)]
        out += [SwipeSideways(side), SwipeVertical(side), BrushOff(side),
                (Flick if settings.get("select_with") == "flick" else Point)(side),
                EarTapUpDown(side), EarHold(side, settings.get("ear_hold_delay", 0)),
                ShapeChange("burst", side, "fist", "open"), ShapeChange("unburst", side, "open", "fist")]
    return out
