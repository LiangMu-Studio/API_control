# AI CLI Manager - Flet Version (Modular)
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3

import flet as ft
import asyncio
import sys
import os
import ctypes
from ctypes import wintypes
from pathlib import Path

# 单实例锁（Windows）
if sys.platform == 'win32':
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AI_CLI_Manager_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # 使用 EnumWindows 查找窗口（更可靠）
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        found_hwnd = [None]

        def enum_callback(hwnd, lparam):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if f"AI CLI Manager v" in buf.value:
                    found_hwnd[0] = hwnd
                    return False  # 停止枚举
            return True

        ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
        if found_hwnd[0]:
            hwnd = found_hwnd[0]
            # 如果窗口最小化或隐藏，先恢复
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        sys.exit(0)
from ui.state import AppState
from ui.common import VERSION, save_settings, detect_terminals, detect_python_envs
from ui.clipboard_paste import setup_clipboard_paste, cleanup_clipboard_paste
from ui.theme_manager import ThemeManager

# 获取图标路径（兼容打包后）
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
ICON_PATH = str(BASE_DIR / "icon.ico")
from ui.database import history_manager, codex_history_manager, history_cache
from ui.hotkey import setup_screenshot_hotkey, setup_copypath_hotkey, cleanup_hotkeys
from ui.pages.api_keys import create_api_page
from ui.pages.prompts import create_prompts_page
from ui.pages.mcp import create_mcp_page
from ui.pages.history import create_history_page

# 全局托盘图标引用
_tray_icon = None


def main(page: ft.Page):
    page.title = f"AI CLI Manager v{VERSION}"
    page.window.width = 1200
    page.window.height = 800
    page.padding = 0
    page.theme = ft.Theme(font_family="SimSun")
    page.window.icon = ICON_PATH
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True

    # 初始化状态
    state = AppState(page)
    L = state.L
    theme = state.get_theme()

    # 始终阻止关闭，只能通过托盘退出
    page.window.prevent_close = True

    # 点击 X 时最小化到托盘
    def on_window_event(e):
        if e.data == "close":
            page.window.minimized = True
            # 只有托盘存在时才隐藏任务栏图标
            if _tray_icon:
                page.window.skip_task_bar = True
            page.update()

    page.window.on_event = on_window_event

    # 初始化主题管理器
    theme_mgr = ThemeManager(state, page)

    page.bgcolor = theme['bg']
    page.theme_mode = ft.ThemeMode.DARK if state.theme_mode == 'dark' else ft.ThemeMode.LIGHT

    # 窗口控制按钮（使用 Windows API 直接操作）
    def get_hwnd():
        """获取当前窗口句柄"""
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        found = [None]
        def cb(hwnd, _):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if f"AI CLI Manager v{VERSION}" in buf.value:
                    found[0] = hwnd
                    return False
            return True
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(cb), 0)
        return found[0]

    _hwnd_cache = [None]

    def minimize_to_tray(_):
        hwnd = _hwnd_cache[0] or get_hwnd()
        _hwnd_cache[0] = hwnd
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        # 只有托盘存在时才隐藏任务栏图标
        if _tray_icon:
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            page.window.skip_task_bar = True
        page.update()

    def do_minimize(_):
        hwnd = _hwnd_cache[0] or get_hwnd()
        _hwnd_cache[0] = hwnd
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE

    def do_maximize(_):
        hwnd = _hwnd_cache[0] or get_hwnd()
        _hwnd_cache[0] = hwnd
        if hwnd:
            if ctypes.windll.user32.IsZoomed(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            else:
                ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE

    # 自定义标题栏
    title_bar = ft.WindowDragArea(
        content=ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TERMINAL, size=18, color=theme["text"]),
                ft.Text(f"AI CLI Manager v{VERSION}", size=14, color=theme["text"], weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.MINIMIZE, icon_size=16, icon_color=theme["text_sec"], on_click=do_minimize),
                ft.IconButton(ft.Icons.CROP_SQUARE, icon_size=16, icon_color=theme["text_sec"], on_click=do_maximize),
                ft.IconButton(ft.Icons.CLOSE, icon_size=16, icon_color=theme["text_sec"],
                             on_click=minimize_to_tray, tooltip=L.get('minimize_to_tray', '最小化到托盘')),
            ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=theme["surface"],
            padding=ft.padding.only(left=10, right=5, top=5, bottom=5),
        )
    )
    theme_mgr.set_title_bar(title_bar)

    # 创建页面
    api_page, refresh_api = create_api_page(state)
    prompt_page, refresh_prompts = create_prompts_page(state)
    mcp_page, refresh_mcp = create_mcp_page(state)
    history_page, refresh_history = create_history_page(state)

    # 注册页面刷新回调
    theme_mgr.register_page(0, refresh_api)
    theme_mgr.register_page(1, refresh_prompts)
    theme_mgr.register_page(2, refresh_mcp)
    theme_mgr.register_page(3, refresh_history)

    current_page_idx = [0]
    content_area = ft.Container(api_page, expand=True, padding=20)

    def switch_page(e):
        idx = e.control.selected_index
        current_page_idx[0] = idx
        t = state.get_theme()
        if idx == 0:
            content_area.content = api_page
            refresh_api()
        elif idx == 1:
            content_area.content = prompt_page
            refresh_prompts()
        elif idx == 2:
            content_area.content = mcp_page
            refresh_mcp()
        elif idx == 3:
            content_area.content = history_page
            refresh_history()
        content_area.bgcolor = t["surface"]
        page.update()

    def toggle_theme(_):
        theme_mgr.toggle(current_page_idx[0])

    def switch_lang(_):
        w, h, x, y = page.window.width, page.window.height, page.window.left, page.window.top
        state.toggle_lang()
        if page.controls:
            page.controls.clear()
        page.update()
        main(page)
        page.window.width, page.window.height, page.window.left, page.window.top = w, h, x, y
        page.update()

    def open_feedback(_):
        page.launch_url("https://github.com/LiangMu-Studio/AI_CLI_Manager/issues")

    divider = ft.VerticalDivider(width=1, color=theme["border"])
    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        bgcolor=theme["surface"],
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.KEY, label=L['api_config']),
            ft.NavigationRailDestination(icon=ft.Icons.CHAT, label=L['prompts']),
            ft.NavigationRailDestination(icon=ft.Icons.EXTENSION, label=L['mcp']),
            ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label=L['history']),
        ],
        on_change=switch_page,
        trailing=ft.Container(
            content=ft.Column([
                ft.IconButton(ft.Icons.DARK_MODE if state.theme_mode == 'light' else ft.Icons.LIGHT_MODE, on_click=toggle_theme, tooltip=L['toggle_theme']),
                ft.TextButton(L['switch_lang'], icon=ft.Icons.LANGUAGE, on_click=switch_lang),
                ft.TextButton(L['feedback'], on_click=open_feedback),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(bottom=20),
        ),
    )

    # 注册布局组件到主题管理器
    theme_mgr.set_layout(content_area, nav_rail, divider)

    main_content = ft.Row([nav_rail, divider, content_area], expand=True)
    page.add(ft.Column([title_bar, main_content], spacing=0, expand=True))
    # 注：不需要调用 refresh_api()，create_api_page 内部已完成初始化

    # 后台预加载历史
    async def preload_history():
        loop = asyncio.get_event_loop()
        if history_manager:
            history_cache["claude"] = await loop.run_in_executor(None, history_manager.load_sessions)
        if codex_history_manager:
            history_cache["codex"] = await loop.run_in_executor(None, codex_history_manager.load_sessions)
    page.run_task(preload_history)

    # 启动时检查更新
    def check_for_updates():
        import threading
        def run():
            from core.update_checker import check_update
            has_update, new_ver, url = check_update(VERSION)
            if has_update and url:
                async def show_update():
                    page.open(ft.SnackBar(
                        content=ft.Row([
                            ft.Text(L.get('update_available', f'发现新版本 v{new_ver}')),
                            ft.TextButton(L.get('view_update', '查看'), on_click=lambda _: page.launch_url(url)),
                        ]),
                        duration=10000,
                    ))
                page.run_task(show_update)
        threading.Thread(target=run, daemon=True).start()
    check_for_updates()

    # 注册截图快捷键 Ctrl+Alt+A
    setup_screenshot_hotkey(page=page)
    setup_copypath_hotkey(page=page)

    # 注册 Win+V 剪贴板粘贴支持
    setup_clipboard_paste(page)

    # 启动系统托盘图标
    global _tray_icon
    try:
        from ui.tray import create_tray_icon, run_tray_in_background, stop_tray

        def show_window():
            def do_show():
                hwnd = _hwnd_cache[0] or get_hwnd()
                _hwnd_cache[0] = hwnd
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                page.window.skip_task_bar = False
                page.update()
            page.run_thread(do_show)

        def quit_app():
            cleanup_hotkeys()  # 清理热键钩子
            cleanup_clipboard_paste()  # 清理剪贴板钩子
            page.window.prevent_close = False  # 允许关闭
            stop_tray(_tray_icon)
            page.window.close()

        def tray_screenshot():
            import subprocess
            script = str(Path(__file__).parent / "ui" / "tools" / "screenshot_tool.py")
            subprocess.Popen([sys.executable, script, ""], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

        def tray_copy_path():
            import subprocess
            script = str(Path(__file__).parent / "ui" / "tools" / "path_picker.py")
            subprocess.Popen([sys.executable, script], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

        _tray_icon = create_tray_icon(state, show_window, quit_app, tray_screenshot, tray_copy_path)
        run_tray_in_background(_tray_icon)
    except Exception:
        pass


if __name__ == "__main__":
    ft.app(target=main)
