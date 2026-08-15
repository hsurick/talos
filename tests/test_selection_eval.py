import sys
from pathlib import Path

from talos.record import Recorder
from tests.helpers import frame, landmarks

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import eval as scoring  # noqa: E402

OPEN = (True,) * 4


def pinched():
    """An upright open hand with the thumb tip on the index tip."""
    pts = landmarks(fingers=OPEN)
    pts[4] = list(pts[8])
    return pts


def test_a_recorded_sequence_opens_the_overview_itself(tmp_path):
    """A collect sequence "burst+point@90": fist, open hand (Burst opens Mission Control in the simulated actions),
    the open hand pointing up, then a pinch to choose. No forced overview: the Burst opened it, so Point could fire."""
    path = tmp_path / "seq.jsonl.gz"
    rec = Recorder(path)
    hands = [landmarks(fingers=(False,) * 4)] * 10 + [landmarks(fingers=(True,) * 4)] * 10 + \
        [landmarks(fingers=OPEN)] * 30 + [pinched()] * 6
    for n, pts in enumerate(hands):
        rec.write(frame(t=n / 30, hands=[("Right", pts)]))
    rec.label("burst+point@90", 0.2, 1.9)
    rec.close()
    assert [g for _, g in scoring.events(path)] == ["burst", "point@90"]
    assert scoring.score(path, [(0.2, 1.9, {"burst": 1, "point@90": 1})])[:3] == (2, 0, 0)


def test_closing_the_overview_that_is_not_open_is_harmless():
    from talos import state
    from talos.pipeline import simulate
    from talos.events import Event
    e = Event("x", "once", 0)
    try:
        assert simulate("open_overview", e, None) and state.overview_open  # Burst opens it
        assert simulate("close_overview", e, None) and not state.overview_open  # Unburst closes it
        assert not simulate("close_overview", e, None)  # again: nothing open, a harmless misfire
    finally:
        state.overview_open = False


def test_a_recorded_point_scores_by_the_direction_it_chose(tmp_path):
    """A collect clip "point@90" (point up): the made-up hand points up, then pinches. Replayed with the
    overview counted as open during the clip, it scores as point@90 (also in the mirror); asked for "point@0"
    (right), the same clip is a miss plus a wrong choice."""
    path = tmp_path / "clip.jsonl.gz"
    rec = Recorder(path)
    hands = [landmarks(fingers=OPEN)] * 40 + [pinched()] * 3
    for n, pts in enumerate(hands):
        rec.write(frame(t=n / 30, hands=[("Right", pts)]))
    rec.label("point@90", 1.0, 1.5)
    rec.close()
    assert [g for _, g in scoring.events(path)] == ["point@90"]
    assert scoring.score(path, [(1.0, 1.5, {"point@90": 1})])[:3] == (1, 0, 0)
    assert scoring.score(path, [(1.0, 1.5, {"point@90": 1})], variant="mirrored = left hand")[:3] == (1, 0, 0)
    assert scoring.score(path, [(1.0, 1.5, {"point@0": 1})])[:3] == (0, 1, 1)
