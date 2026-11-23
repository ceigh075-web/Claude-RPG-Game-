# PyInstaller build spec:  pyinstaller KindredRoads.spec
# Produces a single-file executable (dist/KindredRoads or dist/KindredRoads.exe) with all game data bundled.
# Saves and the user's config.json are written to a "KindredRoads_data" folder next to the executable.
import sys

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[("data", "data"), ("config.json", "."), ("assets/icon32.png", "assets"),
           ("assets/pixel_crawler", "assets/pixel_crawler"), ("ASSETS.md", ".")],
    hiddenimports=[],
    excludes=["tkinter", "numpy", "unittest", "test", "pydoc"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="KindredRoads",
    console=False,          # no terminal window on Windows
    upx=False,
    icon="assets/icon.png" if sys.platform == "win32" else None,  # PyInstaller converts it (needs Pillow)
)
