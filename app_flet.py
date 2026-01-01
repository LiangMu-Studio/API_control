# AI CLI Manager - Flet Version (Modular)
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3

import flet as ft
import asyncio
import sys
from pathlib import Path
from ui.state import AppState
from ui.common import VERSION, save_settings, detect_terminals, detect_python_envs

# 获取图标路径（兼容打包后）
if getattr(sys, 'frozen', False):
    ICON_PATH = str(Path(sys.executable).parent / "icon.ico")
else:
    ICON_PATH = "icon.ico"
from ui.database import history_manager, codex_history_manager, history_cache
from ui.pages.api_keys import create_api_page
from ui.pages.prompts import create_prompts_page
from ui.pages.mcp import create_mcp_page
from ui.pages.history import create_history_page


def main(page: ft.Page):
    page.title = f"AI CLI Manager v{VERSION}"
    page.window.width = 1200
    page.window.height = 800
    page.padding = 0
    page.window.icon = ICON_PATH
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True

    # 初始化状态
    state = AppState(page)
    L = state.L
    theme = state.get_theme()

    page.bgcolor = theme['bg']
    page.theme_mode = ft.ThemeMode.DARK if state.theme_mode == 'dark' else ft.ThemeMode.LIGHT

    # 自定义标题栏
    title_bar = ft.WindowDragArea(
        content=ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TERMINAL, size=18, color=theme["text"]),
                ft.Text(f"AI CLI Manager v{VERSION}", size=14, color=theme["text"], weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.MINIMIZE, icon_size=16, icon_color=theme["text_sec"],
                             on_click=lambda _: setattr(page.window, 'minimized', True) or page.update()),
                ft.IconButton(ft.Icons.CROP_SQUARE, icon_size=16, icon_color=theme["text_sec"],
                             on_click=lambda _: setattr(page.window, 'maximized', not page.window.maximized) or page.update()),
                ft.IconButton(ft.Icons.CLOSE, icon_size=16, icon_color=theme["text_sec"],
                             on_click=lambda _: page.window.close()),
            ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=theme["surface"],
            padding=ft.padding.only(left=10, right=5, top=5, bottom=5),
        )
    )

    # 创建页面
    api_page, refresh_api = create_api_page(state)
    prompt_page, refresh_prompts = create_prompts_page(state)
    mcp_page, refresh_mcp = create_mcp_page(state)
    history_page, refresh_history = create_history_page(state)

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

    def refresh_title_bar():
        t = state.get_theme()
        container = title_bar.content
        container.bgcolor = t["surface"]
        for ctrl in container.content.controls:
            if isinstance(ctrl, ft.Icon):
                ctrl.color = t["text"]
            elif isinstance(ctrl, ft.Text):
                ctrl.color = t["text"]
            elif isinstance(ctrl, ft.IconButton):
                ctrl.icon_color = t["text_sec"]

    def toggle_theme(_):
        state.toggle_theme()
        page.bgcolor = state.get_theme()['bg']
        page.theme_mode = ft.ThemeMode.DARK if state.theme_mode == 'dark' else ft.ThemeMode.LIGHT
        refresh_title_bar()
        refresh_api()
        refresh_prompts()
        page.update()

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

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
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

    main_content = ft.Row([nav_rail, ft.VerticalDivider(width=1), content_area], expand=True)
    page.add(ft.Column([title_bar, main_content], spacing=0, expand=True))
    refresh_api()

    # 后台预加载历史
    async def preload_history():
        loop = asyncio.get_event_loop()
        if history_manager:
            history_cache["claude"] = await loop.run_in_executor(None, history_manager.load_sessions)
        if codex_history_manager:
            history_cache["codex"] = await loop.run_in_executor(None, codex_history_manager.load_sessions)
    page.run_task(preload_history)


if __name__ == "__main__":
    ft.app(target=main)
