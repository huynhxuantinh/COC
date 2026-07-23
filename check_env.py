from __future__ import annotations

from pathlib import Path
import sys

from adb_client import ADBClient, ADBError
from config_manager import load_config
from vision import Vision


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    config = load_config()
    print("=== CHECK COC BOT ENV ===")
    print(f"Device: {config['adb']['device']}")

    try:
        adb = ADBClient(config["adb"]["path"], config["adb"]["device"], print)
        print(f"ADB path: {adb.adb_path}")
        adb.connect()
        print("ADB connect: OK")
    except ADBError as exc:
        print(f"ADB connect: FAIL - {exc}")
        print("Cach sua: mo GUI -> Cai dat khac -> chon file adb.exe.")
        print("Neu khong co adb.exe, cai Android platform-tools.")

    vision = Vision(config, print)
    print(f"OCR ready: {vision.available}")
    tess_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    print(f"Tesseract default exists: {tess_default.exists()}")


if __name__ == "__main__":
    main()
