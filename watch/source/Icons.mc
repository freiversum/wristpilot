// Simple icons drawn with Graphics primitives (no bitmaps), sized by a "radius" r:
// every icon fits into a square of 2r x 2r around (x, y).

import Toybox.Graphics;
import Toybox.Lang;

module Icons {

    function draw(dc, sym, x, y, r, color) {
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        var pen = (r / 6).toNumber();
        if (pen < 2) {
            pen = 2;
        }
        dc.setPenWidth(pen);
        if (sym == :left) {
            poly(dc, x, y, r, [[-1.0, 0.0], [-0.1, -0.8], [-0.1, -0.32], [1.0, -0.32], [1.0, 0.32], [-0.1, 0.32], [-0.1, 0.8]]);
        } else if (sym == :right) {
            poly(dc, x, y, r, [[1.0, 0.0], [0.1, -0.8], [0.1, -0.32], [-1.0, -0.32], [-1.0, 0.32], [0.1, 0.32], [0.1, 0.8]]);
        } else if (sym == :up) {
            poly(dc, x, y, r, [[0.0, -1.0], [0.8, -0.1], [0.32, -0.1], [0.32, 1.0], [-0.32, 1.0], [-0.32, -0.1], [-0.8, -0.1]]);
        } else if (sym == :uturn) {
            drawUturn(dc, x, y, r, pen);
        } else if (sym == :bolt) {
            poly(dc, x, y, r, [[0.25, -1.0], [-0.65, 0.12], [-0.05, 0.12], [-0.25, 1.0], [0.65, -0.18], [0.05, -0.18]]);
        } else if (sym == :thumb) {
            drawThumb(dc, x, y, r, color);
        } else if (sym == :elbow) {
            // bent arm: upper arm, forearm, fist
            dc.setPenWidth(pen + 2);
            dc.drawLine(x - 0.8 * r, y + 0.8 * r, x + 0.15 * r, y + 0.1 * r);
            dc.drawLine(x + 0.15 * r, y + 0.1 * r, x - 0.35 * r, y - 0.75 * r);
            dc.fillCircle(x - 0.4 * r, y - 0.8 * r, 0.22 * r);
            // flick marks
            dc.setPenWidth(pen);
            dc.drawLine(x + 0.45 * r, y + 0.05 * r, x + 0.9 * r, y - 0.1 * r);
            dc.drawLine(x + 0.4 * r, y + 0.35 * r, x + 0.85 * r, y + 0.45 * r);
        } else if (sym == :wave) {
            // open hand: palm plus four fingers and a thumb
            dc.fillRoundedRectangle(x - 0.45 * r, y - 0.05 * r, 0.9 * r, 0.85 * r, 0.2 * r);
            var fw = 0.17 * r;
            for (var i = 0; i < 4; i++) {
                var fx = x - 0.45 * r + i * 0.245 * r;
                dc.fillRoundedRectangle(fx, y - 0.85 * r + (i == 0 || i == 3 ? 0.2 * r : 0), fw, 0.9 * r, fw / 2);
            }
            dc.fillRoundedRectangle(x + 0.35 * r, y + 0.0 * r, 0.6 * r, 0.2 * r, 0.1 * r);
            // motion lines
            dc.drawLine(x - 0.95 * r, y - 0.6 * r, x - 0.75 * r, y - 0.2 * r);
            dc.drawLine(x - 0.95 * r, y - 0.05 * r, x - 0.75 * r, y + 0.35 * r);
        } else if (sym == :hammer) {
            dc.fillRoundedRectangle(x - 0.85 * r, y - 0.9 * r, 1.7 * r, 0.55 * r, 0.1 * r);
            dc.fillRectangle(x - 0.14 * r, y - 0.4 * r, 0.28 * r, 1.4 * r);
        } else if (sym == :bell) {
            poly(dc, x, y, r, [[-0.2, -0.85], [0.2, -0.85], [0.5, -0.55], [0.6, 0.35], [0.9, 0.6], [-0.9, 0.6], [-0.6, 0.35], [-0.5, -0.55]]);
            dc.fillCircle(x, y + 0.82 * r, 0.2 * r);
            dc.fillCircle(x, y - 0.9 * r, 0.12 * r);
        } else if (sym == :photo) {
            dc.fillRoundedRectangle(x - r, y - 0.55 * r, 2 * r, 1.35 * r, 0.2 * r);
            dc.fillRectangle(x - 0.35 * r, y - 0.8 * r, 0.7 * r, 0.3 * r);
            dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(x, y + 0.1 * r, 0.45 * r);
            dc.setColor(color, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(x, y + 0.1 * r, 0.25 * r);
        } else if (sym == :camera) {
            // video camera = "next camera view"
            dc.fillRoundedRectangle(x - r, y - 0.5 * r, 1.3 * r, r, 0.15 * r);
            poly(dc, x, y, r, [[0.3, 0.0], [1.0, -0.5], [1.0, 0.5]]);
        } else if (sym == :hud) {
            dc.drawRoundedRectangle(x - r, y - 0.7 * r, 2 * r, 1.4 * r, 0.2 * r);
            dc.fillRectangle(x - 0.75 * r, y - 0.45 * r, 0.6 * r, 0.25 * r);
            dc.fillRectangle(x + 0.25 * r, y - 0.45 * r, 0.5 * r, 0.25 * r);
            dc.fillRectangle(x - 0.75 * r, y + 0.25 * r, 1.5 * r, 0.2 * r);
        } else if (sym == :minus) {
            dc.fillRectangle(x - 0.8 * r, y - 0.18 * r, 1.6 * r, 0.36 * r);
        } else if (sym == :more) {
            // three dots
            var d = (r * 0.22).toNumber();
            dc.fillCircle(x - r * 0.65, y, d);
            dc.fillCircle(x, y, d);
            dc.fillCircle(x + r * 0.65, y, d);
        } else if (sym == :plus) {
            dc.fillRectangle(x - 0.8 * r, y - 0.18 * r, 1.6 * r, 0.36 * r);
            dc.fillRectangle(x - 0.18 * r, y - 0.8 * r, 0.36 * r, 1.6 * r);
        } else if (sym == :skip) {
            poly(dc, x, y, r, [[-0.95, -0.7], [-0.1, 0.0], [-0.95, 0.7]]);
            poly(dc, x, y, r, [[-0.15, -0.7], [0.7, 0.0], [-0.15, 0.7]]);
            dc.fillRectangle(x + 0.7 * r, y - 0.7 * r, 0.25 * r, 1.4 * r);
        } else if (sym == :x) {
            dc.setPenWidth(pen + 2);
            dc.drawLine(x - 0.7 * r, y - 0.7 * r, x + 0.7 * r, y + 0.7 * r);
            dc.drawLine(x - 0.7 * r, y + 0.7 * r, x + 0.7 * r, y - 0.7 * r);
        } else if (sym == :bt) {
            // Bluetooth rune
            dc.drawLine(x - 0.5 * r, y - 0.45 * r, x + 0.5 * r, y + 0.45 * r);
            dc.drawLine(x + 0.5 * r, y + 0.45 * r, x, y + 0.9 * r);
            dc.drawLine(x, y + 0.9 * r, x, y - 0.9 * r);
            dc.drawLine(x, y - 0.9 * r, x + 0.5 * r, y - 0.45 * r);
            dc.drawLine(x + 0.5 * r, y - 0.45 * r, x - 0.5 * r, y + 0.45 * r);
        }
        dc.setPenWidth(1);
    }

    // Filled polygon from unit coordinates (-1..1) around (x, y).
    function poly(dc, x, y, r, pts) {
        var abs = new [pts.size()];
        for (var i = 0; i < pts.size(); i++) {
            abs[i] = [x + pts[i][0] * r, y + pts[i][1] * r];
        }
        dc.fillPolygon(abs);
    }

    function drawUturn(dc, x, y, r, pen) {
        var rr = 0.5 * r;
        var cyArc = y - 0.25 * r;
        // half circle over the top, from the right leg to the left leg
        dc.drawArc(x, cyArc, rr, Graphics.ARC_COUNTER_CLOCKWISE, 0, 180);
        dc.drawLine(x + rr, cyArc, x + rr, y + r);           // right leg (coming up)
        dc.drawLine(x - rr, cyArc, x - rr, y + 0.35 * r);     // left leg (going down)
        poly(dc, x, y, r, [[-0.9, 0.3], [-0.1, 0.3], [-0.5, 0.95]]);   // arrow head down
    }

    // Thumbs-up approximation: fist, raised thumb, cuff.
    function drawThumb(dc, x, y, r, color) {
        dc.fillRoundedRectangle(x - 0.35 * r, y - 0.15 * r, 1.05 * r, 1.05 * r, 0.22 * r);   // fist
        dc.fillRoundedRectangle(x - 0.32 * r, y - r, 0.38 * r, 1.0 * r, 0.18 * r);           // thumb
        dc.fillRectangle(x - 0.95 * r, y - 0.05 * r, 0.45 * r, 0.95 * r);                    // cuff
        // finger gaps
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        for (var i = 1; i < 4; i++) {
            var fy = y - 0.15 * r + i * 0.26 * r;
            dc.drawLine(x + 0.15 * r, fy, x + 0.7 * r, fy);
        }
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
    }
}
