"""Window actions through the Accessibility API: focus an app, snap the front window to a half or the next monitor,
zoom it."""
import subprocess

import AppKit
import ApplicationServices as AX
import Quartz

from talos.actions import action


def ax_get(element, attr):
    err, value = AX.AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == 0 else None


def ax_frame(window):
    """(x, y, width, height), or None once the element is gone (a Mission Control thumbnail after it closed)."""
    pos, size = ax_get(window, "AXPosition"), ax_get(window, "AXSize")
    if pos is None or size is None:
        return None
    _, pos = AX.AXValueGetValue(pos, AX.kAXValueCGPointType, None)
    _, size = AX.AXValueGetValue(size, AX.kAXValueCGSizeType, None)
    return pos.x, pos.y, size.width, size.height


def ax_set_frame(window, x, y, w, h):
    AX.AXUIElementSetAttributeValue(window, "AXPosition", AX.AXValueCreate(AX.kAXValueCGPointType, Quartz.CGPoint(x, y)))
    AX.AXUIElementSetAttributeValue(window, "AXSize", AX.AXValueCreate(AX.kAXValueCGSizeType, Quartz.CGSize(w, h)))


def front_window():
    if not AX.AXIsProcessTrusted():
        raise PermissionError("Allow your terminal app in System Settings > Privacy & Security > Accessibility.")
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    return ax_get(AX.AXUIElementCreateApplication(app.processIdentifier()), "AXFocusedWindow")


def screens():
    """Usable area of each monitor (no menu bar or Dock), left to right, in Accessibility coordinates (top-left origin)."""
    main_height = AppKit.NSScreen.screens()[0].frame().size.height
    out = []
    for s in AppKit.NSScreen.screens():
        v = s.visibleFrame()
        out.append((v.origin.x, main_height - v.origin.y - v.size.height, v.size.width, v.size.height))
    return sorted(out)


def _close(a, b, tol=12):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def half(screen, side):
    x, y, w, h = screen
    return (x, y, w / 2, h) if side == "left" else (x + w / 2, y, w / 2, h)


def snap_target(window, monitors, side):
    """Where a window goes: that half of its monitor, or, if already there, the next monitor in that direction."""
    cx, cy = window[0] + window[2] / 2, window[1] + window[3] / 2
    i = min(range(len(monitors)), key=lambda k: abs(monitors[k][0] + monitors[k][2] / 2 - cx)
            + abs(monitors[k][1] + monitors[k][3] / 2 - cy))
    if not _close(window, half(monitors[i], side)):
        return half(monitors[i], side)
    j = i + (1 if side == "right" else -1)
    if 0 <= j < len(monitors):
        return half(monitors[j], "left" if side == "right" else "right")  # keep travelling in the swipe direction
    return None


@action("snap_window")
def snap_window(event, side):
    window = front_window()
    if window is None:
        return
    frame = ax_frame(window)
    if frame is None:
        return
    target = snap_target(frame, screens(), side)
    if target:
        ax_set_frame(window, *target)


@action("zoom_window")
def zoom_window(event, arg):
    """The front app's Window > Zoom: grows the window to fit its content or the screen, and back (not the
    green button, which goes full screen). Apps without that menu item: the window's zoom button."""
    front_window()  # checks the Accessibility permission
    app = AX.AXUIElementCreateApplication(AppKit.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier())
    for bar_item in ax_get(ax_get(app, "AXMenuBar"), "AXChildren") or []:
        if ax_get(bar_item, "AXTitle") == "Window":  # shortcut: English menu titles only; localize if needed
            for menu in ax_get(bar_item, "AXChildren") or []:
                for item in ax_get(menu, "AXChildren") or []:
                    if ax_get(item, "AXTitle") == "Zoom":
                        AX.AXUIElementPerformAction(item, "AXPress")
                        return
    button = ax_get(ax_get(app, "AXFocusedWindow"), "AXZoomButton")
    if button is not None:
        AX.AXUIElementPerformAction(button, "AXPress")


@action("focus_app")
def focus_app(event, name):
    subprocess.run(["open", "-a", name], timeout=10)
