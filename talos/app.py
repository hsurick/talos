"""Menu-bar app (stage 3): an icon with camera on/off, start at login, open config, the event log, and "that was
a mistake"; plus a small popup naming each recognized gesture and the action it ran (tells a missed gesture
apart from a failed action).
The camera pipeline runs on its own thread. Everything on screen is drawn from a timer on the main thread,
because AppKit may only be used there.

  python -m talos app      run it from the terminal (permissions then belong to the terminal app)
  Talos.app                the same, bundled (see setup.py); permissions belong to Talos
"""
import collections
import datetime
import plistlib
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import AppKit
import rumps

from talos import actions, state
from talos.actions import overview
from talos.bindings import Bindings
from talos.prefs import readable

BUNDLE_ID = "com.talos.app"  # setup.py gives Talos.app this id
LOG = Path.home() / "Library" / "Logs" / "Talos" / "events.log"  # macOS's place for app logs; Console.app opens it
AGENT = Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.plist"  # a launch agent starts it at login
# Menu-bar icon, SF Symbols drawn as template images (monochrome, follow light/dark like other menu-bar icons):
# the same hand, crossed out while the camera is off.
ON, OFF = "hand.raised.fill", "hand.raised.slash"
POPUP_W, POPUP_H, POPUP_TIME = 460, 56, 1.5  # points, points, seconds
POPUP_LINES, LINE_H = 4, 24  # events shown at once, points per extra line
SKIP_PHASES = ("update", "end")  # ongoing gestures (Ear Hold, Point) show once, when they begin


def log_line(text):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")


def describe(line):
    """'  12.34s twist_1 once (Right) {...} -> focus_app: Google Chrome' -> ('twist_1', 'focus_app: Google Chrome'),
    or None for the middle and end of an ongoing gesture."""
    words = line.split()
    if words[2] in SKIP_PHASES:
        return None
    return words[1], line.split(" -> ", 1)[1]


class Popup:
    """Like the volume overlay: a rounded box near the bottom of the screen. Each event gets its own line for
    POPUP_TIME seconds, newest at the bottom, so two gestures at once both show instead of one replacing the other."""

    def __init__(self):
        screen = AppKit.NSScreen.mainScreen().visibleFrame()
        self.x, self.y = screen.origin.x + (screen.size.width - POPUP_W) / 2, screen.origin.y + 80
        self.panel = overview.overlay_panel(((self.x, self.y), (POPUP_W, POPUP_H)))
        box = self.panel.contentView()
        box.setWantsLayer_(True)
        box.layer().setCornerRadius_(14)
        box.layer().setBackgroundColor_(AppKit.NSColor.colorWithCalibratedWhite_alpha_(0.1, 0.85).CGColor())
        self.label = AppKit.NSTextField.labelWithString_("")
        self.label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(17))
        self.label.setTextColor_(AppKit.NSColor.whiteColor())
        self.label.setAlignment_(AppKit.NSTextAlignmentCenter)
        self.label.setMaximumNumberOfLines_(POPUP_LINES)
        box.addSubview_(self.label)
        self.lines = []  # (text, shown until)

    def show(self, text):
        now = time.monotonic()
        self.lines = [l for l in self.lines if l[1] > now][-(POPUP_LINES - 1):] + [(text, now + POPUP_TIME)]
        self.render()

    def render(self):
        if not self.lines:
            self.panel.orderOut_(None)
            return
        height = POPUP_H + LINE_H * (len(self.lines) - 1)
        self.panel.setFrame_display_(((self.x, self.y), (POPUP_W, height)), True)  # grows upward
        self.label.setFrame_(((12, (POPUP_H - 24) / 2), (POPUP_W - 24, 24 + LINE_H * (len(self.lines) - 1))))
        self.label.setStringValue_("\n".join(text for text, _ in self.lines))
        self.panel.orderFrontRegardless()

    def tick(self):
        now = time.monotonic()
        if any(until <= now for _, until in self.lines):
            self.lines = [l for l in self.lines if l[1] > now]
            self.render()


class Pipeline(threading.Thread):
    """Camera -> gestures -> actions until `running` is cleared. Event lines go to `events` for the main thread."""

    def __init__(self, config, process, events):
        super().__init__(daemon=True)
        self.config, self.process, self.events, self.running = config, process, events, True

    def run(self):
        from talos import vision
        frames, seen = None, 0

        def on_frame(frame, f, found, log):
            nonlocal seen
            for line in log[seen:]:
                self.events.put(line)
            seen = len(log)
            return self.running  # False stops process()

        try:
            frames = vision.frames()
            self.process(frames, Bindings(self.config, run=actions.submit), on_frame)
        except (Exception, SystemExit) as e:  # vision raises SystemExit for no camera / missing models
            traceback.print_exc()
            self.events.put(f"!Talos stopped: {e}")
        finally:
            if frames:
                frames.close()  # releases the camera


class TalosApp(rumps.App):
    def __init__(self, config, process):
        super().__init__("Talos", quit_button=None)
        self.config, self.process, self.events = config, process, queue.Queue()
        self.pipeline = self.popup = self.last = self.settings = None
        self.recent = collections.deque(maxlen=100)  # (time, gesture, action) for the settings window's Activity
        self.camera = rumps.MenuItem("Camera on", callback=self.on_camera)
        self.mistake = rumps.MenuItem("That was a mistake", callback=self.on_mistake)
        self.login = rumps.MenuItem("Start at login", callback=self.on_login)
        self.login.state = AGENT.exists()
        self.menu = [self.camera, rumps.MenuItem("Settings…", callback=self.on_settings), None, self.mistake,
                     rumps.MenuItem("Show event log", callback=self.on_log),
                     rumps.MenuItem("Open config", callback=self.on_config), None, self.login,
                     rumps.MenuItem("Quit Talos", callback=self.on_quit)]
        self.timer = rumps.Timer(self.tick, 1 / 30)  # kept on self: rumps stops timers that get garbage-collected
        self.timer.start()
        self.start()

    def start(self):
        self.pipeline = Pipeline(self.config, self.process, self.events)
        self.pipeline.start()
        self.camera.state = True
        self.set_icon()

    def stop(self):
        if self.pipeline:
            self.pipeline.running = False
            self.pipeline.join(timeout=3)  # exiting while it closes the models crashed MediaPipe
            self.pipeline = None
        state.overview_open = False
        self.camera.state = False
        self.set_icon()

    def set_icon(self):
        """rumps only takes text or image files, so set the status item's image directly. Before AppKit has made
        the status item there's nothing to set; the first tick calls this again."""
        item = getattr(getattr(self, "_nsapp", None), "nsstatusitem", None)
        if item is None:
            return
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            ON if self.pipeline else OFF, "Talos camera on" if self.pipeline else "Talos camera off")
        image.setTemplate_(True)
        item.setImage_(image)
        item.setTitle_("")

    def tick(self, _):
        if self.popup is None:  # first tick: AppKit is running now
            AppKit.NSApp().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)  # no Dock icon
            self.popup = Popup()
            self.set_icon()
        while not self.events.empty():
            line = self.events.get_nowait()
            if line.startswith("!"):  # the pipeline died, e.g. no camera permission
                log_line(line[1:])
                self.popup.show(line[1:])
                self.stop()
                continue
            if found := describe(line):
                gesture, did = found
                self.last = f"{gesture} -> {did}"
                self.mistake.title = f"That was a mistake ({gesture.replace('_', ' ')})"
                log_line(self.last)
                self.popup.show(f"{gesture.replace('_', ' ').title()}  →  {readable(did)}")
                self.recent.appendleft((f"{datetime.datetime.now():%H:%M:%S}", gesture.replace("_", " ").title(), did))
                self.show_recent()
        overview.draw()
        self.popup.tick()

    def on_camera(self, _):
        if self.pipeline:
            self.stop()
        else:
            self.start()
        self.show_recent()

    def on_settings(self, _):
        if self.settings is None:
            from talos.prefs import SettingsWindow
            self.settings = SettingsWindow(self.config)
        self.settings.show()
        self.show_recent()

    def show_recent(self):
        if self.settings:
            self.settings.set_recent(list(self.recent), self.pipeline is not None)

    def on_mistake(self, _):
        if self.last:
            log_line(f"MISTAKE: {self.last}")  # what the week-long misfire review counts
            self.popup.show("Marked as a mistake")

    def on_log(self, _):
        log_line("(log opened)")  # makes sure the file exists
        subprocess.run(["open", str(LOG)])

    def on_config(self, _):
        subprocess.run(["open", "-t", str(self.config)])

    def on_login(self, sender):
        if AGENT.exists():
            AGENT.unlink()
        else:
            AGENT.parent.mkdir(parents=True, exist_ok=True)
            AGENT.write_bytes(plistlib.dumps({"Label": BUNDLE_ID, "ProgramArguments": login_command(),
                                              "RunAtLoad": True}))
        sender.state = AGENT.exists()

    def on_quit(self, _):
        self.stop()
        rumps.quit_application()


def login_command():
    """Inside Talos.app: open the app. From the terminal: run this same Python again."""
    bundle = AppKit.NSBundle.mainBundle()
    if bundle.bundleIdentifier() == BUNDLE_ID:
        return ["/usr/bin/open", "-a", bundle.bundlePath()]
    return [sys.executable, "-m", "talos", "app"]


def run(config, process):
    app = TalosApp(config, process)
    try:
        app.run()
    finally:  # Ctrl+C in the terminal
        app.stop()
