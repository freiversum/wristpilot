// The one view of the app. Draws, depending on the connection and the current page:
// connect screen, "Ride" (four quadrants, MIP layout), the race or the party page,
// "Actions" (8 tiles), "Workout", plus the feedback overlay on top.
// All coordinates are designed for 280 x 280 and scaled with the screen width.

import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

class MainView extends WatchUi.View {

    var page;
    var selected = 0;        // selected tile on the Actions page

    // Layout (set in onLayout)
    var w = 280;
    var h = 280;
    var cx = 140;
    var cy = 140;
    var s = 1.0;             // scale relative to 280 px
    var divY = 165;          // horizontal divider of the Ride page

    hidden var lblLeft;
    hidden var lblRight;
    hidden var lblRideOn;
    hidden var lblPower;
    hidden var lblLeftA;      // AMOLED: mixed-case action names
    hidden var lblRightA;
    hidden var lblRideOnA;
    hidden var lblPowerA;

    function initialize() {
        View.initialize();
        page = Settings.startPage();
        lblLeft = WatchUi.loadResource(Rez.Strings.LblLeft);
        lblRight = WatchUi.loadResource(Rez.Strings.LblRight);
        lblRideOn = WatchUi.loadResource(Rez.Strings.LblRideOn);
        lblPower = WatchUi.loadResource(Rez.Strings.LblPower);
        if (Style.AMOLED || Style.EDGE) {      // Edge: race page uses the mixed-case names
            lblLeftA = WatchUi.loadResource(Rez.Strings.LblLeftA);
            lblRightA = WatchUi.loadResource(Rez.Strings.LblRightA);
            lblRideOnA = WatchUi.loadResource(Rez.Strings.LblRideOnA);
            lblPowerA = WatchUi.loadResource(Rez.Strings.LblPowerA);
        }
    }

    function onLayout(dc) {
        w = dc.getWidth();
        h = dc.getHeight();
        cx = w / 2;
        cy = h / 2;
        s = w / 280.0;
        divY = cy + (25 * s).toNumber();
    }

    function onHide() {
        if ($.gInput != null) {
            $.gInput.resetKeys();
        }
    }

    function setPage(p) {
        page = (p + Settings.PAGE_COUNT) % Settings.PAGE_COUNT;
        WatchUi.requestUpdate();
    }

    function onUpdate(dc) {
        var now = System.getTimer();
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        if (!$.gBle.isReady()) {
            drawConnect(dc, now);
        } else if (page == Settings.PAGE_ACTIONS) {
            drawActions(dc);
        } else if (page == Settings.PAGE_WORKOUT) {
            drawWorkout(dc);
        } else if (Settings.partyOn()) {
            drawParty(dc, now);
        } else if (Settings.raceOn()) {
            drawRace(dc, now);
        } else {
            drawRide(dc, now);
        }
        if ($.gRemote.fbPhase != Feedback.NONE) {
            drawOverlay(dc);
        }
    }

    // --- Ride --------------------------------------------------------------

    function drawRide(dc, now) {
        if (Style.AMOLED) {
            drawRideAmoled(dc, now);
            return;
        }
        if (Style.EDGE) {
            drawRideEdge(dc, now);
            return;
        }
        // thin white cross
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(3);
        dc.drawLine(cx, 0, cx, h);
        dc.drawLine(0, divY, w, divY);
        dc.setPenWidth(1);

        var ir = 24 * s;
        var dx = 70 * s;
        var r = $.gRemote;
        // With a Companion link: directions not offered at the junction ahead are greyed out.
        var leftCol = r.turnPossible(Protocol.GAME_LEFT) ? Actions.COLOR_CYAN : Actions.COLOR_GREY;
        var rightCol = r.turnPossible(Protocol.GAME_RIGHT) ? Actions.COLOR_CYAN : Actions.COLOR_GREY;
        // top: icon above label
        Icons.draw(dc, :left, cx - dx, cy - 50 * s, ir, leftCol);
        Icons.draw(dc, :right, cx + dx, cy - 50 * s, ir, rightCol);
        drawLabel(dc, cx - dx, cy - 4 * s, Graphics.FONT_SMALL, lblLeft);
        drawLabel(dc, cx + dx, cy - 4 * s, Graphics.FONT_SMALL, lblRight);
        // bottom: label next to the divider, icon below (the round edge is closer there)
        var bx = 62 * s;
        var powerText = lblPower;
        var powerCol = Actions.COLOR_ORANGE;
        if (r.linked()) {
            powerText = r.powerupLabel();
            if ((r.game & Protocol.GAME_POWERUP) == 0) {
                powerCol = Actions.COLOR_GREY;
            }
        }
        drawLabel(dc, cx - bx, divY + 26 * s, Graphics.FONT_SMALL, lblRideOn);
        drawLabel(dc, cx + bx, divY + 26 * s, r.linked() ? Graphics.FONT_XTINY : Graphics.FONT_SMALL, powerText);
        Icons.draw(dc, :thumb, cx - 55 * s, divY + 72 * s, 20 * s, Actions.COLOR_GREEN);
        Icons.draw(dc, :bolt, cx + 55 * s, divY + 72 * s, 22 * s, powerCol);
        if (r.linked() && r.rideOns > 0) {
            dc.setColor(Actions.COLOR_GREEN, Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx - 22 * s, divY + 72 * s, Graphics.FONT_XTINY, r.rideOns.toString(),
                Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
        }
        // Junction ahead: a small badge on the cross with an up arrow if straight on is offered.
        if (r.linked() && (r.game & Protocol.GAME_JUNCTION) != 0) {
            var br = (17 * s).toNumber();
            dc.setColor(Actions.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(cx, divY, br + 3);
            dc.setColor(Actions.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(2);
            dc.drawCircle(cx, divY, br);
            dc.setPenWidth(1);
            var upCol = r.turnPossible(Protocol.GAME_STRAIGHT) ? Actions.COLOR_CYAN : Actions.COLOR_GREY;
            Icons.draw(dc, :up, cx, divY, 9 * s, upCol);
        }

        drawStatus(dc, now);
    }

    // --- Race page ------------------------------------------------------------
    // No turns, no U-turn. Power-up big in the middle; in the "power-up + Ride On" variant a
    // Ride On field sits next to DOWN (watch) or at the bottom (Edge).

    hidden function raceRideOn() {
        return Settings.race() == Settings.RACE_POWER_RIDEON;
    }

    // [x, y, r] of the power-up disc and the Ride On disc (round screens)
    hidden function raceDiscs() {
        if (raceRideOn()) {
            return [[cx + 18 * s, cy + 28 * s, 54 * s], [cx - 74 * s, cy + 64 * s, 24 * s]];
        }
        return [[cx + 6 * s, cy + 30 * s, 58 * s], null];
    }

    // [x, y, r] of the lane-change discs: left next to UP (9 o'clock), right next to START (2 o'clock)
    hidden function laneDiscs() {
        return [[cx - 84 * s, cy - 26 * s, 24 * s], [cx + 74 * s, cy - 66 * s, 24 * s]];
    }

    // [[action, x, y, w, h], ...] on the Edge
    hidden function raceTiles() {
        var top = (h * 0.11).toNumber();
        var gap = (w * 0.025).toNumber();
        var tw = w - 2 * gap;
        var w2 = (w - 3 * gap) / 2;
        var laneH = ((h - top) * 0.20).toNumber();
        var y1 = top + gap + laneH + gap;
        var lanes = [[Actions.LANE_L, gap, top + gap, w2, laneH], [Actions.LANE_R, 2 * gap + w2, top + gap, w2, laneH]];
        if (!raceRideOn()) {
            return lanes.addAll([[Actions.POWERUP, gap, y1, tw, h - y1 - gap]]);
        }
        var rideH = ((h - top) * 0.18).toNumber();
        var powH = h - y1 - rideH - 2 * gap;
        return lanes.addAll([[Actions.POWERUP, gap, y1, tw, powH],
                             [Actions.RIDE_ON, gap, y1 + powH + gap, tw, rideH]]);
    }

    // Which race action a touch at (x, y) means (null = none).
    function raceActionAt(x, y) {
        if (Style.EDGE) {
            var tiles = raceTiles();
            for (var i = 0; i < tiles.size(); i++) {
                var t = tiles[i];
                if (x >= t[1] && x < t[1] + t[3] && y >= t[2] && y < t[2] + t[4]) {
                    return t[0];
                }
            }
            return null;
        }
        var lanes = laneDiscs();
        for (var i = 0; i < 2; i++) {
            var lx = x - lanes[i][0];
            var ly = y - lanes[i][1];
            var lr = lanes[i][2] + 16 * s;
            if (lx * lx + ly * ly <= lr * lr) {
                return i == 0 ? Actions.LANE_L : Actions.LANE_R;
            }
        }
        var d = raceDiscs()[1];
        if (d != null) {
            var dx = x - d[0];
            var dy = y - d[1];
            var rr = d[2] + 18 * s;
            if (dx * dx + dy * dy <= rr * rr) {
                return Actions.RIDE_ON;
            }
        }
        return Actions.POWERUP;
    }

    function drawRace(dc, now) {
        var r = $.gRemote;
        var powerText = Style.AMOLED || Style.EDGE ? lblPowerA : lblPower;
        var powerOn = true;
        if (r.linked()) {
            powerText = r.powerupLabel();
            powerOn = (r.game & Protocol.GAME_POWERUP) != 0;
        }
        var rideText = (Style.AMOLED || Style.EDGE) ? lblRideOnA : lblRideOn;
        if (r.linked() && r.rideOns > 0) {
            rideText = rideText + " · " + r.rideOns.toString();
        }
        if (Style.EDGE) {
            var tiles = raceTiles();
            var rad = (w * 0.04).toNumber();
            for (var i = 0; i < tiles.size(); i++) {
                var t = tiles[i];
                if (t[0] == Actions.LANE_L || t[0] == Actions.LANE_R) {
                    dc.setColor(A_CYAN, Graphics.COLOR_TRANSPARENT);
                    dc.setPenWidth(2);
                    dc.drawRoundedRectangle(t[1], t[2], t[3], t[4], rad);
                    dc.setPenWidth(1);
                    var linfo = Actions.info(t[0]);
                    Icons.draw(dc, linfo[4], t[1] + t[3] / 2, t[2] + t[4] * 0.40, t[4] * 0.24, A_CYAN);
                    dc.setColor(A_CYAN, Graphics.COLOR_TRANSPARENT);
                    dc.drawText(t[1] + t[3] / 2, t[2] + t[4] * 0.82, Graphics.FONT_XTINY, WatchUi.loadResource(linfo[2]),
                        Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
                    continue;
                }
                var pow = t[0] == Actions.POWERUP;
                var col = pow ? (powerOn ? A_ORANGE : A_GREY) : A_GREEN;
                dc.setColor(pow ? (powerOn ? 0x1A0D05 : 0x111111) : 0x06180C, Graphics.COLOR_TRANSPARENT);
                dc.fillRoundedRectangle(t[1], t[2], t[3], t[4], rad);
                dc.setColor(col, Graphics.COLOR_TRANSPARENT);
                dc.setPenWidth(3);
                dc.drawRoundedRectangle(t[1], t[2], t[3], t[4], rad);
                dc.setPenWidth(1);
                if (pow) {
                    Icons.draw(dc, :bolt, t[1] + t[3] / 2, t[2] + t[4] * 0.42, t[3] * 0.18, col);
                    dc.setColor(col, Graphics.COLOR_TRANSPARENT);
                    dc.drawText(t[1] + t[3] / 2, t[2] + t[4] * 0.78, Graphics.FONT_MEDIUM, powerText,
                        Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
                } else {
                    Icons.draw(dc, :thumb, t[1] + t[3] * 0.25, t[2] + t[4] / 2, t[4] * 0.22, col);
                    dc.setColor(col, Graphics.COLOR_TRANSPARENT);
                    dc.drawText(t[1] + t[3] * 0.40, t[2] + t[4] / 2, Graphics.FONT_SMALL, rideText,
                        Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
                }
            }
        } else {
            var lanes = laneDiscs();
            for (var i = 0; i < 2; i++) {
                var l = lanes[i];
                var lsym = i == 0 ? :laneLeft : :laneRight;
                if (Style.AMOLED) {
                    dc.setColor(TINT_CYAN, Graphics.COLOR_TRANSPARENT);
                    dc.fillCircle(l[0], l[1], l[2]);
                    Icons.draw(dc, lsym, l[0], l[1], l[2] * 0.6, A_CYAN);
                } else {
                    dc.setColor(Actions.COLOR_CYAN, Graphics.COLOR_TRANSPARENT);
                    dc.fillCircle(l[0], l[1], l[2]);
                    Icons.draw(dc, lsym, l[0], l[1], l[2] * 0.6, Actions.COLOR_BLACK);
                }
            }
            var discs = raceDiscs();
            var p = discs[0];
            var pr = p[2];
            if (Style.AMOLED) {
                dc.setColor(powerOn ? TINT_ORANGE : TINT_GREY, Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(p[0], p[1], pr);
                dc.setColor(powerOn ? A_ORANGE : A_GREY, Graphics.COLOR_TRANSPARENT);
                dc.setPenWidth((5 * s).toNumber());
                dc.drawCircle(p[0], p[1], pr);
                dc.setPenWidth(1);
                Icons.draw(dc, :bolt, p[0], p[1] - pr * 0.18, pr * 0.42, powerOn ? A_ORANGE : A_GREY);
                dc.setColor(powerOn ? A_ORANGE : A_GREY, Graphics.COLOR_TRANSPARENT);
            } else {
                // MIP: solid orange disc, black content, readable in sunlight
                dc.setColor(powerOn ? Actions.COLOR_ORANGE : Actions.COLOR_GREY, Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(p[0], p[1], pr);
                Icons.draw(dc, :bolt, p[0], p[1] - pr * 0.18, pr * 0.42, Actions.COLOR_BLACK);
                dc.setColor(Actions.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
            }
            dc.drawText(p[0], p[1] + pr * 0.52, r.linked() ? Graphics.FONT_XTINY : Graphics.FONT_SMALL, powerText,
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
            var d = discs[1];
            if (d != null) {
                dc.setColor(Style.AMOLED ? TINT_GREEN : Actions.COLOR_GREEN, Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(d[0], d[1], d[2]);
                Icons.draw(dc, :thumb, d[0], d[1], d[2] * 0.5, Style.AMOLED ? A_GREEN : Actions.COLOR_BLACK);
                if (r.linked() && r.rideOns > 0) {
                    dc.setColor(Style.AMOLED ? A_GREEN : Actions.COLOR_GREEN, Graphics.COLOR_TRANSPARENT);
                    dc.drawText(d[0], d[1] - d[2] - 10 * s, Graphics.FONT_XTINY, r.rideOns.toString(),
                        Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
                }
            }
        }
        // "RACE" under the status line
        dc.setColor(Actions.COLOR_RED, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, Style.EDGE ? (h * 0.11).toNumber() - 2 : (48 * s).toNumber(), Graphics.FONT_XTINY,
            WatchUi.loadResource(Rez.Strings.LblRace), Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        drawStatus(dc, now);
    }

    // --- Party page (group rides) ------------------------------------------------
    // Like the ride page, the action sits where its button is: UP wave, START Ride On, DOWN elbow
    // flick, BACK power-up. Edge: tiles (wave, Ride On / elbow, power-up / Nice, Hammer, bell).

    const PARTY_FIELDS = [Actions.WAVE, Actions.RIDE_ON, Actions.ELBOW, Actions.POWERUP];

    hidden function partyTiles() {
        var top = (h * 0.11).toNumber();
        var gap = (w * 0.025).toNumber();
        var w2 = (w - 3 * gap) / 2;
        var w3 = (w - 4 * gap) / 3;
        var rowH = (h - top - 4 * gap) / 3;
        var y1 = top + gap;
        var y2 = y1 + rowH + gap;
        var y3 = y2 + rowH + gap;
        return [
            [Actions.WAVE, gap, y1, w2, rowH], [Actions.RIDE_ON, 2 * gap + w2, y1, w2, rowH],
            [Actions.ELBOW, gap, y2, w2, rowH], [Actions.POWERUP, 2 * gap + w2, y2, w2, rowH],
            [Actions.NICE, gap, y3, w3, rowH], [Actions.HAMMER, 2 * gap + w3, y3, w3, rowH],
            [Actions.BELL, 3 * gap + 2 * w3, y3, w3, rowH]
        ];
    }

    // Which party action a touch at (x, y) means (null = none).
    function partyActionAt(x, y) {
        if (Style.EDGE) {
            var tiles = partyTiles();
            for (var i = 0; i < tiles.size(); i++) {
                var t = tiles[i];
                if (x >= t[1] && x < t[1] + t[3] && y >= t[2] && y < t[2] + t[4]) {
                    return t[0];
                }
            }
            return null;
        }
        if (y < divY) {
            return (x < cx) ? Actions.WAVE : Actions.RIDE_ON;
        }
        return (x < cx) ? Actions.ELBOW : Actions.POWERUP;
    }

    // [colour, label] of a party action; the power-up shows its type with a Companion link.
    hidden function partyLook(a) {
        var r = $.gRemote;
        var info = Actions.info(a);
        var col = info[3];
        var label = WatchUi.loadResource(info[2]);
        if (a == Actions.POWERUP && r.linked()) {
            label = r.powerupLabel();
            if ((r.game & Protocol.GAME_POWERUP) == 0) {
                col = Actions.COLOR_GREY;
            }
        } else if (a == Actions.RIDE_ON && r.linked() && r.rideOns > 0) {
            label = label + " · " + r.rideOns.toString();
        }
        if (Style.AMOLED) {
            // softer AMOLED colours, like the ride page
            if (col == Actions.COLOR_CYAN) {
                col = A_CYAN;
            } else if (col == Actions.COLOR_GREEN) {
                col = A_GREEN;
            } else if (col == Actions.COLOR_ORANGE) {
                col = A_ORANGE;
            } else if (col == Actions.COLOR_GREY) {
                col = A_GREY;
            }
        }
        return [col, label];
    }

    function drawParty(dc, now) {
        if (Style.EDGE) {
            var tiles = partyTiles();
            var rad = (w * 0.04).toNumber();
            for (var i = 0; i < tiles.size(); i++) {
                var t = tiles[i];
                var look = partyLook(t[0]);
                var small = i >= 4;
                dc.setColor(look[0], Graphics.COLOR_TRANSPARENT);
                dc.setPenWidth(2);
                dc.drawRoundedRectangle(t[1], t[2], t[3], t[4], rad);
                dc.setPenWidth(1);
                var iconR = (t[4] < t[3] ? t[4] : t[3]) * (small ? 0.20 : 0.24);
                Icons.draw(dc, Actions.info(t[0])[4], t[1] + t[3] / 2, t[2] + t[4] * 0.40, iconR, look[0]);
                dc.setColor(look[0], Graphics.COLOR_TRANSPARENT);
                dc.drawText(t[1] + t[3] / 2, t[2] + t[4] * 0.80, small ? Graphics.FONT_XTINY : Graphics.FONT_TINY,
                    look[1], Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
            }
        } else if (Style.AMOLED) {
            // [x, y, disc radius, icon radius, label y] per field, at its button
            var spots = [[cx - 82 * s, cy - 20 * s, 32 * s, 17 * s, cy + 24 * s],
                         [cx + 72 * s, cy - 62 * s, 32 * s, 17 * s, cy - 16 * s],
                         [cx - 50 * s, cy + 62 * s, 26 * s, 13 * s, cy + 98 * s],
                         [cx + 68 * s, cy + 58 * s, 30 * s, 16 * s, cy + 98 * s]];
            for (var i = 0; i < PARTY_FIELDS.size(); i++) {
                var a = PARTY_FIELDS[i];
                var p = spots[i];
                var look = partyLook(a);
                dc.setColor(tintOf(look[0]), Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(p[0], p[1], p[2]);
                Icons.draw(dc, Actions.info(a)[4], p[0], p[1], p[3], look[0]);
                dc.setColor(look[0], Graphics.COLOR_TRANSPARENT);
                dc.drawText(p[0], p[4], Graphics.FONT_XTINY, look[1], Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
            }
        } else {
            // MIP: four fields as on the ride page, bold labels
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(3);
            dc.drawLine(cx, (58 * s).toNumber(), cx, h);
            dc.drawLine(0, divY, w, divY);
            dc.setPenWidth(1);
            var dx = 66 * s;
            var pos = [[cx - dx, cy - 46 * s, cy - 4 * s], [cx + dx, cy - 46 * s, cy - 4 * s],
                       [cx - 58 * s, divY + 62 * s, divY + 26 * s], [cx + 58 * s, divY + 62 * s, divY + 26 * s]];
            for (var i = 0; i < PARTY_FIELDS.size(); i++) {
                var a = PARTY_FIELDS[i];
                var look = partyLook(a);
                Icons.draw(dc, Actions.info(a)[4], pos[i][0], pos[i][1], 22 * s, look[0]);
                var text = look[1];
                var font = Graphics.FONT_XTINY;
                if (!(a == Actions.POWERUP && $.gRemote.linked())) {
                    text = text.toUpper();
                    font = text.length() > 8 ? Graphics.FONT_XTINY : Graphics.FONT_TINY;
                }
                drawLabel(dc, pos[i][0], pos[i][2], font, text);
            }
        }
        dc.setColor(Actions.COLOR_VIOLET, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, Style.EDGE ? (h * 0.11).toNumber() - 2 : (48 * s).toNumber(), Graphics.FONT_XTINY,
            WatchUi.loadResource(Rez.Strings.LblParty), Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        drawStatus(dc, now);
    }

    // Dark tint behind an AMOLED colour.
    hidden function tintOf(col) {
        if (col == A_CYAN) {
            return TINT_CYAN;
        } else if (col == A_GREEN) {
            return TINT_GREEN;
        } else if (col == A_ORANGE) {
            return TINT_ORANGE;
        }
        return TINT_GREY;
    }

    // --- Ride, AMOLED style -------------------------------------------------
    // Each action sits next to its button: UP (9 o'clock) left, START (2 o'clock) right,
    // DOWN (8 o'clock) Ride On, BACK (4 o'clock) power-up. Tinted discs, coloured labels.

    const TINT_CYAN   = 0x0B3A44;
    const TINT_GREEN  = 0x0C3A22;
    const TINT_ORANGE = 0x4A2410;
    const TINT_GREY   = 0x2A2A2A;
    const A_CYAN      = 0x35C8E8;
    const A_GREEN     = 0x2FBF71;
    const A_ORANGE    = 0xFF7A2F;
    const A_GREY      = 0x6E6E6E;

    // b = [x, y, r, tint, sym, iconR, color, label, labelColor, labelY, font]
    // (one array: CIQ 3.x devices allow at most 9 arguments per method)
    hidden function bubble(dc, b) {
        var x = b[0];
        var y = b[1];
        var r = b[2];
        var tint = b[3];
        var sym = b[4];
        var iconR = b[5];
        var color = b[6];
        var label = b[7];
        var labelColor = b[8];
        var labelY = b[9];
        var font = b[10];
        dc.setColor(tint, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x, y, r);
        Icons.draw(dc, sym, x, y, iconR, color);
        dc.setColor(labelColor, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, labelY, font, label, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    function drawRideAmoled(dc, now) {
        var r = $.gRemote;
        var font = Graphics.FONT_XTINY;
        var br = (32 * s).toNumber();
        var ir = 17 * s;
        var leftOk = r.turnPossible(Protocol.GAME_LEFT);
        var rightOk = r.turnPossible(Protocol.GAME_RIGHT);

        // left (UP, 9 o'clock)
        bubble(dc, [cx - 82 * s, cy - 20 * s, br, leftOk ? TINT_CYAN : TINT_GREY, :left, ir,
            leftOk ? A_CYAN : A_GREY, lblLeftA, leftOk ? A_CYAN : A_GREY, cy + 24 * s, font]);
        // right (START, 2 o'clock)
        bubble(dc, [cx + 72 * s, cy - 62 * s, br, rightOk ? TINT_CYAN : TINT_GREY, :right, ir,
            rightOk ? A_CYAN : A_GREY, lblRightA, rightOk ? A_CYAN : A_GREY, cy - 16 * s, font]);
        // Ride On (DOWN, 8 o'clock)
        bubble(dc, [cx - 50 * s, cy + 62 * s, (26 * s).toNumber(), TINT_GREEN, :thumb, 13 * s,
            A_GREEN, lblRideOnA, A_GREEN, cy + 98 * s, font]);
        if (r.linked() && r.rideOns > 0) {
            dc.setColor(A_GREEN, Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx - 18 * s, cy + 48 * s, Graphics.FONT_XTINY, r.rideOns.toString(),
                Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
        }
        // power-up (BACK, 4 o'clock)
        var powerText = lblPowerA;
        var powerOn = true;
        if (r.linked()) {
            powerText = r.powerupLabel();
            powerOn = (r.game & Protocol.GAME_POWERUP) != 0;
        }
        bubble(dc, [cx + 68 * s, cy + 58 * s, (30 * s).toNumber(), powerOn ? TINT_ORANGE : TINT_GREY, :bolt,
            16 * s, powerOn ? A_ORANGE : A_GREY, powerText, powerOn ? A_ORANGE : A_GREY, cy + 98 * s,
            r.linked() ? Graphics.FONT_XTINY : font]);

        // centre: straight on (DOWN held); bright ring when a junction is ahead
        var junction = r.linked() && (r.game & Protocol.GAME_JUNCTION) != 0;
        var straightOk = r.turnPossible(Protocol.GAME_STRAIGHT);
        var cr = (22 * s).toNumber();
        dc.setColor(junction ? Actions.COLOR_WHITE : 0x3A3A3A, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth((3 * s).toNumber());
        dc.drawCircle(cx + 2 * s, cy + 4 * s, cr);
        dc.setPenWidth(1);
        Icons.draw(dc, :up, cx + 2 * s, cy + 4 * s, 11 * s,
            junction ? (straightOk ? A_CYAN : A_GREY) : 0x9A9A9A);

        drawStatus(dc, now);
    }

    // --- Ride, Edge style ---------------------------------------------------
    // Portrait screen, three rows of big tiles:
    //   [Left] [Straight] [Right]      LAP (bottom left) = Left, START (bottom right) = Right
    //   [Ride On]      [Power-up]
    //   [U-turn]       [More …]
    // Tiles: [action, x, y, w, h], recomputed in edgeTiles() from the screen size.

    hidden function edgeTiles() {
        var top = (h * 0.11).toNumber();          // status line
        var gap = (w * 0.025).toNumber();
        var m = gap;
        var rowH1 = ((h - top) * 0.36).toNumber();
        var rowH2 = ((h - top) * 0.34).toNumber();
        var rowH3 = h - top - rowH1 - rowH2 - 4 * gap;
        var w3 = (w - 2 * m - 2 * gap) / 3;
        var w2 = (w - 2 * m - gap) / 2;
        var y1 = top + gap;
        var y2 = y1 + rowH1 + gap;
        var y3 = y2 + rowH2 + gap;
        return [
            [Actions.LEFT, m, y1, w3, rowH1],
            [Actions.STRAIGHT, m + w3 + gap, y1, w3, rowH1],
            [Actions.RIGHT, m + 2 * (w3 + gap), y1, w3, rowH1],
            [Actions.RIDE_ON, m, y2, w2, rowH2],
            [Actions.POWERUP, m + w2 + gap, y2, w2, rowH2],
            [Actions.U_TURN, m, y3, w2, rowH3],
            [Actions.MORE, m + w2 + gap, y3, w2, rowH3]
        ];
    }

    function edgeTileAt(x, y) {
        var tiles = edgeTiles();
        for (var i = 0; i < tiles.size(); i++) {
            var t = tiles[i];
            if (x >= t[1] && x < t[1] + t[3] && y >= t[2] && y < t[2] + t[4]) {
                return t[0];
            }
        }
        return Actions.MORE;
    }

    function drawRideEdge(dc, now) {
        var r = $.gRemote;
        var tiles = edgeTiles();
        var junction = r.linked() && (r.game & Protocol.GAME_JUNCTION) != 0;
        for (var i = 0; i < tiles.size(); i++) {
            var t = tiles[i];
            var a = t[0];
            var col = Actions.COLOR_WHITE;
            var sym = :more;
            var label = null;
            var font = Graphics.FONT_SMALL;
            var on = true;
            if (a == Actions.MORE) {
                col = Actions.COLOR_GREY;
                label = WatchUi.loadResource(Rez.Strings.LblMore);
            } else {
                var info = Actions.info(a);
                col = info[3];
                sym = info[4];
                label = WatchUi.loadResource(info[2]);
                if (a == Actions.LEFT) {
                    on = r.turnPossible(Protocol.GAME_LEFT);
                } else if (a == Actions.RIGHT) {
                    on = r.turnPossible(Protocol.GAME_RIGHT);
                } else if (a == Actions.STRAIGHT) {
                    on = r.turnPossible(Protocol.GAME_STRAIGHT);
                } else if (a == Actions.POWERUP && r.linked()) {
                    label = r.powerupLabel();
                    on = (r.game & Protocol.GAME_POWERUP) != 0;
                    font = Graphics.FONT_TINY;
                } else if (a == Actions.RIDE_ON && r.linked() && r.rideOns > 0) {
                    label = label + " · " + r.rideOns.toString();
                }
            }
            if (!on) {
                col = Actions.COLOR_GREY;
            }
            var x = t[1];
            var y = t[2];
            var tw = t[3];
            var th = t[4];
            var rad = (w * 0.04).toNumber();
            // turn tiles get a white frame while a junction is ahead
            var framed = junction && on && (a == Actions.LEFT || a == Actions.RIGHT || a == Actions.STRAIGHT);
            dc.setColor(framed ? Actions.COLOR_WHITE : 0x333333, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(framed ? 3 : 2);
            dc.drawRoundedRectangle(x, y, tw, th, rad);
            dc.setPenWidth(1);
            var iconR = (th < tw ? th : tw) * 0.22;
            var small = a == Actions.U_TURN || a == Actions.MORE;
            if (small) {
                // one line: icon left, label right
                Icons.draw(dc, sym, x + tw * 0.22, y + th / 2, iconR * 1.1, col);
                dc.setColor(col, Graphics.COLOR_TRANSPARENT);
                dc.drawText(x + tw * 0.40, y + th / 2, Graphics.FONT_TINY, label,
                    Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
            } else {
                Icons.draw(dc, sym, x + tw / 2, y + th * 0.40, iconR, col);
                dc.setColor(col, Graphics.COLOR_TRANSPARENT);
                dc.drawText(x + tw / 2, y + th * 0.80, w3font(tw, font), label,
                    Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
            }
        }
        drawStatus(dc, now);
    }

    // Narrow tiles (three per row) get the smaller font.
    hidden function w3font(tileW, font) {
        return tileW < w / 2 - 10 ? Graphics.FONT_TINY : font;
    }

    function drawLabel(dc, x, y, font, text) {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, y, font, text, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    // Small status pill at the top: coloured dot + "Zwift" / "nicht vorne" / ...
    function drawStatus(dc, now) {
        var st = $.gRemote.statusLine(now);
        var text = WatchUi.loadResource(st[1]);
        var font = Graphics.FONT_XTINY;
        var tw = dc.getTextWidthInPixels(text, font);
        var fh = dc.getFontHeight(font);
        var dot = (5 * s).toNumber();
        var gap = (6 * s).toNumber();
        var total = 2 * dot + gap + tw;
        var y = (24 * s).toNumber();
        var x0 = cx - total / 2;
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.fillRectangle(x0 - gap, y - fh / 2, total + 2 * gap, fh);
        dc.setColor(st[0], Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x0 + dot, y, dot);
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x0 + 2 * dot + gap, y, font, text, Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    // Which Ride action a tap at (x, y) means.
    function rideActionAt(x, y) {
        if (Style.EDGE) {
            return edgeTileAt(x, y);
        }
        if (y < divY) {
            return (x < cx) ? Actions.LEFT : Actions.RIGHT;
        }
        return (x < cx) ? Actions.RIDE_ON : Actions.POWERUP;
    }

    // --- Actions -----------------------------------------------------------

    // [x, y, size] of tile i (rows of four; the last, shorter row is centred)
    function tileRect(i) {
        var t = (46 * s).toNumber();
        var g = (6 * s).toNumber();
        var y0 = (60 * s).toNumber();
        var n = Actions.ACTION_TILES.size();
        var col = i % 4;
        var row = i / 4;
        var inRow = (row == (n - 1) / 4) ? n - row * 4 : 4;
        var x0 = cx - (inRow * t + (inRow - 1) * g) / 2;
        return [x0 + col * (t + g), y0 + row * (t + g), t];
    }

    function drawActions(dc) {
        drawTitle(dc, Rez.Strings.PageActions);
        var tiles = Actions.ACTION_TILES;
        for (var i = 0; i < tiles.size(); i++) {
            var info = Actions.info(tiles[i]);
            var r = tileRect(i);
            var t = r[2];
            var rad = (10 * s).toNumber();
            if (i == selected) {
                dc.setColor(info[3], Graphics.COLOR_TRANSPARENT);
                dc.fillRoundedRectangle(r[0], r[1], t, t, rad);
                Icons.draw(dc, info[4], r[0] + t / 2, r[1] + t / 2, t * 0.3, Graphics.COLOR_BLACK);
            } else {
                dc.setColor(0x555555, Graphics.COLOR_TRANSPARENT);
                dc.setPenWidth(2);
                dc.drawRoundedRectangle(r[0], r[1], t, t, rad);
                dc.setPenWidth(1);
                Icons.draw(dc, info[4], r[0] + t / 2, r[1] + t / 2, t * 0.3, info[3]);
            }
        }
        var sel = Actions.info(tiles[selected]);
        drawLabel(dc, cx, (238 * s).toNumber(), Graphics.FONT_TINY, WatchUi.loadResource(sel[2]));
        drawDots(dc);
    }

    function tileAt(x, y) {
        for (var i = 0; i < Actions.ACTION_TILES.size(); i++) {
            var r = tileRect(i);
            if (x >= r[0] && x < r[0] + r[2] && y >= r[1] && y < r[1] + r[2]) {
                return i;
            }
        }
        return -1;
    }

    function moveSelection(delta) {
        var n = Actions.ACTION_TILES.size();
        selected = (selected + delta + n) % n;
        WatchUi.requestUpdate();
    }

    // --- Workout -----------------------------------------------------------

    function drawWorkout(dc) {
        drawTitle(dc, Rez.Strings.PageWorkout);
        var bx = 62 * s;
        var by = cy - 18 * s;
        var br = 40 * s;
        dc.setPenWidth(3);
        dc.setColor(Actions.COLOR_CYAN, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(cx - bx, by, br);
        dc.setColor(Actions.COLOR_ORANGE, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(cx + bx, by, br);
        dc.setPenWidth(1);
        Icons.draw(dc, :minus, cx - bx, by, 22 * s, Actions.COLOR_CYAN);
        Icons.draw(dc, :plus, cx + bx, by, 22 * s, Actions.COLOR_ORANGE);
        drawLabel(dc, cx - bx, by + br + 18 * s, Graphics.FONT_XTINY, WatchUi.loadResource(Rez.Strings.LblEasier));
        drawLabel(dc, cx + bx, by + br + 18 * s, Graphics.FONT_XTINY, WatchUi.loadResource(Rez.Strings.LblHarder));
        // skip interval (long press / hold only)
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(1);
        dc.drawLine(cx - 90 * s, skipTop(), cx + 90 * s, skipTop());
        // AMOLED fonts are relatively larger: keep the hint inside the round edge
        var off = Style.AMOLED ? 0.8 : 1.0;
        Icons.draw(dc, :skip, cx, skipTop() + 26 * s * off, 15 * s, Actions.COLOR_WHITE);
        // Edge with touch (most have no DOWN key): "hold to skip"
        var touchEdge = Style.EDGE && System.getDeviceSettings().isTouchScreen;
        drawLabel(dc, cx, skipTop() + 56 * s * off, Graphics.FONT_XTINY,
            WatchUi.loadResource(touchEdge ? Rez.Strings.WkHoldSkipTouch : Rez.Strings.WkHoldSkip));
    }

    function skipTop() {
        return cy + 62 * s;
    }

    // Which Workout action a touch at (x, y) means.
    function workoutActionAt(x, y) {
        if (y >= skipTop()) {
            return Actions.SKIP;
        }
        return (x < cx) ? Actions.EASIER : Actions.HARDER;
    }

    // --- Shared pieces -----------------------------------------------------

    function drawTitle(dc, res) {
        var text = WatchUi.loadResource(res).toUpper();
        drawLabel(dc, cx, (40 * s).toNumber(), Graphics.FONT_TINY, text);
    }

    function drawDots(dc) {
        var y = h - (14 * s).toNumber();
        var step = (14 * s).toNumber();
        var x0 = cx - step;
        for (var i = 0; i < Settings.PAGE_COUNT; i++) {
            if (i == page) {
                dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(x0 + i * step, y, (4 * s).toNumber());
            } else {
                dc.setColor(0x555555, Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(x0 + i * step, y, (3 * s).toNumber());
            }
        }
    }

    // --- Connect screen ------------------------------------------------------

    function drawConnect(dc, now) {
        var ble = $.gBle;
        drawLabel(dc, cx, (40 * s).toNumber(), Graphics.FONT_TINY, WatchUi.loadResource(Rez.Strings.AppName));

        // pulsing rings around a Bluetooth disc
        var ry = cy - 22 * s;
        var phase = (now / 400) % 3;
        dc.setPenWidth(2);
        for (var i = 0; i < 3; i++) {
            dc.setColor(i == phase ? Actions.COLOR_CYAN : 0x005555, Graphics.COLOR_TRANSPARENT);
            dc.drawCircle(cx, ry, (34 + i * 14) * s);
        }
        dc.setPenWidth(1);
        dc.setColor(Actions.COLOR_CYAN, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(cx, ry, 26 * s);
        Icons.draw(dc, :bt, cx, ry, 16 * s, Graphics.COLOR_BLACK);

        var dotList = ["", ".", "..", "..."];
        var dots = dotList[(now / 500) % 4];
        var line1 = null;
        var line2 = null;
        var line3 = null;
        var st = ble.state;
        if (st == BleState.CONNECTING) {
            line1 = WatchUi.loadResource(Rez.Strings.ConConnecting) + dots;
            line2 = ble.connectingName;
        } else if (st == BleState.SETUP) {
            line1 = WatchUi.loadResource(Rez.Strings.ConSetup) + dots;
        } else if (st == BleState.RECONNECTING) {
            line1 = WatchUi.loadResource(Rez.Strings.ConLost);
            line2 = WatchUi.loadResource(Rez.Strings.ConConnecting) + dots;
        } else if (st == BleState.ERROR) {
            line1 = WatchUi.loadResource(Rez.Strings.ConBtError);
        } else {
            line1 = WatchUi.loadResource(Rez.Strings.ConSearching) + dots;
            if (ble.showPickHint(now)) {
                line2 = Lang.format(WatchUi.loadResource(Rez.Strings.ConFound), [ble.candidates.size()]);
                line3 = WatchUi.loadResource(Rez.Strings.ConPickHint);
            } else {
                line2 = WatchUi.loadResource(Rez.Strings.ConHint1);
                line3 = WatchUi.loadResource(Rez.Strings.ConHint2);
            }
        }
        var y = cy + 52 * s;
        drawLabel(dc, cx, y, Graphics.FONT_SMALL, line1);
        if (line2 != null) {
            dc.setColor(Actions.COLOR_GREY, Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, y + 30 * s, Graphics.FONT_XTINY, line2, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        }
        if (line3 != null) {
            dc.setColor(Actions.COLOR_GREY, Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, y + 50 * s, Graphics.FONT_XTINY, line3, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        }
    }

    // --- Feedback overlay ----------------------------------------------------

    function drawOverlay(dc) {
        var rm = $.gRemote;
        var phase = rm.fbPhase;
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();

        var info = (rm.fbAction != null) ? Actions.info(rm.fbAction) : null;
        var name = (info != null) ? WatchUi.loadResource(info[2]) : "";
        var color = (info != null) ? info[3] : Actions.COLOR_GREY;
        var icon = (info != null) ? info[4] : :x;
        var sub = "";
        if (phase == Feedback.SENDING) {
            sub = WatchUi.loadResource(Rez.Strings.Sending) + " ...";
        } else if (phase == Feedback.OK) {
            sub = WatchUi.loadResource(Rez.Strings.Delivered) + " · " + rm.fbLatency + " ms";
        } else if (phase == Feedback.ERROR) {
            color = Actions.COLOR_RED;
            icon = :x;
            sub = WatchUi.loadResource(Actions.resultText(rm.fbResult));
        } else if (phase == Feedback.TIMEOUT) {
            color = Actions.COLOR_RED;
            icon = :x;
            sub = WatchUi.loadResource(Rez.Strings.NotDelivered);
        } else if (phase == Feedback.NOT_CONN) {
            color = Actions.COLOR_RED;
            icon = :x;
            sub = WatchUi.loadResource(Rez.Strings.NotConnected);
        } else if (phase == Feedback.HINT) {
            color = Actions.COLOR_GREY;
            icon = :skip;
            name = WatchUi.loadResource(rm.fbText);
        } else if (phase == Feedback.ARMED) {
            name = name + "?";
            sub = WatchUi.loadResource(rm.fbText);
        } else if (phase == Feedback.HOLD) {
            sub = WatchUi.loadResource(rm.fbProgress >= 1.0 ? Rez.Strings.HoldRelease : Rez.Strings.Holding);
        }

        var ry = cy - 30 * s;
        var rr = 50 * s;
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        if (phase == Feedback.SENDING || phase == Feedback.ARMED) {
            dc.setPenWidth(4);
            dc.drawCircle(cx, ry, rr);
            dc.setPenWidth(1);
            Icons.draw(dc, icon, cx, ry, 28 * s, color);
        } else if (phase == Feedback.HOLD) {
            // grey ring, filled clockwise from 12 o'clock as the key is held
            dc.setColor(0x555555, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth((6 * s).toNumber());
            dc.drawCircle(cx, ry, rr);
            dc.setColor(color, Graphics.COLOR_TRANSPARENT);
            var deg = (rm.fbProgress * 360).toNumber();
            if (deg >= 360) {
                dc.drawCircle(cx, ry, rr);
            } else if (deg > 0) {
                dc.drawArc(cx, ry, rr, Graphics.ARC_CLOCKWISE, 90, (450 - deg) % 360);
            }
            dc.setPenWidth(1);
            Icons.draw(dc, icon, cx, ry, 28 * s, color);
        } else {
            dc.fillCircle(cx, ry, rr);
            Icons.draw(dc, icon, cx, ry, 28 * s, Graphics.COLOR_BLACK);
        }
        drawLabel(dc, cx, cy + 45 * s, Graphics.FONT_MEDIUM, name);
        dc.setColor(Actions.COLOR_GREY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, cy + 80 * s, Graphics.FONT_XTINY, sub, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }
}
