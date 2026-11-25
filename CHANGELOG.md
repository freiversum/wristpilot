# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Watch app: **turn protection**, on by default. Turns, straight on and the U-turn need a second
  action: *press twice* (the same button, tap or swipe again within 2 s; the first press shows
  "Turn left? Again to send") or *hold* (hold until the ring is full, 0.6 s; U-turn and menu at
  1.5 s). Ride On and power-up stay instant. Menu: *Turn protection*.
- Watch app: **race mode** with two layouts, chosen in the menu: *power-up only* (one big
  power-up, START and BACK fire it) and *power-up + Ride On* (DOWN gives a Ride On). No turns, no
  U-turn, and holding BACK does not exit. Watches (MIP, AMOLED) and Edge.
- Watch app: **party mode** for group rides: UP wave, START Ride On, DOWN elbow flick, BACK
  power-up; held: Hammer Time, Nice, photo (no exit). Edge: tiles for wave, Ride On, elbow flick,
  power-up, Nice, Hammer Time and bell. With the Companion link the Ride Ons received are shown.
- **Steering:** the bridge offers Zwift a virtual Elite Sterzo Smart over DIRCON (Windows, Linux,
  Tretlager); pair it once in Zwift under *Steering*. On the race page UP and START change lanes
  (12 degrees for 0.45 s, about four presses across the road; `steering_angle`, `steering_time`
  in `config.json`), BACK fires the power-up. The Actions page gets *Lane left* and *Lane right*.
  New protocol action 0x81 (lane) and result 7 (steering not paired in Zwift).
- Watch app: one menu item *Ride page* (normal, race: power-up, race: + Ride On, party) instead of
  a separate race switch. "Nice" has its own star icon (it shared the thumb with Ride On).

## [0.3.0] - 2026-11-25

### Changed
- **ZWindoor is now called Wristpilot.** The name no longer leans on Zwift's, and the app also
  works with other platforms through OpenBikeControl. Everything is renamed: watch app, bridge
  (`wristpilot_bridge`, `wristpilot-bridge`), Windows program (`WristpilotBridge.exe`), settings
  folder (`%APPDATA%\Wristpilot`, `~/.config/wristpilot`) and the repository
  (github.com/freiversum/wristpilot). The bridge advertises as "Wristpilot" (shortened to
  "Wristpil" in the advertising packet, which has room for 8 characters next to the service UUID).
  Settings and the Zwift sign-in of ZWindoor are not taken over.

### Added
- Bridge: `companion_capture` in `config.json` records every Companion frame as JSON Lines, and
  `bridge/tools/companion_dump.py` turns a capture into readable frames and a summary of the open
  questions (junction messages, action buttons, Ride Ons). Prepares the first real ride.

### Fixed
- Windows tray: *Test actions* is greyed out while Bluetooth is not running; before, the actions
  did nothing.
- Watch app: "Exit app" is now the first item of the settings menu (hold UP). On firmware with a
  task switcher (fēnix 7X Pro 27.18) holding BACK opens the system's app switcher instead of the
  exit confirmation, and the item at the end of the long menu was easy to miss.
- Watch app: handles being sent to the background by the task switcher on devices that support
  it (`onInactive`/`onActive`, fēnix 8 and newer): a long press that was running is dropped and the
  screen is redrawn on return.
- Windows build: the Realtek firmware (`rtl8761bu_fw.bin` and friends) is packed into the .exe
  again. Nuitka's `--include-data-dir` left the `.bin` files out, so Bumble ran the UB500 on its
  ROM firmware.
- Windows bridge: the scan response carries the name "Wristpilot" and the service UUID. It was empty,
  so scanners that read the name from the scan response listed the bridge as "unknown".

## [0.2.0] - 2026-11-24

### Changed
- **The Windows bridge needs a dedicated USB Bluetooth adapter** with the WinUSB driver (set up
  once with Zadig, see the README). The built-in Bluetooth of the computer stays free.

### Added
- Tray menu: *Set up a Bluetooth adapter* (opens the guide) and *Start Bluetooth again* while
  Bluetooth is not running.
- The advertising packet carries the name "ZWindoor", so the watch's device list shows it.

### Fixed
- Windows bridge: Garmin watches could not connect. Windows advertises GATT servers with a private
  address, which the watches refuse for devices they are not bonded with. The bridge now runs its own
  Bluetooth stack (Bumble) on a dedicated USB adapter with the WinUSB driver and advertises with the
  adapter's public address. Realtek adapters such as the TP-Link UB500 get their firmware from the
  bridge. On Linux, `--adapter hci-socket:N` or `usb:N` selects the same backend.

## [0.1.1] - 2026-11-24

### Fixed
- Windows bridge: Bluetooth did not start ("the Python package 'bless' is missing"). bless 0.2.6/0.3.0
  import the unpublished package `pysetupdi` on Windows and open the Bluetooth adapter directly to
  rename it. The bridge now has its own small backend on the WinRT `GattServiceProvider` API
  (pywinrt), which needs no admin rights; bless is only used on macOS.
- Error messages name the underlying cause when a Bluetooth module cannot be loaded.
- Windows build: the pywinrt projection tables are packed into the .exe (`--include-package-data=winrt`).
- *Quit* in the tray menu did nothing after Bluetooth had failed to start ("Event loop is closed").
- Windows bridge: acknowledgements and state updates did not reach the watch. The write request is
  now completed before the notification goes out, and failed notifications are logged.

## [0.1.0] - 2026-11-24

First release.

### Added

- Watch app (Connect IQ) for the fēnix 7 Pro family (MIP): ride page with four bold fields,
  actions page (elbow flick, wave, Nice, Hammer Time, bell, photo, camera, HUD), workout page
  (easier, harder, skip interval), settings menu, device list, acknowledgement overlay with
  vibration.
- AMOLED layout for fēnix 8, 8 Pro, 9, 9 Pro, E and epix Pro (Gen 2): coloured buttons next to the
  physical keys and larger launcher icons. Layout and icon are chosen per device at build time
  (`source-style-mip`, `source-style-amoled`, `monkey.jungle`).
- Edge bike computers (530/540/550, 830/840/850, 1030/1040/1050/1060, Explore 2/3, MTB): tile
  layout in portrait mode (Left, Straight on, Right, Ride On, Power-up, U-turn, More); LAP turns
  left, START turns right (hold: U-turn); ENTER/UP/DOWN/BACK on button-only models; launcher
  icons from 35 to 68 px.
- Watch app: junction indicator on the ride page with directions not on offer greyed out, name of
  the power-up, number of Ride Ons received, short tick at a junction (can be turned off).
- Bridge core `zwindoor_bridge` 0.1.0: GATT service for the watch (BlueZ over dbus-fast on Linux,
  bless on macOS; WinRT on Windows since 0.1.1), commands as OpenBikeControl button IDs, acknowledgement and state by
  notification, keep-alive ping, keyboard outputs SendInput (scan codes), XTest (Wine/XWayland)
  and uinput, focus check and bringing the Zwift window to the front, camera cycling, custom key
  per action, command line with `--dry-run`.
- OpenBikeControl output (mDNS + TCP) as a second output for trainer apps such as MyWhoosh,
  TrainingPeaks Virtual or Incyclist.
- Optional Zwift Companion link (`companion.py`, opt-in): the bridge registers with Zwift's relay
  as the phone of the Companion app (plain mode as used by Sauce for Zwift), the game connects
  over TCP; pairing like the Companion app, 1 Hz heartbeat, new message `[0x04, flags, powerup,
  rideOns]` to the watch. Turns including straight on, U-turn, Ride On, power-up, emotes,
  photo/video, camera and HUD go straight to the game; workout keys stay on the keyboard. Small
  protobuf codec (`pb.py`) and Zwift web calls (`zwiftapi.py`). Using the link contradicts Zwift's
  terms of service.
- ZWindoor Bridge for Windows: tray program with state in the menu, switches, test actions,
  start with Windows, log, English and German texts, Zwift sign-in through the browser with the
  token encrypted by DPAPI, switch for the Companion link; built as a single .exe with Nuitka, by
  GitHub Actions on version tags.
- Tretlager integration: page *Watch remote* with a vendored copy of the core
  (`tools/sync-tretlager.sh`) and a switch for the Companion link (token from Tretlager's sign-in;
  locked while Tretlager uses the Companion app for sensors).
- Store preparation: `.iq` package, beta manifest with its own app ID, demo build for
  screenshots, store images (`watch/store/make_assets.py`), store texts in English and German,
  privacy policy.

### Fixed

- Watch app crashed right after connecting: `StringUtil.convertEncodedString` raises an
  uncatchable system error on the fēnix 7X Pro (Connect IQ 6.0.4) for non-ASCII characters; the
  info text is now decoded by hand.
- Crash on devices without a vibration motor (Edge): `Attention.VibeProfile` does not exist there;
  feedback is now a tone, and the menu item is called "Vibration / tone".
- Edge with touch: the workout hint says "Hold to skip" instead of "hold DOWN: skip".

[Unreleased]: https://github.com/freiversum/wristpilot/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/freiversum/wristpilot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/freiversum/wristpilot/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/freiversum/wristpilot/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/freiversum/wristpilot/releases/tag/v0.1.0
