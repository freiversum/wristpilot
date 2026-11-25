// Settings menu (long press UP), device pick list and exit confirmation.

import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

// --- Settings menu ------------------------------------------------------------

function openSettingsMenu(view) {
    var menu = new WatchUi.Menu2({ :title => Rez.Strings.AppName });
    // Exit comes first: on firmware with a task switcher, holding BACK no longer reaches the app,
    // so the menu is the way out and must not hide at the end of a long list.
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuExit, null, :exit, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuRace,
        Settings.raceName(Settings.race()), :race, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuGuard,
        Settings.guardName(Settings.guard()), :guard, null));
    menu.addItem(new WatchUi.ToggleMenuItem(Rez.Strings.MenuVibe,
        { :enabled => Rez.Strings.On, :disabled => Rez.Strings.Off },
        :vibe, Settings.vibrationOn(), null));
    menu.addItem(new WatchUi.ToggleMenuItem(Rez.Strings.SetJunctionVibe,
        { :enabled => Rez.Strings.On, :disabled => Rez.Strings.Off },
        :junctionVibe, Settings.get(Settings.KEY_JUNCTION_VIBE, true) == true, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuStartPage,
        Settings.pageName(Settings.startPage()), :startPage, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuGoRide, null, :goRide, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuGoActions, null, :goActions, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuGoWorkout, null, :goWorkout, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuPick, null, :pick, null));
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuReconnect, null, :reconnect, null));
    var info = $.gBle.bridgeInfo;
    if (info != null) {
        menu.addItem(new WatchUi.MenuItem(Rez.Strings.MenuInfo, info, :info, null));
    }
    WatchUi.pushView(menu, new SettingsMenuDelegate(view), WatchUi.SLIDE_UP);
}

class SettingsMenuDelegate extends WatchUi.Menu2InputDelegate {

    hidden var view;

    function initialize(v) {
        Menu2InputDelegate.initialize();
        view = v;
    }

    function onSelect(item) {
        var id = item.getId();
        if (id == :vibe) {
            // the toggle has already flipped its state
            Settings.setVibration((item as WatchUi.ToggleMenuItem).isEnabled());
        } else if (id == :junctionVibe) {
            Settings.setJunctionVibration((item as WatchUi.ToggleMenuItem).isEnabled());
        } else if (id == :race) {
            var r = (Settings.race() + 1) % Settings.RACE_COUNT;
            Settings.setRace(r);
            item.setSubLabel(Settings.raceName(r));
            WatchUi.requestUpdate();
        } else if (id == :guard) {
            // order on the watch: press twice (default) -> hold -> off -> press twice
            var g = Settings.guard();
            g = (g == Settings.GUARD_TWICE) ? Settings.GUARD_HOLD
                : ((g == Settings.GUARD_HOLD) ? Settings.GUARD_OFF : Settings.GUARD_TWICE);
            Settings.setGuard(g);
            item.setSubLabel(Settings.guardName(g));
            WatchUi.requestUpdate();
        } else if (id == :startPage) {
            var p = (Settings.startPage() + 1) % Settings.PAGE_COUNT;
            Settings.setStartPage(p);
            item.setSubLabel(Settings.pageName(p));
            WatchUi.requestUpdate();
        } else if (id == :goRide) {
            view.setPage(Settings.PAGE_RIDE);
            WatchUi.popView(WatchUi.SLIDE_DOWN);
        } else if (id == :goActions) {
            view.setPage(Settings.PAGE_ACTIONS);
            WatchUi.popView(WatchUi.SLIDE_DOWN);
        } else if (id == :goWorkout) {
            view.setPage(Settings.PAGE_WORKOUT);
            WatchUi.popView(WatchUi.SLIDE_DOWN);
        } else if (id == :pick) {
            WatchUi.popView(WatchUi.SLIDE_IMMEDIATE);
            $.openDevicePicker();
        } else if (id == :reconnect) {
            $.gBle.reconnect();
            WatchUi.popView(WatchUi.SLIDE_DOWN);
        } else if (id == :exit) {
            System.exit();
        }
    }
}

// --- Device pick list ----------------------------------------------------------
// Fallback for the fenix scan bug (empty advertising data): all devices seen
// during the scan, strongest signal first.

function openDevicePicker() {
    var list = $.gBle.sortedCandidates();
    var menu = new WatchUi.Menu2({ :title => Rez.Strings.PickTitle });
    menu.addItem(new WatchUi.MenuItem(Rez.Strings.PickRescan, null, -1, null));
    if (list.size() == 0) {
        menu.addItem(new WatchUi.MenuItem(Rez.Strings.PickEmpty, null, -2, null));
    }
    var unknown = WatchUi.loadResource(Rez.Strings.PickUnknown);
    var rssiFmt = WatchUi.loadResource(Rez.Strings.PickRssi);
    for (var i = 0; i < list.size(); i++) {
        var name = (list[i][1] != null) ? list[i][1] : unknown;
        menu.addItem(new WatchUi.MenuItem(name, Lang.format(rssiFmt, [list[i][2]]), i, null));
    }
    WatchUi.pushView(menu, new DevicePickerDelegate(list), WatchUi.SLIDE_UP);
}

class DevicePickerDelegate extends WatchUi.Menu2InputDelegate {

    hidden var list;

    function initialize(l) {
        Menu2InputDelegate.initialize();
        list = l;
    }

    function onSelect(item) {
        var id = item.getId();
        if (id == -1) {
            $.gBle.reconnect();
            WatchUi.popView(WatchUi.SLIDE_DOWN);
        } else if (id instanceof Number && id >= 0 && id < list.size()) {
            $.gBle.connectTo(list[id][0], list[id][1]);
            WatchUi.popView(WatchUi.SLIDE_DOWN);
        }
    }
}

// --- Exit confirmation -----------------------------------------------------------

class ExitConfirmDelegate extends WatchUi.ConfirmationDelegate {

    function initialize() {
        ConfirmationDelegate.initialize();
    }

    function onResponse(response) {
        if (response == WatchUi.CONFIRM_YES) {
            System.exit();
        }
        return true;
    }
}
