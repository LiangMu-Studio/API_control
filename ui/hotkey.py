"""全局快捷键模块"""

import ctypes
import subprocess
import sys
import threading
import time
import json
from pathlib import Path

from .lang import LANG
from .common import load_settings

try:
    import keyboard
    import mouse
    import win32gui
    import win32clipboard
    import pythoncom
    import win32com.client
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

CONFIG_PATH = Path(__file__).parent.parent / "data" / "hotkey.json"
DEFAULT_SCREENSHOT_HOTKEY = "alt+s"
DEFAULT_COPYPATH_HOTKEY = "alt+c"

_lock = threading.Lock()
_current_screenshot_hotkey = None
_current_copypath_hotkey = None
_grab_mode = False
_esc_hook = None
_prev_selected = set()  # 进入抓取模式前已选中的文件
_old_title = None  # 保存原始窗口标题


def _get_selected_files():
    """获取当前选中的文件"""
    pythoncom.CoInitialize()
    try:
        selected = []
        shell = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()
        for i in range(windows.Count):
            try:
                window = windows.Item(i)
                if window and window.Document:
                    sel = window.Document.SelectedItems()
                    if sel.Count > 0:
                        for j in range(sel.Count):
                            selected.append(sel.Item(j).Path)
            except Exception:
                pass
        return selected
    finally:
        pythoncom.CoUninitialize()


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


def setup_screenshot_hotkey(save_dir: str = None, hotkey: str = None, page=None):
    """注册截图全局快捷键"""
    global _current_screenshot_hotkey
    if not HAS_KEYBOARD:
        return

    hotkey = hotkey or load_hotkey("screenshot")
    script = str(Path(__file__).parent / "tools" / "screenshot_tool.py")
    # 默认截图目录
    if not save_dir:
        save_dir = str(Path(__file__).parent.parent / "screenshots")

    def take_screenshot():
        old_title = None
        if page:
            try:
                old_title = page.title
                lang = load_settings().get('lang', 'zh')
                page.title = LANG[lang].get('screenshot_in_progress', '截图中...')
                page.update()
            except Exception:
                pass

        def run():
            result = subprocess.run(
                [sys.executable, script, save_dir or ""],
                capture_output=True, text=True, check=False
            )
            if page and old_title:
                try:
                    page.title = old_title
                    page.update()
                except Exception:
                    pass
            # 复制截图路径到剪贴板
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    _set_clipboard(path)
        threading.Thread(target=run, daemon=True).start()

    with _lock:
        if _current_screenshot_hotkey:
            try:
                keyboard.remove_hotkey(_current_screenshot_hotkey)
            except Exception:
                pass

        keyboard.add_hotkey(hotkey, take_screenshot)
        _current_screenshot_hotkey = hotkey


def _get_all_files(path: Path) -> list:
    """递归获取文件夹下所有文件路径"""
    files = []
    if path.is_file():
        files.append(str(path))
    elif path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                files.append(str(item))
    return files


def _set_clipboard(text: str):
    """设置剪贴板"""
    for _ in range(3):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def _show_toast(title: str, msg: str, timeout_ms: int = 2000):
    """显示提示框，自动关闭，置顶显示，使用软件图标"""
    def show():
        import tkinter as tk
        root = tk.Tk()
        root.title(title)
        root.attributes('-topmost', True)
        # 设置图标
        icon_path = Path(__file__).parent.parent / "icon.ico"
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
        # 内容 - 增加行距
        lines = msg.split('\n')
        for line in lines:
            tk.Label(root, text=line, padx=20, pady=3, justify='left', anchor='w').pack(fill='x')
        # 居中显示
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f'+{x}+{y}')
        # 自动关闭
        root.after(timeout_ms, root.destroy)
        root.mainloop()
    threading.Thread(target=show, daemon=True).start()


def _is_explorer_or_desktop():
    """检查前台窗口是否是资源管理器或桌面"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        class_name = win32gui.GetClassName(hwnd)
        return class_name in ("CabinetWClass", "ExploreWClass", "Progman", "WorkerW")
    except Exception:
        return False


def _set_grab_cursor():
    """设置全局抓手光标"""
    hand = ctypes.windll.user32.LoadCursorW(None, 32649)
    cursor_ids = [32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644, 32645, 32646, 32648, 32649, 32650]
    for cid in cursor_ids:
        copy = ctypes.windll.user32.CopyImage(hand, 2, 0, 0, 0)
        if copy:
            ctypes.windll.user32.SetSystemCursor(copy, cid)


def _restore_cursor():
    """恢复默认光标"""
    ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)


def setup_copypath_hotkey(hotkey: str = None, page=None):
    """注册复制路径全局快捷键"""
    global _current_copypath_hotkey, _grab_mode, _esc_hook, _prev_selected, _old_title
    if not HAS_KEYBOARD:
        return

    hotkey = hotkey or load_hotkey("copy_path")

    def cancel_grab():
        global _grab_mode, _esc_hook, _old_title
        if _grab_mode:
            _grab_mode = False
            _restore_cursor()
            mouse.unhook_all()
            if _esc_hook:
                keyboard.unhook(_esc_hook)
                _esc_hook = None
            if page:
                try:
                    if _old_title:
                        page.title = _old_title
                    page.window.minimized = False  # 恢复窗口
                    page.update()
                except Exception:
                    pass

    def do_copy():
        global _grab_mode, _esc_hook, _old_title
        _grab_mode = False
        _restore_cursor()
        mouse.unhook_all()
        if _esc_hook:
            keyboard.unhook(_esc_hook)
            _esc_hook = None
        # 恢复窗口标题
        if page and _old_title:
            try:
                page.title = _old_title
                page.update()
            except Exception:
                pass
        # 直接获取选中文件并复制
        selected = _get_selected_files()
        if selected:
            all_files = []
            for p in selected:
                all_files.extend(_get_all_files(Path(p)))
            if all_files:
                text = ",".join(all_files)
                if _set_clipboard(text):
                    # 显示提示框（不恢复软件窗口）
                    paths = "\n".join(all_files[:10])
                    if len(all_files) > 10:
                        paths += f"\n... 等 {len(all_files)} 个文件"
                    _show_toast("复制成功", f"已复制 {len(all_files)} 个文件:\n{paths}")

    def on_left_click():
        """左键点击后检查是否新选中了文件"""
        global _grab_mode, _prev_selected
        if not _grab_mode:
            return

        # 立即检查点击时的前台窗口（点击前的状态）
        was_explorer = _is_explorer_or_desktop()

        # 如果 Shift/Ctrl 按住，等待释放（多选操作）
        while keyboard.is_pressed("shift") or keyboard.is_pressed("ctrl"):
            time.sleep(0.05)
        time.sleep(0.15)

        # 再次检查当前前台窗口
        is_explorer_now = _is_explorer_or_desktop()

        if not is_explorer_now:
            return

        selected = set(_get_selected_files())
        new_selected = selected - _prev_selected

        # 如果点击前就在资源管理器，有选中就复制（用户明确点击）
        # 如果是从其他窗口切换过来，只有新选中才复制
        if was_explorer:
            if selected:
                threading.Thread(target=do_copy, daemon=True).start()
        else:
            if new_selected:
                threading.Thread(target=do_copy, daemon=True).start()

    def on_hotkey():
        global _grab_mode, _esc_hook, _prev_selected, _old_title

        if not _grab_mode:
            _grab_mode = True
            _prev_selected = set(_get_selected_files())  # 记录当前已选中的文件
            _set_grab_cursor()
            if page:
                try:
                    _old_title = page.title
                    lang = load_settings().get('lang', 'zh')
                    page.title = LANG[lang].get('pick_path_in_progress', '复制路径中...')
                    page.window.minimized = True
                    page.update()
                except Exception:
                    pass
            # 延迟注册监听，避免误触发
            def setup_hooks():
                time.sleep(0.3)
                if _grab_mode:
                    mouse.on_click(on_left_click)
                    mouse.on_right_click(lambda: cancel_grab())
                    global _esc_hook
                    _esc_hook = keyboard.on_press_key("escape", lambda _: cancel_grab())
            threading.Thread(target=setup_hooks, daemon=True).start()

    with _lock:
        if _current_copypath_hotkey:
            try:
                keyboard.remove_hotkey(_current_copypath_hotkey)
            except Exception:
                pass

        keyboard.add_hotkey(hotkey, on_hotkey)
        _current_copypath_hotkey = hotkey


def update_hotkey(new_hotkey: str, save_dir: str = None, page=None):
    """更新截图快捷键"""
    save_hotkey("screenshot", new_hotkey)
    setup_screenshot_hotkey(save_dir, new_hotkey, page)


def update_copypath_hotkey(new_hotkey: str):
    """更新复制路径快捷键"""
    save_hotkey("copy_path", new_hotkey)
    setup_copypath_hotkey(new_hotkey)


def cleanup_hotkeys():
    """清理所有热键钩子"""
    global _current_screenshot_hotkey, _current_copypath_hotkey
    if not HAS_KEYBOARD:
        return
    with _lock:
        if _current_screenshot_hotkey:
            try:
                keyboard.remove_hotkey(_current_screenshot_hotkey)
            except Exception:
                pass
            _current_screenshot_hotkey = None
        if _current_copypath_hotkey:
            try:
                keyboard.remove_hotkey(_current_copypath_hotkey)
            except Exception:
                pass
            _current_copypath_hotkey = None
    # 清理所有钩子
    try:
        keyboard.unhook_all()
        mouse.unhook_all()
    except Exception:
        pass
