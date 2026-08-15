from pathlib import Path

import yaml

from talos.prefs import ARGS, SECTIONS, number, rows_from, to_config
from talos.recognizers import GESTURES

CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def test_saving_unchanged_rows_gives_back_the_same_config():
    data = yaml.safe_load(CONFIG.read_text())
    again = yaml.safe_load(yaml.safe_dump(to_config(rows_from(data), data["settings"]), sort_keys=False))
    assert again == data


def test_the_window_lists_every_gesture_once_and_every_bound_one():
    listed = [g for _, names in SECTIONS for g in names]
    assert sorted(listed) == sorted(GESTURES)
    assert set(yaml.safe_load(CONFIG.read_text())["bindings"]) <= set(listed)


def test_every_choice_in_the_config_is_offered():
    for specs in rows_from(yaml.safe_load(CONFIG.read_text())).values():
        for action, arg in specs:
            kind, options = ARGS.get(action, (None, None))
            if kind == "choice":
                assert arg in [value for value, _ in options], (action, arg)


def test_changes_are_saved_right_away(tmp_path):
    """Values come back from AppKit controls as AppKit strings, which YAML refused to write before conversion."""
    import AppKit

    from talos import actions
    from talos.prefs import ADD, SettingsWindow
    AppKit.NSApplication.sharedApplication()
    actions.load()
    copy = tmp_path / "config.yaml"
    copy.write_text(CONFIG.read_text())
    w = SettingsWindow(copy)
    w.load()
    w.set_arg("twist_2", 0, "Mail")  # unchanged, as when you just leave a field: the file stays as it was
    assert copy.read_text() == CONFIG.read_text()
    w.set_action("swipe_up", 0, AppKit.NSString.stringWithString_("focus_app"))
    w.set_arg("swipe_up", 0, AppKit.NSString.stringWithString_("Notes"))
    w.set_action("twist_1", 0, "snap_window")  # a fixed-choice argument starts at its first choice
    w.set_action("ear_tap", 0, ADD)  # only shows an empty second slot; nothing written for it
    w.set_action("walk_away", 1, None)  # remove the second action
    assert w.set_setting("walk_away_seconds", "abc") is not None
    assert w.set_setting("walk_away_seconds", "20") is None
    data = yaml.safe_load(copy.read_text())
    assert data["bindings"]["swipe_up"] == [{"focus_app": "Notes"}]
    assert data["bindings"]["twist_1"] == [{"snap_window": "left"}]
    assert data["bindings"]["ear_tap"] == ["play_pause"]
    assert data["bindings"]["walk_away"] == ["lock_screen"]
    assert data["settings"]["walk_away_seconds"] == 20


def test_point_and_flick_stay_the_window_picker(tmp_path):
    import AppKit

    from talos import actions
    from talos.prefs import SettingsWindow
    AppKit.NSApplication.sharedApplication()
    actions.load()
    copy = tmp_path / "config.yaml"
    copy.write_text(CONFIG.read_text().replace("  point:\n  - select_window", "  point:\n  - play_pause"))
    w = SettingsWindow(copy)
    w.load()
    assert w.rows["point"] == w.rows["flick"] == [("select_window", None)]  # whatever the file says
    titles = [w._action_menu("twist_1", 0, None, False).itemTitles(), w._action_menu("point", 0, None, False).itemTitles()]
    assert "Select window" not in titles[0] and "Select window" in titles[1]  # no other gesture gets it


def test_activity_shows_actions_in_plain_words():
    from talos.prefs import readable
    assert readable("snap_window: left") == "Snap window: Left half"
    assert readable("lock_screen, pause_media") == "Lock screen, Pause media"
    assert readable("focus_app: Google Chrome") == "Open app: Google Chrome"
    assert readable("open_overview") == "Open Mission Control"
    assert readable("close_overview") == "Close Mission Control"


def test_numbers_stay_whole_when_they_can():
    assert number("15") == 15 and isinstance(number("15"), int)
    assert number("0.5") == 0.5
