import time

from talos.bindings import Bindings
from talos.events import Event
from talos.record import Recorder, labels, read
from tests.helpers import frame, landmarks


def test_bindings_run_each_action_with_its_setting(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("bindings:\n  twist_1:\n    - focus_app: Google Chrome\n    - play_pause\nsettings:\n  select_with: flick\n")
    calls = []
    b = Bindings(cfg, run=lambda name, e, arg: calls.append((name, arg)))
    b.handle(Event("twist_1", "once", 0))
    assert calls == [("focus_app", "Google Chrome"), ("play_pause", None)]


def test_broken_config_keeps_the_last_good_one(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("bindings:\n  ear_tap:\n    - play_pause\n")
    b = Bindings(cfg, run=lambda *a: None)
    time.sleep(0.01)
    cfg.write_text("bindings:\n  ear_tap:\n    - no_such_action\n")
    assert not b.reload_if_changed()
    assert b.describe(Event("ear_tap", "once", 0)) == ["play_pause"]


def test_rebinding_mid_hold_releases_the_key_it_pressed(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("bindings:\n  ear_hold:\n    - hold_key: fn\n")
    calls = []
    b = Bindings(cfg, run=lambda name, e, arg: calls.append((e.phase, arg)))
    b.handle(Event("ear_hold", "begin", 0, "Right"))
    time.sleep(0.01)
    cfg.write_text("bindings:\n  ear_hold:\n    - hold_key: escape\n")
    assert b.reload_if_changed()
    b.handle(Event("ear_hold", "end", 1, "Right"))
    assert calls == [("begin", "fn"), ("end", "fn")]


def test_stopping_mid_hold_ends_the_gesture(tmp_path, monkeypatch):
    from talos import recognizers
    from talos.pipeline import process

    class Hold:
        def update(self, f):
            return [Event("ear_hold", "begin", f.t, "Right", score=6)] if f.t == 0 else []
    monkeypatch.setattr(recognizers, "build", lambda settings: [Hold()])
    cfg = tmp_path / "config.yaml"
    cfg.write_text("bindings:\n  ear_hold:\n    - hold_key: fn\n")
    calls = []
    b = Bindings(cfg, run=lambda name, e, arg: calls.append(e.phase))
    process([frame(t=0.0), frame(t=0.2), frame(t=0.3)], b, lambda fr, *_: fr.t < 0.3)  # camera off at 0.3s
    assert calls == ["begin", "end"]


def test_record_round_trip(tmp_path):
    path = tmp_path / "r.jsonl.gz"
    rec = Recorder(path)
    rec.write(frame(t=1.5, hands=[("Right", landmarks())], motion=(0.1, 0.5)))
    rec.close()
    (f,) = read(path)
    assert f.t == 1.5 and f.hands[0]["side"] == "Right" and len(f.hands[0]["pts"]) == 21 and f.image is None


def test_record_labels_and_world_points(tmp_path):
    path = tmp_path / "r.jsonl.gz"
    rec = Recorder(path)
    f = frame(t=1.0, hands=[("Right", landmarks())])
    f.hands[0]["world"] = [[0.01, 0.02, 0.03]] * 21
    rec.write(f)
    rec.label("twist_1", 1.0, 4.0)
    rec.write(frame(t=2.0))
    rec.close()
    assert [f.t for f in read(path)] == [1.0, 2.0]  # label lines aren't frames
    assert next(read(path)).hands[0]["world"][0] == [0.01, 0.02, 0.03]
    assert labels(path) == [(1.0, 4.0, "twist_1")]
