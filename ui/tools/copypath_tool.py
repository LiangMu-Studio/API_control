"""复制路径工具 - 模拟 Ctrl+Shift+C"""
import ctypes
import time

user32 = ctypes.windll.user32
user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
user32.keybd_event(0x10, 0, 0, 0)  # Shift down
user32.keybd_event(0x43, 0, 0, 0)  # C down
time.sleep(0.05)
user32.keybd_event(0x43, 0, 2, 0)  # C up
user32.keybd_event(0x10, 0, 2, 0)  # Shift up
user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
