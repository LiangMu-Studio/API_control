"""测试后台快捷键是否能在资源管理器中触发"""
import keyboard
import ctypes
import time
import threading

ready = False

def copy_path():
    if not ready:
        return
    print("快捷键被触发!")
    def run():
        user32 = ctypes.windll.user32
        user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        user32.keybd_event(0x10, 0, 0, 0)  # Shift down
        user32.keybd_event(0x43, 0, 0, 0)  # C down
        time.sleep(0.05)
        user32.keybd_event(0x43, 0, 2, 0)  # C up
        user32.keybd_event(0x10, 0, 2, 0)  # Shift up
        user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
        print("Ctrl+Shift+C 已发送")
    threading.Thread(target=run, daemon=True).start()

print("注册 Alt+C 快捷键...")
keyboard.add_hotkey('alt+c', copy_path, suppress=False)
time.sleep(0.5)
ready = True
print("快捷键已就绪，现在去资源管理器选中文件，按 Alt+C 测试")
print("按 Esc 退出")

keyboard.wait('esc')
