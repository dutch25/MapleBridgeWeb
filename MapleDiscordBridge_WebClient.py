import ctypes
from ctypes import wintypes

# Đảm bảo Windows không ảo hóa / scale sai toạ độ và kích thước pixel trên laptop và màn hình 2K/4K
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import configparser
import threading
import time
import sys
import os
import requests
import json
import urllib.request
import subprocess
from pathlib import Path
import traceback
import atexit
import psutil
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import cv2
import numpy as np
import base64
import re
from datetime import datetime

_orig_print = print
def print(*args, **kwargs):
    if not args:
        _orig_print(*args, **kwargs)
        return

    first = args[0]
    if isinstance(first, str):
        stripped = first.strip()
        # Bỏ qua nếu là dòng trống hoàn toàn
        if not stripped:
            _orig_print(*args, **kwargs)
            return

        # Bỏ qua nếu là dòng kẻ phân cách banner (ví dụ: "======", "------", "******")
        if len(stripped) >= 4 and all(c in "=-*#_~ " for c in stripped):
            _orig_print(*args, **kwargs)
            return

        # Bỏ qua nếu đã có sẵn timestamp [HH:MM:SS] ở đầu
        if re.match(r'^\s*\[\d{2}:\d{2}:\d{2}\]', stripped):
            _orig_print(*args, **kwargs)
            return

        # Giữ nguyên các ký tự \n ở đầu chuỗi (ví dụ: "\n[AUTO-BUFF 1]...")
        prefix_newlines = ""
        content = first
        while content.startswith("\n"):
            prefix_newlines += "\n"
            content = content[1:]

        now = datetime.now().strftime("[%H:%M:%S]")
        new_first = f"{prefix_newlines}{now} {content}"
        _orig_print(new_first, *args[1:], **kwargs)
    else:
        now = datetime.now().strftime("[%H:%M:%S]")
        _orig_print(f"{now}", *args, **kwargs)

VERSION = 1
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent

CONFIG_PATH = BASE / "config.ini"
TEMPLATE_DIR = BASE / "templates"

# Embedded Base64 templates for out-of-the-box detector support
DEFAULT_TEMPLATES_B64 = {
    "image1.png": "iVBORw0KGgoAAAANSUhEUgAAADAAAAAJCAYAAAB0d6/iAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAKdSURBVDhPnVTdUlJRFP7gAeAZQAQ1JGzKF2hqugA1lQtnFH2EEl6gCy8sfnoE/upGaxQZm6bxBZzSA8fAdMBngBc4rbX22XLAY019zsdeP+y1l3t9G8/VddcCPLgPlES1UoJhGMgXiipog3Pq4+9wO6FSKaNpNJHLO+ra9e6UdTnHophXKnvIErLtpAUPx9kkn3mb06bDd8Of0un0FvLO5gVqB//d7rYctlA1z/CqRcNCq2kgHAoKXzx/ZscVwqEJRGw6Gzdpz1R4QpjNvJYYp2p0wxnyIxTntUo+54d+SVZdymxRnamAMJt9pcsL2J+eDgizWXUGw6tvljkY9LG6sozrblf4IBqVQzl3VK/j+9mZxJMLC6iUKU4FOJdaXcHpjzP8uu6i/fNCGtFdNY7qIJmiwPLjOuxfkZ9/Lw0M4UEqtYzTUwOXlzdot02Y5rlIR1ZCu8PxG3Q6Ji4uDFtCDhweHEhzGoViEenNTbE57vf7xY7H42jSrTN4YsFgEH6fyu2+fYcy/XMaieSwHiM55mu0WudSx6fr7OZH6nDTGo3GCaLRuFyIVx6HJoGbG4nZcYFbjNDr9RCZJGkReRo8hf8B19ESSqVeyhS4ydnZOaytbWCG5DMzE0Ai8VS+z0P2OnvikfCvje5Pr+MNj4NvlWXCEmJ++frNzvwbEolFkY/m8fGJSlCn6+tbSkKdHr2DWdRqJUnRBKg7m4tLS6J1ti0i63x7e/hg3BCLxUXX/X5fbiRD35d3o9L3YvxOYrE5ksYhvcOB+Pxoq1XVJNuqYccu+4CRN+D3+bC//wnhyZDw44fa8Gdu/ET27RjvefL4Ee2ZEPmk0+rduMGx7Q729j5jfv6hSIjls7GxJfFcroidnTckoaCQwROBB/gNhOcxtKle9PsAAAAASUVORK5CYII=",
    "image2.png": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAQCAYAAAB6Hg0eAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAM2SURBVEhLpVY9TxVBFL07yyOCCVg8YwEEgzEWFNCYKAH5DLGCyB/gL2goJQj2Blo7tZXv2ElIQBI1NtArgp2dGD7fe7vrOXdm3lvgIYKHnJ07d2bvnD0zb5cg03w3aW6ok5ejI1IeAf4sEiWvNi61yCJQupgXbXT84jAVlRkJKysQcvlytMXTi9g2kQDDRmkkRMC+nZhI7MLLwkRxJEkUue7Z8GJ862GghqJCY6ww4H8EeZgwCST+B2EWbuWTbuKi24ccxZVGLw+TFOBYrOUdRd7OzMjTsTGN02B+1OV1Nh6Kgnh7rOo4QnHHBZ7H+bk5GR8fP5Yzuf1fEuQPEWrVVHsWSrdzphcV41A5XUqKM3ruzufQ0JA8n5g4ljPxfg62sRpxnqgS2trbdTqNmp6eUTenZ2dlbOyZBBQEzjoneA7nEJMPOjuLZN6P+XlFysGhxPmCSkqTONm3sD+A3p5u2fm9owZtbGxIf1+fxgRkaez7HpNTU/JucVFWV1aku6tLH4Ru6xp0PUUThBnhOTupYGl5We7BlTRfTE660USGh4fl/dKS9r5vb8m12tqiGMvT0iimBvMooqWlRdbX1zWm7V6cp7mSwTsMv0od10GtAUd65OPamnxa++C4KiNPHusYy2SzWZlfWJCvm9/k0eAgntAJ0m2wsk6iuLiLiXIxaQ52dxHFNoGLH7DwUSnjUVNbo+2b16/kIbbRaM/CelWSlq6ZrqRuOaRjwkiSlzATnipGlb6gpwIBZ1EIndrc2rbbg35Layv6W8VzQkf91rDeRWCyN65LRRgidKLc/dpoPRa2dd2QBgHY39crTY2NPiW3m5o0vt/RIW3g4MCA9rWGRsfBbT8LQd2tO8nN+nr58fmL4KRJhBXZxlwZrXXSlqVLae5FsWRMKFfxveXMI5zVHJjHS60ARiRE0T11DUJsPSvK58uJNnt7R5LL57EQb8ItOjnGC5OESLCAlyc08ChKAIbgz4Mj2c3lpRpuc01+1AoIKMgL8+JUAFfjRIDvqZAi/+KYKUQolsfNzoYAH2N+kCvKkHnSgA1VVVJXXa3/RdCVCE4pGXtBGEu7wZgOUSjnqYtlIfIHDFbh6EdEV4sAAAAASUVORK5CYII=",
    "image3.png": "iVBORw0KGgoAAAANSUhEUgAAABUAAAAWCAYAAAAvg9c4AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAFYSURBVEhLvZWxTsMwEEDP/ABKV7bC1qVS+gFIpRsrC0iwFbEwsyG2LiwMSO0EAwsrTFD+gEosjGVjTcQXlLuLL4lbn51KiCed7ETxy50dO+bs7mnxAwCbGOtAYzQ2bPun/I+UytLi9mS/7IdwpLGHiQcUx1i//JaJillKKx/KkiSOKCI2h/hJ2b6DM+h0GyDPAaYYdbIFHN0/24sKb/ks/BqgpAcwQaGGkvGKtHgIhcRSYl484vBCJbYNgVPQPb+yFwWO9Hs2s72GWGEnTe2NgnCmUv54DvCYsaREERJh6cE7wHDOg50SA0JCl7ZfYXphuPtxc8ktExESirQS5pMWt0L3GIU7upDwSkmYthMOgTJjYc8K5WSRqOFIt3DgLpa2N/JuskoYYSVTESfDjKMkdDgs4S1fxCJnmv5v8OXqgSJ8vhUbotOvzaWP2lFn+tcvQWljypcB/AIuf3XBQNCuGgAAAABJRU5ErkJggg==",
    "image4.png": "iVBORw0KGgoAAAANSUhEUgAAACgAAAAOCAIAAADSackRAAAD0klEQVQ4EW3By2+UVRzH4c/v7ZQSAzSgmIAGsECkSMNlhQkmyG2DphYkIQItiS7cookLjdiemeEipeUvEAsoMjNnUCIbogmGiuKm5ywVZuRfYNvOvF/fd7iIxOcxK/Ru3rR+YvwkkJglZkmSAEaHWZdZkrEcqZBIlTH+XwopaiPxiMDIGTkjI6Nr4ZbN6yfGTxskZknGDBA5gySxxJLEckhKhYQEZvyXkUkhlVIknmU8IaNr4ZaN/ecmzxiYWWI5OoQMzCyxxDqQUA5hdIiMmWFgZCRSlEriWcYjQta7eNXA+r5TJ0cN7CEQGdFhGTAzMBACJDCRkxlgmBkGhoQySOIZ4jHJlix5eWDDutMnRumoen92cpKn7NzxZtk5MAMZ/xKZmvchxBPFIglmhiGBHuIZIidAst4FL2zcNHDmVJGOqvchxpJzIJHRoeGjQ4ODB/bvA8MwwMhIICQQlmA5MANJICGeEDmByEmyxQte3LBxw9nTTuSq3ocYS86BAEHN12MMJeeAWr0+PjFJx53bvypV1fsQQsk5M6vV6+MTE3TcmZ7mKRXvQ4wl55QBJFu6ZMVrA/1flj8HBFXvQ4wl53hE7w2PDA0Ovrt/6F6j+cWY++7SxSSxKzUfZmaKY67ifZgJRecafzdHx8YuX7wIqnofQiw7x2MCgTKAJLDly9e80rfq3KlRkat4Pz45yVM+PnbswP4hCYzELOn48+698+e/dm6sWq3NhFB0LrFcQu6vRmNqaqrsHI8JlAFlQJItXrqsf926cyeLdFS8DzGWnQM+O368ef/+txemAEkYhm3d9gYdu3buKI65qvchhKJzBonZ1m3b6Ni9Y0e5WCQniYyEkISQwJaufGndmlfPjjk6Kt7HGMvO0XFweLhv1cqSc8DdRuPIyNHfpm8BNV8PMRRd0XsfYiw5d6/RODIycmd62swq3scYT5aKEkhCEgghCYGQrXi9f/PqtZ9++ImRq3gfYyw7R8eDBw927917cWpq7eq+qq+HEJwbk/D1+g/Xrl26cMHX6zGEcrFY9T6EUHbOEqt6769+X738jVIh9AgZCSGB7fngrVXPL3v/7RHAoOJ9jPGEczx2xfvxyckb168vXLTo0MhIs9kEtm/ffvPmzdvTt+r1qzHGE6WSpIOHDzebTWDPrp03fvp55o/flUmlVFdqtRBiyTmEQMje+WhfL8/98tWPCRgkYOSMnKQ5aQ5aUitNZ9vtVrvdSlNJha6u7kKhp7u7p1BAQkIC5s8rzOspzO/p7u7qmptttWZbc3Ot1mx7rp3OtdNWqlaatk3/AHQwPho2TRFmAAAAAElFTkSuQmCC"
}

def ensure_templates_exist():
    try:
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        # 1. Kiểm tra từ PyInstaller bundle nếu có
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            bundle_tmpl = Path(bundle_dir) / "templates"
            if bundle_tmpl.exists():
                for p in bundle_tmpl.glob("*.png"):
                    target = TEMPLATE_DIR / p.name
                    if not target.exists():
                        try:
                            target.write_bytes(p.read_bytes())
                            print(f"[DETECTOR] Đã giải nén mẫu ảnh: templates/{p.name}")
                        except Exception:
                            pass
        # 2. Tạo từ Base64 dự phòng nếu vẫn thiếu
        for name, b64_str in DEFAULT_TEMPLATES_B64.items():
            tmpl_file = TEMPLATE_DIR / name
            if not tmpl_file.exists():
                try:
                    tmpl_file.write_bytes(base64.b64decode(b64_str))
                    print(f"[DETECTOR] Đã tự động tạo mẫu ảnh: templates/{name}")
                except Exception as ex:
                    print(f"[DETECTOR ERROR] Không thể tạo {name}: {ex}")
    except Exception as e:
        print(f"[DETECTOR ERROR] Lỗi tạo thư mục templates: {e}")

ensure_templates_exist()

LAUNCHER_BAT_PATH = BASE / "Mo_KuroMS.bat"
LAUNCHER_BAT_CONTENT = (
    "@echo off\r\n"
    "title KuroMS Web Launcher\r\n\r\n"
    "echo =======================================================\r\n"
    "echo    KHOI DONG KUROMS WEB (HO TRO AUTO DANH NGAM)\r\n"
    "echo =======================================================\r\n"
    "echo.\r\n\r\n"
    "set \"EDGE_EXE=C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe\"\r\n"
    "if not exist \"%EDGE_EXE%\" set \"EDGE_EXE=C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe\"\r\n\r\n"
    "set \"CHROME_EXE=C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\"\r\n"
    "if not exist \"%CHROME_EXE%\" set \"CHROME_EXE=C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe\"\r\n\r\n"
    "set FLAGS=--app=https://play.playkuro.com/ --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=\"%LOCALAPPDATA%\\KuroMS_Browser\" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist --use-angle=d3d11 --force-device-scale-factor=1 --disable-features=WakeLock\r\n\r\n"
    "powercfg -requestsoverride PROCESS msedge.exe awaymode display system >nul 2>&1\r\n"
    "powercfg -requestsoverride PROCESS chrome.exe awaymode display system >nul 2>&1\r\n\r\n"
    "if exist \"%EDGE_EXE%\" (\r\n"
    "    echo [OK] Dang mo KuroMS tren Microsoft Edge...\r\n"
    "    start \"\" \"%EDGE_EXE%\" %FLAGS%\r\n"
    "    goto done\r\n"
    ")\r\n\r\n"
    "if exist \"%CHROME_EXE%\" (\r\n"
    "    echo [OK] Dang mo KuroMS tren Google Chrome...\r\n"
    "    start \"\" \"%CHROME_EXE%\" %FLAGS%\r\n"
    "    goto done\r\n"
    ")\r\n\r\n"
    "start https://play.playkuro.com/\r\n\r\n"
    ":done\r\n"
    "echo.\r\n"
    "echo [THANH CONG] Da khoi dong xong! Cua so game da mo.\r\n"
    "echo Cua so nay se tu dong dong sau 3 giay...\r\n"
    "timeout /t 3 >nul 2>&1\r\n"
)

def ensure_launcher_bat_exists():
    try:
        if not LAUNCHER_BAT_PATH.exists():
            with open(LAUNCHER_BAT_PATH, "w", encoding="utf-8") as f:
                f.write(LAUNCHER_BAT_CONTENT)
            print("[SETUP] Đã tự động tạo file khởi động game: Mo_KuroMS.bat")
    except Exception as e:
        print(f"[SETUP ERROR] Không thể tạo Mo_KuroMS.bat: {e}")

ensure_launcher_bat_exists()

def kill_other_instances():
    """Tự động đóng các tiến trình MapleDiscordBridge_Web cũ đang chạy ngầm để tránh xung đột phím và CDP."""
    try:
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['pid'] != current_pid:
                    pname = (proc.info['name'] or "").lower()
                    if "maplediscordbridge_web" in pname:
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

kill_other_instances()

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
IsWindow = user32.IsWindow
IsWindowVisible = user32.IsWindowVisible
GetClientRect = user32.GetClientRect
ClientToScreen = user32.ClientToScreen
SetForegroundWindow = user32.SetForegroundWindow

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long)
    ]

# Win32 SendInput Structures
PUL = ctypes.POINTER(ctypes.c_ulong)
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", PUL)
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

VK_RETURN = 0x0D
VK_LEFT, VK_RIGHT = 0x25, 0x27

# Bảng mã phím chuẩn
KEY_VK_MAP = {
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "space": 0x20, "enter": 0x0D,
    "esc": 0x1B, "tab": 0x09, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35,
    "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39, "0": 0x30,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C,
    "m": 0x4D, "n": 0x4E, "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5A,
    "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC, "`": 0xC0
}

def send_key_event(vk_code, is_down=True):
    extra = ctypes.c_ulong(0)
    ii_ = INPUT()
    ii_.type = INPUT_KEYBOARD
    flags = 0 if is_down else KEYEVENTF_KEYUP
    scan = user32.MapVirtualKeyW(vk_code, 0)
    ii_.ki = KEYBDINPUT(vk_code, scan, flags, 0, ctypes.pointer(extra))
    user32.SendInput(1, ctypes.pointer(ii_), ctypes.sizeof(ii_))

def send_unicode_char(char):
    extra = ctypes.c_ulong(0)
    # Down
    ii_down = INPUT()
    ii_down.type = INPUT_KEYBOARD
    ii_down.ki = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
    # Up
    ii_up = INPUT()
    ii_up.type = INPUT_KEYBOARD
    ii_up.ki = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
    user32.SendInput(1, ctypes.pointer(ii_down), ctypes.sizeof(ii_down))
    time.sleep(0.015)
    user32.SendInput(1, ctypes.pointer(ii_up), ctypes.sizeof(ii_up))

def send_key_press(vk_code, hold_time=0.05):
    send_key_event(vk_code, is_down=True)
    time.sleep(hold_time)
    send_key_event(vk_code, is_down=False)

def find_web_game():
    """
    Tự động tìm kiếm cửa sổ trình duyệt (Chrome, Edge, Firefox, Brave, Cốc Cốc)
    đang chạy game KuroMS Web (play.playkuro.com).
    Hỗ trợ cả môi trường sandbox hoặc nhiều desktop bằng cách chuyển thread desktop sang Default.
    """
    try:
        hdesk = user32.OpenDesktopW('Default', 0, False, 0x10000000)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception:
        pass

    found = []
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                t_low = title.lower()
                # Nhận diện cửa sổ game KuroMS Web
                if "kuroms" in t_low or "play.playkuro.com" in t_low or "playkuro" in t_low:
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w > 300 and h > 300:
                        found.append(hwnd)
        return 1

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    if found:
        return found[0]
    return None

CDP_KEY_MAP = {
    "ctrl": {"key": "Control", "code": "ControlLeft", "windowsVirtualKeyCode": 17},
    "alt": {"key": "Alt", "code": "AltLeft", "windowsVirtualKeyCode": 18},
    "shift": {"key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16},
    "space": {"key": " ", "code": "Space", "windowsVirtualKeyCode": 32},
    "enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
    "esc": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
    "left": {"key": "ArrowLeft", "code": "ArrowLeft", "windowsVirtualKeyCode": 37},
    "up": {"key": "ArrowUp", "code": "ArrowUp", "windowsVirtualKeyCode": 38},
    "right": {"key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39},
    "down": {"key": "ArrowDown", "code": "ArrowDown", "windowsVirtualKeyCode": 40},
    "insert": {"key": "Insert", "code": "Insert", "windowsVirtualKeyCode": 45},
    "delete": {"key": "Delete", "code": "Delete", "windowsVirtualKeyCode": 46},
    "home": {"key": "Home", "code": "Home", "windowsVirtualKeyCode": 36},
    "end": {"key": "End", "code": "End", "windowsVirtualKeyCode": 35},
    "pageup": {"key": "PageUp", "code": "PageUp", "windowsVirtualKeyCode": 33},
    "pagedown": {"key": "PageDown", "code": "PageDown", "windowsVirtualKeyCode": 34},
}
for _c in "abcdefghijklmnopqrstuvwxyz":
    CDP_KEY_MAP[_c] = {"key": _c, "code": f"Key{_c.upper()}", "windowsVirtualKeyCode": ord(_c.upper())}
for _d in "0123456789":
    CDP_KEY_MAP[_d] = {"key": _d, "code": f"Digit{_d}", "windowsVirtualKeyCode": ord(_d)}
for _i in range(1, 13):
    CDP_KEY_MAP[f"f{_i}"] = {"key": f"F{_i}", "code": f"F{_i}", "windowsVirtualKeyCode": 0x6F + _i}

class CDPController:
    def __init__(self):
        self.ws = None
        self.ws_url = None
        self.msg_id = 0
        self.lock = threading.Lock()
        self.last_check = 0.0
        self._cached_url = None

    def get_ws_url(self):
        # Nếu đã có kết nối WebSocket đang mở, không cần gọi HTTP liên tục
        if self.ws and getattr(self.ws, "connected", False) and self._cached_url:
            return self._cached_url
        now = time.time()
        if now - self.last_check < 3.0 and self._cached_url:
            return self._cached_url
        self.last_check = now
        try:
            r = requests.get("http://127.0.0.1:9222/json", timeout=0.6)
            if r.status_code == 200:
                for p in r.json():
                    if "playkuro" in p.get("url", "") or "KuroMS" in p.get("title", ""):
                        self._cached_url = p.get("webSocketDebuggerUrl")
                        return self._cached_url
        except Exception:
            pass
        self._cached_url = None
        return None

    def is_available(self):
        if self.ws and getattr(self.ws, "connected", False):
            return True
        return bool(self.get_ws_url())

    def ensure_connected(self):
        if self.ws and getattr(self.ws, "connected", False):
            return True
        url = self.get_ws_url()
        if not url:
            if self.ws:
                try: self.ws.close()
                except Exception: pass
                self.ws = None
            return False
        try:
            import websocket
            self.ws = websocket.create_connection(url, timeout=3, suppress_origin=True)
            self.ws_url = url
            return True
        except Exception:
            self.ws = None
            return False

    def focus_game(self):
        with self.lock:
            if not self.ensure_connected():
                return False
            self.msg_id += 1
            payload = {
                "id": self.msg_id,
                "method": "Runtime.evaluate",
                "params": {"expression": "let g = document.getElementById('game'); if (g && document.activeElement !== g) g.focus();"}
            }
            try:
                self.ws.send(json.dumps(payload))
                return True
            except Exception:
                return False

    def send_key(self, key_str, is_down=True):
        with self.lock:
            if not self.ensure_connected():
                return False
            k = (key_str or "").lower().strip()
            key_info = CDP_KEY_MAP.get(k)
            if not key_info:
                vk = KEY_VK_MAP.get(k, 17)
                key_info = {"key": k, "code": f"Key{k.upper()}", "windowsVirtualKeyCode": vk}
            self.msg_id += 1
            params = {
                "type": "rawKeyDown" if is_down else "keyUp",
                "windowsVirtualKeyCode": key_info["windowsVirtualKeyCode"],
                "key": key_info["key"],
                "code": key_info["code"]
            }
            if len(key_info["key"]) == 1 and is_down:
                params["text"] = key_info["key"]
                params["unmodifiedText"] = key_info["key"]
            payload = {
                "id": self.msg_id,
                "method": "Input.dispatchKeyEvent",
                "params": params
            }
            try:
                self.ws.send(json.dumps(payload))
                return True
            except Exception:
                try: self.ws.close()
                except Exception: pass
                self.ws = None
                return False

    def tap_key(self, key_str, hold_sec=0.08):
        self.send_key(key_str, is_down=True)
        time.sleep(hold_sec)
        self.send_key(key_str, is_down=False)

    def is_connected(self):
        return bool(self.ws and getattr(self.ws, "connected", False))

    def capture_canvas_crop(self, bottom_offset=220, width=550, height=180, left_offset=0):
        with self.lock:
            if not self.ensure_connected():
                return None
            self.msg_id += 1
            curr_id = self.msg_id
            expr = f"""(() => {{
                let g = document.getElementById('game');
                if (!g) return null;
                let w = g.width;
                let h = g.height;
                let rx = Math.max(0, {int(left_offset)});
                let ry = Math.max(0, h - {int(bottom_offset)});
                let rw = Math.min(w - rx, {int(width)});
                let rh = Math.min(h - ry, {int(height)});
                let off = document.createElement('canvas');
                off.width = rw;
                off.height = rh;
                let offCtx = off.getContext('2d');
                offCtx.drawImage(g, rx, ry, rw, rh, 0, 0, rw, rh);
                return off.toDataURL('image/png').split(',')[1];
            }})()"""
            payload = {
                "id": curr_id,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True}
            }
            try:
                self.ws.send(json.dumps(payload))
                while True:
                    resp = json.loads(self.ws.recv())
                    if resp.get("id") == curr_id:
                        val = resp.get("result", {}).get("result", {}).get("value")
                        if not val:
                            return None
                        raw_bytes = base64.b64decode(val)
                        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
                        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                try: self.ws.close()
                except Exception: pass
                self.ws = None
                return None

    def close_browser(self):
        with self.lock:
            if self.ensure_connected():
                try:
                    self.msg_id += 1
                    self.ws.send(json.dumps({"id": self.msg_id, "method": "Browser.close"}))
                    time.sleep(0.2)
                except Exception:
                    pass
            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass
                self.ws = None
            self._cached_url = None

    def disconnect(self):
        with self.lock:
            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass
                self.ws = None
            self._cached_url = None

cdp = CDPController()

def cleanup_on_exit():
    """Nhả toàn bộ phím đánh, phím di chuyển và ngắt kết nối CDP khi tắt exe."""
    global monitor_running, auto_attack_running, is_buffing
    monitor_running = False
    auto_attack_running = False
    is_buffing = False
    try:
        # 1. Nhả phím trên CDP (nếu trình duyệt đang mở)
        if cdp and cdp.is_available():
            atk_k = "ctrl"
            try:
                atk_k = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
            except Exception:
                pass
            cdp.send_key(atk_k, is_down=False)
            if atk_k != "ctrl":
                cdp.send_key("ctrl", is_down=False)
            for d in ("left", "right", "up", "down"):
                cdp.send_key(d, is_down=False)
            time.sleep(0.06)
            cdp.disconnect()
    except Exception:
        pass
    try:
        # 2. Nhả phím Windows Virtual Key cấp OS
        atk_k = "ctrl"
        try:
            atk_k = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
        except Exception:
            pass
        vk_code = KEY_VK_MAP.get(atk_k, 0x11)
        send_key_event(vk_code, is_down=False)
        send_key_event(0x11, is_down=False) # VK_CONTROL
    except Exception:
        pass

# Đăng ký xử lý đóng cửa sổ console Windows (Bấm X, tắt cmd, End Process, Ctrl+C)
PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

def win_exit_handler(event_type):
    # 0 = CTRL_C, 1 = CTRL_BREAK, 2 = CTRL_CLOSE, 5 = LOGOFF, 6 = SHUTDOWN
    cleanup_on_exit()
    return False

_win_exit_handler_ref = PHANDLER_ROUTINE(win_exit_handler)
try:
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_win_exit_handler_ref, True)
except Exception:
    pass

atexit.register(cleanup_on_exit)

def kill_kuroms_session():
    """
    Dừng toàn bộ luồng tự động, nhả phím và tắt hoàn toàn phiên KuroMS Web trên port 9222.
    TUYỆT ĐỐI BẢO VỆ PORT 9223 (KuroMarketTracker) VÀ CÁC TRÌNH DUYỆT KHÁC.
    """
    global auto_attack_running, auto_buff_running, auto_buff2_running, auto_buff3_running
    global anchor_running, anchor_paused_by_bot, is_buffing

    # 1. Dừng mọi trạng thái auto
    auto_attack_running = False
    auto_buff_running = False
    auto_buff2_running = False
    auto_buff3_running = False
    anchor_running = False
    anchor_paused_by_bot = False
    is_buffing = False

    # 2. Nhả phím qua CDP nếu còn kết nối
    try:
        if cdp and cdp.is_available():
            atk_k = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
            cdp.send_key(atk_k, is_down=False)
            if atk_k != "ctrl":
                cdp.send_key("ctrl", is_down=False)
            for d in ("left", "right", "up", "down"):
                cdp.send_key(d, is_down=False)
            time.sleep(0.05)
    except Exception:
        pass

    # 3. Nhả phím Windows cấp OS
    try:
        atk_k = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
        vk_code = KEY_VK_MAP.get(atk_k, 0x11)
        send_key_event(vk_code, is_down=False)
        send_key_event(0x11, is_down=False)
        for vk in (0x25, 0x26, 0x27, 0x28):
            send_key_event(vk, is_down=False)
    except Exception:
        pass

    # 4. Yêu cầu CDP đóng browser (chỉ đóng browser kết nối trên port 9222)
    try:
        if cdp:
            cdp.close_browser()
    except Exception:
        pass

    # 5. Dùng psutil để diệt tiến trình trình duyệt dành riêng cho KuroMS port 9222
    killed_count = 0
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pname = (proc.info.get('name') or '').lower()
                cmdline_list = proc.info.get('cmdline') or []
                cmdline = ' '.join(cmdline_list).lower()

                # 1. BẢO VỆ TUYỆT ĐỐI CHO KUROMARKETTRACKER (PORT 9223):
                if '9223' in cmdline or 'market' in cmdline or 'kuromarket' in cmdline:
                    continue

                # 2. CHỈ QUÉT CÁC TIẾN TRÌNH TRÌNH DUYỆT (MSEDGE, CHROME, BRAVE...):
                if not any(b in pname for b in ('msedge', 'chrome', 'brave', 'opera', 'vivaldi')):
                    continue

                # 3. CHỈ TARGET ĐÚNG CÁC TIẾN TRÌNH THUỘC PORT 9222 HOẶC USER-DATA-DIR KuroMS_Browser
                is_target = False
                if '9222' in cmdline or 'kuroms_browser' in cmdline:
                    is_target = True
                elif 'play.playkuro.com' in cmdline and '9223' not in cmdline:
                    is_target = True

                if is_target:
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        print(f"[KILL] Lỗi quét tiến trình: {e}")

    # 6. Fallback: Nếu vẫn còn cửa sổ game web, gửi WM_CLOSE (trừ market)
    try:
        hwnd = find_web_game()
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            w_title = buff.value.lower()
            if 'market' not in w_title and '9223' not in w_title:
                user32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
                time.sleep(0.2)
    except Exception:
        pass

    # 7. Đảm bảo ngắt kết nối CDP
    try:
        if cdp:
            cdp.disconnect()
    except Exception:
        pass

    return killed_count

def get_cdp_ws_url():
    return cdp.get_ws_url()

def web_game_status():
    hwnd = find_web_game()
    if cdp.is_available():
        return {"connected": True, "hwnd": int(hwnd) if hwnd else "WEB", "visible": True}
    if not hwnd:
        return {"connected": False, "hwnd": None, "visible": False}
    return {"connected": True, "hwnd": int(hwnd), "visible": bool(IsWindowVisible(hwnd))}

# Tải cấu hình đa bảng mã chống crash Windows
def load_config_file(cfg_obj, path):
    p = Path(path)
    if not p.exists():
        return False
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            cfg_obj.read(str(p), encoding=enc)
            if cfg_obj.sections():
                return True
        except Exception:
            continue
    return False

cfg = configparser.ConfigParser()
def generate_formatted_config(cfg_obj):
    b = lambda opt, fb: cfg_obj.get("bridge", opt, fallback=fb)
    d = lambda opt, fb: cfg_obj.get("detector", opt, fallback=fb)
    
    return f"""[bridge]
# Ten may tinh (dutch, fox, jira, dao, bae, fan, fan2, peo, sin, jen, minh)
machine_name = {b('machine_name', '')}

# Cho phep nhan lenh /reply tu Discord vao game (true/false)
reply_enabled = {b('reply_enabled', 'true')}


# ==================================================
# AUTO ATTACK (Danh quai)
# ==================================================
# Phim tat tren ban phim de BAT/TAT tu danh (nen de F1, F6... tranh de chu cai nhu g gay can tro khi go chat)
attack_hotkey = {b('attack_hotkey', 'f1')}
# Phim skill danh trong game (ctrl, g, shift, space, x...)
attack_key = {b('attack_key', 'ctrl')}
attack_interval_ms = {b('attack_interval_ms', '50')}
attack_mode = {b('attack_mode', 'hold')}


# ==================================================
# AUTO BUFF 1
# ==================================================
autobuff_hotkey = {b('autobuff_hotkey', 'f2')}
autobuff_key = {b('autobuff_key', 't')}
autobuff_interval_ms = {b('autobuff_interval_ms', '240000')}
# Thoi gian cho nhan vat mua xong skill/macro (ms). 900ms cho skill don; Neu gan macro 3 skill in-game thi de 3500!
autobuff_delay_ms = {b('autobuff_delay_ms', '900')}


# ==================================================
# AUTO BUFF 2
# ==================================================
autobuff2_hotkey = {b('autobuff2_hotkey', 'f8')}
autobuff2_key = {b('autobuff2_key', 'pageup')}
autobuff2_interval_ms = {b('autobuff2_interval_ms', '601000')}
autobuff2_delay_ms = {b('autobuff2_delay_ms', '900')}


# ==================================================
# AUTO BUFF 3
# ==================================================
autobuff3_hotkey = {b('autobuff3_hotkey', 'f7')}
autobuff3_key = {b('autobuff3_key', 'v')}
autobuff3_interval_ms = {b('autobuff3_interval_ms', '31500')}
autobuff3_delay_ms = {b('autobuff3_delay_ms', '500')}


# ==================================================
# AUTO ANCHOR (Giu vi tri theo Minimap)
# ==================================================
anchor_enabled = {b('anchor_enabled', 'false')}
anchor_hotkey = {b('anchor_hotkey', '-')}
anchor_tolerance = {b('anchor_tolerance', '2')}
anchor_interval_ms = {b('anchor_interval_ms', '800')}
anchor_face_direction = {b('anchor_face_direction', 'right')}


[detector]
# ==================================================
# IMAGE DETECTOR (Canh bao GM / Trade tren KuroMS Web)
# ==================================================
enabled = {d('enabled', 'false')}
ntfy_server = {d('ntfy_server', 'https://ntfy.sh')}
ntfy_topic = {d('ntfy_topic', '')}
scan_interval = {d('scan_interval', '0.5')}
threshold = {d('threshold', '0.86')}
cooldown = {d('cooldown', '30.0')}
scales = {d('scales', '1.0, 1.1, 1.25')}

# ==================================================
# VUNG QUET KHUNG CHAT (FLEXIBLE ROI - TUY CHINH SIZE)
# Tu dong thich ung theo Canvas Game, khong phu thuoc size trinh duyet
# ==================================================
# Khoang cach tu day man hinh game len dinh khung chat (pixel)
chat_roi_bottom = {d('chat_roi_bottom', '180')}
# Chieu rong vung quet (pixel)
chat_roi_width = {d('chat_roi_width', '550')}
# Chieu cao vung quet (pixel) - da nhich len tranh dinh chatbar o day
chat_roi_height = {d('chat_roi_height', '115')}
# Khoang cach lech tu mep trai (pixel, mac dinh 0)
chat_roi_left = {d('chat_roi_left', '0')}
"""

if not load_config_file(cfg, CONFIG_PATH):
    print("Không tìm thấy config.ini, sẽ tự động tạo mới...")

WORKER_URL = "https://maple-discord-bridge.dutch25.workers.dev/"
MACHINE_NAME = cfg.get("bridge", "machine_name", fallback="").strip()
MAX_MESSAGE_LENGTH = 70
PUSHER_KEY = "0233d516a943fa684018"
PUSHER_CLUSTER = "ap1"
DISCORD_WEBHOOK_URL = ""

if not MACHINE_NAME:
    print("==================================================")
    print(" LẦN ĐẦU CHẠY: CẦN THIẾT LẬP TÊN MÁY TÍNH (WEB)")
    print("==================================================")
    print(" Chọn máy tính của bạn:")
    print(" 1. dutch")
    print(" 2. fox")
    print(" 3. jira")
    print(" 4. dao")
    print(" 5. bae")
    print(" 6. fan")
    print(" 7. fan2")
    print(" 8. peo")
    print(" 9. sin")
    print(" 10. jen")
    print(" 11. minh")
    print("==================================================")
    while True:
        choice = input(" Nhập số (1-11) hoặc gõ tên máy tính: ").strip().lower()
        mapping = {"1": "dutch", "2": "fox", "3": "jira", "4": "dao", "5": "bae", "6": "fan", "7": "fan2", "8": "peo", "9": "sin", "10": "jen", "11": "minh"}
        if choice in mapping:
            MACHINE_NAME = mapping[choice]
            break
        elif choice in mapping.values():
            MACHINE_NAME = choice
            break
        else:
            print(" [!] Lựa chọn không hợp lệ, vui lòng thử lại!")
    if not cfg.has_section("bridge"):
        cfg.add_section("bridge")
    cfg.set("bridge", "machine_name", MACHINE_NAME)
    cfg.set("bridge", "reply_enabled", "true")
    if not cfg.has_section("detector"):
        cfg.add_section("detector")
        cfg.set("detector", "enabled", "false")
        cfg.set("detector", "ntfy_server", "https://ntfy.sh")
        cfg.set("detector", "ntfy_topic", "")
        cfg.set("detector", "scan_interval", "0.5")
        cfg.set("detector", "threshold", "0.86")
        cfg.set("detector", "cooldown", "30.0")
        cfg.set("detector", "scales", "1.0, 1.1, 1.25")
        cfg.set("detector", "chat_roi_bottom", "180")
        cfg.set("detector", "chat_roi_width", "550")
        cfg.set("detector", "chat_roi_height", "115")
        cfg.set("detector", "chat_roi_left", "0")
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(generate_formatted_config(cfg))
    print(f" [OK] Đã lưu máy tính: {MACHINE_NAME.upper()} và tạo file config.ini chuẩn!\n")

# Tự động đồng bộ các trường cấu hình mới vào config.ini nếu người dùng dùng file config cũ
DEFAULT_CONFIG = {
    "attack_hotkey": "f1",
    "attack_key": "ctrl",
    "attack_interval_ms": "50",
    "attack_mode": "hold",
    "autobuff_hotkey": "f2",
    "autobuff_key": "t",
    "autobuff_interval_ms": "240000",
    "autobuff_delay_ms": "900",
    "autobuff2_hotkey": "f8",
    "autobuff2_key": "pageup",
    "autobuff2_interval_ms": "601000",
    "autobuff2_delay_ms": "900",
    "autobuff3_hotkey": "f7",
    "autobuff3_key": "v",
    "autobuff3_interval_ms": "31500",
    "autobuff3_delay_ms": "500",
    "anchor_enabled": "false",
    "anchor_hotkey": "-",
    "anchor_tolerance": "2",
    "anchor_interval_ms": "800",
    "anchor_face_direction": "right",
    "reply_enabled": "true",
}

DEFAULT_DETECTOR_CONFIG = {
    "enabled": "false",
    "ntfy_server": "https://ntfy.sh",
    "ntfy_topic": "",
    "scan_interval": "0.5",
    "threshold": "0.86",
    "cooldown": "30.0",
    "scales": "1.0, 1.1, 1.25",
    "chat_roi_bottom": "180",
    "chat_roi_width": "550",
    "chat_roi_height": "115",
    "chat_roi_left": "0",
}

if not cfg.has_section("bridge"):
    cfg.add_section("bridge")
if not cfg.has_section("detector"):
    cfg.add_section("detector")

config_updated = False
for key, default_val in DEFAULT_CONFIG.items():
    if not cfg.has_option("bridge", key):
        cfg.set("bridge", key, default_val)
        config_updated = True

for key, default_val in DEFAULT_DETECTOR_CONFIG.items():
    if not cfg.has_option("detector", key):
        cfg.set("detector", key, default_val)
        config_updated = True

if config_updated:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(generate_formatted_config(cfg))
        print("[CONFIG] Đã tự động cập nhật các tùy chọn mới vào config.ini!")
    except Exception as e:
        pass

print(f"\n=======================================================")
print(f"   MAPLE DISCORD BRIDGE (PHIÊN BẢN KUROMS WEB)")
print(f"   Máy: {MACHINE_NAME.upper()} | Trình duyệt: Chrome/Edge/Firefox")
print(f"=======================================================\n")

# Biến cờ kiểm soát các luồng
monitor_running = True
auto_attack_running = False
auto_buff_running = False
auto_buff2_running = False
auto_buff3_running = False
buff_lock = threading.Lock()
is_buffing = False
anchor_running = False
anchor_paused_by_bot = False
anchor_x = None
anchor_y = None

def get_vk_and_lparams(key_str, default_vk=0x11):
    vk = default_vk
    key_str = (key_str or "").lower().strip()
    if key_str in KEY_VK_MAP:
        vk = KEY_VK_MAP[key_str]
    elif len(key_str) == 1 and 'a' <= key_str <= 'z':
        vk = ord(key_str.upper())
    elif len(key_str) == 1 and '0' <= key_str <= '9':
        vk = ord(key_str)
        
    scan_code = user32.MapVirtualKeyW(vk, 0)
    if scan_code == 0 and vk == 0x11:
        scan_code = 0x1D
    
    lparam = 1 | (scan_code << 16)
    lparam_up = lparam | 0xC0000000
    return vk, lparam, lparam_up

VK_TO_CHAR = {
    0x41: "a", 0x42: "b", 0x43: "c", 0x44: "d", 0x45: "e", 0x46: "f",
    0x47: "g", 0x48: "h", 0x49: "i", 0x4A: "j", 0x4B: "k", 0x4C: "l",
    0x4D: "m", 0x4E: "n", 0x4F: "o", 0x50: "p", 0x51: "q", 0x52: "r",
    0x53: "s", 0x54: "t", 0x55: "u", 0x56: "v", 0x57: "w", 0x58: "x",
    0x59: "y", 0x5A: "z",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
    0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x21: "pageup", 0x22: "pagedown", 0x24: "home", 0x23: "end",
    0x2D: "insert", 0x2E: "delete", 0x20: "space", 0x11: "ctrl", 0x12: "alt", 0x10: "shift"
}
for _fi in range(1, 13):
    VK_TO_CHAR[0x6F + _fi] = f"f{_fi}"

def parse_buff_key(raw_msg):
    raw = (raw_msg or "").strip().lower()
    if raw.startswith("0x"):
        try:
            vk = int(raw, 16)
            k_name = VK_TO_CHAR.get(vk, chr(vk).lower() if 0x20 <= vk <= 0x7E else hex(vk))
            return vk, k_name
        except Exception:
            pass
    if raw in KEY_VK_MAP:
        return KEY_VK_MAP[raw], raw
    elif len(raw) == 1 and 'a' <= raw <= 'z':
        return ord(raw.upper()), raw
    return 0x46, "f"

def toggle_auto_attack():
    global auto_attack_running, anchor_running, anchor_paused_by_bot, anchor_x
    auto_attack_running = not auto_attack_running
    key_str = cfg.get("bridge", "attack_key", fallback="ctrl").upper()
    ms = cfg.getint("bridge", "attack_interval_ms", fallback=50)
    mode = cfg.get("bridge", "attack_mode", fallback="hold").lower().strip()
    if auto_attack_running:
        if anchor_paused_by_bot:
            anchor_running = True
            anchor_paused_by_bot = False
            print(f"[ANCHOR] Tự động TIẾP TỤC giữ vị trí tại X={anchor_x} do Auto-Attack đã BẬT!")
        print(f"\n[AUTO-ATTACK] BẬT tự đánh ({mode.upper()} phím {key_str} mỗi {ms}ms)")
    else:
        if anchor_running:
            anchor_running = False
            anchor_paused_by_bot = True
            print(f"[ANCHOR] Tự động TẠM DỪNG giữ vị trí do Auto-Attack đã TẮT (Vẫn nhớ toạ độ X={anchor_x})!")
        print("\n[AUTO-ATTACK] TẮT tự đánh")

def toggle_auto_buff():
    global auto_buff_running
    auto_buff_running = not auto_buff_running
    key_str = cfg.get("bridge", "autobuff_key", fallback="t").upper()
    ms = cfg.getint("bridge", "autobuff_interval_ms", fallback=240000)
    state = "BẬT" if auto_buff_running else "TẮT"
    print(f"\n[AUTO-BUFF 1] {state} (Bấm {key_str} mỗi {ms}ms)")

def toggle_auto_buff2():
    global auto_buff2_running
    auto_buff2_running = not auto_buff2_running
    key_str = cfg.get("bridge", "autobuff2_key", fallback="pageup").upper()
    ms = cfg.getint("bridge", "autobuff2_interval_ms", fallback=601000)
    state = "BẬT" if auto_buff2_running else "TẮT"
    print(f"\n[AUTO-BUFF 2] {state} (Bấm {key_str} mỗi {ms}ms)")

def toggle_auto_buff3():
    global auto_buff3_running
    auto_buff3_running = not auto_buff3_running
    key_str = cfg.get("bridge", "autobuff3_key", fallback="v").upper()
    ms = cfg.getint("bridge", "autobuff3_interval_ms", fallback=31500)
    state = "BẬT" if auto_buff3_running else "TẮT"
    print(f"\n[AUTO-BUFF 3] {state} (Bấm {key_str} mỗi {ms}ms)")

def auto_attack_thread():
    key_str = cfg.get("bridge", "attack_key", fallback="ctrl")
    interval_ms = cfg.getint("bridge", "attack_interval_ms", fallback=50)
    mode = cfg.get("bridge", "attack_mode", fallback="hold").lower().strip()
    vk_code, lparam, lparam_up = get_vk_and_lparams(key_str, default_vk=0x11)
    interval_sec = max(0.02, interval_ms / 1000.0)
    was_running = False
    was_foreground = False
    win32_held = False

    while monitor_running:
        if auto_attack_running and not is_buffing:
            # 1. ƯU TIÊN 1: Chạy ngầm 100% qua CDP (Game mở bằng Mo_KuroMS.bat)
            if cdp.is_available():
                if mode == "hold":
                    # Ở chế độ hold trên web: Gửi keydown đều đặn
                    # - Chống mất phím khi trình duyệt bị unfocus / blur
                    # - Đảm bảo sau khi buff xong sẽ tiếp tục bắn ngay lập tức
                    cdp.send_key(key_str, is_down=True)
                    time.sleep(interval_sec)
                else:
                    cdp.tap_key(key_str, hold_sec=0.03)
                    time.sleep(interval_sec)
                was_running = True
            else:
                # 2. FALLBACK WIN32: Trình duyệt thường (không có cổng 9222)
                hwnd = find_web_game()
                if hwnd:
                    is_fg = (hwnd == user32.GetForegroundWindow())
                    if is_fg:
                        was_foreground = True
                        if mode == "hold":
                            if not win32_held:
                                send_key_event(vk_code, is_down=True)
                                win32_held = True
                            time.sleep(0.05)
                        else:
                            send_key_press(vk_code, hold_time=0.03)
                            time.sleep(interval_sec)
                    else:
                        # CHỐNG LIỆT PHÍM: Nếu tab ra ngoài, LẬP TỨC nhả phím vật lý để không bị kẹt Ctrl khi chat Discord!
                        if was_foreground or win32_held:
                            send_key_event(vk_code, is_down=False)
                            win32_held = False
                            was_foreground = False
                        time.sleep(0.2)
                was_running = True
        else:
            if was_running or win32_held:
                if cdp.is_available():
                    cdp.send_key(key_str, is_down=False)
                send_key_event(vk_code, is_down=False)
                win32_held = False
                was_running = False
                was_foreground = False
            time.sleep(0.05)

def run_auto_buff(key_opt, interval_opt, delay_opt, get_flag, default_key, default_ms, name, start_offset_sec=2.0):
    interval_sec = max(1.0, cfg.getint("bridge", interval_opt, fallback=default_ms) / 1000.0)
    last_time = 0.0
    was_running_prev = False

    while monitor_running:
        is_active = get_flag()
        if is_active:
            if not was_running_prev:
                last_time = 0.0
                was_running_prev = True

            now = time.time()
            interval_sec = max(1.0, cfg.getint("bridge", interval_opt, fallback=default_ms) / 1000.0)
            if now - last_time >= interval_sec:
                raw_keys = cfg.get("bridge", key_opt, fallback=default_key).strip().lower()
                key_list = [k.strip() for k in raw_keys.split(',') if k.strip()]
                if not key_list:
                    key_list = [default_key]
                delay_ms = cfg.getint("bridge", delay_opt, fallback=900)

                global is_buffing
                with buff_lock:
                    is_buffing = True
                    try:
                        # 1. Tạm nhả phím tấn công trước khi buff
                        atk_key = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
                        atk_vk = KEY_VK_MAP.get(atk_key, 0x11)
                        if cdp.is_available():
                            cdp.send_key(atk_key, is_down=False)
                        else:
                            send_key_event(atk_vk, is_down=False)

                        # Chờ 0.5s để luồng đánh dừng hẳn và nhân vật về trạng thái idle
                        time.sleep(0.5)

                        # Đảm bảo canvas nhận focus
                        if cdp.is_available():
                            cdp.focus_game()

                        # 2. Gửi phím buff (hỗ trợ cả danh sách phím)
                        for k in key_list:
                            if cdp.is_available():
                                cdp.tap_key(k, hold_sec=0.08)
                            else:
                                hwnd = find_web_game()
                                if hwnd:
                                    vk = KEY_VK_MAP.get(k, 0x54)
                                    if hwnd == user32.GetForegroundWindow():
                                        send_key_press(vk, 0.08)
                                    else:
                                        prev = user32.GetForegroundWindow()
                                        user32.SetForegroundWindow(hwnd)
                                        time.sleep(0.04)
                                        send_key_press(vk, 0.08)
                                        if prev and prev != hwnd:
                                            user32.SetForegroundWindow(prev)
                            time.sleep(0.08)

                        print(f"\n[{name}] Đã tự động buff phím {raw_keys.upper()}!")

                        # 3. Delay chờ hoàn tất animation cast skill (thêm buffer an toàn cho macro)
                        cast_delay = max(1.0, (delay_ms + 300) / 1000.0)
                        time.sleep(cast_delay)

                    finally:
                        is_buffing = False

                last_time = time.time()
            time.sleep(0.1)
        else:
            was_running_prev = False
            time.sleep(0.2)

def auto_buff1_thread():
    run_auto_buff("autobuff_key", "autobuff_interval_ms", "autobuff_delay_ms", lambda: auto_buff_running, "t", 240000, "AUTO-BUFF 1", start_offset_sec=2.0)

def auto_buff2_thread():
    run_auto_buff("autobuff2_key", "autobuff2_interval_ms", "autobuff2_delay_ms", lambda: auto_buff2_running, "pageup", 601000, "AUTO-BUFF 2", start_offset_sec=5.0)

def auto_buff3_thread():
    run_auto_buff("autobuff3_key", "autobuff3_interval_ms", "autobuff3_delay_ms", lambda: auto_buff3_running, "v", 31500, "AUTO-BUFF 3", start_offset_sec=8.0)

def get_web_game_rect(hwnd):
    """
    Lấy toạ độ khung chơi game bên trong trình duyệt.
    Tự động trừ phần thanh tab/URL bar nếu không ở chế độ Fullscreen.
    """
    rect = RECT()
    if not GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    p = POINT(0, 0)
    if not ClientToScreen(hwnd, ctypes.byref(p)):
        return None
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None

    # Kiểm tra xem có phải chế độ Fullscreen (F11) hoặc chế độ App không viền hay không
    # Màn hình chuẩn Desktop thường h >= 1000, nếu window chiếm hết màn hình thì top_offset = 0
    screen_h = user32.GetSystemMetrics(1)
    if abs(h - screen_h) <= 5:
        top_offset = 0
    else:
        # Trình duyệt thông thường có tab bar + thanh URL cao ~85px
        top_offset = 85

    canvas_top = p.y + top_offset
    canvas_h = max(300, h - top_offset)
    return p.x, canvas_top, w, canvas_h

def send_chat_cdp(ws_url, text):
    import websocket
    ws = websocket.create_connection(ws_url, timeout=3, suppress_origin=True)
    try:
        def cdp_call(method, params):
            ws.send(json.dumps({"id": 1, "method": method, "params": params}))
            while True:
                resp = json.loads(ws.recv())
                if resp.get("id") == 1:
                    return resp

        # 1. Gán text và kích hoạt event input vào chat-input (ngầm 100%)
        script = f"""
        (() => {{
            let inp = document.getElementById('chat-input');
            if (!inp) return false;
            inp.focus();
            inp.value = {json.dumps(text)};
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            return true;
        }})()
        """
        cdp_call("Runtime.evaluate", {"expression": script})
        time.sleep(0.05)

        # 2. Gửi phím Enter LẦN 1 để nộp nội dung chat
        cdp_call("Input.dispatchKeyEvent", {
            "type": "rawKeyDown",
            "windowsVirtualKeyCode": 13,
            "unmodifiedText": "\r",
            "text": "\r",
            "key": "Enter",
            "code": "Enter"
        })
        time.sleep(0.04)
        cdp_call("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "windowsVirtualKeyCode": 13,
            "unmodifiedText": "\r",
            "text": "\r",
            "key": "Enter",
            "code": "Enter"
        })
        time.sleep(0.08)

        # 3. Gửi thêm 1 lần Enter nữa để tắt khung chat / tiếp tục tự đánh (y hệt bản client desktop line 198)
        cdp_call("Input.dispatchKeyEvent", {
            "type": "rawKeyDown",
            "windowsVirtualKeyCode": 13,
            "unmodifiedText": "\r",
            "text": "\r",
            "key": "Enter",
            "code": "Enter"
        })
        time.sleep(0.04)
        cdp_call("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "windowsVirtualKeyCode": 13,
            "unmodifiedText": "\r",
            "text": "\r",
            "key": "Enter",
            "code": "Enter"
        })
        time.sleep(0.08)

        # 4. Đảm bảo thoát hoàn toàn state chatbar: blur input, dispatch JS enter và focus canvas game
        cdp_call("Runtime.evaluate", {
            "expression": """(() => {
                let inp = document.getElementById('chat-input');
                if (inp) {
                    let evDown = new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true});
                    let evUp = new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true});
                    inp.dispatchEvent(evDown);
                    inp.dispatchEvent(evUp);
                    inp.value = '';
                    inp.blur();
                }
                let g = document.getElementById('game');
                if (g) g.focus();
            })()"""
        })
        time.sleep(0.15)
        return True, "Đã gửi chat ngầm vào KuroMS Web thành công!"
    except Exception as e:
        return False, f"Lỗi gửi chat: {e}"
    finally:
        try:
            ws.close()
        except Exception:
            pass

def capture_screenshot_cdp(ws_url, filename):
    import websocket
    ws = websocket.create_connection(ws_url, timeout=5, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == 1:
                img_data = resp["result"]["data"]
                with open(filename, "wb") as f:
                    f.write(base64.b64decode(img_data))
                return True
    except Exception:
        return False
    finally:
        try:
            ws.close()
        except Exception:
            pass
    return False

def send_chat(text):
    text = text.strip().replace("\r", " ").replace("\n", " ")
    if not text:
        return False, "Tin nhắn rỗng."

    # 0. Tạm dừng bot (auto-attack và auto-buff) trước khi chat để tránh xung đột phím (y hệt bản client line 150)
    global auto_attack_running
    was_attack_running = auto_attack_running
    global is_buffing
    with buff_lock:
        is_buffing = True
        try:
            if was_attack_running:
                atk_key = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
                atk_vk = KEY_VK_MAP.get(atk_key, 0x11)
                if cdp.is_available():
                    cdp.send_key(atk_key, is_down=False)
                else:
                    send_key_event(atk_vk, is_down=False)
                print("\n[REPLY] Đã tạm dừng Auto-Attack ngầm để bắt đầu gõ chat...")
                time.sleep(0.4) # Chờ luồng attack nhả phím hoàn toàn

            # 1. Ưu tiên gửi ngầm 100% qua CDP (Hoàn toàn không cần focus / không giật màn hình)
            ws_url = get_cdp_ws_url()
            if ws_url:
                ok, res = send_chat_cdp(ws_url, text)
                if ok:
                    return True, res

            # 2. Fallback: Gửi qua Win32 API (Lưu và khôi phục lại ngay cửa sổ user đang làm việc)
            hwnd = find_web_game()
            if not hwnd:
                return False, "Không tìm thấy cửa sổ KuroMS Web (Hãy mở https://play.playkuro.com/ trên trình duyệt)"

            prev_hwnd = user32.GetForegroundWindow()
            try:
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.08)

                # 1. Nhấn Enter mở khung chat
                send_key_press(VK_RETURN, 0.04)
                time.sleep(0.15)

                # 2. Gõ từng ký tự Unicode
                for ch in text:
                    send_unicode_char(ch)

                time.sleep(0.06)

                # 3. Nhấn Enter gửi chat
                send_key_press(VK_RETURN, 0.04)
                time.sleep(0.06)

                # 4. Nhấn Enter lần 2 để đóng khung chat (y hệt bản client line 198)
                send_key_press(VK_RETURN, 0.04)
                time.sleep(0.2)
            finally:
                if prev_hwnd and prev_hwnd != hwnd:
                    user32.SetForegroundWindow(prev_hwnd)

            return True, "Đã gửi chat vào KuroMS Web thành công!"
        finally:
            is_buffing = False
            if was_attack_running:
                print("[REPLY] Đã bật lại Auto-Attack sau khi chat xong!")

def send_screenshot():
    filename = f"screenshot_{MACHINE_NAME}.png"

    # 1. Ưu tiên chụp ngầm qua CDP (chuẩn 100% canvas, không dính thanh công cụ)
    ws_url = get_cdp_ws_url()
    if ws_url:
        if capture_screenshot_cdp(ws_url, filename):
            return True, filename

    # 2. Fallback: Chụp màn hình qua mss
    hwnd = find_web_game()
    if not hwnd:
        return False, "Không tìm thấy cửa sổ KuroMS Web."
    box = get_web_game_rect(hwnd)
    if not box:
        return False, "Không lấy được toạ độ cửa sổ KuroMS Web."
    left, top, w, h = box

    try:
        import mss
        with getattr(mss, "MSS", mss.mss)() as sct:
            shot = sct.grab({"left": left, "top": top, "width": w, "height": h})
            mss.tools.to_png(shot.rgb, shot.size, output=filename)
            return True, filename
    except Exception as e:
        return False, f"Lỗi chụp ảnh: {e}"

# Quét viền sáng GM
def scan_gm_glow_bar(chat_roi, min_w=80):
    if chat_roi is None or chat_roi.size == 0 or chat_roi.shape[0] < 15 or chat_roi.shape[1] < min_w:
        return []

    gray = cv2.cvtColor(chat_roi, cv2.COLOR_BGR2GRAY)
    b, g, r = cv2.split(chat_roi.astype(int))

    is_bright = gray > 165
    is_neutral = (np.abs(r - g) <= 14) & (np.abs(b - g) <= 14) & (np.abs(r - b) <= 14)
    mask = (is_bright & is_neutral).astype(np.uint8) * 255

    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 2))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 2))
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    bars = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, close_kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bars)
    detected = []
    for i in range(1, num_labels):
        bx, by, bw, bh, area = stats[i]
        if bx <= 20 and bw >= min_w and 6 <= bh <= 35:
            bar_crop = chat_roi[by:by+bh, bx:bx+bw]
            dark_count = np.sum(cv2.cvtColor(bar_crop, cv2.COLOR_BGR2GRAY) < 130)
            if dark_count >= 15:
                detected.append({'x': bx, 'y': by, 'w': bw, 'h': bh, 'dark_count': int(dark_count)})
    return detected

def is_smega_patch(patch_bgr):
    if patch_bgr is None or patch_bgr.shape[0] < 3 or patch_bgr.shape[1] < 3:
        return False
    bg_sample = patch_bgr[0:3, :]
    mean_b, mean_g, mean_r = np.mean(bg_sample, axis=(0, 1))
    return bool((mean_r - mean_g > 18) and (mean_b - mean_g > 12))

def notify_detector_ntfy(server, topic, message):
    if not topic or not topic.strip():
        return
    try:
        r = requests.post(
            f"{server.rstrip('/')}/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": f"KuroMS Web GM Alert: {MACHINE_NAME.upper()}",
                "Priority": "urgent",
                "Tags": "warning,rotating_light"
            },
            timeout=5
        )
        print(f"[DETECTOR NTFY] Đã gửi thông báo thành công (HTTP {r.status_code}) tới topic '{topic}': {message}")
    except Exception as e:
        print(f"[DETECTOR NTFY ERROR] Lỗi gửi NTFY: {e}")

def notify_detector_discord(name, score, chat_roi=None):
    try:
        img_bytes = None
        if chat_roi is not None:
            _, buffer = cv2.imencode('.png', chat_roi)
            img_bytes = buffer.tobytes()

        msg = f"Máy: {MACHINE_NAME.upper()} vừa phát hiện: {name}"
        files = {"file": ("alert_chatbox.png", img_bytes, "image/png")} if img_bytes else None

        requests.post(f"{WORKER_URL.rstrip('/')}/api/alert", data={
            "machine": MACHINE_NAME,
            "message": msg,
            "channel_id": "1560437669635432541"
        }, files=files, timeout=10)
        print(f"[DETECTOR DISCORD] Đã gửi cảnh báo lên Discord: {msg}")
    except Exception as e:
        print(f"[DETECTOR DISCORD ERROR] {e}")

# Luồng quét GM Detector cho bản Web
def detector_thread():
    if not cfg.getboolean("detector", "enabled", fallback=False):
        print("[DETECTOR WEB] Tính năng Detector đang TẮT theo config.ini (enabled = false).")
        return

    cooldown = cfg.getfloat("detector", "cooldown", fallback=30.0)
    interval = cfg.getfloat("detector", "scan_interval", fallback=0.5)
    threshold = cfg.getfloat("detector", "threshold", fallback=0.86)

    # Đọc cấu hình Flexible ROI cho khung chat
    roi_bottom = cfg.getint("detector", "chat_roi_bottom", fallback=180)
    roi_w = cfg.getint("detector", "chat_roi_width", fallback=550)
    roi_h = cfg.getint("detector", "chat_roi_height", fallback=115)
    roi_left = cfg.getint("detector", "chat_roi_left", fallback=0)

    # Nạp mẫu templates
    template_defs = [
        ("GM cherries", "image1.png"),
        ("GM hyuni", "image2.png"),
        ("Trade", "image3.png"),
        ("GM raia", "image4.png"),
    ]
    loaded_templates = []
    for name, filename in template_defs:
        file_path = TEMPLATE_DIR / filename
        if file_path.exists():
            raw = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
            if raw is None: continue
            h, w = raw.shape[:2]
            if "image2" in filename.lower() and h >= 14:
                clean = raw[4:13, 6:38]
            elif "image4" in filename.lower() and h >= 14:
                clean = raw[4:13, 5:31]
            elif "image1" in filename.lower() and w >= 40:
                clean = raw[:, 4:46]
            else:
                clean = raw
            clean_gray = cv2.cvtColor(clean, cv2.COLOR_BGR2GRAY)
            is_text = np.mean(clean_gray) > 120 and np.min(clean_gray) < 80
            variants = [("normal", clean, clean_gray)]
            if is_text:
                variants.append(("inverted", 255 - clean, 255 - clean_gray))
            loaded_templates.append((name, variants))

    print(f"[DETECTOR WEB] Đã khởi chạy detector web linh hoạt qua CDP Canvas ({len(loaded_templates)} mẫu | ROI: {roi_w}x{roi_h} | Cooldown: {cooldown}s)!")
    last_alert = 0.0
    import mss

    with mss.mss() as sct:
        while monitor_running:
            chat_roi = None

            # 1. ƯU TIÊN 1: Trích xuất trực tiếp từ Canvas qua CDP (Siêu nét 1:1, không sợ resize cửa sổ, không sợ che khuất)
            if cdp.is_available():
                chat_roi = cdp.capture_canvas_crop(bottom_offset=roi_bottom, width=roi_w, height=roi_h, left_offset=roi_left)

            # 2. FALLBACK: Chụp màn hình qua mss nếu không có kết nối CDP
            if chat_roi is None:
                hwnd = find_web_game()
                if not hwnd or not IsWindowVisible(hwnd):
                    time.sleep(1)
                    continue
                box = get_web_game_rect(hwnd)
                if not box:
                    time.sleep(interval)
                    continue
                left, top, w, h = box
                try:
                    shot = np.array(sct.grab({"left": left, "top": top, "width": w, "height": h}))
                    frame_bgr = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
                    chat_roi = frame_bgr[max(0, h - roi_bottom):max(30, h - max(0, roi_bottom - roi_h)), roi_left:min(w, roi_left + roi_w)]
                except Exception:
                    time.sleep(interval)
                    continue

            if chat_roi is None or chat_roi.size == 0:
                time.sleep(interval)
                continue

            found = None
            best = 0.0
            matched_box = None

            # 1. Quét viền sáng GM
            gm_bars = scan_gm_glow_bar(chat_roi, min_w=80)
            if gm_bars:
                found = "GM Chat (Viền sáng GM)"
                best = 1.0
            else:
                # 2. Quét template matching
                chat_gray = cv2.cvtColor(chat_roi, cv2.COLOR_BGR2GRAY)
                for name, variants in loaded_templates:
                    for v_tag, tmpl_bgr, tmpl_gray in variants:
                        th, tw = tmpl_gray.shape[:2]
                        if th > chat_gray.shape[0] or tw > chat_gray.shape[1]:
                            continue
                        res = cv2.matchTemplate(chat_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
                        _, score, _, max_loc = cv2.minMaxLoc(res)
                        if score >= threshold:
                            x, y = max_loc
                            patch_bgr = chat_roi[y:y+th, x:x+tw]
                            if is_smega_patch(patch_bgr):
                                continue
                            # Khóa biên từ (loại trừ từ ghép như Raises)
                            if x + tw + 4 <= chat_gray.shape[1]:
                                after_patch = chat_gray[y:y+th, x+tw:x+tw+5]
                                if "inverted" in v_tag and np.sum(after_patch[3:6, :] > 140) >= 3:
                                    continue
                                elif "normal" in v_tag and np.sum(after_patch[3:6, :] < 130) >= 3:
                                    continue
                            res_bgr = cv2.matchTemplate(patch_bgr, tmpl_bgr, cv2.TM_CCOEFF_NORMED)
                            if float(res_bgr[0, 0]) >= (threshold - 0.08):
                                if score > best:
                                    best = score
                                    found = name
                                    matched_box = (x, y, tw, th)
                                break
                    if found: break

            if found and best >= threshold:
                now = time.time()
                if now - last_alert >= cooldown:
                    print(f"\n[DETECTOR ALERT WEB] Phát hiện: {found} (Tỷ lệ khớp: {best:.3f})")
                    topic = cfg.get("detector", "ntfy_topic", fallback="").strip()
                    server = cfg.get("detector", "ntfy_server", fallback="https://ntfy.sh").strip()
                    if topic:
                        notify_detector_ntfy(server, topic, f"Máy: {MACHINE_NAME.upper()} vừa phát hiện: {found}")

                    # 2. Gửi ảnh lên Discord qua Worker (Trade thì chỉ báo NTFY, không spam Discord)
                    if "trade" not in found.lower():
                        alert_crop = chat_roi.copy()
                        if gm_bars:
                            for b in gm_bars:
                                cv2.rectangle(alert_crop, (b['x'], b['y']), (b['x'] + b['w'], b['y'] + b['h']), (0, 255, 255), 2)
                        elif matched_box:
                            mx, my, mw, mh = matched_box
                            cv2.rectangle(alert_crop, (mx, my), (mx + mw, my + mh), (0, 255, 255), 2)
                        notify_detector_discord(found, best, chat_roi=alert_crop)

                    last_alert = now

            time.sleep(interval)

# Minimap Auto-Anchor cho Web
def scan_web_minimap(frame_bgr):
    # Minimap trong KuroMS Web nằm ở góc trên bên trái canvas (x=0..350, y=0..250)
    h, w = frame_bgr.shape[:2]
    crop = frame_bgr[0:min(h, 250), 0:min(w, 350)]
    yellow = (crop[:, :, 2] > 200) & (crop[:, :, 1] > 200) & (crop[:, :, 0] < 80)
    y_idx, x_idx = np.where(yellow)
    if len(y_idx) >= 15:
        return int(np.mean(x_idx)), int(np.mean(y_idx))
    return None

def anchor_thread():
    global anchor_running, anchor_x, anchor_y
    interval = cfg.getfloat("bridge", "anchor_interval_ms", fallback=800.0) / 1000.0
    tolerance = cfg.getint("bridge", "anchor_tolerance", fallback=2)
    face_dir = cfg.get("bridge", "anchor_face_direction", fallback="right").strip().lower()

    import mss
    with mss.mss() as sct:
        while monitor_running:
            if not anchor_running or anchor_x is None:
                time.sleep(0.5)
                continue

            hwnd = find_web_game()
            if not hwnd:
                time.sleep(1)
                continue

            box = get_web_game_rect(hwnd)
            if not box:
                time.sleep(0.5)
                continue
            left, top, w, h = box

            try:
                shot = np.array(sct.grab({"left": left, "top": top, "width": min(w, 400), "height": min(h, 300)}))
                frame = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
                cur_pos = scan_web_minimap(frame)
            except Exception:
                time.sleep(interval)
                continue

            if cur_pos is None:
                time.sleep(interval)
                continue

            cx, cy = cur_pos
            dx = cx - anchor_x
            if abs(dx) > tolerance:
                move_k = "left" if dx > 0 else "right"
                face_k = "left" if face_dir == "left" else "right"
                move_vk = VK_LEFT if dx > 0 else VK_RIGHT
                face_vk = VK_LEFT if face_dir == "left" else VK_RIGHT
                walk_duration = min(0.6, max(0.08, abs(dx) * 0.05))

                # Tạm nhả phím tấn công trước khi bước đi để không bị kẹt đứng bắn tại chỗ
                atk_key = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
                atk_vk = KEY_VK_MAP.get(atk_key, 0x11)
                if cdp.is_available():
                    cdp.send_key(atk_key, is_down=False)
                else:
                    send_key_event(atk_vk, is_down=False)
                time.sleep(0.04)

                if cdp.is_available():
                    cdp.send_key(move_k, is_down=True)
                    time.sleep(walk_duration)
                    cdp.send_key(move_k, is_down=False)
                    time.sleep(0.04)
                    cdp.tap_key(face_k, hold_sec=0.04)
                else:
                    user32.SetForegroundWindow(hwnd)
                    send_key_event(move_vk, is_down=True)
                    time.sleep(walk_duration)
                    send_key_event(move_vk, is_down=False)
                    # Quay mặt lại hướng mặc định
                    send_key_press(face_vk, 0.05)

            time.sleep(interval)

# Xử lý lệnh từ Discord
def handle_command(cmd, msg="", token=None, caller=None):
    global auto_attack_running, anchor_running, anchor_x, anchor_y
    cmd = (cmd or "").strip().lower()

    if cmd == "reply":
        if not cfg.getboolean("bridge", "reply_enabled", fallback=True):
            return False, "Tính năng /reply đang bị TẮT trong config.ini của máy này."
        return send_chat(msg)

    elif cmd == "bot":
        toggle_auto_attack()
        key_str = cfg.get("bridge", "attack_key", fallback="ctrl").upper()
        if auto_attack_running:
            if anchor_running and anchor_x is not None:
                return True, f"Đã BẬT tự đánh & TIẾP TỤC giữ vị trí Anchor (đang tự quay về X={anchor_x}, Y={anchor_y})."
            return True, f"Đã BẬT tính năng tự đánh ({key_str}) trên KuroMS Web."
        else:
            if anchor_paused_by_bot and anchor_x is not None:
                return True, f"Đã TẮT tự đánh & TẠM DỪNG Anchor (vẫn nhớ vị trí X={anchor_x}, Y={anchor_y})."
            return True, f"Đã TẮT tính năng tự đánh trên KuroMS Web."

    elif cmd == "anchor":
        ok, res = toggle_anchor()
        return ok, res

    elif cmd == "status":
        s = web_game_status()
        conn = "CONNECTED" if s["connected"] else "DISCONNECTED"
        bot_st = "ON" if auto_attack_running else "OFF"
        if anchor_running and anchor_x is not None:
            anc_st = f"ON (X={anchor_x}, Y={anchor_y})"
        elif anchor_paused_by_bot and anchor_x is not None:
            anc_st = f"PAUSED (X={anchor_x}, Y={anchor_y})"
        else:
            anc_st = "OFF"
        det_st = "ON" if cfg.getboolean("detector", "enabled", fallback=False) else "OFF"
        reply_st = "ON" if cfg.getboolean("bridge", "reply_enabled", fallback=True) else "OFF"
        return True, f"[v{VERSION}-WEB] {conn} | HWND: {s['hwnd']} | Reply: {reply_st} | Attack: {bot_st} | Anchor: {anc_st} | Detector: {det_st}"

    elif cmd == "buff":
        try:
            vk, k_name = parse_buff_key(msg)
            global is_buffing
            with buff_lock:
                is_buffing = True
                try:
                    # 1. Tạm nhả phím tấn công trước khi buff để nhân vật dừng bắn
                    atk_key = cfg.get("bridge", "attack_key", fallback="ctrl").strip().lower()
                    atk_vk = KEY_VK_MAP.get(atk_key, 0x11)
                    if cdp.is_available():
                        cdp.send_key(atk_key, is_down=False)
                    else:
                        send_key_event(atk_vk, is_down=False)

                    # Chờ 0.5s để nhân vật dừng hẳn động tác tấn công về trạng thái idle (giống client desktop)
                    time.sleep(0.5)

                    # 2. Xử lý combo đặc biệt cho máy 'fox' (A, S, D)
                    if MACHINE_NAME == "fox" and k_name in ["a", "f"]:
                        print(f"\n[BUFF DISCORD] Thực hiện combo A, S, D đặc biệt cho Fox!")
                        for combo_k in ["a", "s", "d"]:
                            if cdp.is_available():
                                cdp.tap_key(combo_k, hold_sec=0.08)
                            else:
                                send_key_press(KEY_VK_MAP.get(combo_k, 0x41), hold_time=0.08)
                            time.sleep(0.9)
                        return True, f"[{MACHINE_NAME.upper()}] Đã thực hiện combo buff A, S, D thành công!"

                    # 3. Gửi phím buff chỉ định (chỉ bấm 1 lần để kích hoạt macro in-game)
                    if cdp.is_available():
                        cdp.tap_key(k_name, hold_sec=0.08)
                        print(f"\n[BUFF DISCORD] Đã buff phím {k_name.upper()}!")
                    else:
                        hwnd = find_web_game()
                        if hwnd:
                            prev = user32.GetForegroundWindow()
                            user32.SetForegroundWindow(hwnd)
                            time.sleep(0.04)
                            send_key_press(vk, 0.08)
                            if prev and prev != hwnd:
                                user32.SetForegroundWindow(prev)
                            print(f"\n[BUFF DISCORD] Đã buff phím {k_name.upper()}!")
                        else:
                            return False, "Không tìm thấy cửa sổ KuroMS Web."

                    # 4. Chờ 3.5 giây để nhân vật múa xong trọn vẹn 3 skill của macro in-game (giống client desktop)
                    time.sleep(3.5)

                finally:
                    is_buffing = False

            return True, f"✅ [{MACHINE_NAME.upper()}] Đã ngắt auto và bấm ngầm nút {k_name.upper()} thành công!"
        except Exception as e:
            return False, f"Lỗi buff: {e}"

    elif cmd in ("kill", "klll"):
        caller_name = (caller.get("name") or caller.get("username") or "Discord User") if isinstance(caller, dict) else "Discord User"
        caller_id = str(caller.get("id") or "") if isinstance(caller, dict) else ""
        
        # Kiểm tra danh sách user được phép kill (Dutch, Jira, Fox)
        KILL_AUTHORIZED_USERS = {
            "464953468759572481": "Dutch",
            "403929712684040202": "Jira",
            "372666814511185923": "Fox"
        }
        if caller_id and caller_id not in KILL_AUTHORIZED_USERS:
            print(f"\n[KILL] ⛔ CẢNH BÁO: User @{caller_name} (ID: {caller_id}) không có quyền thực hiện /kill!")
            return False, f"⛔ Bạn không có quyền thực hiện /kill! Chỉ Dutch, Jira và Fox mới có quyền."

        now_str = datetime.now().strftime("%H:%M:%S")
        print(f"\n[KILL] ⚠️ CẢNH BÁO: KuroMS Web đang bị KILL từ xa bởi @{caller_name} (ID: {caller_id or 'Unknown'}) lúc {now_str}!")
        killed = kill_kuroms_session()
        print(f"[KILL] Đã dừng toàn bộ auto (Attack/Buff/Anchor), nhả phím và tắt KuroMS Web port 9222 ({killed} tiến trình đã đóng).")
        return True, f"[{MACHINE_NAME.upper()}] 🛑 KuroMS Web đã được tắt bởi **@{caller_name}** lúc {now_str}! ({killed} tiến trình port 9222 đã đóng)"

    return False, f"Lệnh không xác định: {cmd}"

last_anchor_toggle_time = 0.0

def toggle_anchor():
    global anchor_running, anchor_x, anchor_y, anchor_paused_by_bot, last_anchor_toggle_time
    now = time.time()
    if now - last_anchor_toggle_time < 0.6:
        return False, "Bấm quá nhanh"
    last_anchor_toggle_time = now

    if not cfg.getboolean("bridge", "anchor_enabled", fallback=False):
        print("\n[ANCHOR] Tính năng Anchor đang tắt trong config.ini (anchor_enabled = false)")
        return False, "Tính năng Anchor đang tắt trong config.ini"

    anchor_running = not anchor_running
    if anchor_running:
        hwnd = find_web_game()
        if not hwnd:
            anchor_running = False
            print("\n[ANCHOR] Chưa tìm thấy game KuroMS Web.")
            return False, "Chưa tìm thấy game KuroMS Web."

        box = get_web_game_rect(hwnd)
        if not box:
            anchor_running = False
            return False, "Không lấy được khung game."
        left, top, w, h = box

        import mss
        with getattr(mss, "MSS", mss.mss)() as sct:
            shot = np.array(sct.grab({"left": left, "top": top, "width": min(w, 400), "height": min(h, 300)}))
            pos = scan_web_minimap(cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR))

        if pos:
            anchor_x, anchor_y = pos
            anchor_paused_by_bot = False
            face_dir = cfg.get("bridge", "anchor_face_direction", fallback="right").strip().lower()
            if cdp.is_available():
                cdp.tap_key(face_dir, hold_sec=0.04)
            print(f"\n[ANCHOR] BẬT Auto-Anchor tại toạ độ: X={anchor_x}, Y={anchor_y} | Face: {face_dir.upper()}")
            return True, f"BẬT Auto-Anchor tại toạ độ X={anchor_x}, Y={anchor_y} (Face: {face_dir.upper()})."
        else:
            anchor_running = False
            anchor_x, anchor_y = None, None
            anchor_paused_by_bot = False
            print("\n[ANCHOR] Không nhận diện được chấm vàng nhân vật trên Minimap.")
            return False, "Không nhận diện được vị trí nhân vật trên Minimap."
    else:
        anchor_x, anchor_y = None, None
        anchor_paused_by_bot = False
        print("\n[ANCHOR] TẮT Auto-Anchor")
        return True, "TẮT Auto-Anchor"

def main():
    try:
        import pysher
    except ImportError:
        print("Vui lòng cài đặt: pip install pysher websocket-client mss opencv-python requests keyboard")
        sys.exit(1)

    # Khởi động các luồng ngầm
    threading.Thread(target=auto_attack_thread, daemon=True).start()
    threading.Thread(target=auto_buff1_thread, daemon=True).start()
    threading.Thread(target=auto_buff2_thread, daemon=True).start()
    threading.Thread(target=auto_buff3_thread, daemon=True).start()
    threading.Thread(target=anchor_thread, daemon=True).start()
    threading.Thread(target=detector_thread, daemon=True).start()

    # Đăng ký phím tắt Hotkey
    try:
        import keyboard
        # Hotkey Auto-Attack
        hotkey_atk = cfg.get("bridge", "attack_hotkey", fallback="f1").strip().lower()
        if hotkey_atk:
            keyboard.add_hotkey(hotkey_atk, toggle_auto_attack, suppress=False)
            atk_k = cfg.get("bridge", "attack_key", fallback="ctrl").upper()
            atk_ms = cfg.getint("bridge", "attack_interval_ms", fallback=50)
            print(f"[HOTKEY] Tự Đánh ({atk_k} {atk_ms}ms): Bấm phím [{hotkey_atk.upper()}] để BẬT/TẮT")

        # Hotkey Buff 1
        hotkey_b1 = cfg.get("bridge", "autobuff_hotkey", fallback="f2").strip().lower()
        if hotkey_b1:
            keyboard.add_hotkey(hotkey_b1, toggle_auto_buff, suppress=False)
            b1_k = cfg.get("bridge", "autobuff_key", fallback="t").upper()
            b1_ms = cfg.getint("bridge", "autobuff_interval_ms", fallback=240000)
            print(f"[HOTKEY] Auto Buff 1 ({b1_k} {b1_ms}ms): Bấm phím [{hotkey_b1.upper()}] để BẬT/TẮT")

        # Hotkey Buff 2
        hotkey_b2 = cfg.get("bridge", "autobuff2_hotkey", fallback="f8").strip().lower()
        if hotkey_b2:
            keyboard.add_hotkey(hotkey_b2, toggle_auto_buff2, suppress=False)
            b2_k = cfg.get("bridge", "autobuff2_key", fallback="pageup").upper()
            b2_ms = cfg.getint("bridge", "autobuff2_interval_ms", fallback=601000)
            print(f"[HOTKEY] Auto Buff 2 ({b2_k} {b2_ms}ms): Bấm phím [{hotkey_b2.upper()}] để BẬT/TẮT")

        # Hotkey Buff 3
        hotkey_b3 = cfg.get("bridge", "autobuff3_hotkey", fallback="f7").strip().lower()
        if hotkey_b3:
            keyboard.add_hotkey(hotkey_b3, toggle_auto_buff3, suppress=False)
            b3_k = cfg.get("bridge", "autobuff3_key", fallback="v").upper()
            b3_ms = cfg.getint("bridge", "autobuff3_interval_ms", fallback=31500)
            print(f"[HOTKEY] Auto Buff 3 ({b3_k} {b3_ms}ms): Bấm phím [{hotkey_b3.upper()}] để BẬT/TẮT")

        # Hotkey Anchor
        if cfg.getboolean("bridge", "anchor_enabled", fallback=False):
            hotkey_anc = cfg.get("bridge", "anchor_hotkey", fallback="-").strip().lower()
            if hotkey_anc:
                keyboard.add_hotkey(hotkey_anc, toggle_anchor, suppress=False)
                print(f"[HOTKEY] Giữ vị trí (Minimap Anchor): Bấm phím [{hotkey_anc.upper()}] để BẬT/TẮT")
    except Exception as e:
        print(f"[HOTKEY ERROR] Không thể đăng ký phím tắt: {e}")

    # Kết nối Pusher lắng nghe lệnh từ Discord
    channel_name = f"machine-{MACHINE_NAME.lower()}"
    pusher = pysher.Pusher(key=PUSHER_KEY, cluster=PUSHER_CLUSTER)
    is_pusher_subscribed = False

    def on_command(data):
        try:
            payload = json.loads(data) if isinstance(data, str) else data
            cmd = payload.get("cmd")
            msg = payload.get("message", "")
            token = payload.get("token")
            print(f"\n[DISCORD] Nhận lệnh /{cmd} {msg} (Token: {token[:8]}...)")

            if cmd in ("ss", "screen"):
                ok, res = send_screenshot()
                if ok:
                    with open(res, "rb") as f:
                        requests.post(
                            f"{WORKER_URL.rstrip('/')}/api/result",
                            files={"file": (res, f, "image/png")},
                            data={"token": token, "machine": MACHINE_NAME, "success": "true"},
                            timeout=15
                        )
                else:
                    requests.post(
                        f"{WORKER_URL.rstrip('/')}/api/result",
                        json={"token": token, "result": res, "success": False, "isFollowUp": False, "machine": MACHINE_NAME},
                        timeout=10
                    )
            else:
                ok, res_text = handle_command(cmd, msg, token, caller=payload.get("caller"))
                is_follow_up = (cmd in ("status", "anchor"))
                requests.post(
                    f"{WORKER_URL.rstrip('/')}/api/result",
                    json={
                        "token": token,
                        "result": res_text,
                        "success": ok,
                        "isFollowUp": is_follow_up,
                        "machine": MACHINE_NAME
                    },
                    timeout=10
                )
        except Exception as e:
            print(f"[ERROR] Lỗi xử lý lệnh: {e}")

    def on_connect(data):
        nonlocal is_pusher_subscribed
        if not is_pusher_subscribed:
            ch = pusher.subscribe(channel_name)
            ch.bind("discord_command", on_command)

            ch_all = pusher.subscribe("machine-all")
            ch_all.bind("discord_command", on_command)
            is_pusher_subscribed = True
            print(f"[PUSHER] Đã kết nối! Đang lắng nghe kênh '{channel_name}' và 'machine-all'...")
        else:
            print(f"[PUSHER] Reconnected! Giữ nguyên đăng ký kênh '{channel_name}'.")

    pusher.connection.bind("pusher:connection_established", on_connect)
    pusher.connect()

    print(f"\n[OK] Client KuroMS Web đã sẵn sàng! Đang quét cửa sổ KuroMS trên trình duyệt...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nĐang tắt client...")
        cleanup_on_exit()
        sys.exit(0)

if __name__ == "__main__":
    main()
