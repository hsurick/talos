from talos import state
from talos.actions import overview
from talos.events import Event


def test_mission_control_aims_by_direction_and_presses_only_on_choose(monkeypatch):
    width = overview.AppKit.NSScreen.screens()[0].frame().size.width
    frames = {"left": (0, 400, 300, 200), "right": (width - 300, 400, 300, 200)}  # x, y, w, h like ax_frame
    pressed = []
    monkeypatch.setattr(overview, "dock_buttons", lambda: list(frames))
    monkeypatch.setattr(overview, "ax_frame", lambda b: frames[b])
    monkeypatch.setattr(overview.AX, "AXUIElementPerformAction", lambda b, a: pressed.append(b))
    overview.mission.update(buttons=[], highlight=None)
    state.overview_open = True
    try:
        aim = lambda phase, **data: overview.select_window(Event("select_window", phase, 0, data=data), None)  # noqa: E731
        aim("begin", angle=180)
        assert overview.mission["highlight"] == "left"
        aim("update", angle=0)  # Point moved
        assert overview.mission["highlight"] == "right"
        aim("end", chosen=False)  # Point gave up (hand left): still lit, nothing pressed
        assert overview.mission["highlight"] == "right" and pressed == []
        aim("end", chosen=True)
        assert pressed == ["right"] and not state.overview_open
    finally:
        state.overview_open = False
