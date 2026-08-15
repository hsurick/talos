import os
import sys
from pathlib import Path

# Where config.yaml (the defaults) and models/ are: the source folder, or Talos.app's Resources when bundled by py2app.
ROOT = Path(os.environ["RESOURCEPATH"]) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
