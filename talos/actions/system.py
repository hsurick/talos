"""System actions: lock, pause media, hold a key, dismiss a notification, run a Shortcut or shell command."""
import subprocess

import AppKit
import ApplicationServices as AX
import Quartz

from talos.actions import action
from talos.actions.windows import ax_get

KEYS = {"fn": 63, "q": 12, "escape": 53}
FLAGS = {"fn": Quartz.kCGEventFlagMaskSecondaryFn}


def press(code, flags=0, down=True):
    ev = Quartz.CGEventCreateKeyboardEvent(None, code, down)
    Quartz.CGEventSetFlags(ev, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def tap(code, flags=0):
    press(code, flags, True)
    press(code, flags, False)


def osascript(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10).stdout.strip()


@action("lock_screen")
def lock_screen(event, arg):
    tap(KEYS["q"], Quartz.kCGEventFlagMaskCommand | Quartz.kCGEventFlagMaskControl)  # macOS's Lock Screen shortcut


@action("pause_media")
def pause_media(event, arg):
    # Sends pause rather than the play/pause key, which would start music if nothing is playing.
    # shortcut: browser video (YouTube) isn't paused; upgrade if that matters in daily use.
    for app in ("Music", "Spotify"):
        osascript(f'if application "{app}" is running then tell application "{app}" to pause')


@action("hold_key", phases=("begin", "end"))
def hold_key(event, key):
    press(KEYS[key], FLAGS.get(key, 0) if event.phase == "begin" else 0, down=event.phase == "begin")


@action("press_key")
def press_key(event, key):
    tap(KEYS[key])


def notifications():
    """Notification banners and alerts on screen, through Accessibility. macOS 15 draws them with SwiftUI, which
    AppleScript's "entire contents" doesn't reach. Widgets have a Close action too, so match the notification kind."""
    nc = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.apple.notificationcenterui")
    stack, found = [AX.AXUIElementCreateApplication(nc[0].processIdentifier())] if nc else [], []
    while stack:
        el = stack.pop()
        if (ax_get(el, "AXSubrole") or "").startswith("AXNotificationCenter"):  # ...Banner or ...Alert
            found.append(el)
        else:
            stack += list(ax_get(el, "AXChildren") or [])
    return found


@action("dismiss_notification")
def dismiss_notification(event, arg):
    for el in notifications():
        _, names = AX.AXUIElementCopyActionNames(el, None)
        close = next((n for n in names or [] if n.startswith("Name:Close")), None)  # e.g. "Name:Close\nTarget:0x0..."
        if close:
            AX.AXUIElementPerformAction(el, close)
            print("dismiss_notification: closed")
            return
    print("dismiss_notification: none on screen (or Accessibility isn't allowed)")


@action("run_shortcut")
def run_shortcut(event, name):
    subprocess.run(["shortcuts", "run", name], timeout=60)


@action("run_shell")
def run_shell(event, command):
    subprocess.run(command, shell=True, timeout=60)  # the command comes from your own config file
