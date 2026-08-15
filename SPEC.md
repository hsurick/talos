# Gesture + Presence App: Spec

@Rick

## Purpose and design rules

Talos (working name) is a Mac app that watches through the webcam and reacts to your presence and your hands. It targets macOS Sequoia, the built-in camera, and one or several monitors. Gestures raise events, and a config file binds each event to actions, so any gesture can run any action.

Design rules:

- A gesture has a name and a description of what it is. Some gestures have several parts, like the window overview (open, select, close).
- There is no global arming step. A gesture that opens a mode, like the window overview, arms only that mode.
- No gesture requires holding a pose before the motion; the motion itself is the gesture. Any delay is a per-gesture setting in the config. Hands only count when raised above keyboard level, and (except the Ear gestures) only when clearly in front of the face: the hand must look large next to the head (hand size / ear-to-ear width), which rules out hands touching the face or in the hair. The ratio is one guessed number for now; a per-user calibration comes later.
- A gesture earns a default only if it beats the keyboard: your hands are off the keyboard, no good shortcut exists, or one gesture replaces several steps.
- Every recognized gesture shows a brief on-screen indicator naming the gesture and the action it ran.
- Anything not in the default gestures table ships as an option, not a default.
- Privacy: all tracking runs on the Mac. No video is saved or sent anywhere, and recordings contain only tracked points. The menu-bar icon turns the camera off.

## Gesture vocabulary

Fourteen named gestures. The name is what the default gestures table refers to; the description says what the gesture is. Burst and Unburst are candidates, and Fist Twist is later.

| Name | Description | Notes |
| --- | --- | --- |
| Walk Away | You leave and stay gone for 15 seconds: the camera sees no person and there has been no keyboard or mouse input. Looking down at your phone does not count, because your shoulders are still visible | Uses the body model from day one. The 15 seconds is configurable and resets if you reappear. When you return, nothing happens by default: no resume, no unmute, and never an automatic unlock or face-unlock |
| Hand Swipe | A hand sweeps across the camera, right to left or left to right | Detected from whole-image motion, not hand tracking: real sweeps blur and are tracked in only a frame or two. No start pose. It locks the screen. Anything big crossing the frame (a person walking behind you) can look the same; checked with normal-work recordings |
| Lens Wipe | A hand right at the lens slides across it | Also whole-image motion: the moving area covers most of the image. A covering hand is not dark in a lit room, so darkness is not used. A separate gesture from Hand Swipe, bound to the same away bundle by default |
| Twist-N (N = 1 to 4) | Two parts: first a raised hand with N fingers extended (Twist-4 also needs the thumb tucked, since four fingers with the thumb out is an open palm; for 1 to 3 the thumb doesn't matter), then a roll around the finger axis and back. Recorded twists turn about 150 degrees; the recognizer needs 35 (20 let tracking jitter fake a twist). The roll only counts after the N-finger pose, held still (arming mid-roll counted the way back as a twist). Mid-roll the finger count may read one higher (edge-on, a curled finger reads as up; never one lower, or Twist-2 steals Twist-1), the thumb doesn't matter (the turning hand hides it), and the fingers must stay upright, ignoring a single-frame lean misreading. Collected: Twist-1 17/19, Twist-2 25/30, Twist-3 25/30, Twist-4 27/30, no false Twists in 60 "nothing" clips | Palm direction does not matter. Later: clockwise and counter-clockwise run different actions |
| Swipe Left / Swipe Right | Start pose: hand edge-on to the camera, four fingers up. Then the wrist bends so the fingers lean sideways at least 30 degrees, arm still. The direction is where the fingertips go, so it works the same with either hand. Replaces Push | Edge-on vs flat is what separates it from Swipe Up/Down (recorded: edge-on 0.65-0.9, flat 0.13-0.15 sideways palm component). The lean is measured from the most upright moment of the last 0.4s (leans start gradually); after a swipe, the other direction is measured from where that swipe started, so leaning back home never counts. It arms from whatever lean the hand rests at (collected rests lean ~40 degrees; swipes are a ~45 degree flick from there and back), as long as the hand holds still. Mid-swipe the hand must stay in front of the face with 3+ fingers up (hands at the hair fired swipes). Collected: Left 11/15, Right 14/15, 1 false swipe in 60 "nothing" clips |
| Swipe Up | Start pose: hand flat to the camera. A wrist flip, arm still, from flat (fingers pointing sideways or at the screen, palm down) to upright (fingers up, palm to the camera) | Zooms the front window (Window > Zoom, not the green button's full screen). The flip counts once the hand stays upright as long as it stayed flat (at most 0.4s, which is also the added delay); going on into another pose (a pointing finger) still counts. In front of the face is checked only to start, because the flat hand is foreshortened. Known: fires about once per 30 Twist-3/4 clips |
| Swipe Down | Dropped (2026-10-18) | Every Swipe Up's prep looks like one, and it collided with picking a window downward (pointing down, Flick down). Mission Control closes with Unburst |
| Burst | A fist that opens to five fingers (thumb out), palm to the camera | Opens Mission Control. The fist must be upright (leaning under 65 degrees) and not palm-down (palm y under 0.4): the flat hand of a Swipe Up/Down also reads as zero fingers and fired Burst/Unburst on nearly every flip in the old recordings (17 in swipeandpush, now 0; 10 in swipedemo, now 1). Collected: 29/30 |
| Unburst | Five fingers that close to a fist, palm to the camera | Closes Mission Control. Same fist rule as Burst, and the fist must hold 4 frames (~0.13s): curling an open hand into Point's pointing finger passes through a fist, which closed the overview. Collected: 29/30 |
| Flick | Inside Mission Control only, when chosen instead of Point. The open hand snaps toward the window you want and back in one motion. The outward snap picks the window, and the snap back chooses it | The palm's movement, not a fingertip: the collected flicks were done with the open hand. Snap 0.4 hand sizes, back within 0.35. Collected flick sequences: 18/30 right (Burst-opened: 11/16) |
| Point | Inside Mission Control only. Point the index finger at a window, then pinch thumb and index to choose. Pointing at the screen is neutral; up lights the top window, left the left one, wherever the finger started. The lit window stays lit through neutral. Point or Flick runs, not both (setting select_with, Settings > General). Option (setting choose_with): raise the pinky, middle and ring curled, instead of pinching | Raising the pinky avoids the pinch's problems: the camera sees it plainly (thumb and index can overlap in the image without touching), the index doesn't bend, and the hand never reads as Burst's fist. Not yet tuned on recordings. With pinch choosing, Burst and Unburst need the index folded into the fist (tip to knuckle under 0.55): a pinch curls the other fingers, so opening the hand after choosing fired Burst; this costs Burst some loose fists (11 in the collected sequences). Aiming with the hand was tried: in the collected sequences the hand stayed upright and the finger aimed. Pinching bends the finger, so the choice is where it pointed the last time thumb and index were apart (over 0.4). Pinch = thumb tip to index tip under 0.3 hand sizes (pointing down shrinks the hand-size measure, so pinches there read 0.25-0.3), and the index tip not folded in (tip to knuckle over 0.55; a fist's thumb also lies near the index tip). Collected point sequences: 19/30 right (Burst-opened: 10/16). Misses: pinches the camera didn't see (~4 cm apart at closest), pinching while the finger was still moving, and "up" reading 11-37 degrees left of straight |
| Ear Tap | Point at your ear, then take the hand away: away, at the ear, away. A visit of up to 0.8s | All three Ear gestures are one visit, judged when the fingertip leaves the ear. The finger count flickers at the ear (the index hides behind the head), so the pose is judged over the whole visit: pointing (1-2 fingers) in at least half its frames, and the hand at the head's depth: the median of the hand's size next to the head's under 0.9 (collected ear visits 0.55-0.85; hands only overlapping the ear in the image, in front of the face, ~1.16). The pose model's own z didn't separate them. The ear position comes from the body model's ear points |
| Ear Up / Down | Point at your ear, then leave upward (Ear Up); or stay a moment (0.3s+) and leave downward (Ear Down) | Leaving upward rarely happens by accident, so Ear Up asks less of the pose. Ear Down and Ear Tap overlap with simply lowering your hand after touching your head; pointing is what tells them apart. A hand resting on the head over 2s isn't a visit. Collected: Tap 9/15, Up 11/15, Down 8/15 (3 taps read as Down), 1 false Ear gesture in 60 "nothing" clips |
| Ear Hold | Index and middle finger at the ear in a "tube" pose, like holding an earpiece, then a press, like activating it. The key goes down on the press and up on release. Any delay is a config setting | Willow may ignore a synthesized Fn key. The first word can be clipped |
| Brush Off | Start pose is an open palm (thumb out) facing you. Then the wrist turns and the fingers flick outward, so the back of the hand pushes away, like shooing someone off | Collected clips: the palm starts partly toward you (angled or edge-on), held ~1s, then flips to face the camera in ~0.1s, often in place. So: the start pose must be held 0.25s (a twist's roll passes through it), the palm must end toward the camera (a swipe's lean keeps it sideways), and it scores above Swipe, which matches the same motion. Collected: 6/10 (2 clips had no hand tracked); it also fires once on a Swipe Up flip in an old recording (Swipe Up is unbound) |
| Fist Twist | A fist held out, then the same quick roll as Twist. A held fist alone does nothing | Later. Mutes the current audio |

## Default gestures

These are the default gestures that ship, one row per action. Each can be changed in the config. Gestures are defined above.

| Action | Gesture | Scope | Notes |
| --- | --- | --- | --- |
| Away bundle (lock + pause media) | Walk Away (15 seconds), Hand Swipe, or Lens Wipe | Always | Walk Away is timer-based. Hand Swipe and Lens Wipe are instant, with no timer, and can be bound separately |
| Open Mission Control | Burst | Always | Burst again closes it. Opened or closed any other way (F3, Escape, a click, a trackpad swipe), Talos hears it from the Dock's AXExposeShowAllWindows / AXExposeExit accessibility notifications, no polling (tested: noticed 0.28s after Escape, as the thumbnails disappear). A destroyed-element notification on Mission Control's group never arrived |
| Close Mission Control | Unburst | Inside Mission Control | |
| Select window | Point or Flick (setting select_with) | Inside Mission Control | Point: point a finger, then pinch to choose. Flick: snap the open hand toward the window and back. Either closes Mission Control |
| Zoom front window | Swipe Up | Always | Window > Zoom through the Accessibility API (English menu titles); apps without it: the window's zoom button |
| Play / pause | Ear Tap | Always | Fires instantly |
| Next / previous track | Ear Up / Down | Always |  |
| Fn key held (dictation / AI) | Ear Hold | Always | Key down on press, key up on release |
| Focus app 1 to 4 | Twist-1 to Twist-4 | Always | App slots are a config table (defaults: Safari, Mail, Notes, Music; apps every Mac has) |
| Snap frontmost window to left / right half, then to the next monitor | Swipe Left / Swipe Right | Always | Swiping a window that is already on that half moves it to the next monitor. Set through the Accessibility API, no extra app needed |
| Dismiss notification | Brush Off | Always | Unverified. Fallbacks: close the banner through Notification Center's accessibility interface, or press Escape to dismiss whatever is in front |

## Window overview

The window overview is a fast single-hand flow: Burst opens Mission Control, a Point or Flick selects a window, and Unburst cancels. Talos Control (B) was built and dropped: it was the fallback in case Mission Control couldn't be driven, and it can.

| Version | How it works | Notes |
| --- | --- | --- |
| A. macOS Mission Control (default) | Open Apple's Mission Control and read where each window thumbnail sits through the Dock's accessibility interface. Talos draws a blue ring over the thumbnail being aimed at, since Mission Control has no highlight of its own; choosing presses that thumbnail | Tested with simulated aim events: the thumbnails are listed with their positions 0.3s after opening, the ring follows the aim, and choosing brings that window to the front. Mission Control rearranges windows every time it opens, so aim at where a window is now. The Spaces bar (Desktop buttons) and an untitled button are skipped. A window that doesn't render a thumbnail (Reminders did not) still gets a ring around empty space |
| B. Talos Control (dropped) | Our own full-screen overlay that lays out all open windows in a ring around the center | Removed; Mission Control does the job |
| C. Cursor aim | Hand position moves the real cursor, and a gesture clicks | Last resort, only if Point cannot be made to work. Too slow for the goal |

Both versions choose by direction only, measured from the screen center.

## Available but not bound by default (later)

These ship as options in the config, or come later; none is a default.

| Item | Kind | How it would work | Status |
| --- | --- | --- | --- |
| Mute sound | Action | Fist Twist. System output mute is one line of AppleScript | Later, never a default |
| Mute mic | Action | No system-wide mic mute exists as far as known, so it sets input volume to 0 and restores it | Later |
| Mic mute by finger to lips | Gesture | One finger held at the lips | Later |
| Saved window layouts | Action | One gesture arranges several windows, for example Chrome left and Claude right. Gesture not yet defined | Later |
| Air-drawn letters launch apps | Gesture | Pinch-hold and draw a letter in the air | Later |
| Slack or Teams status from presence | Action | Set away when you actually leave | Later |
| Wake display on return | Action | Screen wakes when you sit down; unlock stays manual | Later |
| Break nudge | Action | Notification after about 90 minutes in frame | Post-1.1 |
| Head pose picks monitor | Gesture | Looking at a monitor focuses it; needs calibration | Post-1.1, weakest idea on the list |
| Run a Shortcut or shell command | Action | Any gesture can run any macOS Shortcut or script | Spare |
| Volume, switch Space, region screenshot, lock now | Actions | Plain macOS actions available to any gesture | Spare |
| Fist held, peace sign | Gestures | Simple poses with no default job | Spare |
| Call mode | Action | When another app is using the microphone, hand gestures pause and Walk Away keeps running, because people gesture while talking on calls | Later |
| Twist direction | Gesture | Clockwise and counter-clockwise Twist run different actions, doubling the app slots | Later |

## Tech stack and architecture

The app is a lightweight Python program that runs in the background and is configured by a file. It is not an Electron app. Electron bundles a whole web browser into every app, which is heavy for something that runs all day, and it would not track hands any better than Python does.

What gets built: one Python program in two forms. During stages 1 and 2 it runs as a script from the terminal. From stage 3 it is a menu-bar app (a small app bundle with no window, only an icon in the menu bar) that starts at login, so macOS permissions belong to the app and not to Terminal.

| Piece | What it is | Stage |
| --- | --- | --- |
| Vision part | Python module: camera loop, MediaPipe, and one recognizer per gesture. It outputs events | 1 |
| Event bus and bindings | Passes events around, reads the config file, and runs the actions bound to each gesture | 1 |
| Config file | A YAML file with which gesture runs which actions, plus timings and app slots | 1 |
| Actions | Python functions registered by name, grouped by kind (system, media, windows) | 1 |
| Record and replay tool | Saves camera landmarks to a file and plays them back for tests | 1 |
| Menu-bar wrapper | A small app bundle with an on/off icon and start at login (for example built with py2app and rumps) | 3 |

The config file looks like this:

```yaml
bindings:
  hand_swipe:
    - lock_screen
    - pause_media
  ear_tap_1:
    - play_pause
  twist_1:
    - focus_app: Google Chrome
  swipe_left:
    - snap_window: left
settings:
  walk_away_seconds: 15
```

The config says which gesture runs which actions. A plugin is a Python action function; adding one makes it available by name in the config. A new gesture recognizer is code, not config.

| Part | Choice | Notes |
| --- | --- | --- |
| Language | Python for stages 1 and 2 | Fastest to iterate. Gesture recognizers are plain functions of the tracked points, with no camera or macOS code inside, so they can be ported. Whether the finished app stays Python or is rewritten in Swift is decided at stage 3 |
| Hand and body tracking | MediaPipe hand and body models | The body model gives the shoulders (Walk Away) and ear points (Ear gestures). The face model is not used. MediaPipe gives depth on every hand point, which Swipe Up/Down and Brush Off need to read which way the palm faces. Apple's Vision framework is the native alternative: more power-efficient, but its hand points are flat (no depth). Decided: MediaPipe only for now; Apple Vision is revisited at stage 3 if battery use is a problem |
| Features | One step per frame turns the tracked points into a shared record of facts (fingers up, palm direction, roll angle, hand speed, distance to ear) | Recognizers read only this record, never the raw points, so every gesture agrees on the same facts and the debug window shows what the recognizers see |
| Camera | OpenCV at 30 frames per second all the time | A cheap motion check runs on every frame, and the hand model (about 10 ms per frame) runs only when something moves or a hand was seen in the last frame. The body model (about 7 ms) runs on every third frame, since shoulders and ears move slowly. Dropping the frame rate when idle would miss the first gesture |
| Events | A small event bus | One event shape for all gestures: gesture name, phase, time, and optional data. The phase is `once` for instant gestures (Hand Swipe) and `begin`, `update`, `end` for ongoing ones (Point, Ear Hold). If tracking is lost mid-gesture, the app sends the `end` itself so no key stays stuck. Gestures never call actions directly |
| Bindings (the plugin part) | A config file (YAML) maps each gesture to one or more actions, optionally per app | The Default gestures table is the starting config. The app watches the config file and reloads it on save, with no restart (hot reload) |
| Actions | Small Python functions registered by name: lock, pause media (sends pause to Music and Spotify, because the play/pause key would start music if nothing is playing), media keys, key down and up, focus app, set window frame, run a Shortcut or shell command | Anyone can add one. A gesture can run several actions. Each action handles the phases itself (for example `hold_key: fn` presses on `begin` and releases on `end`), so the config stays a list of action names per gesture |
| Feedback | A small on-screen indicator, like the volume overlay, showing the recognized gesture and the action it ran | Tells a missed gesture apart from a failed action. Built in stage 3; in stages 1 and 2 the debug window and terminal show recognized gestures |
| macOS access | Camera and Accessibility permissions. Screen Recording only for live thumbnails in Talos Control | macOS ties permissions to the app's signature, so builds are signed with a stable certificate and permission is not re-granted after every build |
| Interface | A menu-bar icon (camera on/off, "that was a mistake", event log, start at login, quit) and a native settings window: one row per gesture with up to two actions and their arguments, Point or Flick, Walk Away and Ear Hold timing, and the recent gestures | Changed from "config file only": the window writes config.yaml, which hot-reloads, so the file stays the single source. Saving drops the file's comments apart from a fixed header. Built in AppKit through PyObjC, no new dependency |
| Start at login | A macOS launch agent |  |
| Testing | Recorded landmark files replayed without a camera | Built in stage 1. Recordings save the raw tracked points per frame (never video, never only features, so old recordings stay valid when feature math changes) as compressed JSON Lines, one line per frame. `talos collect` records prompted, labeled clips: single gestures, and (the user's request) whole sequences like Swipe Up, Point left, as in real use. Replays simulate the actions' effect on the overview (open, close, choose), so a sequence opens the overview itself; a clip passes only if its steps fire and nothing else that has an effect (a stray close with nothing open is harmless) |
| Code layout | One module or folder per pipeline layer: `talos/vision.py`, `features.py`, `recognizers/`, `events.py`, `bindings.py`, `actions/`, `record.py`, `debug.py`, plus `config.yaml` and `tests/` | Each file is created when its stage needs it |

Speed target (proposed): about 150ms or less from a recognized gesture to the action, not counting any per-gesture delay set in the config. Everything runs in one process.

Python or Swift for the finished app is decided at stage 3. If the Python app packages, signs and runs well, it stays. If not, the app is rewritten in Swift with Apple's Vision framework, and the recognizers are ported as plain functions. Wrapping the Python program inside a Swift app is avoided, because it keeps the problems of both.

## How gestures are detected and tested

Tracking and gesture detection are two separate jobs. MediaPipe does the tracking and is ready-made; the gesture detection is ours to write.

1. **Tracking (MediaPipe).** Every frame it returns 21 points per hand and 33 on the body, including the shoulders and ears, with 3D coordinates. This is the only part we do not build.
2. **Features (ours).** Plain math on those points: which fingers are extended, which way the palm faces, the hand's roll angle, where the hand is and how fast it moves, how far a fingertip is from the ear.
3. **Gesture rules (ours).** A small state machine per gesture that watches those features over time. For example, Twist-2 is two fingers extended, then a roll faster than a set speed and back, with no hold in between. Each recognizer advances while its gesture can still complete, resets when a frame rules it out, fires on the completing frame, and then resets so the same motion cannot fire twice.
4. **Events (ours).** The recognizer emits an event, and the bindings run the actions.

Every gesture starts from a start pose (the first state of its state machine), except Walk Away, Hand Swipe and Lens Wipe, which come from whole-image motion. The pose only needs to show for a couple of frames as the motion begins; it is not a hold. A recognizer whose start pose never appeared cannot fire, which filters out most accidental motion and most conflicts.

When several recognizers still match the same motion, each match scores points for the conditions it met, with high-value conditions like near the ear worth more. The highest score fires. If the top two scores are too close, nothing fires. The tiebreaker collects matches for about 100ms before choosing, because competing gestures do not finish on the same frame.

MediaPipe also ships a Gesture Recognizer with seven ready-made gestures (closed fist, open palm, pointing up, thumb up, thumb down, victory, I-love-you), and it can be extended with a custom trained classifier. Those are still poses. Nearly all of our gestures involve motion or position (swipes, taps, Twist, Point, near the ear), so they are ours. The ready-made ones may help with Burst and Unburst, which are fist and open palm.

Larger gesture sets exist only as training data and trained models, not as a library to call. HaGRID version 2 has 33 gesture classes plus a no-gesture class, and a method for dynamic gestures like swipes, clicks and zooms. Jester has 148,092 webcam video clips in 27 classes, including swipes and hand turns. For tracking, Apple's Vision framework is a native alternative that returns 21 points per hand (macOS 11 and up). Proposed: stay with MediaPipe and our own rules, and try these only if a rule fails in testing.

Proposed approach: write rules first. If a rule cannot reach the target hit rate in testing, train a small classifier on our own recorded examples for that gesture.

Body tracking runs from day one. It keeps Walk Away from locking while you look down at your phone, because your shoulders stay visible, and its ear points place the Ear gestures.

| Tool | What it does |
| --- | --- |
| Live debug window | The camera image with the tracked points drawn on top, each gesture's current state and numbers (finger count, roll speed, hand distance), and the last events fired |
| Record and replay | Saves the tracked points (not video) for every frame to a file. Replay runs the recognizers on that file with no camera, so a change can be re-tested on the same data |
| Labeled examples | About 100 real performances of each gesture, plus long recordings of normal work to count false triggers |
| Scores | Hit rate and false triggers per hour for each gesture, re-run after every change |

What each threshold was tuned against, and the values that were tried and rejected: [TUNING.md](TUNING.md).

## Build checkpoints

The build runs in three stages. Code is written all at once; testing goes from the bottom layer up, so when something fails only one new layer can be the cause. Thresholds are guesses until stage 2 tunes them on real recordings. A failed gesture never blocks the others; it gets changed or moved to later.

| # | Build | Stop and test | Continue when | If it fails |
| --- | --- | --- | --- | --- |
| 1. Build it all | The whole pipeline in one pass: camera and MediaPipe hands and body (late frames dropped), features, events, recorder and replay, config bindings with hot reload, every default action, both window overview versions, Walk Away, all recognizers with guessed thresholds, the conflict rule, and the debug window | One session, bottom up: the debug window's numbers match what your hand does (0-4 fingers, roll, movement) and fps, CPU and memory hold over 10 minutes; each action works 10 of 10 from a script; the Twist roll shows clearly on camera; a synthesized Fn reaches Willow; replay of a recording fires its bindings | Every layer passes its check | Fix or cut on the spot. Twist not visible: change the gesture (for example a sideways wrist tilt) and the focus-app bindings. Fn ignored: use a second Willow hotkey. Notifications won't dismiss: Brush Off presses Escape or gets another job. CPU too high: add the motion check or lower resolution |
| 2. Tune | Record about 20 tries per gesture plus idle time, replay, adjust thresholds and conflict points. Twist and the swipes first, then the rest. After each change, replay every older recording too. Pick one window overview version | Hit rate and false triggers per gesture on replay; swipe recordings fire their swipe, not Twist-4 | Each gesture fires reliably, rarely fires by accident, and no older gesture got worse | Change the gesture or move it to later |
| 3. Ship and live with it | Decide Python or Swift, wrap as a menu-bar app that starts at login, then one week of daily use with a misfire log (this also covers Walk Away over full workdays, including phone use) | Review the log | Misfires are rare, no false locks while seated, and nothing is annoying enough to turn off | Retune thresholds; cut what annoys |

## Open questions

Nine items need a decision or a test before the build plan is final.

1. **MediaPipe or Apple Vision.** MediaPipe has depth on every hand point; Apple Vision is flat but runs on the Neural Engine and uses less power. Decided: MediaPipe only for stages 1 and 2. Apple Vision is revisited at stage 3 with the Python or Swift decision, using the battery measured in stage 1. fasthands (MediaPipe's hand models on the Neural Engine) is an upgrade to try either way.
2. **Hand orientation.** Swipe Left/Right (the hand leans), Swipe Up/Down (the palm flips), Twist (the hand rolls, fingers upright) and Brush Off (palm toward you, then turned out) share the four-finger pose and are separated by which way the hand moves. Known overlaps found in recordings: a 150-degree Twist-4 passes through Brush Off's start pose (the earlier start wins the tie), a lean looked like Twist-4 (Twist now requires upright fingers), and a palm flip passes through a lean (a lean must stop short of 110 degrees).
3. **Window overview.** Decided: Mission Control only (Talos Control dropped); Burst opens it and Unburst closes it; Swipe Up zooms the front window; no Swipe Down.
4. **Window selection.** Point (pinch) or Flick, user's choice. Cursor aim is the last resort.
5. **Willow and the Fn key.** Decided: a synthesized Fn press works (the user verified it with Willow).
6. **Dismiss notification.** Decided: yes, through Accessibility. macOS 15 draws Notification Center in SwiftUI, out of AppleScript's reach, so Talos finds the notification elements directly and presses their Close (verified on a real notification; widgets are left alone).
7. **Brush Off.** Confirmed from collected clips (see its row): it separates from Twist by the held start pose and from the swipes by ending palm to the camera.
8. **Python or Swift for the finished app.** Decided: Python. The menu-bar app (rumps) and the Talos.app bundle (py2app) work, and permissions belong to the bundle. Revisit if battery is a problem: the pipeline uses about one CPU core (102-126% in stage 1), and the cheaper fixes come first (lower frame rate when no hand is in view, fasthands, Apple Vision).
9. **Name and files.** Check availability of Talos. For Claude Code, keep this spec and a separate build plan as two markdown files.
