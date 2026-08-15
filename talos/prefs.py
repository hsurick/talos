"""Settings window (menu-bar app), laid out like macOS's own settings windows (Apple's Human Interface Guidelines):
a toolbar of panes (Gestures, General, Activity), grouped rows, standard controls, and no Save button: every change
is written to config.yaml as it's made, and the running pipeline picks it up by itself (hot reload). Comments in the
file are lost, apart from a fixed header."""
import os

import AppKit
import objc
import yaml

from talos import actions
from talos.bindings import parse, specs
from talos.recognizers import HINTS

HEADER = ("# Which gesture runs which actions. Saving this file applies it immediately (hot reload).\n"
          "# Also written by the Talos settings window (menu-bar icon > Settings), which drops other comments.\n")
SECTIONS = (("Switch apps", ("twist_1", "twist_2", "twist_3", "twist_4")),
            ("Windows", ("swipe_left", "swipe_right", "swipe_up", "burst", "unburst", "point", "flick")),
            ("Media", ("ear_tap", "ear_up", "ear_down", "ear_hold")),
            ("Away", ("hand_swipe", "lens_wipe", "walk_away")),
            ("Notifications", ("brush_off",)))
# One line under each gesture's name: the collect prompts' reminders, shortened where they don't fit, plus the
# gestures collect leaves out.
DESCRIPTIONS = {g: d[0].upper() + d[1:] for g, d in {
    **HINTS,
    **{f"twist_{n}": f"{n} finger{'s' if n > 1 else ''} up: roll the hand and back" for n in range(1, 5)},
    "twist_4": "4 fingers up, thumb tucked: roll and back",
    "point": "In Mission Control: point at a window, then pinch or raise your pinky",
    "flick": "In Mission Control: snap the open hand toward a window and back",
    "ear_hold": "2 fingers at your ear: press and hold",
    "walk_away": "Leave the camera's view",
}.items()}
LABELS = {"lock_screen": "Lock screen", "pause_media": "Pause media", "play_pause": "Play / pause",
          "next_track": "Next track", "previous_track": "Previous track", "hold_key": "Hold key",
          "press_key": "Press key", "focus_app": "Open app", "snap_window": "Snap window",
          "zoom_window": "Zoom window", "dismiss_notification": "Dismiss notification",
          "open_overview": "Open Mission Control", "close_overview": "Close Mission Control",
          "select_window": "Select window",
          "run_shortcut": "Run Shortcut", "run_shell": "Run shell command"}
KEYS = (("fn", "fn"), ("escape", "Esc"), ("q", "Q"))  # the keys talos/actions/system.py can press
# What each action's argument is: a fixed choice (value, label), an app name, or free text (placeholder).
ARGS = {"snap_window": ("choice", (("left", "Left half"), ("right", "Right half"))),
        "hold_key": ("choice", KEYS), "press_key": ("choice", KEYS),
        "focus_app": ("app", "App name"), "run_shortcut": ("text", "Shortcut name"), "run_shell": ("text", "Command")}
# settings picked from a menu: key -> (title, detail, options, default)
CHOICES = {"select_with": ("Pick windows with", "Point: point a finger, then choose. Flick: snap the hand there "
                           "and back", (("point", "Point"), ("flick", "Flick")), "point"),
           "choose_with": ("Point chooses with", "Pinch thumb and index, or raise your pinky (middle and ring "
                           "curled)", (("pinch", "Pinch"), ("pinky", "Pinky")), "pinch")}
NUMBERS = (("walk_away_seconds", "Lock after you leave", "Walk Away: seconds out of view", 15),
           ("ear_hold_delay", "Ear Hold delay", "Seconds between the press and the key going down", 0))
ADD = "+add"  # the "Add another action" menu item
# Gestures shown but not rebindable, and actions no other gesture may use: Point and Flick only make sense as the
# Mission Control picker (they only fire there), and Select window does nothing without their aim.
LOCKED = {"point": "select_window", "flick": "select_window"}
PANES = (("Gestures", "hand.raised"), ("General", "gearshape"), ("Activity", "list.bullet.rectangle"))
W, MARGIN, INSET = 700, 20, 16           # window width; group margin; row inset inside a group (points)
POP_W, ARG_W, ROW_H, SLOT_H = 190, 160, 54, 32  # action menu, argument control, row, extra row per second action
GESTURES_H, ACTIVITY_H = 620, 440        # pane heights; General fits its rows


def rows_from(data):
    """Config dict -> {gesture: [(action, arg or None), ...]}."""
    return {g: [parse(s) for s in specs(entry)] for g, entry in (data.get("bindings") or {}).items()}


def to_config(rows, settings):
    """The inverse of rows_from, plus settings; gestures with no actions are left out."""
    bindings = {g: [n if a is None else {n: a} for n, a in acts] for g, acts in rows.items() if acts}
    return {"bindings": bindings, "settings": settings}


def readable(did):
    """'snap_window: left, pause_media' (what the pipeline logs) -> 'Snap window: Left half, Pause media'."""
    out = []
    for part in did.split(", "):
        name, _, arg = part.partition(": ")
        kind, options = ARGS.get(name, (None, None))
        arg = dict(options).get(arg, arg) if kind == "choice" else arg
        out.append(LABELS.get(name, name) + (f": {arg}" if arg else ""))
    return ", ".join(out)


def number(text):
    value = float(text)
    return int(value) if value.is_integer() else value


def app_names():
    """Installed apps, for the Open app suggestions."""
    names = set()
    for folder in ("/Applications", "/System/Applications", os.path.expanduser("~/Applications")):
        if os.path.isdir(folder):
            names.update(f[:-4] for f in os.listdir(folder) if f.endswith(".app"))
    return sorted(names, key=str.lower)


def _text(text, size=13, weight=0.0, color=None):
    field = AppKit.NSTextField.labelWithString_(text)
    field.setFont_(AppKit.NSFont.systemFontOfSize_weight_(size, weight))
    field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    if color is not None:
        field.setTextColor_(color)
    return field


def _put(parent, view, x, y, w, h):
    view.setFrame_(((x, y), (w, h)))
    parent.addSubview_(view)
    return view


def _group(parent, top, height):
    """The rounded, lightly filled box System Settings draws behind a group of rows. Added before the rows, so it
    sits behind them; system colors, so it follows light and dark mode."""
    box = AppKit.NSBox.alloc().initWithFrame_(((MARGIN, top), (W - 2 * MARGIN, height)))
    box.setBoxType_(AppKit.NSBoxCustom)
    box.setTitlePosition_(AppKit.NSNoTitle)
    box.setCornerRadius_(8)
    box.setBorderColor_(AppKit.NSColor.separatorColor())
    box.setFillColor_(AppKit.NSColor.quaternarySystemFillColor())
    parent.addSubview_(box)


def _separator(parent, y):
    line = AppKit.NSBox.alloc().initWithFrame_(((MARGIN + INSET, y), (W - 2 * MARGIN - 2 * INSET, 1)))
    line.setBoxType_(AppKit.NSBoxSeparator)
    parent.addSubview_(line)


def _row_labels(parent, top, height, title, detail, width):
    """Name and one line of detail, vertically centered in the row, like System Settings."""
    y = top + (height - 34) / 2
    _put(parent, _text(title, 13, AppKit.NSFontWeightMedium), MARGIN + INSET, y, width, 17)
    _put(parent, _text(detail, 11, color=AppKit.NSColor.secondaryLabelColor()), MARGIN + INSET, y + 18, width, 15)


def _edit_menu():
    """A menu-bar-only app has no menu bar of its own, so without this Cmd+C / V / X / A / Z do nothing in text
    fields."""
    main, item, edit = AppKit.NSMenu.alloc().init(), AppKit.NSMenuItem.alloc().init(), AppKit.NSMenu.alloc().initWithTitle_("Edit")
    for title, selector, key in (("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"),
                                 ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")):
        edit.addItemWithTitle_action_keyEquivalent_(title, selector, key)
    item.setSubmenu_(edit)
    main.addItem_(item)
    AppKit.NSApp().setMainMenu_(main)


class Flipped(AppKit.NSView):
    """A view whose y grows downward, so panes are laid out top to bottom."""

    def isFlipped(self):
        return True


class Target(AppKit.NSObject):
    """AppKit controls call an Objective-C method on a target; this one looks up the Python callback per control."""

    def changed_(self, sender):
        self.owner.callbacks[sender]()


class Toolbar(AppKit.NSObject, protocols=[objc.protocolNamed("NSToolbarDelegate")]):
    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return [name for name, _ in PANES]

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return [name for name, _ in PANES]

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return [name for name, _ in PANES]

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, ident, insert):
        item = AppKit.NSToolbarItem.alloc().initWithItemIdentifier_(ident)
        item.setLabel_(ident)
        item.setImage_(AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(dict(PANES)[ident], ident))
        item.setTarget_(self)
        item.setAction_("pick:")
        return item

    def pick_(self, item):
        self.owner.show_pane(item.itemIdentifier())


class Activity(AppKit.NSObject, protocols=[objc.protocolNamed("NSTableViewDataSource")]):
    """The Activity table's rows: (time, gesture, what ran)."""

    def numberOfRowsInTableView_(self, table):
        return len(self.rows)

    def tableView_objectValueForTableColumn_row_(self, table, column, row):
        value = self.rows[row][int(column.identifier())]
        return readable(value) if column.identifier() == "2" else value


class SettingsWindow:
    def __init__(self, config):
        self.config, self.callbacks, self.adding, self.pane = config, {}, set(), "Gestures"
        self.names = [n for n in LABELS if n in actions.REGISTRY] + sorted(n for n in actions.REGISTRY if n not in LABELS)
        self.apps = app_names()
        self.target, self.toolbar_delegate, self.activity = Target.alloc().init(), Toolbar.alloc().init(), Activity.alloc().init()
        self.target.owner = self.toolbar_delegate.owner = self
        self.activity.rows, self.camera_on, self.table, self.empty, self.scroll = [], True, None, None, None
        style = AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable | AppKit.NSWindowStyleMaskMiniaturizable
        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (W, GESTURES_H)), style, AppKit.NSBackingStoreBuffered, False)
        self.window.setReleasedWhenClosed_(False)  # closing only hides it; we keep using the object
        toolbar = AppKit.NSToolbar.alloc().initWithIdentifier_("TalosSettings")
        toolbar.setDelegate_(self.toolbar_delegate)
        self.window.setToolbar_(toolbar)
        self.window.setToolbarStyle_(AppKit.NSWindowToolbarStylePreference)
        self.window.center()

    # --- the model: what config.yaml says, changed by the controls and written back right away

    def load(self):
        data = yaml.safe_load(self.config.read_text()) or {}
        self.rows, self.settings = rows_from(data), dict(data.get("settings") or {})
        self.rows.update({g: [(action, None)] for g, action in LOCKED.items()})

    def save(self):
        """Writes only real changes: fields also report "edited" when you merely leave them or switch panes, and a
        rewrite drops the file's comments."""
        data = to_config(self.rows, self.settings)
        old = yaml.safe_load(self.config.read_text()) or {}
        if data != to_config(rows_from(old), old.get("settings") or {}):
            # Write a copy, then swap it in: the pipeline may reload mid-write, and a half-written file reads as empty.
            tmp = self.config.with_suffix(".tmp")
            tmp.write_text(HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
            os.replace(tmp, self.config)

    def set_action(self, gesture, slot, choice):
        """A choice in a gesture's action menu: an action name, None (remove), or ADD (show a second, empty slot)."""
        acts = list(self.rows.get(gesture, []))
        self.adding.discard(gesture)
        if choice == ADD:
            self.adding.add(gesture)
            return
        if choice is None:
            del acts[slot:slot + 1]
        else:
            choice = str(choice)  # AppKit's own string type can't be written as YAML
            kind, options = ARGS.get(choice, (None, None))
            keep = slot < len(acts) and acts[slot][0] == choice
            arg = acts[slot][1] if keep else options[0][0] if kind == "choice" else None
            acts[slot:slot + 1] = [(choice, arg)]
        self.rows[gesture] = acts
        self.save()

    def set_arg(self, gesture, slot, value):
        """An emptied field keeps the last value: Open app, Run Shortcut and Run shell command can't run without one."""
        if not str(value).strip():
            return
        acts = self.rows[gesture]
        acts[slot] = (acts[slot][0], str(value).strip())
        self.save()

    def set_setting(self, key, value):
        """Returns an error message, or None once saved."""
        if key not in CHOICES:
            try:
                value = number(value)
            except ValueError:
                return "Enter a number of seconds."
            if value < 0:
                return "Seconds can't be negative."
        self.settings[key] = str(value) if key in CHOICES else value
        self.save()

    # --- the panes

    def _on(self, control, callback):
        control.setTarget_(self.target)
        control.setAction_("changed:")
        self.callbacks[control] = callback
        return control

    def _later(self, fn):
        """Rebuilding a pane from inside one of its own controls' actions would free that control mid-call."""
        AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(fn)

    def _action_menu(self, gesture, slot, current, can_add):
        popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(((0, 0), (POP_W, 26)), False)
        menu = popup.menu()

        def add(title, value):
            item = menu.addItemWithTitle_action_keyEquivalent_(title, None, "")
            item.setRepresentedObject_(value)
            if value == current:
                popup.selectItem_(item)
        add("None", None)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        for name in self.names:
            if name not in LOCKED.values() or gesture in LOCKED:
                add(LABELS.get(name, name), name)
        if can_add:
            menu.addItem_(AppKit.NSMenuItem.separatorItem())
            add("Add another action", ADD)

        def changed():
            self.set_action(gesture, slot, popup.selectedItem().representedObject())
            self._later(self.rebuild)
        return self._on(popup, changed)

    def _arg_control(self, gesture, slot, action, arg):
        kind, options = ARGS[action]
        if kind == "choice":
            control = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(((0, 0), (ARG_W, 26)), False)
            for value, label in options:
                item = control.menu().addItemWithTitle_action_keyEquivalent_(label, None, "")
                item.setRepresentedObject_(value)
                if value == arg:
                    control.selectItem_(item)
            return self._on(control, lambda: self.set_arg(gesture, slot, control.selectedItem().representedObject()))
        control = (AppKit.NSComboBox if kind == "app" else AppKit.NSTextField).alloc().initWithFrame_(((0, 0), (ARG_W, 24)))
        if kind == "app":
            control.addItemsWithObjectValues_(self.apps)
            control.setCompletes_(True)
            control.setNumberOfVisibleItems_(12)
        control.setPlaceholderString_(options)
        control.setStringValue_(arg or "")
        control.cell().setSendsActionOnEndEditing_(True)  # save when you leave the field, not only on Return
        return self._on(control, lambda: self.set_arg(gesture, slot, control.stringValue()))

    def _gestures_pane(self):
        doc = Flipped.alloc().initWithFrame_(((0, 0), (W, 10)))
        label_w = W - 2 * MARGIN - 2 * INSET - POP_W - ARG_W - 24
        x_pop = W - MARGIN - INSET - ARG_W - 8 - POP_W
        y = MARGIN
        for title, names in SECTIONS:
            _put(doc, _text(title, 13, AppKit.NSFontWeightSemibold), MARGIN + 4, y, 300, 18)
            y += 24
            slots = {g: max(1, len(self.rows.get(g, [])) + (g in self.adding)) for g in names}
            heights = [ROW_H + SLOT_H * (slots[g] - 1) for g in names]
            _group(doc, y, sum(heights))
            for i, (g, h) in enumerate(zip(names, heights)):
                if i:
                    _separator(doc, y)
                _row_labels(doc, y, ROW_H, g.replace("_", " ").title(), DESCRIPTIONS.get(g, ""), label_w)
                acts = self.rows.get(g, [])
                for slot in range(slots[g]):
                    action, arg = acts[slot] if slot < len(acts) else (None, None)
                    top = y + (ROW_H - 26) / 2 + slot * SLOT_H
                    menu = self._action_menu(g, slot, action,
                                             can_add=slot == 0 and slots[g] == 1 and action and g not in LOCKED)
                    menu.setEnabled_(g not in LOCKED)
                    _put(doc, menu, x_pop, top, POP_W, 26)
                    if action in ARGS:
                        _put(doc, self._arg_control(g, slot, action, arg), x_pop + POP_W + 8, top + 1, ARG_W, 24)
                y += h
            y += 22
        doc.setFrameSize_((W, y))
        self.scroll = AppKit.NSScrollView.alloc().initWithFrame_(((0, 0), (W, GESTURES_H)))
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setDrawsBackground_(False)
        self.scroll.setDocumentView_(doc)
        return self.scroll

    def _general_pane(self):
        view = Flipped.alloc().initWithFrame_(((0, 0), (W, 10)))
        rows = [(k, t, d) for k, (t, d, _, _) in CHOICES.items()] + [(k, t, d) for k, t, d, _ in NUMBERS]
        y = MARGIN
        _group(view, y, ROW_H * len(rows))
        error = _text("", 11, color=AppKit.NSColor.systemRedColor())
        for i, (key, title, detail) in enumerate(rows):
            if i:
                _separator(view, y)
            _row_labels(view, y, ROW_H, title, detail, 380)
            right, top = W - MARGIN - INSET, y + (ROW_H - 26) / 2
            if key in CHOICES:
                _, _, options, default = CHOICES[key]
                control = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(((0, 0), (190, 26)), False)
                for value, label in options:
                    item = control.menu().addItemWithTitle_action_keyEquivalent_(label, None, "")
                    item.setRepresentedObject_(value)
                    if value == self.settings.get(key, default):
                        control.selectItem_(item)
                self._on(control, lambda c=control, k=key: self.set_setting(k, c.selectedItem().representedObject()))
                _put(view, control, right - 190, top, 190, 26)
            else:
                default = next(d for k, _, _, d in NUMBERS if k == key)
                field = AppKit.NSTextField.alloc().initWithFrame_(((0, 0), (64, 24)))
                field.setStringValue_(str(self.settings.get(key, default)))
                field.setAlignment_(AppKit.NSTextAlignmentRight)
                field.cell().setSendsActionOnEndEditing_(True)

                def changed(key=key, field=field):
                    error.setStringValue_(self.set_setting(key, field.stringValue()) or "")
                self._on(field, changed)
                _put(view, field, right - 64 - 18, top + 1, 64, 24)
                _put(view, _text("s", 13, color=AppKit.NSColor.secondaryLabelColor()), right - 12, top + 4, 12, 17)
            y += ROW_H
        _put(view, error, MARGIN + 4, y + 8, W - 2 * MARGIN, 15)
        _put(view, _text("Changes are saved to config.yaml as you make them.", 11,
                         color=AppKit.NSColor.secondaryLabelColor()), MARGIN + 4, y + 26, W - 2 * MARGIN, 15)
        view.setFrameSize_((W, y + 26 + 15 + MARGIN))
        return view

    def _activity_pane(self):
        view = Flipped.alloc().initWithFrame_(((0, 0), (W, ACTIVITY_H)))
        self.table = AppKit.NSTableView.alloc().initWithFrame_(((0, 0), (W - 2 * MARGIN, 10)))
        for ident, title, width in (("0", "Time", 90), ("1", "Gesture", 170), ("2", "Action", 360)):
            column = AppKit.NSTableColumn.alloc().initWithIdentifier_(ident)
            column.setTitle_(title)
            column.setWidth_(width)
            self.table.addTableColumn_(column)
        self.table.setStyle_(AppKit.NSTableViewStyleInset)
        self.table.setUsesAlternatingRowBackgroundColors_(True)
        self.table.setDataSource_(self.activity)
        box = AppKit.NSScrollView.alloc().initWithFrame_(((0, 0), (W - 2 * MARGIN, ACTIVITY_H - 2 * MARGIN)))
        box.setDocumentView_(self.table)
        box.setHasVerticalScroller_(True)
        box.setBorderType_(AppKit.NSBezelBorder)
        _put(view, box, MARGIN, MARGIN, W - 2 * MARGIN, ACTIVITY_H - 2 * MARGIN)
        self.empty = _put(view, _text("", 13, color=AppKit.NSColor.secondaryLabelColor()), MARGIN, ACTIVITY_H / 2 - 10,
                          W - 2 * MARGIN, 20)
        self.empty.setAlignment_(AppKit.NSTextAlignmentCenter)
        self._fill_activity()
        return view

    def _fill_activity(self):
        if self.table is not None:
            self.table.reloadData()
            self.empty.setStringValue_("" if self.activity.rows else
                                       "No gestures yet." if self.camera_on else "The camera is off.")

    def show_pane(self, name):
        self.pane, self.table, self.scroll = name, None, None
        view = {"Gestures": self._gestures_pane, "General": self._general_pane, "Activity": self._activity_pane}[name]()
        self.window.setTitle_(name)
        self.window.toolbar().setSelectedItemIdentifier_(name)
        old = self.window.frame()
        frame = self.window.frameRectForContentRect_(((0, 0), view.frame().size))  # before setContentView_ stretches it
        self.window.setContentView_(view)
        top = old.origin.y + old.size.height  # keep the title bar where it is, like System Settings
        self.window.setFrame_display_animate_(((old.origin.x, top - frame.size.height), frame.size), True,
                                              self.window.isVisible())

    def rebuild(self):
        """Redraw the Gestures pane after its rows changed shape, keeping the scroll position."""
        if self.pane != "Gestures" or self.scroll is None:
            return
        at = self.scroll.contentView().bounds().origin
        self.show_pane("Gestures")
        self.scroll.documentView().scrollPoint_(at)

    def show(self):
        if not self.window.isVisible():
            self.load()
            self.adding.clear()
            self.show_pane(self.pane)
        _edit_menu()
        AppKit.NSApp().activateIgnoringOtherApps_(True)  # a menu-bar app isn't in front by itself
        self.window.makeKeyAndOrderFront_(None)

    def set_recent(self, rows, camera_on):
        self.activity.rows, self.camera_on = rows, camera_on
        self._fill_activity()
