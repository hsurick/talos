from talos import state
from talos.recognizers.ear import EarHold, EarTapUpDown
from talos.recognizers.frame import MotionSweep, WalkAway
from talos.recognizers.hand_moves import BrushOff, Flick, Point, ShapeChange
from talos.recognizers.twist import Twist
from talos.recognizers.wrist import SwipeSideways, SwipeVertical
from tests.helpers import feats, hand, run

DT = 1 / 30


def frames(hands_by_frame, start=0.0):
    return [feats(start + i * DT, *([h] if h else [])) for i, h in enumerate(hands_by_frame)]


def twist_hands(rolls, fingers=(True, True, False, False)):
    return [hand(fingers=fingers, roll=r) for r in rolls]


def test_twist_2_fires_on_roll_out_and_back():
    events = run(Twist(2, "Right"), frames(twist_hands([0, 0, 0, 15, 40, 20, 3])))
    assert [e.gesture for e in events] == ["twist_2"]


def test_twist_needs_the_matching_finger_count():
    assert run(Twist(3, "Right"), frames(twist_hands([0, 0, 0, 15, 40, 20, 3]))) == []


def test_twist_needs_the_roll_back():
    assert run(Twist(2, "Right"), frames(twist_hands([0, 0, 0, 15, 40, 45, 45, 45]))) == []


def test_twist_survives_a_short_pose_dropout_but_resets_on_a_long_one():
    blip = twist_hands([0, 0, 0, 10]) + [None] + twist_hands([40, 20, 3])
    assert len(run(Twist(2, "Right"), frames(blip))) == 1
    long_gap = twist_hands([0, 0, 0, 10]) + [None] * 5 + twist_hands([40, 20, 3])
    assert run(Twist(2, "Right"), frames(long_gap)) == []


def test_twist_ignores_fingers_at_the_ear():
    hands = [hand(roll=r, ear_dist=0.1, depth_ratio=0.7) for r in [0, 0, 0, 15, 40, 20, 3]]
    assert run(Twist(2, "Right"), frames(hands)) == []


def test_twist_survives_the_thumb_vanishing_mid_roll():
    """In the twist1 recording the turning hand hid the thumb for 3-5 frames, resetting half the twists."""
    hands = twist_hands([0, 0, 0, 10]) + [hand(roll=r, thumb_tucked=False) for r in (22, 40, 60, 40, 22)] \
        + twist_hands([12, 3])
    assert [e.gesture for e in run(Twist(2, "Right"), frames(hands))] == ["twist_2"]


def test_twist_survives_an_extra_finger_and_a_one_frame_lean_mid_roll():
    """Collected twist_3: edge-on, a curled finger read as up at the peak of the roll; twist_2: the lean read -86
    degrees for one frame. Neither may reset the twist."""
    three = (True, True, True, False)
    rolls = [hand(fingers=three, roll=r) for r in (0, 0, 0, 15)] + \
        [hand(fingers=(True,) * 4, roll=60, tilt=-80)] + [hand(fingers=three, roll=r) for r in (40, 20, 3)]
    assert [e.gesture for e in run(Twist(3, "Right"), frames(rolls))] == ["twist_3"]
    # But one finger fewer mid-roll doesn't count: Twist-2 stole Twist-1's rolls that way.
    two_then_one = twist_hands([0, 0, 0, 15]) + [hand(fingers=(True, False, False, False), roll=r) for r in (40, 20, 3)]
    assert run(Twist(2, "Right"), frames(two_then_one)) == []


def test_twist_does_not_arm_on_a_hand_that_is_already_rolling():
    rolling = twist_hands([0, 40, 80, 120, 80, 40, 0])  # the pose shows only mid-roll: no still start
    assert run(Twist(2, "Right"), frames(rolling)) == []


def test_twist_1_to_3_ignore_the_thumb_but_twist_4_needs_it_tucked():
    """Collected twist_1 clips: a thumb resting on the curled fingers read "out" and blocked the start pose.
    Four fingers with the thumb out is an open palm (Brush Off, Burst), so Twist-4 keeps the rule."""
    rolls = [0, 0, 0, 15, 40, 20, 3]
    one = [hand(fingers=(True, False, False, False), thumb_tucked=False, roll=r) for r in rolls]
    assert [e.gesture for e in run(Twist(1, "Right"), frames(one))] == ["twist_1"]
    four = [hand(fingers=(True,) * 4, thumb_tucked=False, roll=r) for r in rolls]
    assert run(Twist(4, "Right"), frames(four)) == []


EDGE_ON = dict(fingers=(True,) * 4, facing="left", palm=(-0.9, 0.0, -0.4))  # hand seen edge-on


def lean(tilts, centers=None, **pose):
    return [hand(tilt=t, center=(centers[i] if centers else (0.5, 0.5)), **{**EDGE_ON, **pose})
            for i, t in enumerate(tilts)]


def test_swipe_left_and_right_from_leaning_the_hand():
    """swipeandpush, 9s and 15s: edge-on hand, fingers up, the wrist bends so the fingers sweep sideways."""
    left = lean([0, 0, 0, -15, -30, -45]) + lean([-45, -20, 0])  # ...and back upright: ignored
    assert [e.gesture for e in run(SwipeSideways("Right"), frames(left))] == ["swipe_left"]
    right = lean([0, 0, 0, 15, 30, 45], palm=(0.6, 0.0, -0.8))  # the palm turns partly to the camera
    assert [e.gesture for e in run(SwipeSideways("Right"), frames(right))] == ["swipe_right"]


def test_a_gradual_lean_counts_from_where_it_started():
    """swipedemo: leans crept -11, -18, -28, -44; measuring step by step never reached the threshold."""
    assert [e.gesture for e in run(SwipeSideways("Right"), frames(lean([-10] * 3 + [-11, -18, -28, -44])))] \
        == ["swipe_left"]


def test_leaning_back_after_a_swipe_is_not_a_swipe_the_other_way():
    """swipeandpush, Swipe Rights: the return lean fired Swipe Left between every pair."""
    there_and_back = lean([0, 0, 0, 15, 30, 45, 30, 15, 0, -10, -20])
    assert [e.gesture for e in run(SwipeSideways("Right"), frames(there_and_back))] == ["swipe_right"]


def test_back_to_back_swipes_the_other_way_count():
    """Collected left/right swipes with the rests cut short: a quick left after a right fired as another right
    (the start was taken from the previous swipe's far end, and the way back fired)."""
    rest = [-20, -21, -21, -21]
    far_end = [-67, -66, -65, -64, -60]  # the hand slows at the far end of the left swipe before coming back
    swipes = lean(rest + [-35, -50] + far_end + [-50, -35] + rest + [-2, 11, 30, 18, 0] + rest + [-40, -71, -50, -38]
                  + rest)
    assert [e.gesture for e in run(SwipeSideways("Right"), frames(swipes))] == ["swipe_left", "swipe_right",
                                                                                "swipe_left"]


def test_one_flat_frame_mid_lean_is_a_glitch():
    """swipedemo 6.43s: the palm read flat for a single frame in the middle of a real lean."""
    glitch = lean([0, 0, 0, -10]) + lean([-20], palm=(-0.15, 0.3, -0.9)) + lean([-35])
    assert [e.gesture for e in run(SwipeSideways("Right"), frames(glitch))] == ["swipe_left"]


def test_a_flat_hand_tipping_over_is_a_flip_not_a_sideways_swipe():
    """swipedemo: flips (hand flat to the camera) read as Swipe Left; leans are edge-on (|palm x| 0.65-0.9)."""
    flip = lean([0, 0, 0, -20, -45, -90], palm=(-0.1, 0.3, -0.9))
    assert run(SwipeSideways("Right"), frames(flip)) == []
    turns_flat = lean([0, 0, 0, -20]) + lean([-45, -90], palm=(-0.1, 0.3, -0.9))
    assert run(SwipeSideways("Right"), frames(turns_flat)) == []


def test_swipe_sideways_ignores_slow_leans_and_arm_movement():
    slow = lean([0, 0, 0] + [-i for i in range(0, 60, 2)])
    assert run(SwipeSideways("Right"), frames(slow)) == []
    arm = lean([0, 0, 0, -15, -30, -45], centers=[(0.5, 0.5)] * 3 + [(0.5 - 0.08 * i, 0.5) for i in range(1, 4)])
    assert run(SwipeSideways("Right"), frames(arm)) == []


def test_twist_resets_when_the_hand_leans():
    """swipeandpush: the sideways lean fired Twist-4 thirteen times."""
    hands = [hand(fingers=(True,) * 4, roll=r, tilt=t) for r, t in [(0, 0)] * 3 + [(10, -15), (40, -35), (3, -50)]]
    assert run(Twist(4, "Right"), frames(hands)) == []


UPRIGHT_HAND = hand(fingers=(True,) * 4, facing="camera", tilt=-10)
FLAT_HAND = hand(fingers=(False,) * 4, facing="camera", tilt=-90)  # fingers sideways toward the face (swipedemo)


def vertical(seq):
    return [e.gesture for e in run(SwipeVertical("Right"), frames(seq))]


def test_swipe_up_counts_once_the_hand_stays_upright_and_the_flip_down_is_nothing():
    assert vertical([FLAT_HAND] * 6 + [UPRIGHT_HAND] * 12) == ["swipe_up"]
    assert vertical([UPRIGHT_HAND] * 6 + [FLAT_HAND] * 12) == []  # no Swipe Down
    pointing_at_screen = hand(fingers=(False,) * 4, facing="down", tilt=-150)  # swipeandpush's flat pose
    assert vertical([pointing_at_screen] * 6 + [UPRIGHT_HAND] * 12) == ["swipe_up"]
    pointing = hand(fingers=(True, False, False, False), facing="camera", tilt=-10)  # finger up: not upright, not flat
    assert vertical([FLAT_HAND] * 6 + [UPRIGHT_HAND] * 4 + [pointing] * 10) == ["swipe_up"]  # ending in another pose
    state.overview_open = True
    try:
        assert vertical([FLAT_HAND] * 6 + [UPRIGHT_HAND] * 12) == []  # not during Mission Control
    finally:
        state.overview_open = False


def test_the_quick_prep_or_return_of_a_swipe_is_not_a_swipe():
    """swipeandpush, Swipe Ups: the hand lingered upright (the end) and dipped flat only briefly (the prep)."""
    ups = ([UPRIGHT_HAND] * 12 + [FLAT_HAND] * 4) * 3 + [UPRIGHT_HAND] * 12
    assert vertical(ups) == ["swipe_up"] * 3


def test_lingering_flat_mid_run_fires_nothing_extra():
    """swipeandpush 30s: mid-run the hand lingered flat a little longer once (it read as a Swipe Down before)."""
    up, flat = [UPRIGHT_HAND], [FLAT_HAND]
    run = up * 12 + flat * 4 + up * 12 + flat * 4 + up * 12 + flat * 14 + up * 13
    assert vertical(run) == ["swipe_up"] * 3


def test_swipe_vertical_ignores_arm_movement():
    moved = hand(fingers=(True,) * 4, facing="camera", tilt=-10, wrist=(0.5, 0.2))  # 3 hand sizes away
    assert vertical([FLAT_HAND] * 6 + [moved] * 12) == []


def sweep(frac, xs):
    return [feats(i * DT, motion=(frac, x)) for i, x in enumerate(xs)]


def test_motion_sweeps_are_hand_swipe_or_lens_wipe_by_size():
    across = [0.2 + 0.07 * i for i in range(8)]
    assert [e.gesture for e in run(MotionSweep(), sweep(0.2, across))] == ["hand_swipe"]
    assert [e.gesture for e in run(MotionSweep(), sweep(0.7, across))] == ["lens_wipe"]
    assert run(MotionSweep(), sweep(0.7, [0.5] * 8)) == []  # e.g. the camera adjusting brightness: no travel


def test_walk_away_waits_for_absence_and_no_input():
    gone = [feats(t, body=False, idle=t) for t in range(20)]
    events = run(WalkAway(15), gone)
    assert [(e.gesture, e.t) for e in events] == [("walk_away", 15)]
    looking_at_phone = [feats(t, body=True, idle=t) for t in range(20)]
    assert run(WalkAway(15), looking_at_phone) == []


EAR_ONE = dict(fingers=(True, False, False, False), ear_dist=0.2, depth_ratio=0.7)  # beside the head, not in front


def ear_visit(stay_frames, exit_tip, fingers=(True, False, False, False)):
    """A fingertip comes to the ear (ear_dist 0.1), stays, and leaves (ear_dist 0.6) to exit_tip."""
    at = [hand(tip=(0.5, 0.5), fingers=fingers, ear_dist=0.1, depth_ratio=0.6)] * stay_frames  # beside the head
    return [hand(tip=(0.5, 0.8), ear_dist=0.9)] + at + [hand(tip=exit_tip, fingers=fingers, ear_dist=0.6)]


def test_ear_gestures_are_judged_when_the_finger_leaves_the_ear():
    gesture = lambda stream: [e.gesture for e in run(EarTapUpDown("Right"), frames(stream))]  # noqa: E731
    assert gesture(ear_visit(12, (0.5, 0.3))) == ["ear_up"]  # leaves upward (0.2 = 0.67 shoulder widths)
    assert gesture(ear_visit(12, (0.5, 0.6))) == ["ear_down"]  # stayed 0.4s, leaves downward
    assert gesture(ear_visit(6, (0.6, 0.5))) == ["ear_tap"]  # a short visit, leaving sideways
    assert gesture(ear_visit(6, (0.5, 0.5))[:-1] + [None]) == ["ear_tap"]  # ...or leaving the picture
    assert gesture(ear_visit(2, (0.5, 0.6))) == []  # passing by
    assert gesture(ear_visit(80, (0.5, 0.6))) == []  # resting on the head
    assert gesture(ear_visit(12, (0.5, 0.6), fingers=(False,) * 4)) == []  # a fist or a scratch: not pointing
    in_front = [hand(tip=(0.5, 0.5), fingers=(True, False, False, False), ear_dist=0.1)] * 12  # overlaps the ear in 2D
    assert gesture(in_front + [hand(tip=(0.5, 0.3), ear_dist=0.6)]) == []


def test_ear_hold_begins_on_press_and_always_ends():
    tube = dict(fingers=(True, True, False, False), depth_ratio=0.7)
    hold = [hand(ear_dist=0.3, **tube)] * 3 + [hand(ear_dist=0.2, **tube)] * 3
    events = run(EarHold("Right"), frames(hold + [None] * 5))  # hand leaves the frame mid-hold
    assert [(e.gesture, e.phase) for e in events] == [("ear_hold", "begin"), ("ear_hold", "end")]
    assert events[1].data["lost"]
    blip = run(EarHold("Right"), frames(hold + [None] + hold[-2:]))  # tracking misses the hand for one frame
    assert [e.phase for e in blip] == ["begin"]


def test_brush_off_flips_a_held_palm_to_the_camera():
    pose = dict(fingers=(True,) * 4, thumb_tucked=False)
    held = [hand(facing="left", palm=(-0.8, 0, 0.6), tip=(0.5, 0.5), **pose)] * 10  # 0.33s, angled toward you
    flick = [hand(facing="camera", palm=(-0.3, 0, -0.95), tip=(0.53, 0.5), **pose)]
    assert [e.gesture for e in run(BrushOff("Right"), frames(held + flick))] == ["brush_off"]
    # A twist's roll passes through the same palm direction for a frame or two: not held, so nothing fires.
    passing = [hand(palm=(0, 0, -1), tip=(0.5, 0.5), **pose)] * 5 + held[:2] + flick
    assert run(BrushOff("Right"), frames(passing)) == []
    # Turning only to edge-on (palm sideways) is a swipe's lean, not a Brush Off.
    sideways = [hand(facing="right", palm=(1, 0, 0), tip=(0.53, 0.5), **pose)]
    assert run(BrushOff("Right"), frames(held + sideways)) == []


def burst():
    return ShapeChange("burst", "Right", "fist", "open")


def test_burst():
    fist = [hand(fingers=(False,) * 4)] * 3
    open_hand = [hand(fingers=(True,) * 4, thumb_tucked=False)]
    assert [e.gesture for e in run(burst(), frames(fist + open_hand))] == ["burst"]


def test_burst_needs_the_thumb_out():
    """demo1: raising a fist into the Twist-4 pose (four fingers, thumb tucked) fired Burst."""
    fist = [hand(fingers=(False,) * 4)] * 3
    twist_4_pose = [hand(fingers=(True,) * 4, thumb_tucked=True)]
    assert run(burst(), frames(fist + twist_4_pose)) == []


def test_burst_needs_the_palm_facing_the_camera():
    fist = [hand(fingers=(False,) * 4, facing="user")] * 3
    open_hand = [hand(fingers=(True,) * 4, thumb_tucked=False, facing="user")]
    assert run(burst(), frames(fist + open_hand)) == []


def test_flick_snaps_the_open_hand_out_and_back():
    open_hand = dict(fingers=(True,) * 4)
    snap = [hand(center=(0.5, 0.5), **open_hand)] * 3 + [hand(center=(0.45, 0.5), **open_hand),
                                                         hand(center=(0.5, 0.5), **open_hand)]
    state.overview_open = False
    assert run(Flick("Right"), frames(snap)) == []  # overview closed
    state.overview_open = True
    try:
        events = run(Flick("Right"), frames(snap))
    finally:
        state.overview_open = False
    assert [(e.phase, e.data.get("angle")) for e in events] == [("begin", 180), ("end", None)]
    assert events[1].data["chosen"]


def test_point_aims_where_the_hand_points_and_a_pinch_chooses():
    open_hand = dict(fingers=(True,) * 4)  # thumb and index apart (pinch 1.0)
    pinch = hand(fingers=(False, True, True, True), pinch=0.1, aim=(0.5, -0.6))  # index bent to the thumb
    at_screen = [hand(aim=(0.05, -0.1), **open_hand)] * 3  # neutral: nothing lit
    right = [hand(aim=(0.9, 0.0), **open_hand)] * 3
    up_right = [hand(aim=(0.6, -0.7), **open_hand)] * 3  # y points down in the image
    fist = hand(fingers=(False,) * 4, pinch=0.2, aim=(0.6, -0.7), index_reach=0.35)  # index tip folded in
    state.overview_open = True
    try:
        events = run(Point("Right"), frames(at_screen + right + up_right + at_screen + [pinch]))
        neutral_pinch = run(Point("Right"), frames(at_screen * 5 + [hand(aim=(0.05, -0.1), pinch=0.1)]))
        straight_up = run(Point("Right"), frames([hand(aim=(0.0, -0.9), **open_hand)] * 3))
        fisted = run(Point("Right"), frames(up_right + [fist] * 3))
        pinched_all_along = run(Point("Right"), frames([hand(aim=(0.9, 0.0), pinch=0.1)] * 6))
    finally:
        state.overview_open = False
    assert [(e.phase, e.data.get("angle")) for e in events[:2]] == [("begin", 0), ("update", 49)]
    assert events[-1].phase == "end" and events[-1].data["chosen"]  # the lit window survives passing through neutral
    assert events[-1].data["angle"] == 49  # where the finger pointed while thumb and index were apart
    assert neutral_pinch == []  # nothing lit, nothing chosen
    assert straight_up[0].data["angle"] == 90  # starting already pointed up selects the top right away
    assert all(e.phase != "end" for e in fisted)  # a fist (Unburst) isn't a pinch
    assert all(e.phase != "end" for e in pinched_all_along)  # pinched from the start: open it first
    assert run(Point("Right"), frames(right + [pinch])) == []  # overview closed


def test_ear_jitter_and_continued_motion_fire_at_most_once():
    jitter = [hand(tip=(0.5 + (0.008 if i % 2 else -0.008), 0.5), **EAR_ONE) for i in range(30)]
    assert run(EarTapUpDown("Right"), frames(jitter)) == []  # the first recording fired ~30 times on this
    up_and_keep_going = ear_visit(6, (0.5, 0.3)) + [hand(tip=(0.5, 0.3 - 0.03 * i), ear_dist=0.6 + 0.1 * i)
                                                    for i in range(1, 8)]
    assert len(run(EarTapUpDown("Right"), frames(up_and_keep_going))) == 1


def test_hands_at_face_depth_are_ignored():
    """Hands touching the face or in the hair (second recording) opened and closed into Bursts."""
    fist = [hand(fingers=(False,) * 4, depth_ratio=0.6)] * 3
    open_hand = [hand(fingers=(True,) * 4, thumb_tucked=False, depth_ratio=0.6)]
    assert run(burst(), frames(fist + open_hand)) == []
    pose = dict(fingers=(True,) * 4, thumb_tucked=False, depth_ratio=0.6)
    start = [hand(facing="user", palm=(0, 0, 1), tip=(0.5, 0.5), **pose)] * 3
    flick = [hand(facing="right", palm=(1, 0, 0), tip=(0.6, 0.5), **pose)]
    assert run(BrushOff("Right"), frames(start + flick)) == []
