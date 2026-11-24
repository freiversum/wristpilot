// Input handling for MainView.
//
// Buttons use onKeyPressed/onKeyReleased so that short and long presses can be
// told apart: a long press fires after LONG_PRESS ms while the key is still held
// (driven by tick()), a short press fires on release.
//
// Ride page (connected):
//   UP    (left, 9 o'clock)  short: turn left     long: settings menu
//   START (right, 2 o'clock) short: turn right    long: U-turn
//   DOWN  (left, 8 o'clock)  short: Ride On       long: straight on
//   BACK  (right, 4 o'clock) short: power-up      long: exit question
//   Touch: swipe left/right = turn, swipe up = straight on, tap quadrant = its
//          action, hold = power-up, swipe down = next page.
// Actions page:  UP/DOWN select, START send, BACK -> Ride; tap tile = send;
//                swipe down = next page, swipe up = previous page.
// Workout page:  UP easier, START harder, DOWN long = skip interval, BACK -> Ride;
//                tap left/right half = easier/harder, hold bottom area = skip.
// Connect screen: START (or tap) = device list, BACK = exit question.

import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

class MainDelegate extends WatchUi.InputDelegate {

    const LONG_PRESS = 600;     // ms
    const ECHO_WINDOW = 300;    // ms: onKey right after our own release/touch is ignored

    hidden var view;
    hidden var keyDown = null;
    hidden var keyDownAt = 0;
    hidden var keyConsumed = false;
    hidden var lastReleaseKey = null;
    hidden var lastReleaseAt = 0;
    hidden var lastTouchAt = 0;
    hidden var lastMenuAt = -10000;

    function initialize(v) {
        InputDelegate.initialize();
        view = v;
    }

    // --- Buttons -------------------------------------------------------------

    function onKeyPressed(keyEvent) {
        var k = keyEvent.getKey();
        if (k == WatchUi.KEY_MENU) {
            openMenu();
            return true;
        }
        if (!isOurKey(k)) {
            return false;
        }
        keyDown = k;
        keyDownAt = System.getTimer();
        keyConsumed = false;
        return true;
    }

    function onKeyReleased(keyEvent) {
        var k = keyEvent.getKey();
        if (k == WatchUi.KEY_MENU) {
            return true;
        }
        if (!isOurKey(k)) {
            return false;
        }
        if (keyDown == k && !keyConsumed) {
            shortPress(k);
        }
        keyDown = null;
        keyConsumed = false;
        lastReleaseKey = k;
        lastReleaseAt = System.getTimer();
        return true;
    }

    // onKey comes in addition to pressed/released. Only used as a fallback when a
    // key arrives without a pressed/released pair (not expected on the fenix).
    function onKey(keyEvent) {
        var k = keyEvent.getKey();
        if (k == WatchUi.KEY_MENU) {
            openMenu();
            return true;
        }
        if (!isOurKey(k)) {
            return false;
        }
        var now = System.getTimer();
        var echo = (lastReleaseKey == k && now - lastReleaseAt < ECHO_WINDOW)
            || now - lastTouchAt < ECHO_WINDOW;
        if (keyDown == null && !echo) {
            // Some devices turn a touch gesture into KEY_ESC/KEY_ENTER. Never send a
            // command from such a synthetic key on the Ride page; just ignore it there.
            if (!(view.page == Settings.PAGE_RIDE && $.gBle.isReady())) {
                shortPress(k);
            }
        }
        return true;
    }

    function isOurKey(k) {
        if (Style.EDGE && (k == WatchUi.KEY_START || k == WatchUi.KEY_LAP)) {
            return true;
        }
        return k == WatchUi.KEY_UP || k == WatchUi.KEY_DOWN
            || k == WatchUi.KEY_ENTER || k == WatchUi.KEY_ESC;
    }

    // Called every 100 ms by the app timer.
    function tick(now) {
        if (keyDown != null && !keyConsumed && now - keyDownAt >= LONG_PRESS) {
            keyConsumed = true;
            longPress(keyDown);
        }
    }

    // Forget a held key (e.g. when another view was pushed on top).
    function resetKeys() {
        keyDown = null;
        keyConsumed = false;
    }

    hidden function shortPress(k) {
        var rm = $.gRemote;
        if (!$.gBle.isReady()) {
            if (k == WatchUi.KEY_ESC) {
                confirmExit();
            } else if (k == WatchUi.KEY_ENTER) {
                $.openDevicePicker();
            }
            return;
        }
        var page = view.page;
        if (Style.EDGE) {
            edgeShortPress(k, page);
            return;
        }
        if (page == Settings.PAGE_ACTIONS) {
            if (k == WatchUi.KEY_UP) {
                view.moveSelection(-1);
            } else if (k == WatchUi.KEY_DOWN) {
                view.moveSelection(1);
            } else if (k == WatchUi.KEY_ENTER) {
                rm.send(Actions.ACTION_TILES[view.selected]);
            } else {
                view.setPage(Settings.PAGE_RIDE);
            }
        } else if (page == Settings.PAGE_WORKOUT) {
            if (k == WatchUi.KEY_UP) {
                rm.send(Actions.EASIER);
            } else if (k == WatchUi.KEY_ENTER) {
                rm.send(Actions.HARDER);
            } else if (k == WatchUi.KEY_DOWN) {
                rm.showHint(Rez.Strings.WkHoldHint);
            } else {
                view.setPage(Settings.PAGE_RIDE);
            }
        } else {
            if (k == WatchUi.KEY_UP) {
                rm.send(Actions.LEFT);
            } else if (k == WatchUi.KEY_ENTER) {
                rm.send(Actions.RIGHT);
            } else if (k == WatchUi.KEY_DOWN) {
                rm.send(Actions.RIDE_ON);
            } else {
                rm.send(Actions.POWERUP);
            }
        }
    }

    // Edge bike computers. LAP (bottom left) / START (bottom right) work on every model; the button-only
    // models (Edge 530/540/550/MTB) also have UP/DOWN (left) and ENTER/BACK (right).
    //   Ride:    LAP left · START right · ENTER straight · UP Ride On · DOWN power-up · BACK next page
    //   Actions: UP/DOWN select · ENTER or START send · LAP or BACK next page
    //   Workout: LAP or UP easier · START or ENTER harder · BACK next page (skip: hold DOWN/tap-hold)
    hidden function edgeShortPress(k, page) {
        var rm = $.gRemote;
        if (k == WatchUi.KEY_ESC) {
            view.setPage(page + 1);
            return;
        }
        if (page == Settings.PAGE_ACTIONS) {
            if (k == WatchUi.KEY_UP) {
                view.moveSelection(-1);
            } else if (k == WatchUi.KEY_DOWN) {
                view.moveSelection(1);
            } else if (k == WatchUi.KEY_ENTER || k == WatchUi.KEY_START) {
                rm.send(Actions.ACTION_TILES[view.selected]);
            } else {
                view.setPage(page + 1);
            }
        } else if (page == Settings.PAGE_WORKOUT) {
            if (k == WatchUi.KEY_LAP || k == WatchUi.KEY_UP) {
                rm.send(Actions.EASIER);
            } else if (k == WatchUi.KEY_START || k == WatchUi.KEY_ENTER) {
                rm.send(Actions.HARDER);
            } else {
                rm.showHint(Rez.Strings.WkHoldHint);
            }
        } else {
            if (k == WatchUi.KEY_LAP) {
                rm.send(Actions.LEFT);
            } else if (k == WatchUi.KEY_START) {
                rm.send(Actions.RIGHT);
            } else if (k == WatchUi.KEY_ENTER) {
                rm.send(Actions.STRAIGHT);
            } else if (k == WatchUi.KEY_UP) {
                rm.send(Actions.RIDE_ON);
            } else if (k == WatchUi.KEY_DOWN) {
                rm.send(Actions.POWERUP);
            }
        }
    }

    hidden function longPress(k) {
        if (k == WatchUi.KEY_UP) {
            openMenu();
            return;
        }
        if (k == WatchUi.KEY_ESC) {
            confirmExit();
            return;
        }
        if (!$.gBle.isReady()) {
            return;
        }
        var page = view.page;
        if (Style.EDGE) {
            if (page == Settings.PAGE_RIDE && k == WatchUi.KEY_START) {
                $.gRemote.send(Actions.U_TURN);
            } else if (page == Settings.PAGE_WORKOUT && k == WatchUi.KEY_DOWN) {
                $.gRemote.send(Actions.SKIP);
            }
            return;
        }
        if (page == Settings.PAGE_RIDE) {
            if (k == WatchUi.KEY_ENTER) {
                $.gRemote.send(Actions.U_TURN);
            } else if (k == WatchUi.KEY_DOWN) {
                $.gRemote.send(Actions.STRAIGHT);
            }
        } else if (page == Settings.PAGE_WORKOUT) {
            if (k == WatchUi.KEY_DOWN) {
                $.gRemote.send(Actions.SKIP);
            }
        }
    }

    // --- Touch ---------------------------------------------------------------

    function onTap(clickEvent) {
        lastTouchAt = System.getTimer();
        var xy = clickEvent.getCoordinates();
        if (!$.gBle.isReady()) {
            $.openDevicePicker();
            return true;
        }
        var page = view.page;
        if (page == Settings.PAGE_ACTIONS) {
            var i = view.tileAt(xy[0], xy[1]);
            if (i >= 0) {
                view.selected = i;
                $.gRemote.send(Actions.ACTION_TILES[i]);
            }
        } else if (page == Settings.PAGE_WORKOUT) {
            var a = view.workoutActionAt(xy[0], xy[1]);
            if (a == Actions.SKIP) {
                $.gRemote.showHint(Rez.Strings.WkHoldHint);   // skipping needs a hold
            } else {
                $.gRemote.send(a);
            }
        } else {
            var act = view.rideActionAt(xy[0], xy[1]);
            if (act == Actions.MORE) {
                view.setPage(Settings.PAGE_ACTIONS);
            } else {
                $.gRemote.send(act);
            }
        }
        return true;
    }

    function onHold(clickEvent) {
        lastTouchAt = System.getTimer();
        if (!$.gBle.isReady()) {
            return true;
        }
        var xy = clickEvent.getCoordinates();
        var page = view.page;
        if (page == Settings.PAGE_RIDE && !Style.EDGE) {
            $.gRemote.send(Actions.POWERUP);
        } else if (page == Settings.PAGE_WORKOUT && view.workoutActionAt(xy[0], xy[1]) == Actions.SKIP) {
            $.gRemote.send(Actions.SKIP);
        }
        return true;
    }

    function onRelease(clickEvent) {
        lastTouchAt = System.getTimer();
        return true;
    }

    function onSwipe(swipeEvent) {
        lastTouchAt = System.getTimer();
        var dir = swipeEvent.getDirection();
        if (!$.gBle.isReady()) {
            return true;
        }
        if (dir == WatchUi.SWIPE_DOWN) {
            view.setPage(view.page + 1);
            return true;
        }
        if (view.page == Settings.PAGE_RIDE) {
            if (dir == WatchUi.SWIPE_LEFT) {
                $.gRemote.send(Actions.LEFT);
            } else if (dir == WatchUi.SWIPE_RIGHT) {
                $.gRemote.send(Actions.RIGHT);
            } else if (dir == WatchUi.SWIPE_UP) {
                $.gRemote.send(Actions.STRAIGHT);
            }
        } else if (dir == WatchUi.SWIPE_UP) {
            view.setPage(view.page - 1);
        } else if (view.page == Settings.PAGE_ACTIONS) {
            view.moveSelection(dir == WatchUi.SWIPE_LEFT ? 1 : -1);
        }
        return true;
    }

    // --- Pushed views ----------------------------------------------------------

    hidden function openMenu() {
        keyConsumed = true;
        var now = System.getTimer();
        if (now - lastMenuAt < 1000) {
            return;     // KEY_MENU may arrive both as pressed and as onKey
        }
        lastMenuAt = now;
        $.openSettingsMenu(view);
    }

    hidden function confirmExit() {
        keyConsumed = true;
        WatchUi.pushView(new WatchUi.Confirmation(WatchUi.loadResource(Rez.Strings.ExitQuestion)),
            new ExitConfirmDelegate(), WatchUi.SLIDE_IMMEDIATE);
    }
}
