from talos.actions.windows import snap_target

LAPTOP, EXTERNAL = (0, 25, 1440, 875), (1440, 0, 2560, 1415)


def test_snaps_to_the_half_then_moves_to_the_next_monitor():
    window = (100, 100, 800, 600)
    assert snap_target(window, [LAPTOP, EXTERNAL], "right") == (720, 25, 720, 875)
    assert snap_target((720, 25, 720, 875), [LAPTOP, EXTERNAL], "right") == (1440, 0, 1280, 1415)


def test_no_monitor_further_left_leaves_it():
    assert snap_target((0, 25, 720, 875), [LAPTOP, EXTERNAL], "left") is None
