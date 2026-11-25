// Wristpilot: Garmin watch as a Zwift remote. Entry point.

import Toybox.Application;
import Toybox.Lang;
import Toybox.System;
import Toybox.Timer;
import Toybox.WatchUi;

// App-wide singletons (untyped on purpose, see README "Type checking").
var gBle = null;      // BleManager
var gRemote = null;   // Remote
var gView = null;     // MainView
var gInput = null;    // MainDelegate
var gDirty = false;   // something changed, redraw on the next tick

class WristpilotApp extends Application.AppBase {

    const TICK = 100;            // ms; drives pings, timeouts, long presses, overlays
    const IDLE_REDRAW = 500;     // ms; animation of the connect screen

    hidden var timer = null;
    hidden var lastRedraw = 0;

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state) {
        $.gRemote = new Remote();
        $.gBle = new BleManager($.gRemote);
        if (Build.DEMO) {
            // store screenshots: bridge connected, Zwift in front, Companion link with a junction ahead
            $.gRemote.flags = Protocol.STATE_ENABLED | Protocol.STATE_KEYBOARD_ON | Protocol.STATE_ZWIFT_RUNNING
                | Protocol.STATE_ZWIFT_FOCUSED | Protocol.STATE_COMPANION;
            $.gRemote.game = Protocol.GAME_LINKED | Protocol.GAME_JUNCTION | Protocol.GAME_LEFT
                | Protocol.GAME_STRAIGHT | Protocol.GAME_POWERUP;
            $.gRemote.powerup = 2;   // draft boost
            $.gRemote.rideOns = 12;
        } else {
            $.gBle.start();
        }
        timer = new Timer.Timer();
        timer.start(method(:onTick), TICK, true);
    }

    function onStop(state) {
        if (timer != null) {
            timer.stop();
            timer = null;
        }
        if ($.gBle != null) {
            $.gBle.shutdown();
        }
    }

    // Task switcher on devices with API 4.2.3 lifecycle support (fenix 8, Venu 3, ...): the app goes
    // to the background without onStop. A long press that started before must not fire later, and
    // the screen has to be redrawn when the app comes back. (The fenix 7 Pro, firmware 27.18, does
    // not call these: holding BACK ends the app with a plain onStop.)
    function onInactive(state) {
        if ($.gInput != null) {
            $.gInput.resetKeys();
        }
    }

    function onActive(state) {
        if ($.gInput != null) {
            $.gInput.resetKeys();
        }
        $.gDirty = true;
        WatchUi.requestUpdate();
    }

    function getInitialView() {
        $.gView = new MainView();
        $.gInput = new MainDelegate($.gView);
        return [$.gView, $.gInput];
    }

    function onTick() as Void {
        var now = System.getTimer();
        $.gBle.tick(now);
        $.gRemote.tick(now);
        if ($.gInput != null) {
            $.gInput.tick(now);
        }
        // connect screen animates; the Ride status line may turn "no answer"
        var every = $.gBle.isReady() ? 4 * IDLE_REDRAW : IDLE_REDRAW;
        var animate = now - lastRedraw >= every;
        if ($.gDirty || animate) {
            $.gDirty = false;
            lastRedraw = now;
            WatchUi.requestUpdate();
        }
    }
}
