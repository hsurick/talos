from talos import features
from tests.helpers import frame, landmarks


def one_hand(**kw):
    return features.compute(frame(hands=[("Right", landmarks(**kw))])).hands["Right"]


def test_counts_extended_fingers_and_thumb():
    h = one_hand(fingers=(True, True, False, False), thumb_tucked=True)
    assert h.fingers == (True, True, False, False) and h.fingers_up == 2 and h.thumb_tucked
    assert not one_hand(thumb_tucked=False).thumb_tucked


def test_palm_to_camera():
    assert one_hand().facing == "camera"


def test_left_hand_mirrored_also_faces_camera():
    pts = [[1 - x, y, z] for x, y, z in landmarks()]  # mirror image of the right hand = a left hand
    assert features.compute(frame(hands=[("Left", pts)])).hands["Left"].facing == "camera"


def test_roll_follows_rotation_about_finger_axis():
    assert abs(one_hand(yaw=25).roll - one_hand().roll - 25) < 1


def test_edge_on_hand_faces_sideways():
    assert one_hand(yaw=90).facing in ("left", "right")


def test_near_ear_uses_body_points():
    body = [[0.5, 0.5, 0, 1]] * 33
    body[features.LEFT_EAR] = [0.45, 0.45, 0, 1]   # index tip of landmarks() is at (0.45, 0.4)
    body[features.RIGHT_EAR] = [0.9, 0.45, 0, 1]
    body[features.LEFT_SHOULDER] = [0.3, 0.9, 0, 1]
    body[features.RIGHT_SHOULDER] = [0.7, 0.9, 0, 1]
    h = features.compute(frame(hands=[("Right", landmarks())], body=body)).hands["Right"]
    assert h.near_ear and h.raised


def body_with_ears(left_x, right_x):
    body = [[0.5, 0.5, 0, 1]] * 33
    body[features.LEFT_EAR], body[features.RIGHT_EAR] = [left_x, 0.4, 0, 1], [right_x, 0.4, 0, 1]
    body[features.LEFT_SHOULDER], body[features.RIGHT_SHOULDER] = [0.3, 0.9, 0, 1], [0.7, 0.9, 0, 1]
    return body


def test_hand_in_front_of_face_compares_hand_size_to_head_size():
    hand_pts = [("Right", landmarks())]  # appears 0.22 long in the image
    near = features.compute(frame(hands=hand_pts, body=body_with_ears(0.4, 0.6))).hands["Right"]   # head 0.2 wide
    level = features.compute(frame(hands=hand_pts, body=body_with_ears(0.3, 0.75))).hands["Right"]  # head 0.45 wide
    assert near.in_front and not level.in_front
