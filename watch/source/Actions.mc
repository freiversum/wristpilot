// Logical actions of the watch UI and how they map to bridge commands.

import Toybox.Lang;

module Actions {

    // Pure colours that survive the 64-colour MIP palette (0x00/0x55/0xAA/0xFF steps).
    const COLOR_CYAN   = 0x00FFFF;
    const COLOR_GREEN  = 0x00FF00;
    const COLOR_ORANGE = 0xFFAA00;
    const COLOR_YELLOW = 0xFFFF00;
    const COLOR_VIOLET = 0xAA55FF;
    const COLOR_GREY   = 0xAAAAAA;
    const COLOR_RED    = 0xFF0000;
    const COLOR_WHITE  = 0xFFFFFF;
    const COLOR_BLACK  = 0x000000;

    // Logical action ids (index into the table below)
    const LEFT     = 0;
    const RIGHT    = 1;
    const STRAIGHT = 2;
    const U_TURN   = 3;
    const POWERUP  = 4;
    const RIDE_ON  = 5;
    const ELBOW    = 6;
    const WAVE     = 7;
    const NICE     = 8;
    const HAMMER   = 9;
    const BELL     = 10;
    const PHOTO    = 11;
    const CAMERA   = 12;
    const HUD      = 13;
    const HARDER   = 14;
    const EASIER   = 15;
    const SKIP     = 16;
    const MORE     = 99;    // Edge: "more" tile, opens the Actions page (not sent to the bridge)

    // Tiles of the "Actions" page, in display order (two rows of four).
    const ACTION_TILES = [ELBOW, WAVE, NICE, HAMMER, BELL, PHOTO, CAMERA, HUD];

    // [bridge action id, value, label resource, colour, icon symbol]
    function info(a) {
        switch (a) {
            case LEFT:     return [Protocol.ACT_STEER_LEFT, Protocol.VAL_PRESS, Rez.Strings.ActLeft, COLOR_CYAN, :left];
            case RIGHT:    return [Protocol.ACT_STEER_RIGHT, Protocol.VAL_PRESS, Rez.Strings.ActRight, COLOR_CYAN, :right];
            case STRAIGHT: return [Protocol.ACT_UP, Protocol.VAL_PRESS, Rez.Strings.ActStraight, COLOR_CYAN, :up];
            case U_TURN:   return [Protocol.ACT_U_TURN, Protocol.VAL_PRESS, Rez.Strings.ActUturn, COLOR_CYAN, :uturn];
            case POWERUP:  return [Protocol.ACT_POWERUP, Protocol.VAL_PRESS, Rez.Strings.ActPowerup, COLOR_ORANGE, :bolt];
            case RIDE_ON:  return [Protocol.ACT_EMOTE, Protocol.EMOTE_RIDE_ON, Rez.Strings.ActRideOn, COLOR_GREEN, :thumb];
            case ELBOW:    return [Protocol.ACT_EMOTE, Protocol.EMOTE_ELBOW, Rez.Strings.ActElbow, COLOR_CYAN, :elbow];
            case WAVE:     return [Protocol.ACT_EMOTE, Protocol.EMOTE_WAVE, Rez.Strings.ActWave, COLOR_CYAN, :wave];
            case NICE:     return [Protocol.ACT_EMOTE, Protocol.EMOTE_NICE, Rez.Strings.ActNice, COLOR_GREEN, :star];
            case HAMMER:   return [Protocol.ACT_EMOTE, Protocol.EMOTE_HAMMER, Rez.Strings.ActHammer, COLOR_ORANGE, :hammer];
            case BELL:     return [Protocol.ACT_BELL, Protocol.VAL_PRESS, Rez.Strings.ActBell, COLOR_YELLOW, :bell];
            case PHOTO:    return [Protocol.ACT_SCREENSHOT, Protocol.SHOT_PHOTO, Rez.Strings.ActPhoto, COLOR_VIOLET, :photo];
            case CAMERA:   return [Protocol.ACT_CAMERA, Protocol.CAMERA_NEXT, Rez.Strings.ActCamera, COLOR_VIOLET, :camera];
            case HUD:      return [Protocol.ACT_HUD, Protocol.VAL_PRESS, Rez.Strings.ActHud, COLOR_GREY, :hud];
            case HARDER:   return [Protocol.ACT_HARDER, Protocol.VAL_PRESS, Rez.Strings.ActHarder, COLOR_ORANGE, :plus];
            case EASIER:   return [Protocol.ACT_EASIER, Protocol.VAL_PRESS, Rez.Strings.ActEasier, COLOR_CYAN, :minus];
            case SKIP:     return [Protocol.ACT_SKIP_INTERVAL, Protocol.VAL_PRESS, Rez.Strings.ActSkip, COLOR_WHITE, :skip];
        }
        return null;
    }

    // Resource id of the text shown for an ack result other than OK.
    function resultText(result) {
        switch (result) {
            case Protocol.RESULT_NOT_FOCUSED:    return Rez.Strings.Res1;
            case Protocol.RESULT_NOT_RUNNING:    return Rez.Strings.Res2;
            case Protocol.RESULT_UNKNOWN_ACTION: return Rez.Strings.Res3;
            case Protocol.RESULT_OUTPUT_FAILED:  return Rez.Strings.Res4;
            case Protocol.RESULT_DISABLED:       return Rez.Strings.Res5;
            case Protocol.RESULT_MALFORMED:      return Rez.Strings.Res6;
        }
        return Rez.Strings.ResOther;
    }
}
