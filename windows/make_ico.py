"""Write zwindoor.ico (16-256 px) from the same drawing as the tray icon."""

from pathlib import Path

from zwindoor_tray import make_icon

if __name__ == "__main__":
    out = Path(__file__).with_name("zwindoor.ico")
    make_icon(size=256).save(out, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(out)
