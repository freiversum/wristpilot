# Building ZWindoor

## Bridge core (Python)

Python 3.11 or newer. On Linux the BLE peripheral uses BlueZ over `dbus-fast`.

```bash
python3 -m venv .venv
.venv/bin/pip install dbus-fast pytest pytest-asyncio Pillow pystray
```

### Run the tests

```bash
cd bridge && ../.venv/bin/python -m pytest -q
cd ../windows && PYTHONPATH=../bridge ../.venv/bin/python -m pytest -q test_tray.py
```

The GitHub Actions workflow `.github/workflows/ci.yml` runs both on every push to `main`.

### Run the bridge on Linux (for testing)

```bash
cd bridge
../.venv/bin/python -m zwindoor_bridge --dry-run -v
```

| Option | Effect |
|---|---|
| `--dry-run` | log actions instead of typing them |
| `--obc` | also offer an OpenBikeControl controller on the network |
| `--adapter hci1` | use a specific BlueZ adapter |
| `--list-actions` | print the action table and exit |
| `-v` | verbose log |

Settings are read from `~/.config/zwindoor/config.json` (Windows: `%APPDATA%\Zwindoor\config.json`).

`bridge/tools/fake_watch.py` plays the watch over [bleak](https://github.com/hbldh/bleak) and
measures latency. It needs a second computer or Bluetooth adapter, since an adapter cannot connect
to itself.

## Windows program

`windows/build.ps1` builds `ZWindoorBridge.exe` as a single file with
[Nuitka](https://nuitka.net). On Windows with Python 3.11+ installed, in the folder `windows\`:

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

The script creates its own virtual environment (`.venv-build`), installs the bridge with the
`tray` extra plus Nuitka, writes `zwindoor.ico` (`make_ico.py`) and builds
`windows\dist\ZWindoorBridge.exe`.

Releases are built by GitHub Actions: pushing a tag `vX.Y.Z` runs
`.github/workflows/release.yml` on a Windows runner, which builds the .exe, writes
`SHA256SUMS.txt` and attaches both to the GitHub release. The workflow can also be started by
hand (`workflow_dispatch`); the files are then available as a build artifact.

## Watch app (Connect IQ)

1. Install the [Connect IQ SDK](https://developer.garmin.com/connect-iq/sdk/) with the SDK
   Manager and download the devices you want to build for.
2. Create a developer key once and keep it safe – store updates are only possible with the same
   key:

   ```
   openssl genrsa -out developer_key.pem 4096
   openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt
   ```

3. Build, in the folder `watch/`:

   ```
   # one device, for the simulator or sideloading
   monkeyc -d fenix7xpro -f monkey.jungle -o bin/zwindoor.prg -y developer_key.der

   # store package for all devices in manifest.xml
   monkeyc -e -r -f monkey.jungle -o dist/ZWindoor.iq -y developer_key.der
   ```

| Jungle file | Purpose |
|---|---|
| `monkey.jungle` | release build; picks the display style per device (`source-style-mip`, `source-style-amoled`, `source-style-edge`) and the launcher icon size (`resources-icon35` to `resources-icon68`) |
| `monkey-demo.jungle` | demo build for store screenshots: `source-demo/Build.mc` pretends to be connected, with a junction ahead and a power-up (the simulator has no Bluetooth) |
| `monkey-beta.jungle` | beta build with `manifest-beta.xml` and its own app ID, for private testing through the store |

Launcher icons: `../.venv/bin/python tools/make_icon.py`. Store images from simulator captures in
`watch/store/raw/`: `../../.venv/bin/python make_assets.py` in `watch/store/`. Store texts in
English and German are in `watch/store/listing.md`.

More about the app, the simulator and sideloading: [watch/README.md](../watch/README.md).

## Sync the core to Tretlager

[Tretlager](https://github.com/freiversum/tretlager) carries a vendored copy of the bridge core.
With both repositories cloned side by side:

```bash
tools/sync-tretlager.sh                 # default target: ../tretlager/tretlager/zwindoor
tools/sync-tretlager.sh /path/to/tretlager/tretlager/zwindoor
```

The script copies `bridge/zwindoor_bridge/` (without `__main__.py`) and writes a `VENDORED.md`
with the version. Run Tretlager's tests afterwards and commit there.
