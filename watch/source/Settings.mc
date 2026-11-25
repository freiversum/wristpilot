// Persistent user settings (Application.Storage, API 2.4+).

import Toybox.Application;
import Toybox.Lang;

module Settings {

    const KEY_VIBE = "vibe";
    const KEY_JUNCTION_VIBE = "junctionVibe";
    const KEY_START_PAGE = "startPage";
    const KEY_RACE = "race";
    const KEY_GUARD = "guard";

    const PAGE_RIDE = 0;
    const PAGE_ACTIONS = 1;
    const PAGE_WORKOUT = 2;
    const PAGE_COUNT = 3;

    // What the Ride page is (menu "Ride page"; stored under KEY_RACE for older settings):
    // normal ride page, a race page without turns and U-turn, or the party page for group rides.
    const RACE_OFF = 0;          // normal ride page
    const RACE_POWER = 1;        // race A: power-up only
    const RACE_POWER_RIDEON = 2; // race B: power-up and Ride On
    const RACE_PARTY = 3;        // party: four social gestures, no turns, no power-up
    const RACE_COUNT = 4;

    // Turn protection in the normal mode: turns and U-turn need a second action.
    const GUARD_OFF = 0;
    const GUARD_TWICE = 1;      // S1: same key (or gesture) twice within ARM_WINDOW
    const GUARD_HOLD = 2;       // S2: hold until the ring is full
    const GUARD_COUNT = 3;

    function get(key, fallback) {
        var v = null;
        try {
            v = Application.Storage.getValue(key);
        } catch (e) {
            v = null;
        }
        return (v == null) ? fallback : v;
    }

    function set(key, value) {
        try {
            Application.Storage.setValue(key, value);
        } catch (e) {
            // Storage full or unavailable: keep the value for this session only.
        }
    }

    function vibrationOn() {
        return get(KEY_VIBE, true) == true;
    }

    function setVibration(on) {
        set(KEY_VIBE, on);
    }

    function junctionVibrationOn() {
        return vibrationOn() && get(KEY_JUNCTION_VIBE, true) == true;
    }

    function setJunctionVibration(on) {
        set(KEY_JUNCTION_VIBE, on);
    }

    function startPage() {
        var p = get(KEY_START_PAGE, PAGE_RIDE);
        if (!(p instanceof Number) || p < 0 || p >= PAGE_COUNT) {
            return PAGE_RIDE;
        }
        return p;
    }

    function setStartPage(p) {
        set(KEY_START_PAGE, p);
    }

    function pageName(p) {
        if (p == PAGE_ACTIONS) {
            return Rez.Strings.PageActions;
        } else if (p == PAGE_WORKOUT) {
            return Rez.Strings.PageWorkout;
        }
        return Rez.Strings.PageRide;
    }

    function race() {
        var v = get(KEY_RACE, RACE_OFF);
        return (v instanceof Number && v >= 0 && v < RACE_COUNT) ? v : RACE_OFF;
    }

    function setRace(v) {
        set(KEY_RACE, v);
    }

    function raceName(v) {
        if (v == RACE_POWER) {
            return Rez.Strings.RacePower;
        } else if (v == RACE_POWER_RIDEON) {
            return Rez.Strings.RacePowerRideOn;
        } else if (v == RACE_PARTY) {
            return Rez.Strings.ModeParty;
        }
        return Rez.Strings.ModeNormal;
    }

    // Race page (A or B), not party.
    function raceOn() {
        var r = race();
        return r == RACE_POWER || r == RACE_POWER_RIDEON;
    }

    function partyOn() {
        return race() == RACE_PARTY;
    }

    // Protection is on by default (press twice).
    function guard() {
        var v = get(KEY_GUARD, GUARD_TWICE);
        return (v instanceof Number && v >= 0 && v < GUARD_COUNT) ? v : GUARD_TWICE;
    }

    function setGuard(v) {
        set(KEY_GUARD, v);
    }

    function guardName(v) {
        if (v == GUARD_TWICE) {
            return Rez.Strings.GuardTwice;
        } else if (v == GUARD_HOLD) {
            return Rez.Strings.GuardHold;
        }
        return Rez.Strings.Off;
    }
}
