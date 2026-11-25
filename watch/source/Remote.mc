// Remote: sends actions, tracks acknowledgements, holds the bridge state flags
// and the feedback overlay, and drives the vibration motor.

import Toybox.Attention;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

module Feedback {
    const NONE      = 0;
    const SENDING   = 1; // command written, waiting for the ack
    const OK        = 2; // ack with result OK
    const ERROR     = 3; // ack with an error result
    const TIMEOUT   = 4; // no ack within Protocol.ACK_TIMEOUT
    const NOT_CONN  = 5; // no connection to the bridge
    const HINT      = 6; // plain hint text (e.g. "hold to skip")
    const ARMED     = 7; // turn protection: action marked, waiting for the second press
    const HOLD      = 8; // turn protection: key held, ring filling (fbProgress 0..1)
}

class Remote {

    const OK_DURATION    = 600;
    const ERROR_DURATION = 1500;
    const LATE_ACK_LIMIT = 3000; // acks older than this are ignored

    var flags = null;          // last state flags from the bridge, null = unknown
    var game = 0;              // game flags (Protocol.GAME_*), 0 = no Companion link
    var powerup = 0;           // Protocol.PU_*
    var rideOns = 0;           // Ride Ons received in this ride

    // Feedback overlay
    var fbPhase = Feedback.NONE;
    var fbAction = null;       // logical action (Actions.*)
    var fbResult = 0;
    var fbLatency = 0;
    var fbText = null;         // resource id for HINT / ARMED
    var fbProgress = 0.0;      // HOLD: 0..1
    hidden var fbSeq = -1;
    hidden var fbSentAt = 0;
    hidden var fbUntil = 0;
    hidden var seq = 0;

    function initialize() {
    }

    // Send a logical action (Actions.LEFT, ...).
    function send(action) {
        var info = Actions.info(action);
        if (info == null) {
            return;
        }
        var now = System.getTimer();
        fbAction = action;
        if (!$.gBle.isReady()) {
            show(Feedback.NOT_CONN, now, ERROR_DURATION);
            vibrateError();
            return;
        }
        seq = (seq % 255) + 1;          // 1..255; 0 is used for pings
        if (!$.gBle.sendCommand(seq, info[0], info[1])) {
            show(Feedback.TIMEOUT, now, ERROR_DURATION);
            vibrateError();
            return;
        }
        fbSeq = seq;
        fbSentAt = now;
        show(Feedback.SENDING, now, ERROR_DURATION);
    }

    function showHint(textRes) {
        fbText = textRes;
        show(Feedback.HINT, System.getTimer(), ERROR_DURATION);
    }

    // Turn protection, "press twice": the action is marked until `window` ms have passed.
    function showArmed(action, window) {
        fbAction = action;
        fbText = Rez.Strings.ArmAgain;
        show(Feedback.ARMED, System.getTimer(), window);
        buzz([40, 40], Attention.TONE_KEY);
    }

    // Turn protection, "hold": refreshed by the input tick while the key is held.
    function showHold(action, progress) {
        fbAction = action;
        fbProgress = progress > 1.0 ? 1.0 : progress;
        show(Feedback.HOLD, System.getTimer(), 400);
    }

    // Remove a marked action or a hold ring (not the feedback of a sent command).
    function clearPending() {
        if (fbPhase == Feedback.ARMED || fbPhase == Feedback.HOLD) {
            fbPhase = Feedback.NONE;
            $.gDirty = true;
        }
    }

    hidden function show(phase, now, duration) {
        fbPhase = phase;
        fbUntil = now + duration;
        $.gDirty = true;
    }

    function tick(now) {
        if (fbPhase == Feedback.SENDING && now - fbSentAt > Protocol.ACK_TIMEOUT) {
            show(Feedback.TIMEOUT, now, ERROR_DURATION);
            vibrateError();
        } else if (fbPhase != Feedback.NONE && now > fbUntil) {
            fbPhase = Feedback.NONE;
            $.gDirty = true;
        }
    }

    // --- Called by BleManager ----------------------------------------------

    function onStatus(bytes) {
        if (bytes.size() < 2) {
            return;
        }
        var type = bytes[0];
        if (type == Protocol.MSG_ACK && bytes.size() >= 3) {
            onAck(bytes[1], bytes[2]);
        } else if (type == Protocol.MSG_STATE) {
            if (flags != bytes[1]) {
                flags = bytes[1];
                $.gDirty = true;
            }
        } else if (type == Protocol.MSG_HAPTIC) {
            vibratePattern(bytes[1]);
        } else if (type == Protocol.MSG_GAME && bytes.size() >= 5) {
            onGame(bytes[1], bytes[2], bytes[3] + bytes[4] * 256);
        }
    }

    hidden function onGame(newGame, newPowerup, newRideOns) {
        var junctionNow = (newGame & Protocol.GAME_JUNCTION) != 0;
        var junctionBefore = (game & Protocol.GAME_JUNCTION) != 0;
        if (junctionNow && !junctionBefore && Settings.junctionVibrationOn()) {
            buzz([50, 60], Attention.TONE_ALERT_HI);   // gentle tick: a junction is coming
        }
        if (newGame != game || newPowerup != powerup || newRideOns != rideOns) {
            game = newGame;
            powerup = newPowerup;
            rideOns = newRideOns;
            $.gDirty = true;
        }
    }

    function linked() {
        return (game & Protocol.GAME_LINKED) != 0;
    }

    // Is this direction offered at the junction ahead? Without a Companion link or
    // outside a junction everything counts as possible.
    function turnPossible(bit) {
        if (!linked() || (game & Protocol.GAME_JUNCTION) == 0) {
            return true;
        }
        return (game & bit) != 0;
    }

    function powerupLabel() {
        var ids = [Rez.Strings.PuNone, Rez.Strings.PuFeather, Rez.Strings.PuDraft, Rez.Strings.PuAero,
                   Rez.Strings.PuGhost, Rez.Strings.PuBurrito, Rez.Strings.PuSteamroller, Rez.Strings.PuAnvil,
                   Rez.Strings.PuLight, Rez.Strings.PuXp, Rez.Strings.PuUnknown];
        var i = ((game & Protocol.GAME_POWERUP) != 0) ? powerup : Protocol.PU_NONE;
        if (i < 0 || i >= ids.size()) {
            i = Protocol.PU_UNKNOWN;
        }
        return WatchUi.loadResource(ids[i]);
    }

    hidden function onAck(ackSeq, result) {
        var now = System.getTimer();
        if (ackSeq != fbSeq || now - fbSentAt > LATE_ACK_LIMIT) {
            return;
        }
        fbSeq = -1;                    // one ack per command
        fbLatency = now - fbSentAt;
        fbResult = result;
        // A late ack (after "not delivered") still shows the real outcome.
        if (result == Protocol.RESULT_OK) {
            show(Feedback.OK, now, OK_DURATION);
            vibrateOk();
        } else {
            show(Feedback.ERROR, now, ERROR_DURATION);
            vibrateError();
        }
    }

    function onCommandDropped(droppedSeq) {
        if (droppedSeq == fbSeq && fbPhase == Feedback.SENDING) {
            show(Feedback.TIMEOUT, System.getTimer(), ERROR_DURATION);
            vibrateError();
        }
    }

    function onConnectionChanged(ready) {
        if (ready) {
            vibrateOk();
        } else {
            flags = null;
            game = 0;
            fbPhase = Feedback.NONE;
            vibratePattern(4);         // long pulse: connection lost
        }
        $.gDirty = true;
    }

    // --- Vibration -----------------------------------------------------------

    function vibrateOk() {
        buzz([60, 80], Attention.TONE_KEY);
    }

    function vibrateError() {
        buzz([100, 120, 0, 100, 100, 120], Attention.TONE_ERROR);
    }

    // Haptic request from an OpenBikeControl app: 1 single, 2 double, 3 triple, 4 long.
    function vibratePattern(pattern) {
        if (pattern == 2) {
            vibrateError();
        } else if (pattern == 3) {
            buzz([100, 100, 0, 90, 100, 100, 0, 90, 100, 100], Attention.TONE_MSG);
        } else if (pattern == 4) {
            buzz([100, 600], Attention.TONE_FAILURE);
        } else {
            buzz([100, 150], Attention.TONE_MSG);
        }
    }

    // Vibrate (pairs of duty %, duration ms). Devices without a vibration motor – the Edge bike
    // computers – have no Attention.VibeProfile at all (Symbol Not Found); they play a tone instead.
    hidden function buzz(pairs, tone) {
        if (!Settings.vibrationOn()) {
            return;
        }
        if ((Attention has :vibrate) && (Attention has :VibeProfile)) {
            var profiles = [];
            for (var i = 0; i + 1 < pairs.size(); i += 2) {
                profiles.add(new Attention.VibeProfile(pairs[i], pairs[i + 1]));
            }
            Attention.vibrate(profiles);
        } else if (Attention has :playTone) {
            Attention.playTone(tone);
        }
    }

    // --- Bridge state for the status line -----------------------------------

    // [colour, label resource]
    function statusLine(now) {
        var ble = $.gBle;
        if (ble.isStale(now)) {
            return [Actions.COLOR_GREY, Rez.Strings.StStale];
        }
        if (flags == null) {
            return [Actions.COLOR_GREY, Rez.Strings.StZwift];  // first ping still on its way
        }
        if ((flags & Protocol.STATE_ENABLED) == 0) {
            return [Actions.COLOR_GREY, Rez.Strings.StOff];
        }
        if ((flags & (Protocol.STATE_ZWIFT_FOCUSED | Protocol.STATE_COMPANION)) != 0) {
            return [Actions.COLOR_GREEN, Rez.Strings.StZwift];   // Companion link needs no focus
        }
        if ((flags & Protocol.STATE_ZWIFT_RUNNING) != 0) {
            return [Actions.COLOR_ORANGE, Rez.Strings.StNotFront];
        }
        if ((flags & Protocol.STATE_OBC_CONNECTED) != 0) {
            return [Actions.COLOR_GREEN, Rez.Strings.StObc];
        }
        return [Actions.COLOR_RED, Rez.Strings.StNoZwift];
    }
}
