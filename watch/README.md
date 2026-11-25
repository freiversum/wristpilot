# Wristpilot – watch app (Connect IQ)

Watch app for Garmin watches and Edge bike computers. The device connects as a BLE central to
the Wristpilot Bridge (`../bridge/wristpilot_bridge/`) and writes commands into its GATT service. The
bridge turns them into Zwift keyboard shortcuts (or Companion commands) and acknowledges every
command. Protocol: [docs/architecture.md](../docs/architecture.md).

Tested on a real fēnix 7X Pro Sapphire Solar (firmware 27.18, Connect IQ 6.0.4). AMOLED watches
and Edge bike computers have so far been checked in the simulator only.

## Structure

```
watch/
├── manifest.xml              watch app, minApiLevel 3.1.0, permission BluetoothLowEnergy, deu + eng
├── manifest-beta.xml         same with its own app ID (beta uploads)
├── monkey.jungle             release build (display style and icon per device)
├── monkey-demo.jungle        demo build for store screenshots
├── monkey-beta.jungle        beta build
├── resources/                English strings (default), 40 px launcher icon
├── resources-deu/strings/    German strings (used when the device language is German)
├── resources-icon35 … 68/    launcher icons for AMOLED watches and Edge devices
├── tools/make_icon.py        generates the launcher icons (Pillow)
├── store/                    store texts (listing.md), privacy policy, store images (make_assets.py)
├── source-style-mip/         Style.mc: four bold fields, high contrast (fēnix 7 Pro family)
├── source-style-amoled/      Style.mc: coloured buttons next to the keys
├── source-style-edge/        Style.mc: tile layout for Edge bike computers
├── source-build/             Build.mc: release build, no demo data
├── source-demo/              Build.mc: demo build, pretends to be connected
└── source/
    ├── WristpilotApp.mc        entry point, global objects, one 100 ms timer for everything
    ├── Protocol.mc           UUIDs, message types, result codes, action IDs (from protocol.py/actions.py)
    ├── Actions.mc            logical UI actions -> [ID, value, text, colour, icon]
    ├── BleManager.mc         the only BleDelegate: profile, scan, connect, GATT queue, ping
    ├── Remote.mc             sending, acknowledgements, timeout, feedback overlay, vibration, state flags
    ├── MainView.mc           drawing: connect, ride, actions, workout, overlay
    ├── MainDelegate.mc       buttons (short/long) and touch
    ├── Icons.mc              icons from graphics primitives (arrows, thumb, bolt …)
    ├── Menus.mc              settings menu (Menu2), device list, exit confirmation
    └── Settings.mc           Application.Storage: vibration, start page
```

One timer (100 ms) drives the ping (every 5 s), the GATT watchdog, the acknowledgement timeout
(500 ms), the overlay duration and long-press detection. Connect IQ allows only a few timers at
the same time, so the app sticks to one.

## Controls

### Pages

| Page | Content |
|---|---|
| Connect | shown whenever no bridge is connected |
| 1 Ride | left, right, Ride On, power-up; state dot at the top; junction indicator with the Companion link |
| 2 Actions | 8 tiles: elbow flick, wave, Nice, Hammer Time, bell, photo, camera, HUD |
| 3 Workout | easier, harder, skip interval |

Change pages by **swiping down** (Ride -> Actions -> Workout -> Ride). On Actions and Workout,
**swipe up** goes back and **BACK** returns to Ride. With buttons only, use the menu (hold UP ->
"Go to Actions" / "Go to Workout"), because every button on the ride page is a ride action.

### Watches (MIP and AMOLED): ride page

Blind operation: buttons on the left turn left, buttons on the right turn right. A short press
triggers on release, a long press after 600 ms while holding.

| Button | Short | Hold |
|---|---|---|
| UP (left, 9 o'clock) | Turn left | Settings menu |
| START (right, 2 o'clock) | Turn right | U-turn |
| DOWN (left, 8 o'clock) | Ride On | Straight on |
| BACK (right, 4 o'clock) | Power-up | Exit confirmation (on firmware with a task switcher, e.g. fēnix 7 Pro 27.x and fēnix 8, the system takes this for its app switcher; exit through the menu) |
| LIGHT | left to the system | |

| Touch | Action |
|---|---|
| Swipe left / right | Turn left / right |
| Swipe up | Straight on |
| Swipe down | Next page |
| Tap a field | its action (top left: left, top right: right, bottom left: Ride On, bottom right: power-up) |
| Hold anywhere | Power-up |

MIP and AMOLED watches share the same controls; only the drawing differs.

**Actions:** UP/DOWN move the selection, START sends, BACK returns to Ride, hold UP for the menu,
exit through the menu. Tapping a tile sends at once.

**Workout:** UP = easier, START = harder, **hold DOWN = skip interval** (a short DOWN only shows
the hint), BACK = Ride. Touch: left half easier, right half harder, **hold** the bottom area to
skip.

**Connect:** START or tap = device list, BACK = exit confirmation, hold UP = menu.

### Turn protection (default: press twice)

Turns, straight on and the U-turn need a second action, so a stray press does not take you off
the route. Ride On, power-up, the Actions and Workout pages are never delayed. Menu: *Turn
protection* = Press twice (default) · Hold · Off.

| Mode | Turns and straight on | U-turn | Menu |
|---|---|---|---|
| Press twice | first press (or tap, swipe, tile) marks the action ("Turn left? Again to send", short tick), the same press again within 2 s sends it; another action cancels | hold START twice | hold UP |
| Hold | hold UP/START (Edge: LAP/START/ENTER) until the ring is full (0.6 s), sent on release; a short press only shows "Hold to turn"; touch: hold the field or tile | hold START 1.5 s | hold UP 1.5 s |
| Off | as in the tables above | hold START | hold UP |

The watch itself turns a held UP into the menu key after about a second; with *Hold* the app
ignores that key while UP is held for a turn and opens the menu at 1.5 s itself.

### Ride page: normal, race, party

Menu: *Ride page* = Normal · Race: power-up · Race: + Ride On · Party. Stays as chosen, also after
a restart. Race and party pages have no turns, no U-turn and no turn protection.

**Race:** a big power-up and a red "RACE" under the state dot.

| Button | Power-up only | Power-up + Ride On |
|---|---|---|
| START, BACK | Power-up | Power-up |
| DOWN | – | Ride On |
| hold UP | Menu | Menu |
| hold BACK | nothing (no exit in a sprint; exit through the menu) | nothing |
| Touch | tap anywhere: power-up | Ride On disc (bottom left): Ride On, elsewhere power-up |
| Edge | every button but BACK: power-up; one big tile | UP and the bottom tile: Ride On, the rest power-up |

**Party** (group rides): the social gestures sit where the ride actions are, the power-up stays on
BACK; a violet "PARTY" under the state dot. With the Companion link the Ride On field shows the
Ride Ons received and the power-up field its type.

| Button | Short | Hold |
|---|---|---|
| UP | Wave | Menu |
| START | Ride On | Hammer Time |
| DOWN | Elbow flick | Nice |
| BACK | Power-up | Photo (no exit) |
| Touch | tap a field (top left wave, top right Ride On, bottom left elbow, bottom right power-up) | – |
| Edge | LAP wave · START Ride On (hold: Hammer Time) · UP elbow · DOWN power-up · ENTER Nice; tiles: wave, Ride On, elbow, power-up, Nice, Hammer Time, bell | |

### Edge bike computers

LAP (bottom left) and START (bottom right) work on every model. The button-only models
(Edge 530/540/550, MTB) also have UP/DOWN on the left and ENTER/BACK on the right.

| Page | Buttons |
|---|---|
| Ride | LAP left · START right (hold: U-turn) · ENTER straight on · UP Ride On · DOWN power-up · BACK next page |
| Actions | UP/DOWN select · ENTER or START send · LAP or BACK next page |
| Workout | LAP or UP easier · START or ENTER harder · hold DOWN or tap-and-hold to skip · BACK next page |

On touch models the ride page shows big tiles (Left, Straight on, Right, Ride On, Power-up,
U-turn, More); tap them. Edge devices have no vibration motor and beep instead.

### Settings menu (hold UP)

Exit app (first, so it is quick to reach) · ride page (normal / race: power-up / race: + Ride On /
party) ·
turn protection (press twice / hold / off) · vibration / tone on/off · vibrate at junctions · start
page (Ride/Actions/Workout) · go to Ride/Actions/Workout · choose device · reconnect · bridge (info
text of the bridge).

### Feedback

- After every command an overlay with the action name: first "sending …", after an OK
  acknowledgement "arrived · 38 ms" (0.6 s, short vibration).
- Error acknowledgement: red X, reason (for example "Zwift not in front"), double vibration, 1.5 s.
- No acknowledgement after 500 ms: "not arrived", double vibration. If the acknowledgement comes
  later (up to 3 s), the overlay still shows the real result.
- Commands waiting more than 1 s in the GATT queue are dropped (a late "left" is worse than none).
- Haptic request from the bridge (0x03): 1 single, 2 double, 3 triple, 4 long.
- Connection lost: long vibration, connect screen.
- State dot on the ride page: green "Zwift" (in front), orange "not in front", red "no Zwift",
  green "OBC app", grey "bridge off" or "no answer" (15 s without a message).

## BLE flow

1. `setDelegate`, then `registerProfile` (service …b936 with command …b937, status …b938 + CCCD,
   info …b939).
2. After `onProfileRegister` (at the latest after 3 s) start scanning.
3. `onScanResults`: a match is a result whose `getServiceUuids()` contains the service or whose
   name contains "Wristpilot" -> stop scanning, `pairDevice`. Every device seen goes into the device
   list (sorted by RSSI). After 10 s without a match the connect screen points to the list (some
   watches receive empty advertising data).
4. `onConnectedStateChanged` -> `getService`/`getCharacteristic`, write the CCCD `[0x01, 0x00]`,
   read the info. After the CCCD callback the connection is ready; a ping goes out at once.
5. Only one GATT request at a time: a queue advanced by `onCharacteristicWrite`,
   `onDescriptorWrite` and `onCharacteristicRead`, with a 2 s watchdog. Commands are written
   **with response** so that `onCharacteristicWrite` is reliably called.
6. Ping `[seq, 0x00, 0]` every 5 s when nothing else is written (the bridge answers with its
   state; its timeout for the watch is 15 s).
7. Connection lost -> the device stays paired (the stack reconnects paired devices by itself);
   after 8 s without success `unpairDevice` and a new scan. Connecting and setup give up after
   10 s and 8 s and scan again.

## Build

See [docs/building.md](../docs/building.md) for the SDK, the developer key and the store package.
Short version:

```
monkeyc -d fenix7xpro -f monkey.jungle -o bin/wristpilot.prg -y developer_key.der
```

| Jungle file | Purpose |
|---|---|
| `monkey.jungle` | release: MIP devices with `source-style-mip`, AMOLED devices with `source-style-amoled` and icons from `resources-icon60/65`, Edge devices with `source-style-edge` and icons from `resources-icon35`-`68` |
| `monkey-demo.jungle` | demo for store screenshots (`source-demo/Build.mc`: pretends to be connected, junction ahead, power-up) |
| `monkey-beta.jungle` + `manifest-beta.xml` | beta upload with its own app ID |

Launcher icons: `../.venv/bin/python tools/make_icon.py`.

## Simulator

```
connectiq &                                  # start the simulator
monkeydo bin/wristpilot.prg fenix7xpro         # load the app for a device
```

- BLE in the simulator only works with a Nordic nRF52 DK or nRF52840 dongle with Garmin's firmware
  (Simulator -> Settings -> BLE Settings -> COM port). Without one, only the connect screen can be
  checked. For the other pages use the demo build:
  `monkeyc -d edge1040 -f monkey-demo.jungle -o bin/demo-edge1040.prg -y developer_key.der`,
  then `monkeydo bin/demo-edge1040.prg edge1040`.
- If an old simulator process hangs as a zombie, a new one does not start; end the old one first.
- On some Linux distributions the simulator binary needs the same webkit2gtk-4.1 adjustment as
  the SDK Manager.

## Sideloading onto the watch

Copy `bin/wristpilot.prg` over USB (MTP) to `GARMIN/Apps/`, unplug the watch; it installs the app,
which then appears in the app menu. Crash logs: `GARMIN/Apps/LOGS/CIQ_LOG.YML` (with file and
line).

On Linux, blacklist the kernel module `garmin_gps`; otherwise the watch may stay in mode
`091e:0003`. In MTP mode it shows up as `091e:5118`. Cable and port make a difference.

## Type checking

The code has almost no type annotations (only `onTick() as Void`). Global objects (`gBle`,
`gRemote`, …) are untyped on purpose, so that calls like `$.gBle.isReady()` pass the default
("gradual") type check. A strict check (`-l 3`) will report warnings.

## Lessons learned

- `StringUtil.convertEncodedString` raises an **uncatchable** system error on non-ASCII bytes
  (fēnix 7X Pro, Connect IQ 6.0.4). The info text is decoded by hand.
- `Attention.VibeProfile` does not exist on devices without a vibration motor (Edge); using it
  crashes the app. Edge devices get a tone instead.
- Connect IQ 3.x devices allow at most 9 arguments per method; pass an array instead.
- `onCharacteristicWrite` is only reliable with `WRITE_TYPE_WITH_RESPONSE`.
- Connect IQ drops scan results without the "LE General Discoverable" flag, and some watches
  receive empty advertising data. Match on name as well and offer a device list.
- `ScanResult` has `hasAddress()` but no getter for the address, so the app cannot remember the
  last bridge by address.
- The fēnix sends `KEY_MENU` by itself when UP is held; the app opens its menu after 600 ms on its
  own timer and treats the press as used up.
- Some devices turn touch gestures into `KEY_ESC`/`KEY_ENTER`. On the ride page the app never sends
  a command from such a synthetic key, and it ignores key echoes shortly after a touch event.

## Open points

- Battery use of the 100 ms timer over a one-hour ride.
- Heart rate broadcast of the watch alongside the Connect IQ BLE connection.
- Font sizes on the smallest displays (fēnix 7S Pro) on a real device.
