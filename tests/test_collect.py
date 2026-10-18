import types

import talos.__main__ as main
from talos import debug, vision
from talos.record import labels
from tests.helpers import frame


def run_collect(tmp_path, monkeypatch, keys, auto=True, count=6, seconds=30):
    """Fake camera at 10 fps; keys = {time: key pressed}. Each clip: 1s get ready + 2s GO."""
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(vision, "frames", lambda camera=0: (frame(t=n / 10) for n in range(seconds * 10)))
    shown = []

    def show(frame, features, recognizers, events, stats, banner=(), footer=None):
        shown.append(banner[0][0])
        key = keys.get(frame.t)
        return False if key == "q" else ord(key) if key else 255  # like debug.show

    monkeypatch.setattr(debug, "show", show)
    main.collect(types.SimpleNamespace(target=["twist_1"], count=count, slot=2.0, auto=auto))
    return sorted(tmp_path.glob("*.jsonl.gz")), shown


def test_autoplay_saves_one_labeled_file_per_three_prompts(tmp_path, monkeypatch):
    files, shown = run_collect(tmp_path, monkeypatch, {0.0: " "})
    assert len(files) == 2 and all(len(labels(f)) == 3 for f in files)
    assert {g for f in files for *_, g in labels(f)} == {"twist_1"}  # named gesture only, no "nothing"
    assert labels(files[0])[0][:2] == (1.0, 3.0)  # GO after 1s of "get ready", 2s window
    assert shown[1].startswith("get ready") and shown[11].startswith("GO")


def test_manual_waits_for_space_before_each_clip(tmp_path, monkeypatch):
    files, shown = run_collect(tmp_path, monkeypatch, {1.0: " ", 8.0: " "}, auto=False)
    assert shown[0].startswith("next") and shown[50].startswith("next")  # waiting between clips
    assert [s for s, *_ in labels(files[0])] == [2.0, 9.0]


def test_manual_with_no_clips_saves_nothing(tmp_path, monkeypatch):
    files, _ = run_collect(tmp_path, monkeypatch, {}, auto=False)
    assert files == []


def test_space_mid_clip_drops_it_and_stops_autoplay(tmp_path, monkeypatch):
    files, shown = run_collect(tmp_path, monkeypatch, {0.0: " ", 2.0: " ", 4.0: "a"})
    assert shown[25].startswith("next")  # waiting after the stop
    first = labels(files[0])
    assert len(first) == 3 and first[0][0] == 4.0 + 1.0  # the dropped clip got no label; A restarted it at 4s


def test_x_redoes_the_file(tmp_path, monkeypatch):
    files, _ = run_collect(tmp_path, monkeypatch, {0.0: " ", 5.0: "x"})  # during the 2nd prompt of file 1
    assert len(files) == 2 and labels(files[0])[0][0] == 5.0 + 1.0  # file 1 restarted from its first prompt


def test_selection_prompts_carry_a_direction():
    out = main.prompts(["point", "twist_1"], 40)
    assert {p.partition("@")[0] for p in out} == {"point", "twist_1"}
    assert all(int(p.partition("@")[2]) in main.DIRECTIONS for p in out if p.startswith(("point", "flick")))
    assert all("@" not in p for p in out if p.startswith("twist"))


def test_sequence_prompts_open_an_overview_then_pick():
    out = main.prompts(["sequences"], 30)
    assert all(p.startswith("burst+point@") for p in out)
    assert main.step_name("point@135") == "POINT UP-LEFT, then PINCH"


def test_sequences_flick_picks_with_flick(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(vision, "frames", lambda camera=0: (frame(t=n / 10) for n in range(300)))
    monkeypatch.setattr(debug, "show", lambda *a, **k: ord(" ") if a[0].t == 0 else 255)
    main.collect(types.SimpleNamespace(target=["sequences", "flick"], count=3, slot=2.0, auto=True))
    got = [g for f in tmp_path.glob("*.jsonl.gz") for *_, g in labels(f)]
    assert got and all(g.split("+")[1].startswith("flick@") for g in got)


def test_quit_keeps_finished_clips(tmp_path, monkeypatch):
    files, _ = run_collect(tmp_path, monkeypatch, {0.0: " ", 4.0: "q"})
    assert len(files) == 1 and len(labels(files[0])) == 1


def test_first_ctrl_c_stops_the_loop_and_a_second_interrupts():
    import os
    import signal

    import pytest
    stop = main.stop_on_ctrl_c()
    try:
        os.kill(os.getpid(), signal.SIGINT)
        assert stop
        with pytest.raises(KeyboardInterrupt):
            os.kill(os.getpid(), signal.SIGINT)
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler)
