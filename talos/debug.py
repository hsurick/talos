"""Debug window: camera image, tracked points, feature numbers, gesture states, recent events, and fps / CPU / memory."""
import resource
import time

import cv2
import numpy as np
from mediapipe.tasks.python.vision import HandLandmarksConnections

from talos.features import LEFT_EAR, LEFT_SHOULDER, NOSE, RIGHT_EAR, RIGHT_SHOULDER

CONNECTIONS = [(c.start, c.end) for c in HandLandmarksConnections.HAND_CONNECTIONS]
BODY_POINTS = (NOSE, LEFT_EAR, RIGHT_EAR, LEFT_SHOULDER, RIGHT_SHOULDER)
WINDOW = "Talos debug"
HEIGHT, PANEL, LINE = 720, 640, 32  # window height, text panel width, line spacing (pixels)
FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE, GREEN, YELLOW, BLUE, GREY = (240, 240, 240), (140, 255, 140), (0, 220, 255), (255, 200, 80), (150, 150, 150)


class Stats:
    """Frame rate, CPU and peak memory; also printed every 10 seconds for the 10-minute idle test."""

    def __init__(self):
        self.wall, self.cpu = time.monotonic(), time.process_time()
        self.frames, self.text, self.printed = 0, "", self.wall

    def tick(self):
        self.frames += 1
        now = time.monotonic()
        if now - self.wall >= 1:
            cpu = (time.process_time() - self.cpu) / (now - self.wall) * 100
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6  # bytes on macOS
            self.text = f"{self.frames / (now - self.wall):.0f} fps  CPU {cpu:.0f}%  peak mem {mem:.0f} MB"
            self.wall, self.cpu, self.frames = now, time.process_time(), 0
            if now - self.printed >= 10:
                print(self.text)
                self.printed = now
        return self.text


def show(frame, features, recognizers, events, stats, banner=(), footer=None):
    """Draw one frame. Returns False when the user presses q or Esc, otherwise the key pressed (255 = none).
    banner = [(text, color, size)] lines drawn on top of the image; footer = one line at its bottom."""
    img = frame.image.copy()
    h, w = img.shape[:2]
    px = lambda p: (int(p[0] * w), int(p[1] * h))  # noqa: E731
    for hand in frame.hands:
        pts = [px(p) for p in hand["pts"]]
        for a, b in CONNECTIONS:
            cv2.line(img, pts[a], pts[b], (80, 220, 80), 2)
        for p in pts:
            cv2.circle(img, p, 3, (255, 255, 255), -1)
    if frame.body:
        for i in BODY_POINTS:
            cv2.circle(img, px(frame.body[i]), 5, (255, 160, 0), -1)

    # Text goes in its own panel beside the image, at a fixed size, so it stays readable and never overlaps.
    img = cv2.resize(img, (int(w * HEIGHT / h), HEIGHT))
    y = 0
    if banner:
        cv2.rectangle(img, (0, 0), (img.shape[1], sum(int(45 * s) + 12 for *_, s in banner) + 16), (30, 30, 30), -1)
    for text, color, size in banner:
        y += int(45 * size) + 12
        cv2.putText(img, text, (20, y), FONT, size, color, max(1, round(2.5 * size)), cv2.LINE_AA)
    if footer:
        cv2.rectangle(img, (0, HEIGHT - 44), (img.shape[1], HEIGHT), (30, 30, 30), -1)
        cv2.putText(img, footer, (20, HEIGHT - 14), FONT, 0.7, WHITE, 2, cv2.LINE_AA)
    panel = np.full((HEIGHT, PANEL, 3), 30, np.uint8)
    lines = [(stats, WHITE),
             (f"person {'yes' if features.body_present else 'no'}   idle {features.idle:.0f}s   "
              f"motion {features.motion[0]:.2f}", WHITE), ("", WHITE)]
    for side, f in sorted(features.hands.items()):
        fingers = "".join(c if up else "." for c, up in zip("IMRP", f.fingers))
        ear = "-" if f.ear_dist is None else f"{f.ear_dist:.2f}"
        lines += [(f"{side} hand: {fingers}  {f.fingers_up} up   thumb {'tucked' if f.thumb_tucked else 'out'}", GREEN),
                  (f"   palm {f.facing}   roll {f.roll:.0f}   tilt {f.tilt:.0f}", GREEN),
                  (f"   ear {ear}   {'raised' if f.raised else 'low'}", GREEN),
                  (f"   hand/head {'-' if f.depth_ratio is None else f'{f.depth_ratio:.2f}'}   "
                   f"{'in front' if f.in_front else 'at face'}", GREEN), ("", WHITE)]
    lines += [(f"{r.name} [{r.side or 'frame'}]: {r.state}", YELLOW) for r in recognizers if r.state != "idle"]
    for i, (line, color) in enumerate(lines):
        cv2.putText(panel, line, (16, 36 + LINE * i), FONT, 0.75, color, 2, cv2.LINE_AA)
    for i, line in enumerate(reversed(events[-6:])):  # newest at the bottom
        cv2.putText(panel, line.strip()[:64], (16, HEIGHT - 20 - LINE * i), FONT, 0.6, BLUE, 1, cv2.LINE_AA)
    cv2.imshow(WINDOW, np.hstack([img, panel]))
    key = cv2.waitKey(1) & 0xFF
    return False if key in (ord("q"), 27) else key
