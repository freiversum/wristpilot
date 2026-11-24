"""ZWindoor bridge – turns commands from a Garmin watch into input for Zwift.

The watch (Connect IQ, Bluetooth LE central role only) writes commands to a GATT service that
this bridge offers as a peripheral. The bridge types the matching Zwift keyboard shortcut and/or
forwards the command to trainer apps that speak OpenBikeControl.

The same core runs in two shells: a small Windows tray program and a page in Tretlager (Linux).
"""

__version__ = "0.1.0"
