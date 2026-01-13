# AI CLI Manager - Flet Version (Modular)
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3

import flet as ft
import asyncio
import sys
import os
import ctypes
import threading
import atexit
from ctypes import wintypes
from pathlib import Path

# 全局托盘图标引用（用于 atexit 清理）
_global_tray_icon = None

def _cleanup_tray_on_exit():
    """程序退出时清理托盘图标"""
    global _global_tray_icon
    if _global_tray_icon:
        try:
            _global_tray_icon.stop()
        except Exception:
            pass

atexit.register(_cleanup_tray_on_exit)

# 设置 DPI 感知（必须在创建窗口前调用）
if sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

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
from ui.common import VERSION, save_settings, flush_settings, detect_terminals, detect_python_envs
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
from ui.pages.skills import create_skills_page

# 全局托盘图标引用
_tray_icon = None


def main(page: ft.Page):
    page.title = f"AI CLI Manager v{VERSION}"

    # 根据屏幕分辨率自适应窗口大小
    screen_height = 1080
    try:
        user32 = ctypes.windll.user32
        screen_height = user32.GetSystemMetrics(1)
    except Exception:
        pass

    # 窗口宽度固定 1200，高度根据屏幕自适应
    window_width = 1200
    if screen_height <= 1080:
        window_height = 700  # 1080p 屏幕压缩高度
    else:
        window_height = 800  # 1200p 及以上

    page.window.width = window_width
    page.window.height = window_height
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

    # 页面懒加载 - 首次访问时才创建，减少启动时间
    _pages = {}  # {idx: (page_control, refresh_func, extra_refresh_func)}
    _page_creators = {
        0: create_api_page,
        1: create_prompts_page,
        2: create_history_page,
        3: create_mcp_page,
        4: create_skills_page,
    }

    def get_or_create_page(idx):
        """懒加载获取页面"""
        if idx not in _pages:
            creator = _page_creators.get(idx)
            if creator:
                result = creator(state)
                # 支持返回 2 个或 3 个值
                if isinstance(result, tuple) and len(result) == 3:
                    page_ctrl, refresh_fn, extra_fn = result
                elif isinstance(result, tuple):
                    page_ctrl, refresh_fn = result
                    extra_fn = None
                else:
                    page_ctrl, refresh_fn, extra_fn = result, None, None
                _pages[idx] = (page_ctrl, refresh_fn, extra_fn)
                theme_mgr.register_page(idx, refresh_fn)
        return _pages.get(idx, (None, None, None))

    # 启动时只创建首页
    api_page, refresh_api, _ = get_or_create_page(0)

    current_page_idx = [0]
    content_area = ft.Container(api_page, expand=True, padding=20)

    def switch_page(e):
        idx = e.control.selected_index
        current_page_idx[0] = idx
        t = state.get_theme()
        page_ctrl, refresh_fn, extra_fn = get_or_create_page(idx)
        if page_ctrl:
            content_area.content = page_ctrl
            if refresh_fn:
                refresh_fn()
            # 切换到首页时刷新预设下拉菜单
            if idx == 0 and extra_fn:
                extra_fn()
        content_area.bgcolor = t["surface"]
        page.update()

    def toggle_theme(_):
        theme_mgr.toggle(current_page_idx[0])

    def switch_lang(_):
        state.toggle_lang()
        L_new = state.L
        # 更新导航栏标签
        nav_rail.destinations = [
            ft.NavigationRailDestination(icon=ft.Icons.KEY, label=L_new['api_config']),
            ft.NavigationRailDestination(icon=ft.Icons.CHAT, label=L_new['prompts']),
            ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label=L_new['history']),
            ft.NavigationRailDestination(icon=ft.Icons.EXTENSION, label=L_new['mcp']),
            ft.NavigationRailDestination(icon=ft.Icons.AUTO_FIX_HIGH, label=L_new.get('skills', 'Skills')),
        ]
        # 清除页面缓存，下次访问时重建
        _pages.clear()
        # 重建当前页面
        page_ctrl, _, _ = get_or_create_page(current_page_idx[0])
        if page_ctrl:
            content_area.content = page_ctrl
        # 确保窗口和任务栏图标可见
        page.window.skip_task_bar = False
        hwnd = _hwnd_cache[0] or get_hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
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
            ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label=L['history']),
            ft.NavigationRailDestination(icon=ft.Icons.EXTENSION, label=L['mcp']),
            ft.NavigationRailDestination(icon=ft.Icons.AUTO_FIX_HIGH, label=L.get('skills', 'Skills')),
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

    # 后台增量刷新历史（复刻 DEV 版设计）- 并行化加载
    # 首次使用：全量扫描
    # 后续启动：只刷新 mtime > last_startup_time 的文件
    def incremental_refresh_history():
        from concurrent.futures import ThreadPoolExecutor

        def refresh_cli(cli_type):
            """刷新单个 CLI 历史"""
            try:
                import liangmu_history as lh
                updated = lh.refresh_history_on_startup(cli_type)
                if updated > 0:
                    print(f"[启动刷新] {cli_type.title()} 更新了 {updated} 个会话")
                return updated
            except ImportError:
                # Rust 模块不可用，回退
                if cli_type == 'claude' and history_manager:
                    history_cache["claude"] = history_manager.load_sessions()
                elif cli_type == 'codex' and codex_history_manager:
                    history_cache["codex"] = codex_history_manager.load_sessions()
                return 0
            except Exception as e:
                print(f"[启动刷新] {cli_type} 错误: {e}")
                return 0

        # 并行刷新 Claude 和 Codex
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='history_') as executor:
            futures = [executor.submit(refresh_cli, cli) for cli in ['claude', 'codex']]
            for f in futures:
                try:
                    f.result(timeout=30)
                except Exception:
                    pass

    # 延迟 800ms 后在后台执行增量刷新，不阻塞 UI
    def delayed_refresh():
        import time
        time.sleep(0.8)
        incremental_refresh_history()
        # 同步工具使用统计
        try:
            from ui.database import sync_tool_usage_from_history
            sync_tool_usage_from_history()
        except Exception as e:
            print(f"[工具统计同步] 错误: {e}")
    threading.Thread(target=delayed_refresh, daemon=True).start()

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

    # 延迟注册快捷键，确保窗口完全初始化
    def setup_hotkeys():
        import time
        time.sleep(0.5)  # 等待窗口完全初始化
        # 检查快捷键是否启用
        if state.settings.get('hotkey_enabled', True):
            setup_screenshot_hotkey(page=page)
            setup_copypath_hotkey(page=page)
    threading.Thread(target=setup_hotkeys, daemon=True).start()

    # 注册 Win+V 剪贴板粘贴支持
    setup_clipboard_paste(page)

    # 启动系统托盘图标（只创建一次）
    global _tray_icon
    if _tray_icon is None:
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
                flush_settings()  # 立即保存待写入的设置
                page.window.prevent_close = False  # 允许关闭
                stop_tray(_tray_icon)
                page.window.close()

            def tray_screenshot():
                import threading
                from ui.tools.screenshot_tool import ScreenshotTool
                save_dir = str(Path(__file__).parent / "screenshots")
                def run():
                    tool = ScreenshotTool(save_dir)
                    tool.start()
                threading.Thread(target=run, daemon=True).start()

            def tray_copy_path():
                import subprocess
                script = str(Path(__file__).parent / "ui" / "tools" / "path_picker.py")
                subprocess.Popen([sys.executable, script], creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

            _tray_icon = create_tray_icon(state, show_window, quit_app, tray_screenshot, tray_copy_path)
            global _global_tray_icon
            _global_tray_icon = _tray_icon  # 保存到全局变量供 atexit 清理
            run_tray_in_background(_tray_icon)
        except Exception:
            pass


if __name__ == "__main__":
    ft.app(target=main)
