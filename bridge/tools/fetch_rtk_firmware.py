"""Fetch the Realtek Bluetooth firmware for the Bumble backend (build step for the Windows .exe).

Bumble loads the firmware into Realtek USB adapters (RTL8761B/BU, e.g. TP-Link UB500) itself,
because Windows' own driver is replaced by WinUSB. The files come from linux-firmware and are
redistributable in binary form (LICENCE.rtlwifi_firmware.txt, copied next to them).

    python tools/fetch_rtk_firmware.py            # into zwindoor_bridge/firmware/realtek/
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
import urllib.request

MIRRORS = (   # official linux-firmware mirror first: kernel.org answers 403 to some CI runners
    "https://gitlab.com/kernel-firmware/linux-firmware/-/raw/main/",
    "https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/",
)
HEADERS = {"User-Agent": "zwindoor-build"}
FILES = {
    "rtl_bt/rtl8761bu_fw.bin": "1d7a9597349ad89344fa16c1913d3e39e9a12e966e417ca16871bc79bbe59edb",
    "rtl_bt/rtl8761bu_config.bin": "6c28a3f07c6a30ed208c4b64862a23f02b7d93543ea980edd24df16bab45095f",
    "rtl_bt/rtl8761b_fw.bin": "4c50dac2714bad1a75944d1b770304fa3fbf84cd898942489c7eb2ef497ad53b",
    "rtl_bt/rtl8761b_config.bin": "6ddeb15f23588053e00cb08d25588bd7cf98d60fa93d9478efcef4ae8064a7ac",
    "LICENSES/LICENCE.rtlwifi_firmware.txt": None,
}
TARGET = pathlib.Path(__file__).resolve().parent.parent / "zwindoor_bridge" / "firmware" / "realtek"


def fetch(path: str) -> bytes:
    errors = []
    for base in MIRRORS:
        try:
            with urllib.request.urlopen(urllib.request.Request(base + path, headers=HEADERS), timeout=60) as r:
                return r.read()
        except OSError as e:
            errors.append(f"{base}: {e}")
    raise SystemExit(f"cannot fetch {path}: " + "; ".join(errors))


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    for path, sha in FILES.items():
        dest = TARGET / pathlib.Path(path).name
        if dest.is_file() and (sha is None or hashlib.sha256(dest.read_bytes()).hexdigest() == sha):
            continue
        data = fetch(path)
        if sha is not None and hashlib.sha256(data).hexdigest() != sha:
            print(f"checksum mismatch: {path}", file=sys.stderr)
            return 1
        dest.write_bytes(data)
        print(f"fetched {dest.name} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
