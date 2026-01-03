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
DEFAULT_SCREENSHOT_HOTKEY = "alt+s"
DEFAULT_COPYPATH_HOTKEY = "alt+c"

_current_screenshot_hotkey = None
_current_copypath_hotkey = None


def load_hotkey(key: str = "screenshot") -> str:
    """加载快捷键配置"""
    defaults = {"screenshot": DEFAULT_SCREENSHOT_HOTKEY, "copy_path": DEFAULT_COPYPATH_HOTKEY}
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get(key, defaults.get(key, ""))
    except Exception:
        pass
    return defaults.get(key, "")


def save_hotkey(key: str, hotkey: str):
    """保存快捷键配置"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data[key] = hotkey
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def setup_screenshot_hotkey(save_dir: str = None, hotkey: str = None):
    """注册截图全局快捷键"""
    global _current_screenshot_hotkey
    if not HAS_KEYBOARD:
        return

    hotkey = hotkey or load_hotkey("screenshot")
    script = str(Path(__file__).parent / "tools" / "screenshot_tool.py")

    def take_screenshot():
        def run():
            subprocess.run(
                [sys.executable, script, save_dir or ""],
                capture_output=True, check=False
            )
        threading.Thread(target=run, daemon=True).start()

    if _current_screenshot_hotkey:
        try:
            keyboard.remove_hotkey(_current_screenshot_hotkey)
        except Exception:
            pass

    keyboard.add_hotkey(hotkey, take_screenshot)
    _current_screenshot_hotkey = hotkey


def setup_copypath_hotkey(hotkey: str = None, page=None):
    """注册复制路径全局快捷键"""
    global _current_copypath_hotkey
    if not HAS_KEYBOARD:
        return

    hotkey = hotkey or load_hotkey("copy_path")

    def copy_path():
        # 最小化窗口
        if page:
            try:
                page.window.minimized = True
                page.update()
            except Exception:
                pass

        def run():
            import platform
            os_name = platform.system()
            if os_name == "Windows":
                _copy_path_windows()
            elif os_name == "Darwin":
                keyboard.send('cmd+option+c')
            else:
                keyboard.send('ctrl+shift+c')
        threading.Thread(target=run, daemon=True).start()

    if _current_copypath_hotkey:
        try:
            keyboard.remove_hotkey(_current_copypath_hotkey)
        except Exception:
            pass

    keyboard.add_hotkey(hotkey, copy_path)
    _current_copypath_hotkey = hotkey


def _copy_path_windows():
    """Windows: 获取资源管理器或桌面选中的文件路径"""
    try:
        import pythoncom
        import win32com.client
        import win32clipboard
        pythoncom.CoInitialize()

        paths = []
        shell = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()
        print(f"[CopyPath] 找到 {windows.Count} 个窗口")

        # 1. 尝试从资源管理器窗口获取
        for i in range(windows.Count):
            try:
                window = windows.Item(i)
                if window and window.Document:
                    sel = window.Document.SelectedItems()
                    print(f"[CopyPath] 窗口 {i}: 选中 {sel.Count} 个文件")
                    if sel.Count > 0:
                        for j in range(sel.Count):
                            paths.append(sel.Item(j).Path)
            except Exception as e:
                print(f"[CopyPath] 窗口 {i} 错误: {e}")

        if paths:
            text = "\n".join(paths)
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text)
            win32clipboard.CloseClipboard()
            print(f"[CopyPath] 已复制: {text}")
        else:
            print("[CopyPath] 未找到选中的文件")

        pythoncom.CoUninitialize()
    except Exception as e:
        print(f"[CopyPath] 错误: {e}")


def update_hotkey(new_hotkey: str, save_dir: str = None):
    """更新截图快捷键"""
    save_hotkey("screenshot", new_hotkey)
    setup_screenshot_hotkey(save_dir, new_hotkey)


def update_copypath_hotkey(new_hotkey: str):
    """更新复制路径快捷键"""
    save_hotkey("copy_path", new_hotkey)
    setup_copypath_hotkey(new_hotkey)
