"""The gesture catalog: builds one recognizer per gesture (per hand where the gesture uses a hand).
Why each threshold has its value, and what was tried before: TUNING.md."""
from talos.recognizers.ear import EarHold, EarTapUpDown
from talos.recognizers.frame import MotionSweep, WalkAway
from talos.recognizers.hand_moves import BrushOff, Flick, Point, ShapeChange
from talos.recognizers.twist import Twist
from talos.recognizers.wrist import SwipeSideways, SwipeVertical

# Every gesture the recognizers can fire, in the order the settings window lists them.
GESTURES = ("twist_1", "twist_2", "twist_3", "twist_4", "swipe_left", "swipe_right", "swipe_up",
            "burst", "unburst",
            "flick", "point", "ear_tap", "ear_up", "ear_down", "ear_hold", "brush_off", "hand_swipe", "lens_wipe",
            "walk_away")
# How to do each gesture, in one line: collect's prompts and the settings window. Walk Away and Ear Hold
# are left out because collect can't prompt them (a 15s absence, a long hold).
HINTS = {
    "twist_1": "1 finger up, thumb tucked: roll the hand and back",
    "twist_2": "2 fingers up, thumb tucked: roll the hand and back",
    "twist_3": "3 fingers up, thumb tucked: roll the hand and back",
    "twist_4": "4 fingers up, thumb tucked: roll the hand and back",
    "swipe_left": "hand edge-on, fingers up: lean fingers left",
    "swipe_right": "hand edge-on, fingers up: lean fingers right",
    "swipe_up": "palm flat, fingers sideways: flip fingers up",
    "point": "aim your hand that way, then pinch thumb and index",
    "flick": "open hand: snap that way and back",
    "burst": "fist, palm to camera: open to 5 fingers",
    "unburst": "5 fingers, palm to camera: close to a fist",
    "hand_swipe": "sweep a hand across the camera",
    "lens_wipe": "slide a hand across the lens",
    "ear_tap": "point at your ear, then take the hand away",
    "ear_up": "point at your ear, then leave upward",
    "ear_down": "point at your ear a moment, then move down",
    "brush_off": "open palm toward you: flick the fingers away",
}


def build(settings):
    out = [WalkAway(settings.get("walk_away_seconds", 15)), MotionSweep()]
    flick, choose = settings.get("select_with") == "flick", settings.get("choose_with", "pinch")
    pinch_safe = not flick and choose == "pinch"  # Burst / Unburst mustn't take Point's pinch for a fist
    for side in ("Left", "Right"):
        out += [Twist(n, side) for n in range(1, 5)]
        out += [SwipeSideways(side), SwipeVertical(side), BrushOff(side),
                Flick(side) if flick else Point(side, choose),
                EarTapUpDown(side), EarHold(side, settings.get("ear_hold_delay", 0)),
                ShapeChange("burst", side, "fist", "open", pinch_safe),
                ShapeChange("unburst", side, "open", "fist", pinch_safe)]
    return out
