"""Made-up hands and feature streams for tests."""
import math

from talos.features import Features, Hand
from talos.vision import Frame


def landmarks(fingers=(True, True, True, True), thumb_tucked=False, yaw=0.0, dx=0.0):
    """21 points of a right hand, palm to the camera, fingers up, in a mirrored image; yaw rotates it about the vertical axis."""
    wrist = (0.5, 0.8, 0.0)
    mcps = [(0.45, 0.6), (0.5, 0.58), (0.55, 0.6), (0.6, 0.62)]
    pts = [wrist, (0.42, 0.75), (0.38, 0.7), (0.36, 0.67), (0.5, 0.54) if thumb_tucked else (0.33, 0.65)]
    for (x, y), up in zip(mcps, fingers):
        pts += [(x, y), (x, y - 0.1), (x, y - 0.15), (x, y - 0.2)] if up else \
               [(x, y), (x, y - 0.06), (x + 0.005, y - 0.02), (x + 0.01, y + 0.02)]
    a = math.radians(yaw)
    out = []
    for p in pts:
        x, y = p[0] - wrist[0], p[1]
        out.append([wrist[0] + dx + x * math.cos(a), y, x * math.sin(a)])
    return out


def frame(t=0.0, hands=(), body=None, idle=100.0, motion=(0.0, None)):
    return Frame(t, 1.0, [{"side": s, "pts": p} for s, p in hands], body, idle, motion)


def hand(side="Right", fingers=(True, True, False, False), thumb_tucked=True, facing="camera", roll=0.0,
         tilt=0.0, center=(0.5, 0.5), tip=None, size=0.1, raised=True, ear_dist=None, palm=(0, 0, -1),
         shoulder=0.3, depth_ratio=1.0, wrist=None, aim=(0.0, 0.0), pinch=1.0, index_reach=1.0):
    return Hand(side, fingers, thumb_tucked, palm, facing, roll, tilt, center, tip or center, size, raised,
                ear_dist, shoulder, depth_ratio, wrist or center, aim, pinch, index_reach)


def feats(t, *hands, body=True, idle=0.0, motion=(0.0, None)):
    return Features(t, {h.side: h for h in hands}, body, idle, motion)


def run(recognizer, stream):
    """Feed (t, Features) pairs; return every event produced."""
    return [e for f in stream for e in recognizer.update(f)]
