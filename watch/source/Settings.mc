// Persistent user settings (Application.Storage, API 2.4+).

import Toybox.Application;
import Toybox.Lang;

module Settings {

    const KEY_VIBE = "vibe";
    const KEY_JUNCTION_VIBE = "junctionVibe";
    const KEY_START_PAGE = "startPage";

    const PAGE_RIDE = 0;
    const PAGE_ACTIONS = 1;
    const PAGE_WORKOUT = 2;
    const PAGE_COUNT = 3;

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
}
