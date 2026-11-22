"""Where things live, both when running from source and as a packaged executable (PyInstaller).

- Bundled, read-only content (data/*.json, default config) sits next to the code, or inside the
  executable's unpack folder (sys._MEIPASS) when frozen.
- Writable files (saves, the user's config.json) must survive between runs, so a frozen build keeps them
  in a "KindredRoads_data" folder next to the executable (falling back to the user's home folder if that
  location is read-only). From source (and the portable Windows folder) they stay in the game folder,
  again falling back to the home folder if it is read-only (e.g. unzipped into Program Files).
"""
import os
import sys

FROZEN = getattr(sys, "frozen", False)
SOURCE_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BUNDLE_ROOT = getattr(sys, "_MEIPASS", SOURCE_ROOT)


def _writable_root():
    if FROZEN:
        first = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "KindredRoads_data")
    else:
        first = SOURCE_ROOT  # running from source / the portable Windows folder
    candidates = [first, os.path.join(os.path.expanduser("~"), "KindredRoads_data")]
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            probe = os.path.join(c, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return c
        except OSError:
            continue
    return candidates[-1]


USER_ROOT = _writable_root()
DATA_DIR = os.path.join(BUNDLE_ROOT, "data")
DEFAULT_CONFIG = os.path.join(BUNDLE_ROOT, "config.json")
CONFIG_PATH = os.path.join(USER_ROOT, "config.json")
SAVE_DIR = os.path.join(USER_ROOT, "saves")
