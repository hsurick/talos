"""Window overview: Apple's Mission Control. Window thumbnails are found through the Dock's accessibility tree, a
blue ring is drawn over the one you're aiming at, and it's chosen by pressing that thumbnail. Picks by direction
only."""
import math
import subprocess

import AppKit
import ApplicationServices as AX
import CoreFoundation
import objc

from talos import state
from talos.actions import action
from talos.actions.system import KEYS, tap
from talos.actions.windows import ax_frame, ax_get

# buttons: the thumbnails; highlight: the one aimed at; ring: the highlight panel; lit: the button it's drawn over;
# observer: the Dock's Mission Control notifications
mission = {"buttons": [], "highlight": None, "ring": None, "lit": None, "observer": None}
RING = 8  # points the highlight sticks out around the thumbnail


def _dock():
    return AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.apple.dock")[0]


@objc.callbackFor(AX.AXObserverCreate)  # the C callback signature PyObjC needs
def _on_dock(observer, element, notification, refcon):
    """The Dock announces Mission Control opening and closing, however it happens (a gesture, F3, Escape, a click,
    a trackpad swipe). Closing arrives ~0.3s after Escape, as the thumbnails disappear. Opening by hand counts too,
    so Point and Flick work in a Mission Control opened with F3."""
    state.overview_open = notification == "AXExposeShowAllWindows"
    mission.update(buttons=[], highlight=None)


def _watch_dock():
    """No polling: subscribe once to the Dock's Mission Control notifications (found by testing: the Dock app posts
    AXExposeShowAllWindows / AXExposeExit; a destroyed-element notification on Mission Control's group never came)."""
    err, observer = AX.AXObserverCreate(_dock().processIdentifier(), _on_dock, None)
    if err:
        mission["observer"] = False  # don't retry every frame
        return
    app = AX.AXUIElementCreateApplication(_dock().processIdentifier())
    for note in ("AXExposeShowAllWindows", "AXExposeExit"):
        AX.AXObserverAddNotification(observer, app, note, None)
    CoreFoundation.CFRunLoopAddSource(CoreFoundation.CFRunLoopGetMain(), AX.AXObserverGetRunLoopSource(observer),
                                      CoreFoundation.kCFRunLoopDefaultMode)
    mission["observer"] = observer  # kept alive for the app's lifetime


def _angle_gap(a, b):
    return abs((a - b + 180) % 360 - 180)


def dock_buttons():
    """Window thumbnails in an open Mission Control: the titled buttons in the Dock's "mc" group. Skipped: the
    Spaces bar along the top (Desktop buttons) and an untitled button (macOS 15)."""
    found, stack = [], [(AX.AXUIElementCreateApplication(_dock().processIdentifier()), False)]
    while stack:
        el, inside = stack.pop()
        ident = ax_get(el, "AXIdentifier") or ""
        if ident == "mc.spaces":
            continue
        inside = inside or ident == "mc" or ax_get(el, "AXTitle") == "Mission Control"
        if inside and ax_get(el, "AXRole") == "AXButton" and ax_get(el, "AXPosition") and ax_get(el, "AXTitle"):
            found.append(el)
        stack += [(c, inside) for c in ax_get(el, "AXChildren") or []]
    return found


@action("open_overview")
def open_overview(event, arg):
    """Opens Mission Control; with it open, closes it."""
    if state.overview_open:
        close_overview(event, arg)
        return
    subprocess.run(["open", "-a", "Mission Control"], timeout=5)
    mission.update(buttons=[], highlight=None)
    state.overview_open = True


@action("close_overview")
def close_overview(event, arg):
    if not state.overview_open:
        return
    tap(KEYS["escape"])
    state.overview_open = False


@action("select_window", phases=("begin", "update", "end"))
def select_window(event, arg):
    if not state.overview_open:
        return
    if "angle" in event.data:  # begin / update: the aim moved; end: where Point aimed before the pinch
        buttons = mission["buttons"] = mission["buttons"] or dock_buttons()
        if not buttons:
            return
        screen = AppKit.NSScreen.screens()[0].frame().size
        cx, cy = screen.width / 2, screen.height / 2

        def gap(b):
            frame = ax_frame(b)
            if frame is None:
                return 360  # gone
            x, y, w, h = frame
            return _angle_gap(math.degrees(math.atan2(cy - (y + h / 2), x + w / 2 - cx)), event.data["angle"])
        mission["highlight"] = min(buttons, key=gap)
    if event.phase == "end" and event.data.get("chosen") and mission["highlight"] is not None:
        chosen, mission["highlight"] = mission["highlight"], None  # not chosen: stays lit
        AX.AXUIElementPerformAction(chosen, "AXPress")
        state.overview_open = False


def overlay_panel(frame):
    """A clear, borderless panel that floats above everything (full-screen apps too), lets clicks through, and never
    takes focus, so the app you were in stays active. Also used by the app's feedback popup."""
    AppKit.NSApplication.sharedApplication()  # AppKit windows need the app object (OpenCV makes it in live runs)
    panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
        AppKit.NSBackingStoreBuffered, False)
    panel.setLevel_(AppKit.NSScreenSaverWindowLevel)
    panel.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                 | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(AppKit.NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHidesOnDeactivate_(False)
    return panel


def _draw_ring():
    """Mission Control has no highlight of its own: a blue rounded ring over the thumbnail being aimed at."""
    ring, lit = mission["ring"], mission["highlight"] if state.overview_open else None
    if lit is mission["lit"]:
        return
    mission["lit"] = lit
    if lit is None:
        if ring is not None:
            ring.orderOut_(None)
        return
    if ring is None:
        ring = mission["ring"] = overlay_panel(((0, 0), (10, 10)))
        box = ring.contentView()
        box.setWantsLayer_(True)
        box.layer().setCornerRadius_(14)
        box.layer().setBorderWidth_(6)
        box.layer().setBorderColor_(AppKit.NSColor.systemBlueColor().CGColor())
    frame = ax_frame(lit)
    if frame is None:  # the thumbnail is gone: Mission Control closed
        ring.orderOut_(None)
        mission["highlight"] = mission["lit"] = None
        return
    x, y, w, h = frame
    top = AppKit.NSScreen.screens()[0].frame().size.height  # accessibility y points down from the top, AppKit's up
    ring.setFrame_display_(((x - RING, top - y - h - RING), (w + 2 * RING, h + 2 * RING)), True)
    ring.orderFrontRegardless()


def draw():
    """Called on the main thread every frame (AppKit windows may only be touched there): shows, moves or hides the
    highlight over Mission Control."""
    if mission["observer"] is None:
        _watch_dock()
    _draw_ring()
    if not AppKit.NSApp() or not AppKit.NSApp().isRunning():  # the menu-bar app runs its own loop; CLI runs don't
        AppKit.NSRunLoop.currentRunLoop().runUntilDate_(AppKit.NSDate.dateWithTimeIntervalSinceNow_(0.001))
