"""测试 Alt+C 快捷键"""
import keyboard
import time

def on_altc():
    print("Alt+C 被按下！")
    keyboard.press_and_release('ctrl+shift+c')
    print("已发送 Ctrl+Shift+C")

print("注册 Alt+C 快捷键...")
keyboard.add_hotkey('alt+c', on_altc)
print("按 Alt+C 测试，按 Esc 退出")

keyboard.wait('esc')
