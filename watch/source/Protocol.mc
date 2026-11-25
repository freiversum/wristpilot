// Wire protocol between watch and Wristpilot bridge.
// Source of truth: bridge/wristpilot_bridge/protocol.py, actions.py, engine.py.

import Toybox.Lang;

module Protocol {

    // GATT service "Wristpilot"
    const SERVICE_UUID = "ae279be2-4f9c-4165-ab88-060ee241b936";
    const COMMAND_UUID = "ae279be2-4f9c-4165-ab88-060ee241b937"; // write: [seq, action, value]
    const STATUS_UUID  = "ae279be2-4f9c-4165-ab88-060ee241b938"; // read / notify
    const INFO_UUID    = "ae279be2-4f9c-4165-ab88-060ee241b939"; // read, UTF-8 text

    // Advertised local name of the bridge (the bridge may drop it if the
    // advertisement gets too long, then only the service UUID is left).
    const BRIDGE_NAME = "Wristpil";   // prefix: the Bumble bridge shortens the name to fit 31 bytes

    // Status message types (first byte of a status notification)
    const MSG_ACK    = 0x01; // [0x01, seq, result]
    const MSG_STATE  = 0x02; // [0x02, flags]
    const MSG_HAPTIC = 0x03; // [0x03, pattern]
    const MSG_GAME   = 0x04; // [0x04, flags, powerup, rideOnsLo, rideOnsHi] (Zwift Companion link)

    // Game flags (MSG_GAME)
    const GAME_LINKED   = 0x01; // bridge is connected to the game as Companion
    const GAME_JUNCTION = 0x02; // turn choices are offered right now
    const GAME_LEFT     = 0x04;
    const GAME_STRAIGHT = 0x08;
    const GAME_RIGHT    = 0x10;
    const GAME_POWERUP  = 0x20; // a power-up is ready

    // Power-up ids (MSG_GAME byte 2), see bridge companion.py
    const PU_NONE = 0;
    const PU_UNKNOWN = 10;

    // Ack results
    const RESULT_OK             = 0;
    const RESULT_NOT_FOCUSED    = 1;
    const RESULT_NOT_RUNNING    = 2;
    const RESULT_UNKNOWN_ACTION = 3;
    const RESULT_OUTPUT_FAILED  = 4;
    const RESULT_DISABLED       = 5;
    const RESULT_MALFORMED      = 6;
    const RESULT_NO_STEERING   = 7;   // lane change, but Zwift has not paired the steering device

    // State flags
    const STATE_ZWIFT_RUNNING = 0x01;
    const STATE_ZWIFT_FOCUSED = 0x02;
    const STATE_OBC_CONNECTED = 0x04;
    const STATE_KEYBOARD_ON   = 0x08;
    const STATE_ENABLED       = 0x10;
    const STATE_COMPANION     = 0x20; // bridge is linked to the game as Zwift Companion

    // OpenBikeControl button IDs (actions.py)
    const ACT_PING          = 0x00; // keep-alive, bridge answers with a STATE message
    const ACT_UP            = 0x10; // straight on
    const ACT_STEER_LEFT    = 0x18;
    const ACT_STEER_RIGHT   = 0x19;
    const ACT_EMOTE         = 0x20;
    const ACT_SCREENSHOT    = 0x24;
    const ACT_HARDER        = 0x30;
    const ACT_EASIER        = 0x31;
    const ACT_SKIP_INTERVAL = 0x32;
    const ACT_U_TURN        = 0x37;
    const ACT_CAMERA        = 0x40;
    const ACT_HUD           = 0x44;
    const ACT_POWERUP       = 0x50;
    const ACT_BELL          = 0x80;
    const ACT_LANE          = 0x81; // lane change through the bridge's virtual steering device

    // Values
    const VAL_PRESS        = 0x01;
    const EMOTE_RIDE_ON    = 0x01;
    const EMOTE_ELBOW      = 0x02;
    const EMOTE_WAVE       = 0x03;
    const EMOTE_HAMMER     = 0x05;
    const EMOTE_NICE       = 0x06;
    const EMOTE_TOAST      = 0x07;
    const SHOT_PHOTO       = 0x01;
    const SHOT_VIDEO       = 0x02;
    const CAMERA_NEXT      = 0x01;
    const LANE_LEFT        = 0x01;
    const LANE_RIGHT       = 0x02;

    // Timing (ms)
    const PING_INTERVAL = 5000;
    const ACK_TIMEOUT   = 500;

    // Build the 3-byte command [seq, action, value].
    function encodeCommand(seq, action, value) {
        var b = [0, 0, 0]b;
        b[0] = seq & 0xFF;
        b[1] = action & 0xFF;
        b[2] = value & 0xFF;
        return b;
    }
}
