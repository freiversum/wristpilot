# Wristpilot – Connect IQ Store listing

Texts for the developer dashboard (apps.garmin.com/developer), English and German. Descriptions are
limited to 4000 characters and Markdown is not rendered, so the texts below are plain. "Zwift" is
only used descriptively ("for Zwift"), never in the name, no Zwift logo; the note that Wristpilot is not
affiliated with Zwift or Garmin is included (review guidelines §3a, §4a).

**URLs:** download and setup https://linuxundich.de/en/projects/wristpilot/ (German:
/projekte/wristpilot/), support https://github.com/freiversum/wristpilot/issues, privacy policy
(dashboard field) https://linuxundich.de/en/projects/wristpilot/privacy/ (German: /projekte/wristpilot/datenschutz/).

## Name

Wristpilot

## Category (suggestion)

Tools / Utilities (Watch App)

---

## Description – English

Wristpilot turns your Garmin watch or Edge bike computer into a remote for indoor cycling in Zwift. Turn left or right at junctions, go straight on, make a U-turn, give a Ride On or fire your power-up – with the buttons of your watch, without letting go of the handlebar.

REQUIRES A COMPANION PROGRAM ON YOUR COMPUTER
The watch cannot control Zwift directly. Wristpilot connects over Bluetooth to the free Wristpilot Bridge on the computer that runs Zwift, which turns your button presses into Zwift's keyboard shortcuts. Download and setup: https://linuxundich.de/en/projects/wristpilot/
- Windows 10/11: Wristpilot Bridge (small tray program) with a second USB Bluetooth adapter of its own, e.g. TP-Link UB500 (about 10 euros). Windows' own Bluetooth uses changing addresses that Garmin watches do not connect to.
- Linux: built into Tretlager (Zwift on Linux).
Without the bridge the app only shows "Searching bridge".

BUTTONS (blind operation – left buttons for left, right buttons for right)
- UP: turn left (hold: menu)
- START: turn right (hold: U-turn)
- DOWN: Ride On (hold: straight on)
- BACK: power-up (hold: exit)

On some watches (fēnix 7 Pro with firmware 27.x, fēnix 8) holding BACK opens the system app switcher instead. Exit through the menu then (hold UP, "Exit app" is the first item), and do not reopen Wristpilot from the switcher: the watch firmware cannot reopen it from there until the watch is restarted.

Touch: swipe left/right to turn, swipe up for straight on, tap a quarter for its action. Swipe down for more pages.

TURN PROTECTION (on by default)
Turns, straight on and the U-turn are only sent after a second action, so a stray press does not take you off the route: press the same button again within 2 seconds, or choose "Hold" in the menu and hold until the ring is full. Ride On and power-up stay instant. Can be switched off in the menu.

RACE MODE
A race page with a big power-up and no turns or U-turn, optionally with Ride On. START and BACK both fire the power-up, and holding BACK does not exit. Switch it on in the menu (hold UP).

MORE PAGES
- Actions: elbow flick, wave, nice, hammer time, bell, photo, camera view, HUD on/off
- Workout: easier, harder, skip interval

FEEDBACK ON THE WRIST
Every command is confirmed by the bridge: a short vibration when it arrived, a double vibration with the reason when Zwift was not in front or not running.

OPTIONAL: ZWIFT COMPANION LINK
The bridge can also connect to Zwift the way the Zwift Companion app does. The watch then shows the junction ahead with the possible directions, the power-up that is ready and the Ride Ons you received, and commands work without the keyboard. This replaces the Companion app on your phone while it is on. It uses an undocumented connection; read the notes in the bridge before switching it on.

ALSO FOR OTHER APPS
The bridge can offer the watch on the network as an OpenBikeControl controller, for trainer apps such as MyWhoosh, TrainingPeaks Virtual or Incyclist.

EDGE BIKE COMPUTERS
On the Edge, big tiles fill the screen: Left, Straight on, Right, Ride On, Power-up, U-turn and More. Tap them, or press LAP (bottom left) to turn left and START (bottom right) to turn right; hold START for a U-turn. Button-only models (Edge 530/540/550, MTB): ENTER straight on, UP Ride On, DOWN power-up, BACK next page.

DISPLAYS
MIP watches (fenix 7 Pro family) get four bold fields that stay readable in sunlight; AMOLED watches (fenix 8, 8 Pro, 9, 9 Pro, E, epix Pro) get coloured buttons next to the physical keys; Edge bike computers get the tile layout.

PRIVACY
Wristpilot collects no data. The watch talks only to the bridge on your own computer via Bluetooth; nothing is sent to the developer or to Garmin.

Wristpilot is an independent project. It is not affiliated with, endorsed or sponsored by Zwift, Inc. or Garmin. Zwift is a trademark of Zwift, Inc. Formerly called ZWindoor.

Support: https://github.com/freiversum/wristpilot/issues

---

## Description – German

Wristpilot macht deine Garmin-Uhr oder deinen Edge-Radcomputer zur Fernbedienung für das Indoor-Training mit Zwift. An Abzweigungen links oder rechts abbiegen, geradeaus fahren, wenden, ein Ride On geben oder das Power-up zünden – mit den Tasten der Uhr, ohne den Lenker loszulassen.

BRAUCHT EIN PROGRAMM AUF DEM COMPUTER
Die Uhr kann Zwift nicht direkt steuern. Wristpilot verbindet sich per Bluetooth mit der kostenlosen Wristpilot Bridge auf dem Rechner, auf dem Zwift läuft. Die Bridge macht aus deinen Tastendrücken Zwifts Tastenkürzel. Download und Einrichtung: https://linuxundich.de/projekte/wristpilot/
- Windows 10/11: Wristpilot Bridge (kleines Programm im Infobereich) mit einem zweiten, eigenen USB-Bluetooth-Stick, z. B. TP-Link UB500 (rund 10 Euro). Das Bluetooth von Windows nutzt wechselnde Adressen, mit denen sich Garmin-Uhren nicht verbinden.
- Linux: in Tretlager eingebaut (Zwift unter Linux).
Ohne Bridge zeigt die App nur „Suche Bridge“.

TASTEN (blind bedienbar – linke Tasten für links, rechte für rechts)
- UP: links abbiegen (halten: Menü)
- START: rechts abbiegen (halten: U-Turn)
- DOWN: Ride On (halten: geradeaus)
- BACK: Power-up (halten: beenden)

Auf manchen Uhren (fēnix 7 Pro mit Firmware 27.x, fēnix 8) öffnet BACK halten stattdessen den App-Umschalter des Systems. Dann über das Menü beenden (UP halten, „App beenden“ ist der erste Eintrag) und Wristpilot nicht aus dem Umschalter wieder öffnen: Die Firmware der Uhr kann die App von dort erst nach einem Neustart der Uhr wieder öffnen.

Touch: nach links/rechts wischen zum Abbiegen, nach oben für geradeaus, Viertel antippen für seine Aktion. Nach unten wischen für weitere Seiten.

SCHUTZ VOR FEHLDRUCK (ab Werk an)
Abbiegen, geradeaus und U-Turn gehen erst nach einer zweiten Aktion raus, damit ein versehentlicher Druck dich nicht von der Strecke bringt: dieselbe Taste innerhalb von 2 Sekunden nochmal drücken, oder im Menü „Halten“ wählen und halten, bis der Ring voll ist. Ride On und Power-up bleiben sofort. Im Menü abschaltbar.

RACE-MODUS
Eine Rennseite mit großem Power-up, ohne Abbiegen und U-Turn, wahlweise mit Ride On. START und BACK lösen das Power-up aus, BACK halten beendet die App nicht. Einschalten im Menü (UP halten).

WEITERE SEITEN
- Aktionen: Ellbogen-Wink, Winken, Nice, Hammer Time, Klingel, Foto, Kamera, HUD ein/aus
- Workout: leichter, schwerer, Intervall überspringen

RÜCKMELDUNG AM HANDGELENK
Jeder Befehl wird von der Bridge bestätigt: kurze Vibration, wenn er angekommen ist, doppelte Vibration mit Grund, wenn Zwift nicht im Vordergrund war oder nicht läuft.

OPTIONAL: ZWIFT-COMPANION-VERBINDUNG
Die Bridge kann sich auch so mit Zwift verbinden wie die Zwift Companion App. Dann zeigt die Uhr den nächsten Abzweig mit den möglichen Richtungen, das bereitliegende Power-up und die erhaltenen Ride Ons, und die Befehle funktionieren ohne Tastatur. Solange das an ist, ersetzt es die Companion App auf dem Smartphone. Die Verbindung ist nicht offiziell dokumentiert; bitte die Hinweise in der Bridge lesen, bevor du sie einschaltest.

AUCH FÜR ANDERE APPS
Die Bridge kann die Uhr im Netzwerk als OpenBikeControl-Controller anbieten, für Trainings-Apps wie MyWhoosh, TrainingPeaks Virtual oder Incyclist.

EDGE-RADCOMPUTER
Auf dem Edge füllen große Kacheln den Bildschirm: Links, Geradeaus, Rechts, Ride On, Power-up, U-Turn und Mehr. Antippen oder LAP (unten links) für links und START (unten rechts) für rechts drücken; START halten für den U-Turn. Modelle nur mit Tasten (Edge 530/540/550, MTB): ENTER geradeaus, UP Ride On, DOWN Power-up, BACK nächste Seite.

DISPLAYS
MIP-Uhren (fēnix-7-Pro-Familie) bekommen vier kräftige Felder, die auch in der Sonne lesbar bleiben; AMOLED-Uhren (fēnix 8, 8 Pro, 9, 9 Pro, E, epix Pro) bekommen farbige Schaltflächen neben den Tasten; Edge-Radcomputer das Kachel-Layout.

DATENSCHUTZ
Wristpilot sammelt keine Daten. Die Uhr spricht per Bluetooth nur mit der Bridge auf deinem eigenen Rechner; nichts geht an den Entwickler oder an Garmin.

Wristpilot ist ein unabhängiges Projekt und steht in keiner Verbindung zu Zwift, Inc. oder Garmin. Zwift ist eine Marke der Zwift, Inc. Früher hieß die App ZWindoor.

Support: https://github.com/freiversum/wristpilot/issues

---

## What's new

1.0.1 (beta, 2026-11-25):

EN: New name: ZWindoor is now Wristpilot. "Exit app" is now the first item of the settings menu (hold UP); on the fēnix 7 Pro with firmware 27.x holding BACK opens the system app switcher instead of exiting.

1.0.0:

EN: First release for watches and Edge bike computers: turn left/right/straight, U-turn, Ride On, power-up, emotes, camera, workout controls; MIP and AMOLED layouts; optional Zwift Companion link (junction and power-up on the watch).

DE: Erste Version für Uhren und Edge-Radcomputer: links/rechts/geradeaus, U-Turn, Ride On, Power-up, Emotes, Kamera, Workout-Steuerung; Darstellung für MIP und AMOLED; optionale Zwift-Companion-Verbindung (Abzweig und Power-up auf der Uhr).

## Images (out/)

| Dashboard field | File |
|---|---|
| App icon / cover (500×500) | `out/store-icon.png` |
| Hero image (1440×720, per language) | `out/hero-en.png`, `out/hero-de.png` |
| Screenshots (suggestion, max. ~150 KB, square) | AMOLED: `out/screenshot-amoled-01-ride.png`, `-02-feedback`, `-03-actions`, `-04-workout`; MIP: `out/screenshot-01-ride.png`, `-05-connect` (all are in `out/`, plus `display-*.png` with the display only) |
| Edge screenshots | `out/screenshot-edge1040-01-ride.png`, `out/screenshot-edge1040-03-actions.png` |
| On-device icon (128×128, optional) | `out/device-icon-amoled.png`, `out/device-icon-mip.png` |
