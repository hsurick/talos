from talos.arbiter import Arbiter
from talos.events import Event


def ev(gesture, t, score, phase="once", began=None):
    return Event(gesture, phase, t, "Right", {}, score, began)


def test_highest_score_wins_after_the_window():
    a = Arbiter(window=0.1, margin=1)
    assert a.push([ev("twist_4", 0.0, 3)], 0.0) == []
    assert a.push([ev("push_left", 0.05, 5)], 0.05) == []
    assert [e.gesture for e in a.push([], 0.1)] == ["push_left"]


def test_too_close_fires_nothing():
    a = Arbiter(window=0.1, margin=1)
    a.push([ev("a", 0.0, 3), ev("b", 0.0, 3.5)], 0.0)
    assert a.push([], 0.2) == []


def test_on_a_tie_the_gesture_that_started_clearly_earlier_wins():
    """demo1: a 150-degree Twist-4 passes through Brush Off's start pose halfway; both scored 4."""
    a = Arbiter(window=0.1, margin=1)
    a.push([ev("brush_off", 10.69, 4, began=10.50), ev("twist_4", 10.72, 4, began=9.95)], 10.72)
    assert [e.gesture for e in a.push([], 10.8)] == ["twist_4"]
    b = Arbiter(window=0.1, margin=1)
    b.push([ev("brush_off", 10.69, 4, began=10.0), ev("twist_4", 10.72, 4, began=9.95)], 10.72)
    assert b.push([], 10.8) == []  # started about together: still too close to call


def test_ongoing_gesture_released_before_the_decision_still_ends():
    a = Arbiter(window=0.1)
    a.push([ev("ear_hold", 0.0, 6, "begin")], 0.0)
    a.push([ev("ear_hold", 0.03, 0, "end")], 0.03)
    assert [e.phase for e in a.push([], 0.1)] == ["begin", "end"]


def test_losing_ongoing_gesture_sends_nothing_later():
    a = Arbiter(window=0.1)
    a.push([ev("ear_hold", 0.0, 2, "begin"), ev("twist_2", 0.0, 6)], 0.0)
    assert [e.gesture for e in a.push([], 0.1)] == ["twist_2"]
    assert a.push([ev("ear_hold", 0.5, 0, "end")], 0.5) == []


def test_an_end_inside_the_window_keeps_its_data_and_a_lost_begin_can_compete_again():
    a = Arbiter()
    out = a.push([Event("flick", "begin", 0.0, "Right", {"angle": 90}, score=3)], 0.0)
    out += a.push([Event("flick", "end", 0.05, "Right", {"chosen": True})], 0.05)
    out += a.push([], 0.2)
    assert [(e.phase, e.data) for e in out] == [("begin", {"angle": 90}), ("end", {"chosen": True})]
    b = Arbiter()
    out = b.push([Event("point", "begin", 0.0, "Right", score=2), Event("swipe_up", "once", 0.0, "Right", score=4)], 0.0)
    out += b.push([], 0.2)  # Swipe Up wins; Point's begin is dropped
    out += b.push([Event("point", "update", 0.3, "Right", {"angle": 45})], 0.3)
    out += b.push([], 0.5)
    assert [(e.gesture, e.phase) for e in out] == [("swipe_up", "once"), ("point", "begin")]
