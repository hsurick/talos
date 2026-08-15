<div align="center">

<h1>✋ Talos</h1>

<p><b>Control your Mac with hand gestures through the webcam.</b><br>
Switch apps, snap and zoom windows, drive Mission Control, play music and lock up, all without touching the keyboard.</p>

<p>
<img src="https://img.shields.io/badge/macOS-15%2B-000000?logo=apple&logoColor=white" alt="macOS 15+">
<img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
<img src="https://img.shields.io/badge/MediaPipe-hands%20%2B%20pose-0097A7?logo=google&logoColor=white" alt="MediaPipe">
<img src="https://img.shields.io/badge/privacy-100%25%20on--device-2ea44f" alt="100% on-device">
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
</p>

<p>
<a href="#-gestures">Gestures</a> ·
<a href="#-install">Install</a> ·
<a href="#%EF%B8%8F-configure">Configure</a> ·
<a href="#-privacy">Privacy</a> ·
<a href="#-development">Development</a>
</p>

</div>

Re-upload of my old Talos project. RIP old github account

---

Talos lives in the menu bar. It watches the built-in camera with Google's MediaPipe hand and body models, recognizes
a small set of deliberate gestures, and runs the actions you bind to them. Every gesture shows a short popup naming
what it did, so a missed gesture is never confused with a failed action.

> [!NOTE]
> Accuracy varies by gesture; see [Known limits](#-known-limits).

## ✋ Gestures

| Gesture | How | Default action |
| --- | --- | --- |
| **Twist 1–4** | 1–4 fingers up (Twist 4: thumb tucked), roll the hand and back | Open Safari / Mail / Notes / Music |
| **Swipe Left / Right** | Hand edge-on, fingers up: lean the fingers left or right | Snap the window to that half, then to the next monitor |
| **Swipe Up** | Palm flat, fingers sideways: flip the fingers up | Zoom the front window (Window › Zoom) |
| **Burst** | Fist facing the camera, open to five fingers | Open Mission Control |
| **Unburst** | Five fingers facing the camera, close to a fist | Close Mission Control |
| **Point** | In Mission Control: point a finger at a window, then pinch thumb and index (or raise your pinky) | Choose that window |
| **Flick** *(instead of Point)* | In Mission Control: snap the open hand toward a window and back | Choose that window |
| **Ear Tap** | Point at your ear, take the hand away | Play / pause |
| **Ear Up / Down** | Point at your ear, leave upward / stay a moment and leave downward | Next / previous track |
| **Ear Hold** | Two fingers at the ear like an earpiece, press | Hold Fn (dictation) while held |
| **Brush Off** | Open palm toward you, flick the fingers away | Dismiss a notification |
| **Hand Swipe / Lens Wipe** | Sweep a hand across the camera / slide it over the lens | Lock the screen and pause media |
| **Walk Away** | Leave the camera's view for 15 s | Lock the screen and pause media |

Hands only count when raised above the keyboard and in front of your face, so typing, resting your chin or touching
your hair doesn't trigger anything.

## 📦 Install

Requires macOS 15 (Sequoia) or later on Apple silicon, and a webcam.

**With Homebrew** (recommended):

```sh
brew install hsurick/talos/talos
ln -sf "$(brew --prefix)/opt/talos/Talos.app" /Applications/Talos.app
open /Applications/Talos.app
```

**Or download it:** get **Talos.zip** from the [latest release](https://github.com/hsurick/talos/releases/latest),
unzip it, and drag **Talos** into Applications. macOS blocks it the first time, because Talos isn't signed with a
paid Apple developer account: go to System Settings › Privacy & Security, scroll down, and click **Open Anyway**
next to "Talos was blocked". You only do this once. (Homebrew installs skip this step.)

Then allow **Camera** when asked, and turn on **Talos** under System Settings › Privacy & Security ›
**Accessibility** (needed to press keys, move windows and drive Mission Control).

A hand icon appears in the menu bar. After an update, macOS may ask for Camera and Accessibility again: an unsigned
app looks new to it each version. If Accessibility already lists Talos but gestures don't act, remove it with **−**
and add it again.

The menu-bar icon turns the camera on and off and opens **Settings…**, the event log, "That was a mistake" (marks
the last gesture as a misfire in the log) and **Start at login**.

## ⚙️ Configure

Open **Settings…** from the menu-bar icon to pick each gesture's actions. Changes apply immediately. Settings are
stored in `~/Library/Application Support/Talos/config.yaml` (menu › Open config), which you can also edit by hand;
it starts as a copy of the defaults in [`config.yaml`](config.yaml):

```yaml
bindings:
  twist_1:
  - focus_app: Safari
  swipe_left:
  - snap_window: left
  hand_swipe:          # a gesture can run several actions
  - lock_screen
  - pause_media
settings:
  walk_away_seconds: 15
  select_with: point   # or flick
  choose_with: pinch   # or pinky: Point chooses by raising the pinky
```

<details>
<summary><b>All actions</b></summary>

| Action | Argument |
| --- | --- |
| `focus_app` | App name |
| `snap_window` | `left` or `right` |
| `zoom_window` | |
| `open_overview` / `close_overview` | Mission Control |
| `select_window` | Point and Flick only |
| `play_pause`, `next_track`, `previous_track` | |
| `pause_media` | Pauses Music and Spotify |
| `lock_screen` | |
| `hold_key` / `press_key` | `fn`, `escape` or `q` |
| `dismiss_notification` | |
| `run_shortcut` | A Shortcuts name |
| `run_shell` | A shell command |

</details>

## 🔒 Privacy

- All tracking runs on your Mac. No video is saved or sent anywhere.
- Recordings (for testing) hold only tracked point coordinates, never images.
- The camera turns off from the menu-bar icon.

## 🚧 Known limits

- **Accuracy:** Twist, Swipe Left/Right, Burst/Unburst and Hand Swipe are reliable. Point and Flick pick the right
  window about 2 times in 3. Ear gestures, Brush Off and the pinch (a single camera can't tell when fingertips only
  overlap) still misfire.
- **Zoom** looks for an English "Window › Zoom" menu item, falling back to the window's zoom button.
- Thresholds are tuned on one person's recordings, so your hands may need different ones.

## 🛠 Development

Run from source (Python 3.12):

```sh
git clone https://github.com/hsurick/talos.git && cd talos
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p models   # MediaPipe models, ~10 MB
curl -L -o models/hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
curl -L -o models/pose_landmarker_lite.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task

python setup.py py2app -A && open dist/Talos.app   # dev build: runs this folder's code, no rebuild after edits
```

```sh
python -m talos app                  # the menu-bar app from the terminal (permissions then belong to the terminal)
python -m talos --debug --dry-run    # camera + tracked points + gesture states; prints actions instead of running them
python -m talos action snap_window left   # run one action
python -m talos collect [GESTURE]    # guided session: do each prompted gesture; labeled clips go to tests/data
python -m talos replay FILE.jsonl.gz # the events a recording produces, no camera
python -m pytest -q                  # unit tests
python tools/eval.py [-v]            # score every gesture on the labeled clips in tests/data
python tools/eval.py --trace FILE [N] # what fired per clip; with N, the math frame by frame
```

**Release:** `./release.sh` builds the standalone app (Python, libraries and models inside), signs it ad hoc and
writes `dist/Talos.zip`; attach that to a GitHub release, then put the new version, URL and the printed sha256 in
`Formula/talos.rb` of [homebrew-talos](https://github.com/hsurick/homebrew-talos). It replaces the dev build in `dist/`.

`tests/data` holds labeled recordings (tracked points only) that act as the gesture regression suite: change a
threshold, run `tools/eval.py`, and see what got better and worse. The design and the reasoning behind every
gesture are in [SPEC.md](SPEC.md).

## License

[MIT](LICENSE)
