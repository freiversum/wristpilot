# Architecture

## Why a bridge

Connect IQ apps can use Bluetooth LE only in the central role (scan, connect, read and write
GATT). A watch cannot advertise, so it cannot pose as a Zwift Click/Play, a BLE keyboard or an
OpenBikeControl controller. ZWindoor turns the roles around: a program on the Zwift computer acts
as a BLE peripheral with its own GATT service, and the watch connects to it.

```
Garmin watch / Edge (Connect IQ, BLE central)
   |  GATT write: command [seq, action, value]
   v
zwindoor_bridge (Python core: protocol, action table, engine, acknowledgements)
   |  BLE peripheral: BlueZ over D-Bus (Linux) | WinRT GattServiceProvider (Windows)
   |
   +-- Output A: keyboard  -> Zwift window
   |     Windows: SendInput (scan codes)
   |     Linux:   XTest into the X11 display of Wine, or uinput
   +-- Output B: OpenBikeControl (mDNS + TCP) -> MyWhoosh, TrainingPeaks Virtual, Incyclist ...
   +-- Output C: Zwift Companion link (optional, opt-in) -> game state back to the watch
   |
   +-- GATT notify: acknowledgement, bridge state, game state -> watch
```

## Components

| Path | Content |
|---|---|
| `bridge/zwindoor_bridge/protocol.py` | wire protocol between watch and bridge |
| `bridge/zwindoor_bridge/actions.py` | action table: OpenBikeControl button IDs to Zwift keyboard shortcuts |
| `bridge/zwindoor_bridge/engine.py` | handles commands: focus check, bring Zwift to the front, typing, acknowledgement |
| `bridge/zwindoor_bridge/keys.py` | logical key names to X11 keysyms, Windows scan codes and evdev codes |
| `bridge/zwindoor_bridge/sinks/` | keyboard outputs: `windows.py` (SendInput), `xtest.py` (X11/XWayland, Wine), `uinput.py` |
| `bridge/zwindoor_bridge/ble/` | GATT peripheral: `bluez.py` (BlueZ over dbus-fast), `winrt_backend.py` (Windows, WinRT API via pywinrt), `bless_backend.py` (macOS) |
| `bridge/zwindoor_bridge/obc.py`, `announce.py` | OpenBikeControl server and its mDNS announcement (Avahi on Linux, python-zeroconf on Windows) |
| `bridge/zwindoor_bridge/companion.py`, `pb.py`, `zwiftapi.py` | Zwift Companion link, minimal protobuf codec, Zwift web calls |
| `bridge/zwindoor_bridge/config.py` | settings as JSON (`%APPDATA%\Zwindoor\config.json`, `~/.config/zwindoor/config.json`) |
| `bridge/zwindoor_bridge/runner.py`, `__main__.py` | event loop in its own thread, command line |
| `bridge/tests/` | tests (pytest), including a simulated game over TCP |
| `bridge/tools/fake_watch.py` | plays the watch over bleak (needs a second computer) |
| `windows/` | tray program for Windows (pystray), Zwift sign-in (`zwiftlogin.py`), build script |
| `watch/` | Connect IQ app (Monkey C), see [watch/README.md](../watch/README.md) |
| `tools/sync-tretlager.sh` | copies the core into Tretlager |

One core, two shells: the Windows tray program and the *Watch remote* page in
[Tretlager](https://github.com/freiversum/tretlager) both use the package `zwindoor_bridge`. Only
the radio backend and the keyboard output differ. Tretlager carries a vendored copy of the core
(`tretlager/zwindoor/`).

## Protocol watch <-> bridge

GATT service `ae279be2-4f9c-4165-ab88-060ee241b936`:

| Characteristic | UUID | Direction | Content |
|---|---|---|---|
| Command | `...b937` | watch -> bridge, write | `[seq, action, value]` |
| Status | `...b938` | bridge -> watch, read / notify | see below |
| Info | `...b939` | read | UTF-8 text `ZWindoor <version> · <host>` |

Command fields:

- `seq` – 0-255, wraps; echoed in the acknowledgement
- `action` – OpenBikeControl button ID (table: `python -m zwindoor_bridge --list-actions`)
- `value` – 1 = press (default); emote, camera view or screenshot type for those actions

Status messages:

| Message | Meaning |
|---|---|
| `[0x01, seq, result]` | acknowledgement: 0 OK, 1 Zwift not in front, 2 Zwift not running, 3 unknown action, 4 output failed, 5 remote disabled, 6 malformed |
| `[0x02, flags]` | bridge state, on subscribe and on change: 0x01 Zwift running, 0x02 Zwift focused, 0x04 OpenBikeControl app connected, 0x08 keyboard on, 0x10 enabled, 0x20 Companion link active |
| `[0x03, pattern]` | haptic request from an OpenBikeControl app |
| `[0x04, flags, powerup, rideOnsLo, rideOnsHi]` | game state from the Companion link: 0x01 linked, 0x02 junction ahead, 0x04/0x08/0x10 left/straight/right offered, 0x20 power-up ready |

The watch writes with response, so that every write is confirmed by the stack, and sends a ping
(`[seq, 0x00, 0]`) every 5 seconds when idle. The bridge answers with its state and considers the
watch gone after 15 seconds of silence. Each command is acknowledged; the watch shows "not
arrived" if no acknowledgement comes within 500 ms and drops commands that waited more than one
second in its queue (a late "turn left" is worse than none).

The bridge advertises the service UUID with flags 0x06 (LE General Discoverable, BR/EDR not
supported). Connect IQ drops scan results without "general discoverable". The watch also matches
on the device name and offers a manual device list, because some watches receive empty advertising
data.

### Keyboard output

The bridge types Zwift's documented keyboard shortcuts (arrow keys to turn, space for the
power-up, F1-F10 for emotes, photo and video, 1-0 for camera views, H for the HUD, Tab and
Page Up/Down for workouts). Each action's key can be changed in the settings. Before typing, the
bridge checks that the Zwift window has the keyboard focus; if not, it brings it to the front or
refuses with "Zwift not in front". It never types into another window. Since 2025 the up arrow
opens Zwift's action menu; going straight on is Zwift's default at a junction.

## OpenBikeControl

With `--obc` (or the switch in the tray program or Tretlager) the bridge also acts as an
[OpenBikeControl](https://openbikecontrol.org/protocol) device over the network transport:

- announces `_openbikecontrol._tcp` over mDNS and listens on TCP (default port 36870)
- sends `[0x01, button, state]` (press and release) for every command from the watch, plus
  `[0x02, battery, connected]` status messages
- receives `[0x03, pattern, duration, intensity]` (haptic, forwarded to the watch) and
  `[0x04, ...]` (app info with supported buttons)

Because the watch already speaks OpenBikeControl button IDs, no second action table is needed.
ZWindoor-specific actions (bell, photo, video) use the app-specific range 0x80-0x9F or app-specific
values.

## Zwift Companion link

Opt-in. **It uses Zwift's undocumented relay and protocol, which contradicts Zwift's terms of
service.**

1. The bridge listens on TCP (default port 21587, Zwift's port for the Companion app; any free port
   if taken).
2. With the user's Zwift access token it registers its LAN address and port as the "phone" of the
   account (`PUT /relay/profiles/me/phone`) and repeats that every minute while no game is
   connected. Only one phone per account: this replaces the real Companion app.
3. The running game connects. Every message is a 4-byte big-endian length followed by a protobuf
   message (`GameToCompanion` from the game, `CompanionToGame` to the game), in the plain
   (unencrypted) mode also used by Sauce for Zwift. Field numbers come from Sauce for Zwift
   (`zwift.proto`, GPL-3.0) and RoadCaptain.
4. After the connection the bridge sends client info, pairing, session start and opens the action
   bar, then a heartbeat about once per second, like the real Companion app.
5. From the game it reads the power-up (set, activated, cleared), the turn options at the next
   junction and social actions (received Ride Ons) and forwards them as `[0x04, ...]` to the watch.
6. Turns (left 1010, straight 1011, right 1012), U-turn, Ride On, power-up, emotes, photo, video,
   camera and HUD go to the game as Companion commands. Workout keys stay on the keyboard.

The Windows program signs in through the browser (Zwift's launcher sign-in; the user pastes the
redirect address) and stores the token with DPAPI. Tretlager hands in the token from its own
sign-in. A small protobuf encoder and decoder (`pb.py`) avoids a protobuf dependency.

Open questions about the link are tracked in [BACKLOG.md](../BACKLOG.md).
