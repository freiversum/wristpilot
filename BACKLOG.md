# Backlog

## Testing on real hardware

- [ ] AMOLED layout on a real AMOLED watch (fēnix 8/9 or epix Pro); so far only checked in the simulator
- [ ] Edge app on a real Edge bike computer; so far only checked in the simulator (1040, 540, 1050)
- [ ] Windows bridge on real hardware: peripheral role of the Bluetooth adapter, SendInput into ZwiftApp.exe, firewall prompt for the Companion port (21587)
- [ ] Keep the connection for 60 minutes, measure latency from button press to acknowledgement on the watch
- [ ] Heart rate broadcast of the watch to Zwift alongside the ZWindoor connection
- [ ] Keyboard "straight on": the up arrow opens Zwift's action menu since 2025 – check in the game

## Companion link in a real ride

- [ ] Does the relay accept the launcher token (Windows sign-in, Tretlager)? Response of `PUT /relay/profiles/me/phone`
- [ ] Does the game connect in plain mode? Otherwise add the secure mode (AES-128-GCM)
- [ ] Turn messages: where do the junction options come from (action buttons 1010-1012 or `IntersectionAhead`), direction values and `enabled` field
- [ ] Straight on via Companion: is command 1011 enough?
- [ ] Are received Ride Ons reported as `SOCIAL_PLAYER_ACTION`? Otherwise remove the counter

## Release

- [ ] Publish the Windows bridge as a GitHub release
- [ ] Tretlager release with the *Watch remote* page
- [ ] Put the privacy policy online and fill in the placeholders (`<CONTACT>`, store links)
- [ ] Connect IQ Store: upload the beta, test on a real watch, then submit for review
- [ ] Code-sign the Windows .exe

## Windows bridge

- [ ] *Test actions* do nothing while Bluetooth is not running – run them anyway (keyboard path) or grey the menu out
- [ ] WinRT advertises the computer name instead of "ZWindoor"; the watch finds the bridge by service UUID, but the device list shows the computer name – check on the watch
