from talos.app import describe


def test_describe_names_the_gesture_and_its_actions():
    line = "  12.34s twist_1 once (Right) {'direction': -1} -> focus_app: Google Chrome"
    assert describe(line) == ("twist_1", "focus_app: Google Chrome")


def test_describe_shows_ongoing_gestures_once():
    assert describe("   3.00s ear_hold begin (Left) -> hold_key: fn") == ("ear_hold", "hold_key: fn")
    assert describe("   4.00s ear_hold end (Left) -> hold_key: fn") is None
