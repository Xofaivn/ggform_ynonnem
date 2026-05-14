import shutil
import sys

from ui.wizard import run_wizard
from core.filler import run_all


def _check_chrome() -> None:
    if shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium"):
        return
    # Windows: thử tìm trong đường dẫn cài đặt phổ biến
    import os
    common_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    if any(os.path.exists(p) for p in common_paths):
        return
    print("=" * 60)
    print("  CHUA CAI CHROME!")
    print()
    print("  Tool nay can Google Chrome de chay.")
    print("  Tai Chrome tai: https://www.google.com/chrome")
    print("  Cai xong roi chay lai tool.")
    print("=" * 60)
    input("\nNhan Enter de thoat...")
    sys.exit(1)


def main() -> None:
    _check_chrome()
    config = run_wizard()
    run_all(config)


if __name__ == "__main__":
    main()
