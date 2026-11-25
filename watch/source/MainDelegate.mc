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
//
// Turn protection (Settings.guard(), normal mode only; Ride On, power-up and the other pages are
// never delayed):
//   press twice: a turn, straight on or U-turn is first marked (overlay, short tick) and only sent
//                when the same key, gesture or tile comes again within ARM_WINDOW.
//   hold:        turns need a hold of HOLD_TURN ms (ring), sent on release; U-turn and the menu move
//                to HOLD_LONG. Taps and swipes for turns only show a hint.
// Race mode (Settings.race()): the Ride page has no turns. BACK and START fire the power-up
// (Edge: every key but BACK), DOWN gives a Ride On in the "power-up + Ride On" variant, holding
// BACK does not exit (only the menu does).
// Party mode (Settings.partyOn(), group rides): UP wave (hold: menu), START Ride On (hold: Hammer
// Time), DOWN elbow flick (hold: Nice), BACK power-up (hold: photo, no exit). Touch: tap a field.
// Edge: LAP wave, START Ride On (hold: Hammer Time), UP elbow, DOWN power-up, ENTER Nice.

import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

class MainDelegate extends WatchUi.InputDelegate {

    const LONG_PRESS = 600;     // ms
    const ECHO_WINDOW = 300;    // ms: onKey right after our own release/touch is ignored
    const ARM_WINDOW = 2000;    // ms: turn protection "press twice"
    const HOLD_TURN = 600;      // ms: turn protection "hold", turn
    const HOLD_LONG = 1500;     // ms: turn protection "hold", U-turn / menu

    hidden var view;
    hidden var keyDown = null;
    hidden var keyDownAt = 0;
    hidden var keyConsumed = false;
    hidden var lastReleaseKey = null;
    hidden var lastReleaseAt = 0;
    hidden var lastTouchAt = 0;
    hidden var lastMenuAt = -10000;
    hidden var armedAction = null;
    hidden var armedAt = 0;

    function initialize(v) {
        InputDelegate.initialize();
        view = v;
    }

    // --- Buttons -------------------------------------------------------------

    function onKeyPressed(keyEvent) {
        var k = keyEvent.getKey();
        if (k == WatchUi.KEY_MENU) {
            // The watch turns a held UP into KEY_MENU (about 1 s). With "hold" protection UP is
            // held to turn left; the menu then opens from tick() at HOLD_LONG instead.
            if (!(keyDown == WatchUi.KEY_UP && holdTurnKey(WatchUi.KEY_UP))) {
                openMenu();
            }
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
            if (holdTurnKey(k)) {
                $.gRemote.clearPending();
                if (System.getTimer() - keyDownAt >= HOLD_TURN) {
                    rideHeld(holdTurnAction(k));
                } else {
                    shortPress(k);      // too short: shows "hold to turn"
                }
            } else {
                shortPress(k);
            }
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
            if (!(keyDown == WatchUi.KEY_UP && holdTurnKey(WatchUi.KEY_UP))) {
                openMenu();
            }
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
        if (keyDown == null || keyConsumed) {
            return;
        }
        var held = now - keyDownAt;
        if (holdTurnKey(keyDown)) {
            if (held >= HOLD_LONG && holdHasLong(keyDown)) {
                keyConsumed = true;
                $.gRemote.clearPending();
                longPress(keyDown);
            } else {
                $.gRemote.showHold(holdTurnAction(keyDown), held / HOLD_TURN.toFloat());
            }
        } else if (held >= LONG_PRESS) {
            keyConsumed = true;
            longPress(keyDown);
        }
    }

    // --- Turn protection and race mode ------------------------------------------

    function raceOn() {
        return Settings.raceOn();
    }

    function partyOn() {
        return Settings.partyOn();
    }

    // Turn protection only on the normal ride page (race and party have no turns).
    hidden function guardMode() {
        return Settings.race() != Settings.RACE_OFF ? Settings.GUARD_OFF : Settings.guard();
    }

    hidden function isTurn(a) {
        return a == Actions.LEFT || a == Actions.RIGHT || a == Actions.STRAIGHT || a == Actions.U_TURN;
    }

    // A Ride action from a short press, tap or swipe, through the turn protection.
    hidden function ride(a) {
        var rm = $.gRemote;
        if (!isTurn(a)) {
            armedAction = null;
            rm.send(a);
            return;
        }
        var g = guardMode();
        if (g == Settings.GUARD_OFF) {
            armedAction = null;
            rm.send(a);
        } else if (g == Settings.GUARD_HOLD) {
            rm.showHint(Rez.Strings.HoldTurn);
        } else {
            var now = System.getTimer();
            if (armedAction == a && now - armedAt <= ARM_WINDOW) {
                armedAction = null;
                rm.send(a);
            } else {
                armedAction = a;
                armedAt = now;
                rm.showArmed(a, ARM_WINDOW);
            }
        }
    }

    // A Ride action from a hold. With "hold" protection the hold is the confirmation.
    hidden function rideHeld(a) {
        if (guardMode() == Settings.GUARD_HOLD) {
            armedAction = null;
            $.gRemote.send(a);
        } else {
            ride(a);
        }
    }

    // Keys that turn by holding ("hold" protection, Ride page).
    hidden function holdTurnKey(k) {
        if (guardMode() != Settings.GUARD_HOLD || !$.gBle.isReady() || view.page != Settings.PAGE_RIDE) {
            return false;
        }
        if (Style.EDGE) {
            return k == WatchUi.KEY_LAP || k == WatchUi.KEY_START || k == WatchUi.KEY_ENTER;
        }
        return k == WatchUi.KEY_UP || k == WatchUi.KEY_ENTER;
    }

    hidden function holdTurnAction(k) {
        if (Style.EDGE) {
            return k == WatchUi.KEY_LAP ? Actions.LEFT : (k == WatchUi.KEY_START ? Actions.RIGHT : Actions.STRAIGHT);
        }
        return k == WatchUi.KEY_UP ? Actions.LEFT : Actions.RIGHT;
    }

    // Does the key have a second action at HOLD_LONG (menu, U-turn)?
    hidden function holdHasLong(k) {
        if (Style.EDGE) {
            return k == WatchUi.KEY_START;
        }
        return true;
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
        } else if (partyOn()) {
            if (k == WatchUi.KEY_UP) {
                rm.send(Actions.WAVE);
            } else if (k == WatchUi.KEY_ENTER) {
                rm.send(Actions.RIDE_ON);
            } else if (k == WatchUi.KEY_DOWN) {
                rm.send(Actions.ELBOW);
            } else {
                rm.send(Actions.POWERUP);
            }
        } else if (raceOn()) {
            if (k == WatchUi.KEY_ENTER || k == WatchUi.KEY_ESC) {
                rm.send(Actions.POWERUP);
            } else if (k == WatchUi.KEY_DOWN && Settings.race() == Settings.RACE_POWER_RIDEON) {
                rm.send(Actions.RIDE_ON);
            }
        } else {
            if (k == WatchUi.KEY_UP) {
                ride(Actions.LEFT);
            } else if (k == WatchUi.KEY_ENTER) {
                ride(Actions.RIGHT);
            } else if (k == WatchUi.KEY_DOWN) {
                ride(Actions.RIDE_ON);
            } else {
                ride(Actions.POWERUP);
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
        } else if (partyOn()) {
            if (k == WatchUi.KEY_LAP) {
                rm.send(Actions.WAVE);
            } else if (k == WatchUi.KEY_START) {
                rm.send(Actions.RIDE_ON);
            } else if (k == WatchUi.KEY_UP) {
                rm.send(Actions.ELBOW);
            } else if (k == WatchUi.KEY_DOWN) {
                rm.send(Actions.POWERUP);
            } else if (k == WatchUi.KEY_ENTER) {
                rm.send(Actions.NICE);
            }
        } else if (raceOn()) {
            if (k == WatchUi.KEY_UP && Settings.race() == Settings.RACE_POWER_RIDEON) {
                rm.send(Actions.RIDE_ON);
            } else {
                rm.send(Actions.POWERUP);
            }
        } else {
            if (k == WatchUi.KEY_LAP) {
                ride(Actions.LEFT);
            } else if (k == WatchUi.KEY_START) {
                ride(Actions.RIGHT);
            } else if (k == WatchUi.KEY_ENTER) {
                ride(Actions.STRAIGHT);
            } else if (k == WatchUi.KEY_UP) {
                ride(Actions.RIDE_ON);
            } else if (k == WatchUi.KEY_DOWN) {
                ride(Actions.POWERUP);
            }
        }
    }

    hidden function longPress(k) {
        if (k == WatchUi.KEY_UP) {
            openMenu();
            return;
        }
        if (k == WatchUi.KEY_ESC) {
            if (partyOn() && $.gBle.isReady() && view.page == Settings.PAGE_RIDE) {
                $.gRemote.send(Actions.PHOTO);
            } else if (!raceOn()) {
                confirmExit();      // race mode: a grab at BACK in a sprint must not end the app
            }
            return;
        }
        if (!$.gBle.isReady()) {
            return;
        }
        var page = view.page;
        if (page == Settings.PAGE_RIDE && raceOn()) {
            return;
        }
        if (page == Settings.PAGE_RIDE && partyOn()) {
            if (k == WatchUi.KEY_ENTER || k == WatchUi.KEY_START) {
                $.gRemote.send(Actions.HAMMER);
            } else if (k == WatchUi.KEY_DOWN && !Style.EDGE) {
                $.gRemote.send(Actions.NICE);
            }
            return;
        }
        if (Style.EDGE) {
            if (page == Settings.PAGE_RIDE && k == WatchUi.KEY_START) {
                rideHeld(Actions.U_TURN);
            } else if (page == Settings.PAGE_WORKOUT && k == WatchUi.KEY_DOWN) {
                $.gRemote.send(Actions.SKIP);
            }
            return;
        }
        if (page == Settings.PAGE_RIDE) {
            if (k == WatchUi.KEY_ENTER) {
                rideHeld(Actions.U_TURN);
            } else if (k == WatchUi.KEY_DOWN) {
                rideHeld(Actions.STRAIGHT);
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
        } else if (partyOn()) {
            var pa = view.partyActionAt(xy[0], xy[1]);
            if (pa != null) {
                $.gRemote.send(pa);
            }
        } else if (raceOn()) {
            var ra = view.raceActionAt(xy[0], xy[1]);
            if (ra != null) {
                $.gRemote.send(ra);
            }
        } else {
            var act = view.rideActionAt(xy[0], xy[1]);
            if (act == Actions.MORE) {
                view.setPage(Settings.PAGE_ACTIONS);
            } else {
                ride(act);
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
        if (page == Settings.PAGE_RIDE && partyOn()) {
            return true;
        } else if (page == Settings.PAGE_RIDE && raceOn()) {
            var ra = view.raceActionAt(xy[0], xy[1]);
            if (ra != null) {
                $.gRemote.send(ra);
            }
        } else if (page == Settings.PAGE_RIDE && guardMode() == Settings.GUARD_HOLD
                && isTurn(view.rideActionAt(xy[0], xy[1]))) {
            rideHeld(view.rideActionAt(xy[0], xy[1]));
        } else if (page == Settings.PAGE_RIDE && !Style.EDGE) {
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
            if (Settings.race() != Settings.RACE_OFF) {
                return true;        // no turns in race and party mode
            }
            if (dir == WatchUi.SWIPE_LEFT) {
                ride(Actions.LEFT);
            } else if (dir == WatchUi.SWIPE_RIGHT) {
                ride(Actions.RIGHT);
            } else if (dir == WatchUi.SWIPE_UP) {
                ride(Actions.STRAIGHT);
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
