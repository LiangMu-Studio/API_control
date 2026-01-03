"""简单测试 Alt+C"""
import keyboard
import time

def on_altc():
    print("Alt+C 触发了!")
    time.sleep(0.1)
    keyboard.send('ctrl+shift+c')
    print("已发送 Ctrl+Shift+C")

print("注册 Alt+C...")
keyboard.add_hotkey('alt+c', on_altc)
print("按 Alt+C 测试，按 Esc 退出")
keyboard.wait('esc')
