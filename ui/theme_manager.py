"""主题管理模块 - 集中处理主题切换和刷新"""

import flet as ft


class ThemeManager:
    """主题管理器"""

    def __init__(self, state, page: ft.Page):
        self.state = state
        self.page = page
        self._refresh_callbacks = {}  # {page_idx: callback}
        self._title_bar = None
        self._content_area = None
        self._nav_rail = None
        self._divider = None

    def register_page(self, idx: int, refresh_callback):
        """注册页面刷新回调"""
        self._refresh_callbacks[idx] = refresh_callback

    def set_title_bar(self, title_bar):
        """设置标题栏引用"""
        self._title_bar = title_bar

    def set_layout(self, content_area, nav_rail, divider):
        """设置布局组件引用"""
        self._content_area = content_area
        self._nav_rail = nav_rail
        self._divider = divider

    def toggle(self, current_page_idx: int):
        """切换主题并刷新"""
        self.state.toggle_theme()
        self._apply_theme()
        self._refresh_title_bar()
        self._refresh_layout()
        self._refresh_page(current_page_idx)
        self.page.update()

    def _apply_theme(self):
        """应用主题到页面"""
        theme = self.state.get_theme()
        self.page.bgcolor = theme['bg']
        self.page.theme_mode = ft.ThemeMode.DARK if self.state.theme_mode == 'dark' else ft.ThemeMode.LIGHT

    def _refresh_title_bar(self):
        """刷新标题栏"""
        if not self._title_bar:
            return
        t = self.state.get_theme()
        container = self._title_bar.content
        container.bgcolor = t["surface"]
        for ctrl in container.content.controls:
            if isinstance(ctrl, ft.Icon):
                ctrl.color = t["text"]
            elif isinstance(ctrl, ft.Text):
                ctrl.color = t["text"]
            elif isinstance(ctrl, ft.IconButton):
                ctrl.icon_color = t["text_sec"]

    def _refresh_layout(self):
        """刷新布局组件"""
        t = self.state.get_theme()
        if self._content_area:
            self._content_area.bgcolor = t["surface"]
        if self._nav_rail:
            self._nav_rail.bgcolor = t["surface"]
            # 更新主题切换按钮图标
            if self._nav_rail.trailing:
                col = self._nav_rail.trailing.content
                if col and col.controls:
                    icon_btn = col.controls[0]
                    if isinstance(icon_btn, ft.IconButton):
                        icon_btn.icon = ft.Icons.DARK_MODE if self.state.theme_mode == 'light' else ft.Icons.LIGHT_MODE
        if self._divider:
            self._divider.color = t["border"]

    def _refresh_page(self, idx: int):
        """刷新指定页面"""
        if idx in self._refresh_callbacks:
            self._refresh_callbacks[idx]()
