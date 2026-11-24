# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-11-24

### Fixed
- Windows bridge: Bluetooth did not start ("the Python package 'bless' is missing"). bless 0.2.6/0.3.0
  import the unpublished package `pysetupdi` on Windows and open the Bluetooth adapter directly to
  rename it. The bridge now has its own small backend on the WinRT `GattServiceProvider` API
  (pywinrt), which needs no admin rights; bless is only used on macOS.
- Error messages name the underlying cause when a Bluetooth module cannot be loaded.

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

[Unreleased]: https://github.com/freiversum/zwindoor/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/freiversum/zwindoor/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/freiversum/zwindoor/releases/tag/v0.1.0
