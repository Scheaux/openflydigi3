# openflydigi3

An unofficial, open-source configuration tool for Flydigi Apex 4 (should probably work on other gamepads too), written in Python + PyQt6. It runs on **Linux** and should
run on Windows and macOS, talking to controllers over HID / USB-CDC /
Bluetooth LE instead of the original Windows kernel drivers.

![status](https://img.shields.io/badge/status-work%20in%20progress-yellow)
![license](https://img.shields.io/badge/license-MIT-blue)

> **Disclaimer:** openflydigi3 is an independent, community-made project.
> It is **not affiliated with, endorsed by, sponsored by, or connected to
> Flydigi (Flydigi Gamepad / 北通) in any way**. "Flydigi" and the names of
> Flydigi products are trademarks of their respective owners, used here
> only for identification and compatibility purposes.

## Features

- Scan for and connect to controllers over HID, serial (USB-CDC) and BLE
- Load and edit device profiles (button remap, stick curves, trigger tuning)
- LED lighting control with live preview and one-click apply
- Firmware flashing with progress and logging
- Dark-themed UI with persisted settings

## Requirements

- Python 3.10+
- Qt 6 (bundled with PyQt6)

```bash
pip install -r requirements.txt
```

## Usage

```bash
python3 main.py
```

On a headless machine you can smoke-test the UI with:

```bash
QT_QPA_PLATFORM=offscreen python3 main.py
```

## Building standalone executables

CI (`.github/workflows/build.yml`) builds a runnable app for every platform
on each push. A successful push to `main` also updates a rolling
**continuous** prerelease with fresh binaries, and pushing a `v*` tag
(e.g. `v1.0.0`) publishes a full GitHub Release:

- **Windows** — single-file `openflydigi3-<version>-windows-x86_64.exe`
- **macOS** — zipped `.app` bundle (`openflydigi3-<version>-macos-<arch>.zip`)
- **Linux** — `openflydigi3-<version>-x86_64.AppImage`

To build locally on any platform:

```bash
pip install -r requirements.txt pyinstaller pillow
python packaging/build.py
```

The script stages the sources under their `openflydigi3` import name,
generates the icon, runs PyInstaller, smoke-tests the result and writes the
artifact to `release/`.

> **Note:** downloaded macOS builds are unsigned — on first launch, right-click
> the app and choose *Open* (or run `xattr -dr com.apple.quarantine` on it).

## Hardware access on Linux

Devices are accessed directly, without the original Windows drivers:

- **HID** — via [`hidapi`](https://github.com/trezor/cython-hidapi)
- **Serial / USB-CDC** — `/dev/ttyACM*` via `pyserial` (firmware flash mode)
- **Bluetooth LE** — via [`bleak`](https://github.com/hbldh/bleak)

Controller handles are opened ephemerally for each operation so that the
kernel's `xpad` driver stays bound and game input keeps working.

## Contributing

Issues and pull requests are welcome. Please keep the non-affiliation
notice intact in derived works.

## License

This project is licensed under the [MIT License](LICENSE).

The original *Flydigi Space Station* Windows application and its drivers
are proprietary software owned by their respective owners. This project
does not include, redistribute, or depend on them at runtime.


