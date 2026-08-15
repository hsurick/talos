"""Media keys, sent the same way the keyboard's play/next/previous keys are."""
import AppKit
import Quartz

from talos.actions import action

PLAY, NEXT, PREVIOUS = 16, 17, 18  # NX_KEYTYPE_* codes


def media_key(key):
    for down in (True, False):
        state = 0xA if down else 0xB
        ev = AppKit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            AppKit.NSEventTypeSystemDefined, (0, 0), state << 8, 0, 0, None, 8, (key << 16) | (state << 8), -1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev.CGEvent())


@action("play_pause")
def play_pause(event, arg):
    media_key(PLAY)


@action("next_track")
def next_track(event, arg):
    media_key(NEXT)


@action("previous_track")
def previous_track(event, arg):
    media_key(PREVIOUS)
