"""路径抓取工具 - 点击文件后自动复制路径

监听鼠标点击，点击后模拟 Ctrl+Shift+C 复制路径
"""

import ctypes
import time

user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_C = 0x43


def copy_path():
    """模拟 Ctrl+Shift+C 复制路径"""
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, 2, 0)
    user32.keybd_event(VK_SHIFT, 0, 2, 0)
    user32.keybd_event(VK_CONTROL, 0, 2, 0)


def wait_for_click_and_copy():
    """监听鼠标点击，点击后复制路径"""
    from pynput import mouse

    def on_click(x, y, button, pressed):
        if not pressed and button == mouse.Button.left:
            time.sleep(0.15)
            copy_path()
            return False

    with mouse.Listener(on_click=on_click) as listener:
        listener.join(timeout=30)


if __name__ == "__main__":
    wait_for_click_and_copy()
