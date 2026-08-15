"""Builds Talos.app, the menu-bar app, so macOS permissions (Camera, Accessibility) belong to Talos, not the terminal.

  python setup.py py2app       standalone app (Python, libraries, models and default config inside), for releases
  python setup.py py2app -A    alias build for development: runs this folder's code with .venv, no rebuild needed
"""
from setuptools import setup

from talos.app import BUNDLE_ID

VERSION = "0.2.0"

setup(
    app=["talos_app.py"],
    data_files=["config.yaml", ("models", ["models/hand_landmarker.task", "models/pose_landmarker_lite.task"])],
    options={"py2app": {
        # Copied as folders, not zipped: MediaPipe and OpenCV load native libraries and data files from next to
        # their Python files.
        "packages": ["talos", "mediapipe", "cv2", "numpy", "rumps", "yaml"],
        "excludes": ["pytest", "_pytest", "pygments", "setuptools"],  # development tools; nothing imports them at runtime
        "plist": {
            "CFBundleName": "Talos",
            "CFBundleDisplayName": "Talos",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "15.0",
            "LSUIElement": True,  # menu-bar only: no Dock icon, no app menu
            "NSCameraUsageDescription": "Talos watches for hand gestures. Video stays on your Mac and is never saved.",
            "NSAppleEventsUsageDescription": "Talos pauses Music and Spotify and dismisses notifications.",
        },
    }},
)
