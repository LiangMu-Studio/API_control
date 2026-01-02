"""全局快捷键模块"""

import subprocess
import sys
import threading
import json
from pathlib import Path

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

CONFIG_PATH = Path(__file__).parent.parent / "data" / "hotkey.json"
DEFAULT_HOTKEY = "alt+s"

_current_hotkey = None


def load_hotkey() -> str:
    """加载快捷键配置"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("screenshot", DEFAULT_HOTKEY)
    except Exception:
        pass
    return DEFAULT_HOTKEY


def save_hotkey(hotkey: str):
    """保存快捷键配置"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"screenshot": hotkey}, f)


def setup_screenshot_hotkey(save_dir: str = None, hotkey: str = None):
    """注册截图全局快捷键"""
    global _current_hotkey
    if not HAS_KEYBOARD:
        return

    hotkey = hotkey or load_hotkey()
    script = str(Path(__file__).parent / "tools" / "screenshot_tool.py")

    def take_screenshot():
        def run():
            subprocess.run([sys.executable, script, save_dir or ""], capture_output=True, check=False)
        threading.Thread(target=run, daemon=True).start()

    # 移除旧快捷键
    if _current_hotkey:
        try:
            keyboard.remove_hotkey(_current_hotkey)
        except Exception:
            pass

    keyboard.add_hotkey(hotkey, take_screenshot)
    _current_hotkey = hotkey


def update_hotkey(new_hotkey: str, save_dir: str = None):
    """更新快捷键"""
    save_hotkey(new_hotkey)
    setup_screenshot_hotkey(save_dir, new_hotkey)
