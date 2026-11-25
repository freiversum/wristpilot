// BLE central: finds the Wristpilot bridge, connects, subscribes to the status
// characteristic and writes commands. The only BleDelegate of the app.
//
// Connect IQ allows only ONE outstanding GATT request, so every read/write goes
// through a small queue that is advanced from the completion callbacks
// (onCharacteristicWrite / onDescriptorWrite / onCharacteristicRead) and from a
// watchdog in tick() in case a callback never arrives.

import Toybox.BluetoothLowEnergy;
import Toybox.Lang;
import Toybox.StringUtil;
import Toybox.System;

module BleState {
    const IDLE         = 0; // nothing started yet
    const REGISTERING  = 1; // registerProfile() sent, waiting for onProfileRegister
    const SCANNING     = 2; // looking for the bridge
    const CONNECTING   = 3; // pairDevice() called, waiting for onConnectedStateChanged
    const SETUP        = 4; // connected, subscribing to the status characteristic
    const READY        = 5; // commands can be sent
    const RECONNECTING = 6; // lost the connection, waiting for the stack to reconnect
    const ERROR        = 7; // profile registration failed, retrying
}

class BleManager extends BluetoothLowEnergy.BleDelegate {

    // Timeouts (ms)
    const REGISTER_TIMEOUT  = 3000;  // start scanning even if onProfileRegister never comes
    const CONNECT_TIMEOUT   = 10000;
    const SETUP_TIMEOUT     = 8000;
    const RECONNECT_TIMEOUT = 8000;  // then unpair and scan again
    const ERROR_RETRY       = 5000;
    const GATT_WATCHDOG     = 2000;  // a request without callback after this long is given up
    const COMMAND_STALE     = 1000;  // queued commands older than this are dropped (a late "left" is worse than none)
    const MAX_QUEUE         = 4;
    const MAX_CANDIDATES    = 16;
    const PICK_HINT_AFTER   = 10000; // offer the manual device list after this long without a match

    // Queue entry kinds
    const Q_WRITE = 0;
    const Q_CCCD  = 1;
    const Q_READ  = 2;

    var state = BleState.IDLE;
    hidden var demoAck = -1;
    var stateSince = 0;
    var device = null;
    var bridgeInfo = null;     // text from the info characteristic
    var notifyOk = false;      // CCCD write succeeded
    var lastStatusAt = 0;      // last notification from the bridge
    var scanStartedAt = 0;
    var candidates;            // [[ScanResult, name or null, rssi], ...]
    var connectingName = null;

    hidden var listener;       // Remote
    hidden var serviceUuid;
    hidden var commandUuid;
    hidden var statusUuid;
    hidden var infoUuid;
    hidden var cccdUuid;
    hidden var cmdChar = null;
    hidden var statusChar = null;
    hidden var infoChar = null;
    hidden var queue;
    hidden var busy = false;
    hidden var busySince = 0;
    hidden var lastPingAt = 0;

    function initialize(remote) {
        BleDelegate.initialize();
        listener = remote;
        candidates = [];
        queue = [];
        serviceUuid = BluetoothLowEnergy.stringToUuid(Protocol.SERVICE_UUID);
        commandUuid = BluetoothLowEnergy.stringToUuid(Protocol.COMMAND_UUID);
        statusUuid = BluetoothLowEnergy.stringToUuid(Protocol.STATUS_UUID);
        infoUuid = BluetoothLowEnergy.stringToUuid(Protocol.INFO_UUID);
        cccdUuid = BluetoothLowEnergy.cccdUuid();
    }

    // --- Public API -------------------------------------------------------

    function start() {
        BluetoothLowEnergy.setDelegate(self);
        registerProfile();
    }

    function shutdown() {
        try {
            BluetoothLowEnergy.setScanState(BluetoothLowEnergy.SCAN_STATE_OFF);
        } catch (e) {
        }
        dropDevice();
        setState(BleState.IDLE);
    }

    function isReady() {
        if (Build.DEMO) {
            return true;
        }
        return state == BleState.READY && cmdChar != null;
    }

    // True if the bridge stopped answering pings although the link is up.
    function isStale(now) {
        return isReady() && notifyOk && lastStatusAt > 0
            && now - lastStatusAt > 3 * Protocol.PING_INTERVAL;
    }

    // Offer the manual device list (fēnix scan bug: advertising data may come back empty).
    function showPickHint(now) {
        return state == BleState.SCANNING && candidates.size() > 0
            && now - scanStartedAt > PICK_HINT_AFTER;
    }

    // Queue a command. Returns false if it cannot be sent right now.
    function sendCommand(seq, action, value) {
        if (!isReady() || queue.size() >= MAX_QUEUE) {
            return false;
        }
        if (Build.DEMO) {
            demoAck = seq;              // answered on the next tick, as if the bridge replied
            return true;
        }
        enqueue([Q_WRITE, cmdChar, Protocol.encodeCommand(seq, action, value), System.getTimer(), seq]);
        return true;
    }

    // Forget the current device and scan again (menu "Reconnect", pick list "Search again").
    function reconnect() {
        dropDevice();
        startScan();
    }

    // Connect to a device chosen from the pick list.
    function connectTo(scanResult, name) {
        dropDevice();
        connect(scanResult, name);
    }

    // Candidates sorted by RSSI, strongest first (for the pick list).
    function sortedCandidates() {
        var list = [];
        for (var i = 0; i < candidates.size(); i++) {
            list.add(candidates[i]);
        }
        // insertion sort, the list is tiny
        for (var i = 1; i < list.size(); i++) {
            var item = list[i];
            var j = i - 1;
            while (j >= 0 && list[j][2] < item[2]) {
                list[j + 1] = list[j];
                j--;
            }
            list[j + 1] = item;
        }
        return list;
    }

    // Called every 100 ms by the app timer.
    function tick(now) {
        if (Build.DEMO) {
            if (demoAck >= 0) {
                listener.onStatus([Protocol.MSG_ACK, demoAck, Protocol.RESULT_OK]b);
                demoAck = -1;
            }
            return;
        }
        var age = now - stateSince;
        if (state == BleState.REGISTERING && age > REGISTER_TIMEOUT) {
            startScan();
        } else if (state == BleState.ERROR && age > ERROR_RETRY) {
            registerProfile();
        } else if (state == BleState.CONNECTING) {
            if (device != null && device.isConnected()) {
                setupGatt();       // connected event got lost
            } else if (age > CONNECT_TIMEOUT) {
                reconnect();
            }
        } else if (state == BleState.SETUP && age > SETUP_TIMEOUT) {
            reconnect();
        } else if (state == BleState.RECONNECTING) {
            if (device != null && device.isConnected()) {
                setupGatt();
            } else if (age > RECONNECT_TIMEOUT) {
                reconnect();
            }
        } else if (state == BleState.READY) {
            if (queue.size() == 0 && !busy && now - lastPingAt >= Protocol.PING_INTERVAL) {
                lastPingAt = now;
                enqueue([Q_WRITE, cmdChar, Protocol.encodeCommand(0, Protocol.ACT_PING, 0), now, -1]);
            }
        }
        if (busy && now - busySince > GATT_WATCHDOG) {
            busy = false;
            pump();
        }
    }

    // --- Internal: connection state machine --------------------------------

    hidden function setState(s) {
        state = s;
        stateSince = System.getTimer();
        $.gDirty = true;
    }

    hidden function registerProfile() {
        var profile = {
            :uuid => serviceUuid,
            :characteristics => [
                { :uuid => commandUuid },
                { :uuid => statusUuid, :descriptors => [cccdUuid] },
                { :uuid => infoUuid }
            ]
        };
        try {
            BluetoothLowEnergy.registerProfile(profile);
            setState(BleState.REGISTERING);
        } catch (e) {
            // Most likely "profile already registered" after a restart of the app
            // within the same session; scanning still works then.
            startScan();
        }
    }

    hidden function startScan() {
        candidates = [];
        connectingName = null;
        scanStartedAt = System.getTimer();
        setState(BleState.SCANNING);
        try {
            BluetoothLowEnergy.setScanState(BluetoothLowEnergy.SCAN_STATE_SCANNING);
        } catch (e) {
            setState(BleState.ERROR);
        }
    }

    hidden function connect(scanResult, name) {
        try {
            BluetoothLowEnergy.setScanState(BluetoothLowEnergy.SCAN_STATE_OFF);
        } catch (e) {
        }
        var dev = null;
        try {
            dev = BluetoothLowEnergy.pairDevice(scanResult);
        } catch (e) {
            dev = null;
        }
        if (dev == null) {
            startScan();
            return;
        }
        device = dev;
        connectingName = name;
        setState(BleState.CONNECTING);
    }

    hidden function dropDevice() {
        cmdChar = null;
        statusChar = null;
        infoChar = null;
        queue = [];
        busy = false;
        notifyOk = false;
        if (device != null) {
            try {
                BluetoothLowEnergy.unpairDevice(device);
            } catch (e) {
            }
        }
        device = null;
    }

    hidden function setupGatt() {
        setState(BleState.SETUP);
        queue = [];
        busy = false;
        notifyOk = false;
        var service = (device != null) ? device.getService(serviceUuid) : null;
        if (service == null) {
            // Not our bridge (picked by hand) or services not resolved yet: start over.
            reconnect();
            return;
        }
        cmdChar = service.getCharacteristic(commandUuid);
        statusChar = service.getCharacteristic(statusUuid);
        infoChar = service.getCharacteristic(infoUuid);
        if (cmdChar == null) {
            reconnect();
            return;
        }
        var cccd = (statusChar != null) ? statusChar.getDescriptor(cccdUuid) : null;
        if (cccd != null) {
            enqueue([Q_CCCD, cccd, [0x01, 0x00]b, System.getTimer(), -1]);
        }
        if (infoChar != null) {
            enqueue([Q_READ, infoChar, null, System.getTimer(), -1]);
        }
        if (cccd == null) {
            becomeReady();
        }
    }

    hidden function becomeReady() {
        lastPingAt = 0;               // ping right away to get the state flags
        lastStatusAt = System.getTimer();
        setState(BleState.READY);
        listener.onConnectionChanged(true);
    }

    // --- Internal: GATT queue ----------------------------------------------

    hidden function enqueue(entry) {
        queue.add(entry);
        pump();
    }

    hidden function pump() {
        while (!busy && queue.size() > 0) {
            var e = queue[0];
            queue = queue.slice(1, null);
            var now = System.getTimer();
            if (e[0] == Q_WRITE && e[4] >= 0 && now - e[3] > COMMAND_STALE) {
                listener.onCommandDropped(e[4]);
                continue;
            }
            try {
                if (e[0] == Q_WRITE) {
                    // With response: guarantees onCharacteristicWrite, which drives the queue.
                    e[1].requestWrite(e[2], { :writeType => BluetoothLowEnergy.WRITE_TYPE_WITH_RESPONSE });
                } else if (e[0] == Q_CCCD) {
                    e[1].requestWrite(e[2]);
                } else {
                    e[1].requestRead();
                }
                busy = true;
                busySince = now;
            } catch (ex) {
                if (e[0] == Q_WRITE && e[4] >= 0) {
                    listener.onCommandDropped(e[4]);
                } else if (e[0] == Q_CCCD && state == BleState.SETUP) {
                    becomeReady();     // without notifications; acks will time out
                }
            }
        }
    }

    // --- BleDelegate callbacks ---------------------------------------------

    function onProfileRegister(uuid, status) {
        if (status == BluetoothLowEnergy.STATUS_SUCCESS) {
            if (state == BleState.REGISTERING || state == BleState.ERROR) {
                startScan();
            }
        } else {
            setState(BleState.ERROR);
        }
    }

    function onScanStateChange(scanState, status) {
        $.gDirty = true;
    }

    function onScanResults(scanResults) {
        if (state != BleState.SCANNING) {
            return;
        }
        var r = scanResults.next();
        while (r != null) {
            if (r instanceof BluetoothLowEnergy.ScanResult) {
                if (handleScanResult(r)) {
                    return;          // connecting, ignore the rest
                }
            }
            r = scanResults.next();
        }
    }

    // Returns true if this result is the bridge and a connection was started.
    hidden function handleScanResult(r) {
        var name = r.getDeviceName();
        var rssi = r.getRssi();
        var known = false;
        for (var i = 0; i < candidates.size(); i++) {
            var c = candidates[i];
            if (c[0].isSameDevice(r)) {
                c[0] = r;
                c[2] = rssi;
                if (name != null) {
                    c[1] = name;
                }
                known = true;
                break;
            }
        }
        if (!known && candidates.size() < MAX_CANDIDATES) {
            candidates.add([r, name, rssi]);
            $.gDirty = true;
        }
        if (advertisesService(r) || (name != null && name.find(Protocol.BRIDGE_NAME) != null)) {
            connect(r, name);
            return true;
        }
        return false;
    }

    hidden function advertisesService(r) {
        var it = r.getServiceUuids();
        if (it == null) {
            return false;
        }
        var u = it.next();
        while (u != null) {
            if (serviceUuid.equals(u)) {
                return true;
            }
            u = it.next();
        }
        return false;
    }

    function onConnectedStateChanged(dev, connectionState) {
        if (connectionState == BluetoothLowEnergy.CONNECTION_STATE_CONNECTED) {
            device = dev;
            if (state != BleState.SETUP && state != BleState.READY) {
                setupGatt();
            }
        } else {
            var wasReady = (state == BleState.READY);
            cmdChar = null;
            statusChar = null;
            infoChar = null;
            queue = [];
            busy = false;
            notifyOk = false;
            if (state == BleState.CONNECTING || state == BleState.SETUP
                    || state == BleState.READY || state == BleState.RECONNECTING) {
                // Keep the device paired: the stack reconnects paired devices on its own.
                // tick() unpairs and scans again after RECONNECT_TIMEOUT.
                setState(BleState.RECONNECTING);
            }
            if (wasReady) {
                listener.onConnectionChanged(false);
            }
        }
    }

    function onCharacteristicWrite(characteristic, status) {
        busy = false;
        pump();
    }

    function onDescriptorWrite(descriptor, status) {
        busy = false;
        notifyOk = (status == BluetoothLowEnergy.STATUS_SUCCESS);
        if (state == BleState.SETUP) {
            becomeReady();
        }
        pump();
    }

    function onCharacteristicRead(characteristic, status, value) {
        busy = false;
        if (status == BluetoothLowEnergy.STATUS_SUCCESS && value != null
                && characteristic.getUuid().equals(infoUuid)) {
            bridgeInfo = decodeText(value);
            $.gDirty = true;
        }
        pump();
    }

    function onDescriptorRead(descriptor, status, value) {
        busy = false;
        pump();
    }

    function onCharacteristicChanged(characteristic, value) {
        if (value == null || !characteristic.getUuid().equals(statusUuid)) {
            return;
        }
        lastStatusAt = System.getTimer();
        listener.onStatus(value);
    }

    // Bridge info text (UTF-8). StringUtil.convertEncodedString raised an uncatchable
    // System Error on the fenix 7X Pro (CIQ 6.0.4, firmware 27.18) for "·", so decode by hand:
    // printable ASCII stays, every multi-byte UTF-8 character becomes a space.
    hidden function decodeText(bytes) {
        var s = "";
        for (var i = 0; i < bytes.size(); i++) {
            var b = bytes[i];
            if (b >= 0x20 && b < 0x7F) {
                s += b.toChar().toString();
            } else if (b >= 0xC0) {
                s += " ";
            }
        }
        return s;
    }
}
