# Backlog

## Testing on real hardware

- [ ] AMOLED layout on a real AMOLED watch (fēnix 8/9 or epix Pro); so far only checked in the simulator
- [ ] Edge app on a real Edge bike computer; so far only checked in the simulator (1040, 540, 1050)
- [ ] Windows bridge on real hardware: SendInput into ZwiftApp.exe, firewall prompt for the Companion port (21587)
- [ ] Keep the connection for 60 minutes, measure latency from button press to acknowledgement on the watch
- [ ] Heart rate broadcast of the watch to Zwift alongside the Wristpilot connection
- [ ] Keyboard "straight on": the up arrow opens Zwift's action menu since 2025 – check in the game
- [x] fēnix 7X Pro: holding BACK opens the system's app switcher instead of the exit confirmation, and
  *Exit app* was not found in the settings menu (2026-11-24). *Exit app* is now the first menu item;
  exiting that way works on the watch (2026-11-25)
- [ ] fēnix 7X Pro (27.18): after holding BACK the switcher lists Wristpilot at the top, and selecting
  it says the app cannot be opened ("close Wristpilot and try again"); only a restart of the watch
  clears it. **Firmware bug, not ours** (2026-11-25): the watch ends the app with a plain `onStop`
  (no `:suspend`, no `onInactive`), lists it anyway, and Garmin's unchanged SDK sample "Timer"
  fails the same way. Selecting another app in the switcher works. Similar report: CIQQA-3801 in
  the Garmin forum. Left to do: post our case there (draft in `_intern/garmin-forum-task-switcher.md`),
  and in the store description say "exit through the menu (hold UP), do not reopen from the switcher"
  (store text done in `watch/store/listing.md`, 2026-11-25)

## Companion link in a real ride

Before the ride: set `companion_capture` (see docs/architecture.md), afterwards read the file with
`bridge/tools/companion_dump.py --summary`. One ride answers most of the points below.

- [ ] Does the relay accept the launcher token (Windows sign-in, Tretlager)? Response of `PUT /relay/profiles/me/phone`
- [ ] Does the game connect in plain mode? Otherwise add the secure mode (AES-128-GCM)
- [ ] Turn messages: where do the junction options come from (action buttons 1010-1012 or `IntersectionAhead`), direction values and `enabled` field
- [ ] Straight on via Companion: is command 1011 enough?
- [ ] Are received Ride Ons reported as `SOCIAL_PLAYER_ACTION`? Otherwise remove the counter

## Release

- [x] Publish the Windows bridge as a GitHub release
- [x] Tretlager release with the *Watch remote* page
- [x] Put the privacy policy online and fill in the placeholders (`<CONTACT>`, store links)
- [ ] Connect IQ Store: upload the beta, test on a real watch, then submit for review
- [ ] Code-sign the Windows .exe

## Windows bridge

- [ ] Support Intel USB adapters in the Windows build (Bumble has a driver, firmware not bundled yet)
- [ ] A setup helper that installs WinUSB for the adapter, so users do not need Zadig
- [x] *Test actions* do nothing while Bluetooth is not running – the menu item is greyed out now (2026-11-25)
- [x] **Blocker: the fēnix does not connect to the Windows bridge.** Windows advertises a GATT server with a resolvable private address, and the watch refuses to connect to private addresses of unbonded devices (verified 2026-11-24 with the same USB adapter on Linux: public address connects, privacy on does not). Connect IQ has no bonding API. Solved in 0.2.0 with Bumble on a dedicated USB adapter (WinUSB); tested in a Windows 11 VM with a TP-Link UB500 and the fēnix 7X Pro
- [x] Windows also interleaves a Microsoft CDP beacon ("Share across devices") on the same address; the watch then misses the service UUID. Name "BOX11EN" only comes in the scan response, which the watch ignores (no longer relevant with Bumble)
