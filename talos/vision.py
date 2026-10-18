"""Camera loop + MediaPipe tracking: camera frames in, tracked points out. No gesture logic."""
import threading
import time
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision as mpv

from talos import ROOT

MODELS = ROOT / "models"
HAND_MODEL = MODELS / "hand_landmarker.task"
POSE_MODEL = MODELS / "pose_landmarker_lite.task"
MOTION_LEVEL = 25  # grayscale change between frames above which a pixel counts as moving
# CPU savings (hand model ~10 ms/frame, body ~7 ms): the body changes slowly, and with no hand in view and
# nothing moving there is nothing for the hand model to find; a hand coming into view makes motion.
BODY_EVERY = 3     # run the body model on every 3rd frame, reusing its result in between
STILL = 0.01       # below this much motion, with no hand in the last frame, skip the hand model
# On our mirrored image MediaPipe labels each hand as the other one (the first live recording showed
# a right hand as "Left", which also flipped every palm direction), so swap the label.
SWAP = {"Left": "Right", "Right": "Left"}


@dataclass
class Frame:
    t: float            # seconds since start, taken when the camera delivered the image
    aspect: float       # width / height, so x and y can be put on the same scale
    hands: list         # [{"side": "Left" | "Right", "pts": [[x, y, z] * 21], "world": (meters, optional)}]
    body: list | None   # [[x, y, z, visibility] * 33], or None when no person is seen
    idle: float         # seconds since the last keyboard or mouse input
    motion: tuple       # (fraction of the image that changed since the last frame, x of the change or None)
    image: np.ndarray | None = None  # mirrored camera image for the debug window; never saved


def idle_seconds():
    import Quartz
    return Quartz.CGEventSourceSecondsSinceLastEventType(
        Quartz.kCGEventSourceStateHIDSystemState, Quartz.kCGAnyInputEventType)


def small_gray(image):
    return cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (32, 18)).astype(np.int16)


def motion_stats(small, prev):
    """Whole-image motion, for sweeps too fast or too close for hand tracking (Hand Swipe, Lens Wipe)."""
    if prev is None:
        return 0.0, None
    mask = np.abs(small - prev) > MOTION_LEVEL
    x = float(np.nonzero(mask)[1].mean() / 31) if mask.any() else None
    return float(mask.mean()), x


class Camera:
    """Reads frames on its own thread and keeps only the newest, so a slow model drops frames instead of lagging."""

    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise SystemExit("Camera not available. Allow your terminal app in System Settings > Privacy & Security > Camera.")
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.latest = None
        self.running = True
        self.cond = threading.Condition()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            ok, image = self.cap.read()
            with self.cond:
                if not ok:
                    self.running = False
                else:
                    self.latest = (time.monotonic(), image)
                self.cond.notify()

    def read(self):
        with self.cond:
            while self.latest is None:
                if not self.running:
                    raise SystemExit("Camera stopped returning frames.")
                self.cond.wait(1)
            frame, self.latest = self.latest, None
        return frame

    def close(self):
        self.running = False
        self.thread.join(timeout=2)  # releasing while the thread is mid-read crashed Python on quit
        self.cap.release()


def frames(camera=0):
    for model in (HAND_MODEL, POSE_MODEL):
        if not model.exists():
            raise SystemExit(f"Missing {model}. See README.md for the download command.")
    base = mp.tasks.BaseOptions
    hands = mpv.HandLandmarker.create_from_options(mpv.HandLandmarkerOptions(
        base_options=base(model_asset_path=str(HAND_MODEL)), running_mode=mpv.RunningMode.VIDEO, num_hands=2))
    body = mpv.PoseLandmarker.create_from_options(mpv.PoseLandmarkerOptions(
        base_options=base(model_asset_path=str(POSE_MODEL)), running_mode=mpv.RunningMode.VIDEO))
    cam = Camera(camera)
    start, last_ms, prev, n, found, person = None, -1, None, 0, [], None
    try:
        while True:
            taken, image = cam.read()
            start = start or taken
            # Mirror once here: x then matches the user's left/right.
            image = cv2.flip(image, 1)
            t = taken - start
            ms = last_ms = max(int(t * 1000), last_ms + 1)  # MediaPipe needs strictly increasing timestamps
            small = small_gray(image)
            motion, prev = motion_stats(small, prev), small
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            if found or motion[0] >= STILL:
                h = hands.detect_for_video(mp_image, ms)
                # world: the same points in meters around the hand's center; steadier depth than pts' z
                found = [{"side": SWAP[side[0].category_name], "pts": [[p.x, p.y, p.z] for p in pts],
                          "world": [[p.x, p.y, p.z] for p in world]}
                         for side, pts, world in zip(h.handedness, h.hand_landmarks, h.hand_world_landmarks)]
            if n % BODY_EVERY == 0:
                b = body.detect_for_video(mp_image, ms)
                person = [[p.x, p.y, p.z, p.visibility] for p in b.pose_landmarks[0]] if b.pose_landmarks else None
            n += 1
            height, width = image.shape[:2]
            yield Frame(
                t=t,
                aspect=width / height,
                hands=found,
                body=person,
                idle=idle_seconds(),
                motion=motion,
                image=image,
            )
    finally:
        cam.close()
        hands.close()
        body.close()
