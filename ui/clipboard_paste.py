"""Win+V 剪贴板历史粘贴模块（仅 Windows）

使用方法:
    from ui.clipboard_paste import setup_clipboard_paste

    # 在 main 函数中初始化，自动为所有 TextField 启用
    setup_clipboard_paste(page)
"""
import sys
import threading
import time

IS_WINDOWS = sys.platform == 'win32'

if IS_WINDOWS:
    import ctypes

try:
    from pynput import mouse
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

_state = {
    'field': None,
    'field_value': "",
    'page': None,
    'monitoring': False,
    'click_pos': None,
    'click_button': None,
    'listener': None,
    'enabled': False,
    'keyboard_hook': None,  # 保存钩子引用以便清理
}


def _get_clipboard():
    """获取剪贴板文本内容（带超时保护）"""
    result = [None]

    def _read():
        for _ in range(10):
            if ctypes.windll.user32.OpenClipboard(0):
                try:
                    ctypes.windll.user32.GetClipboardData.restype = ctypes.c_void_p
                    h = ctypes.windll.user32.GetClipboardData(13)
                    if h:
                        ctypes.windll.kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                        ctypes.windll.kernel32.GlobalLock.restype = ctypes.c_void_p
                        ptr = ctypes.windll.kernel32.GlobalLock(h)
                        if ptr:
                            result[0] = ctypes.wstring_at(ptr)
                            ctypes.windll.kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                            ctypes.windll.kernel32.GlobalUnlock(h)
                finally:
                    ctypes.windll.user32.CloseClipboard()
                return
            time.sleep(0.05)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout=2)
    return result[0]


def _get_clipboard_window_hwnd():
    """获取 Win+V 剪贴板窗口句柄和位置"""
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    hwnd = user32.FindWindowW("ApplicationFrameWindow", None)
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w, h = rect.right - rect.left, rect.bottom - rect.top
            if title.value == "" and 200 < w < 500 and 300 < h < 800:
                return hwnd, (rect.left, rect.top, rect.right, rect.bottom)
        hwnd = user32.FindWindowExW(None, hwnd, "ApplicationFrameWindow", None)
    return None, None


def _on_winv():
    """Win+V 热键回调"""
    if not _state['field'] or _state['monitoring'] or not _state['page']:
        return

    field = _state['field']
    page = _state['page']
    my_hwnd = ctypes.windll.user32.FindWindowW(None, page.title)
    _state['click_pos'] = None
    _state['click_button'] = None

    time.sleep(0.3)

    # 获取剪贴板窗口位置
    clip_hwnd, clip_rect = _get_clipboard_window_hwnd()
    if not clip_rect:
        return

    def on_click(x, y, button, pressed):
        if pressed:
            _state['click_pos'] = (x, y)
            _state['click_button'] = button

    listener = mouse.Listener(on_click=on_click)
    listener.start()
    _state['listener'] = listener

    def monitor():
        _state['monitoring'] = True

        while _state['monitoring']:
            if _state['click_pos']:
                x, y = _state['click_pos']
                btn = _state['click_button']
                r = clip_rect
                # 判断点击是否在窗口内（带 20px 容差）
                margin = 20
                in_clip_window = (r[0] - margin) <= x <= (r[2] + margin) and (r[1] - margin) <= y <= (r[3] + margin)

                if not in_clip_window:
                    break

                time.sleep(0.15)
                # 检测窗口是否关闭
                fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                window_closed = fg_hwnd != clip_hwnd

                if window_closed:
                    if btn == mouse.Button.left:
                        new_clip = _get_clipboard()
                        if new_clip:
                            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                            ctypes.windll.user32.SetForegroundWindow(my_hwnd)
                            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
                            old_val = _state['field'].value or ""
                            def do_paste(old=old_val, txt=new_clip):
                                _state['field'].value = old + txt
                                _state['field'].focus()
                                page.update()
                            page.run_thread(do_paste)
                    break
                else:
                    # 窗口未关闭时重置状态继续监控
                    _state['click_pos'] = None
                    _state['click_button'] = None

            time.sleep(0.05)

        if _state['listener']:
            _state['listener'].stop()
            _state['listener'] = None
        _state['monitoring'] = False

    threading.Thread(target=monitor, daemon=True).start()


def _wrap_textfield(field):
    """为单个 TextField 添加焦点和变化监听"""
    original_on_focus = field.on_focus
    original_on_change = field.on_change

    def on_focus(e):
        _state['field'] = e.control
        _state['field_value'] = e.control.value or ""
        if original_on_focus:
            original_on_focus(e)

    def on_change(e):
        if _state['field'] == e.control:
            _state['field_value'] = e.control.value or ""
        if original_on_change:
            original_on_change(e)

    field.on_focus = on_focus
    field.on_change = on_change


def _scan_and_wrap(control):
    """递归扫描并包装所有 TextField"""
    import flet as ft
    if isinstance(control, ft.TextField):
        _wrap_textfield(control)
    if hasattr(control, 'controls'):
        for c in control.controls:
            _scan_and_wrap(c)
    if hasattr(control, 'content') and control.content:
        _scan_and_wrap(control.content)


def setup_clipboard_paste(page):
    """初始化 Win+V 剪贴板粘贴功能，自动为所有 TextField 启用

    Args:
        page: Flet Page 对象
    """
    if not IS_WINDOWS or not HAS_KEYBOARD or not HAS_PYNPUT:
        return

    if _state['enabled']:
        return

    _state['page'] = page
    _state['enabled'] = True

    # 包装 page.add 方法，自动扫描新添加的控件
    original_add = page.add

    def wrapped_add(*controls):
        result = original_add(*controls)
        for control in controls:
            _scan_and_wrap(control)
        return result

    page.add = wrapped_add

    # 包装 page.open 方法，自动扫描对话框中的控件
    original_open = page.open

    def wrapped_open(dialog):
        _scan_and_wrap(dialog)
        return original_open(dialog)

    page.open = wrapped_open

    # 扫描已有控件
    for control in page.controls:
        _scan_and_wrap(control)

    # 使用 add_hotkey 检测 Win+V（避免 hook 干扰其他快捷键）
    def _on_winv_hotkey():
        threading.Thread(target=_on_winv, daemon=True).start()
    keyboard.add_hotkey('win+v', _on_winv_hotkey)
    _state['keyboard_hook'] = 'win+v'  # 保存用于清理


def cleanup_clipboard_paste():
    """清理键盘钩子"""
    if _state.get('keyboard_hook'):
        try:
            keyboard.remove_hotkey(_state['keyboard_hook'])
        except Exception:
            pass
        _state['keyboard_hook'] = None


def enable_clipboard_paste(field):
    """手动为单个 TextField 启用 Win+V 粘贴功能

    Args:
        field: Flet TextField 对象
    """
    if not IS_WINDOWS or not HAS_KEYBOARD or not HAS_PYNPUT:
        return
    _wrap_textfield(field)
