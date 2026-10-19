#!/usr/bin/env python3
"""Build a standalone openflydigi3 application with PyInstaller.

The repository folder may be named anything (``openflydigi3``, the GitHub
repo name, …) but the code always imports itself as ``openflydigi3``, so
the sources are first staged under that name in ``build/stage/``.  Icons are
generated on the fly, PyInstaller builds the app, the result is smoke-tested
and finally packaged per platform:

    Windows :  release/openflydigi3-<ver>-windows-<arch>.exe  (single file)
    macOS   :  release/openflydigi3-<ver>-macos-<arch>.zip    (.app bundle)
    Linux   :  release/openflydigi3-<ver>-<arch>.AppImage

Usage:
    python packaging/build.py [--skip-smoke]
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
STAGE = BUILD / "stage"  # STAGE/<PKG> is the importable package copy
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
APP_NAME = "openflydigi3"
PKG = "openflydigi3"
BUNDLE_ID = "io.github.openopenflydigi3"

APPMAGETOL_URL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    "appimagetool-{arch}.AppImage"
)

# Everything that must never end up inside the staged package.  "cache" drops
# the unused 40 MB ui/resources/images/cache GIF directory.
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".git", ".github", ".venv", "venv",
    "build", "dist", "release", "packaging", ".idea", ".vscode",
    "*.egg-info", "cache", "settings.json",
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sh(cmd: list, **kw) -> None:
    """Run a command, echoing it, failing the build on error."""
    printable = " ".join(str(c) for c in cmd)
    print(f"+ {printable}", flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def arch() -> str:
    """Normalised architecture name (AMD64 → x86_64)."""
    return {"amd64": "x86_64"}.get(platform.machine().lower(), platform.machine().lower())


# --------------------------------------------------------------------------- #
# build steps
# --------------------------------------------------------------------------- #
def stage_sources() -> None:
    """Copy the sources under their import name + add an entry script."""
    print(f"==> Staging sources as {PKG}/")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    shutil.copytree(ROOT, STAGE / PKG, ignore=IGNORE)
    (STAGE / "entry.py").write_text(
        '"""PyInstaller entry point for openflydigi3."""\n'
        "\n"
        "from openflydigi3.main import main\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    # Import-level smoke test before spending minutes in PyInstaller.
    sh([sys.executable, "-c", "import openflydigi3.main"], cwd=STAGE)


def app_version() -> str:
    text = (STAGE / PKG / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "0.0.0"


def _icon_master(size: int = 1024):
    """Render the app icon on a 1024×1024 design grid and scale it."""
    from PIL import Image, ImageDraw

    s = size / 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        return [x0 * s, y0 * s, x1 * s, y1 * s]

    dark = (27, 29, 33, 255)   # splash-screen background
    orange = (255, 87, 34, 255)  # splash-screen accent

    # Dark rounded tile.
    d.rounded_rectangle(box(0, 0, 1023, 1023), radius=224, fill=dark)

    # Controller silhouette: stadium body + two grip lobes (same colour so
    # the shapes merge seamlessly).
    d.rounded_rectangle(box(140, 252, 884, 596), radius=172, fill=orange)
    d.ellipse(box(110, 412, 370, 772), fill=orange)
    d.ellipse(box(654, 412, 914, 772), fill=orange)

    # D-pad (left).
    d.rounded_rectangle(box(275, 382, 445, 466), radius=16, fill=dark)
    d.rounded_rectangle(box(318, 339, 402, 509), radius=16, fill=dark)

    # Four buttons in a diamond (right).
    for cx, cy in ((668, 348), (668, 500), (592, 424), (744, 424)):
        d.ellipse(box(cx - 46, cy - 46, cx + 46, cy + 46), fill=dark)

    return img


def make_icons() -> dict:
    """Generate the PNG (all platforms) plus .ico/.icns where useful."""
    print("==> Generating icons")
    from PIL import Image

    out = BUILD / "icons"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    master = _icon_master(1024)

    icons: dict = {}
    png = out / f"{PKG}.png"
    master.resize((256, 256), Image.LANCZOS).save(png)
    icons["png"] = png

    if sys.platform == "win32":
        ico = out / f"{PKG}.ico"
        master.save(
            ico,
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
        icons["ico"] = ico

    if sys.platform == "darwin":
        iconset = out / f"{APP_NAME}.iconset"
        iconset.mkdir()
        for logical in (16, 32, 128, 256, 512):
            master.resize((logical, logical), Image.LANCZOS).save(
                iconset / f"icon_{logical}x{logical}.png"
            )
            master.resize((logical * 2, logical * 2), Image.LANCZOS).save(
                iconset / f"icon_{logical}x{logical}@2x.png"
            )
        icns = out / f"{PKG}.icns"
        sh(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)])
        icons["icns"] = icns

    return icons


def run_pyinstaller(icons: dict) -> None:
    """Run PyInstaller with platform-appropriate options."""
    print("==> PyInstaller")
    sep = os.pathsep  # ';' on Windows, ':' elsewhere
    (BUILD / "spec").mkdir(parents=True, exist_ok=True)

    args: list = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--windowed",
        "--specpath", BUILD / "spec",
        "--workpath", BUILD / "pyi",
        "--distpath", DIST,
        "--paths", STAGE,
        "--add-data", f'{STAGE / PKG / "configs"}{sep}{PKG}/configs',
        "--add-data", f'{STAGE / PKG / "data"}{sep}{PKG}/data',
        "--add-data",
        f'{STAGE / PKG / "ui" / "resources" / "images"}'
        f'{sep}{PKG}/ui/resources/images',
        # Conditional imports that PyInstaller cannot always reach:
        "--hidden-import", "hid",
        "--hidden-import", "serial",
        "--hidden-import", "serial.tools.list_ports",
    ]
    if sys.platform == "win32":
        args += ["--onefile", "--icon", icons["ico"]]
    elif sys.platform == "darwin":
        args += [
            "--onedir", "--icon", icons["icns"],
            "--osx-bundle-identifier", BUNDLE_ID,
        ]
    else:
        args += ["--onedir"]
    args.append(STAGE / "entry.py")

    sh(args, cwd=ROOT)


def _kill_tree(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


def smoke_test(exe: Path, timeout: int = 60) -> None:
    """Launch the built app; fail if it crashes instead of staying alive."""
    print(f"==> Smoke test: {exe}")
    if not exe.exists():
        raise SystemExit(f"smoke test failed: {exe} was not built")
    env = os.environ.copy()
    if sys.platform != "win32":
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(exe.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=(sys.platform != "win32"),
    )
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            code = proc.poll()
            if code is not None:
                if code == 0:
                    print("app exited cleanly on its own")
                    return
                raise SystemExit(f"smoke test failed: exit code {code}")
            time.sleep(0.5)
        print("app still running after startup window -> OK")
    finally:
        _kill_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


def _appimagetool() -> Path:
    """Download appimagetool once and reuse it (no FUSE needed)."""
    machine_arch = arch()
    tool_arch = "aarch64" if machine_arch in ("arm64", "aarch64") else machine_arch
    path = BUILD / "downloads" / f"appimagetool-{tool_arch}.AppImage"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = APPMAGETOL_URL.format(arch=tool_arch)
        print(f"==> Downloading {url}")
        urllib.request.urlretrieve(url, path)
    path.chmod(path.stat().st_mode | 0o111)
    return path


def package_linux(version: str, icons: dict) -> Path:
    """Wrap the onedir build into an AppImage."""
    print("==> Packaging AppImage")
    appdir = BUILD / "AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)

    payload = appdir / "usr" / "app"
    payload.mkdir(parents=True)
    shutil.copytree(DIST / APP_NAME, payload / APP_NAME)

    apprun = appdir / "AppRun"
    shutil.copy2(ROOT / "packaging" / "AppRun", apprun)
    apprun.chmod(0o755)
    shutil.copy2(
        ROOT / "packaging" / "openflydigi3.desktop",
        appdir / "openflydigi3.desktop",
    )
    shutil.copy2(icons["png"], appdir / "openflydigi3.png")

    out = RELEASE / f"{APP_NAME}-{version}-{arch()}.AppImage"
    sh(
        [_appimagetool(), "--appimage-extract-and-run", appdir, out],
        env={**os.environ, "ARCH": arch()},
    )
    out.chmod(out.stat().st_mode | 0o111)
    return out


def package(version: str, icons: dict) -> Path:
    """Produce the final distributable in release/."""
    print("==> Packaging")
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    RELEASE.mkdir()

    if sys.platform == "win32":
        dest = RELEASE / f"{APP_NAME}-{version}-windows-{arch()}.exe"
        shutil.copy2(DIST / f"{APP_NAME}.exe", dest)
        return dest

    if sys.platform == "darwin":
        dest = RELEASE / f"{APP_NAME}-{version}-macos-{arch()}.zip"
        # ditto keeps the bundle's symlinks intact, unlike plain zip.
        sh(["ditto", "-c", "-k", "--keepParent", DIST / f"{APP_NAME}.app", dest])
        return dest

    return package_linux(version, icons)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build openflydigi3 executables")
    parser.add_argument(
        "--skip-smoke", action="store_true",
        help="do not launch the built app after building",
    )
    args = parser.parse_args()

    stage_sources()
    version = app_version()
    print(f"==> Building {APP_NAME} {version} for {sys.platform}-{arch()}")

    icons = make_icons()
    run_pyinstaller(icons)

    if not args.skip_smoke:
        if sys.platform == "win32":
            exe = DIST / f"{APP_NAME}.exe"
        elif sys.platform == "darwin":
            exe = DIST / f"{APP_NAME}.app" / "Contents" / "MacOS" / APP_NAME
        else:
            exe = DIST / APP_NAME / APP_NAME
        smoke_test(exe)

    artifact = package(version, icons)
    size_mb = artifact.stat().st_size / 1024 / 1024
    print(f"==> Done: {artifact} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
