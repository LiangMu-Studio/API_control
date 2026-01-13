# AI CLI Manager - API Keys Page
import flet as ft
import json
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import time

from ..common import (
    THEMES, CLI_TOOLS, save_configs, save_settings,
    detect_terminals, detect_python_envs, write_prompt_to_cli, detect_prompt_from_file,
    show_snackbar, has_windows_terminal
)
from ..clipboard_paste import enable_clipboard_paste
from ..database import history_manager, codex_history_manager, mcp_skill_library

# 导入 Rust 历史记录模块
try:
    import liangmu_history as lh
except ImportError:
    lh = None

# 会话选项二级缓存 - 避免重复构建下拉选项
_session_options_cache = {}  # {(cli_type, cwd): (options, raw_sessions, timestamp)}
_SESSION_CACHE_TTL = 30  # 缓存有效期（秒）

def _get_cached_session_options(cli_type: str, cwd: str):
    """获取缓存的会话选项"""
    key = (cli_type, cwd)
    if key in _session_options_cache:
        opts, sessions, ts = _session_options_cache[key]
        if time.time() - ts < _SESSION_CACHE_TTL:
            return opts, sessions
    return None, None

def _set_session_options_cache(cli_type: str, cwd: str, opts, sessions):
    """设置会话选项缓存"""
    key = (cli_type, cwd)
    _session_options_cache[key] = (opts, sessions, time.time())
    # 清理过期缓存（保留最近 10 个）
    if len(_session_options_cache) > 10:
        oldest_key = min(_session_options_cache, key=lambda k: _session_options_cache[k][2])
        del _session_options_cache[oldest_key]

def _safe_env_value(val: str) -> str:
    """转义环境变量值中的特殊字符，防止命令注入"""
    if not val:
        return val
    # 只移除命令分隔符，保留 % 等合法字符
    return re.sub(r'[&|<>^]', '', val)

# 辅助函数：从配置获取 cli_type（兼容新旧格式）
def get_cli_type(cfg):
    """从配置获取 cli_type，用于树形结构分组"""
    return cfg.get('cli_type', 'claude')

# 提供商默认配置 - 完全复刻自 AI_talk
PROVIDER_DEFAULTS = {
    'openai': {
        'endpoint': 'https://api.openai.com/v1',
        'key_name': 'OPENAI_API_KEY',
        'base_url_env': 'OPENAI_BASE_URL',
        'available_models': ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 'gpt-5', 'gpt-5.1-codex-max', 'gpt-5.2-codex'],
        'default_model': 'gpt-4o'
    },
    'anthropic': {
        'endpoint': 'https://api.anthropic.com',
        'key_name': 'ANTHROPIC_AUTH_TOKEN',
        'base_url_env': 'ANTHROPIC_BASE_URL',
        'available_models': ['claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101'],
        'default_model': 'claude-haiku-4-5-20251001'
    },
    'gemini': {
        'endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'key_name': 'x-goog-api-key',
        'base_url_env': 'GEMINI_API_BASE',
        'available_models': [
            {'name': 'gemini-2.5-pro', 'label': 'Gemini 2.5 Pro'},
            {'name': 'gemini-2.5-flash', 'label': 'Gemini 2.5 Flash'},
            {'name': 'gemini-2.5-flash-lite', 'label': 'Gemini 2.5 Flash-Lite'},
            {'name': 'gemini-3-pro-preview', 'label': 'Gemini 3 Pro Preview'},
            {'name': 'gemini-3-pro-high', 'label': 'Gemini 3 Pro High'},
            {'name': 'gemini-3-pro-image', 'label': 'Gemini 3 Pro Image'},
            {'name': 'gemini-2.5-pro-preview-06-05', 'label': 'Gemini 2.5 Pro Preview'}
        ],
        'default_model': 'gemini-2.5-pro'
    },
    'deepseek': {
        'endpoint': 'https://api.deepseek.com/v1',
        'key_name': 'DEEPSEEK_API_KEY',
        'base_url_env': 'DEEPSEEK_BASE_URL',
        'available_models': ['DeepSeek-V3.2', 'DeepSeek-V3', 'DeepSeek-R1'],
        'default_model': 'DeepSeek-V3.2'
    },
    'glm': {
        'endpoint': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key_name': 'ZHIPU_API_KEY',
        'base_url_env': 'ZHIPU_BASE_URL',
        'available_models': [
            {'name': 'glm-4.7', 'label': 'glm-4.7 (快速模式)', 'mode': 'fast'},
            {'name': 'glm-4.7', 'label': 'glm-4.7 (均衡模式)', 'mode': 'balanced'},
            {'name': 'glm-4.7', 'label': 'glm-4.7 (深度思考模式)', 'mode': 'deep'},
            {'name': 'glm-4.7', 'label': 'glm-4.7 (创意模式)', 'mode': 'creative'},
            {'name': 'glm-4.7', 'label': 'glm-4.7 (精确模式)', 'mode': 'precise'},
            {'name': 'cogview-3', 'label': 'GLM 绘画 (CogView-3)', 'mode': 'image'}
        ],
        'default_model': 'glm-4.7'
    },
    'custom': {
        'endpoint': '',
        'key_name': 'API_KEY',
        'base_url_env': 'API_BASE_URL',
        'available_models': [],
        'default_model': None
    }
}


def create_api_page(state):
    """创建 API 密钥页面"""
    page = state.page
    L = state.L
    theme = state.get_theme()

    # 首次运行检测 Windows Terminal
    if sys.platform == 'win32' and not state.settings.get('wt_check_done'):
        if not has_windows_terminal():
            def open_store(e):
                import webbrowser
                webbrowser.open('ms-windows-store://pdp/?productid=9N0DX20HK701')
                page.close(wt_dlg)
            wt_dlg = ft.AlertDialog(
                title=ft.Text(L.get('wt_recommend', '推荐安装 Windows Terminal')),
                content=ft.Text(L.get('wt_recommend_desc', 'Windows Terminal 支持多标签页管理，可以更优雅地管理多个终端窗口。建议从 Microsoft Store 安装。')),
                actions=[
                    ft.TextButton(L.get('later', '稍后'), on_click=lambda e: page.close(wt_dlg)),
                    ft.ElevatedButton(L.get('install_now', '立即安装'), on_click=open_store),
                ],
            )
            page.open(wt_dlg)
        state.settings['wt_check_done'] = True
        save_settings(state.settings)

    # UI 组件
    config_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    current_key_label = ft.Text(L['not_selected'], color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD)
    state.config_tree = config_tree
    state.current_key_label = current_key_label

    # 缓存控件引用
    _tree_refs = {"cli": {}, "endpoint": {}, "config": {}}
    _last_click = {"config": None, "time": 0}  # 双击检测

    # 终端和环境下拉 - 优先使用上次选择的
    last_terminal = state.settings.get('last_terminal', '')
    last_env = state.settings.get('last_python_env', '')

    def on_terminal_change(e):
        """终端切换时的处理"""
        save_last_selection('last_terminal', e.control.value)
        # WSL 无法使用 Windows 的会话历史，自动切换到"不加载"
        if 'wsl' in e.control.value.lower():
            session_dropdown.value = '__none__'
            page.update()

    terminal_dropdown = ft.Dropdown(
        label=L['select_terminal'],
        value=last_terminal if last_terminal in state.terminals else (list(state.terminals.keys())[0] if state.terminals else ''),
        options=[ft.dropdown.Option(k) for k in state.terminals.keys()],
        width=180,
        on_change=on_terminal_change,
    )
    python_env_dropdown = ft.Dropdown(
        label=L['python_env'],
        value=last_env if last_env in state.python_envs else (list(state.python_envs.keys())[0] if state.python_envs else ''),
        options=[ft.dropdown.Option(k) for k in state.python_envs.keys()],
        width=220,
        on_change=lambda e: save_last_selection('last_python_env', e.control.value),
    )

    def save_last_selection(key, value):
        """保存上次选择到 settings"""
        state.settings[key] = value
        save_settings(state.settings)

    # 工作目录历史记录
    work_dir_history = state.settings.get('work_dir_history', [])
    current_work_dir = state.settings.get('work_dir', '')

    # 共享 FilePicker（避免重复创建）
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    def build_workdir_menu_items():
        return [ft.PopupMenuItem(text=d, on_click=lambda e, p=d: select_workdir(p)) for d in reversed(work_dir_history[-10:])]

    def select_workdir(path):
        work_dir_input.value = path
        save_work_dir(path)
        work_dir_input.update()
        _session_loaded[0] = False
        _session_loading[0] = False  # 重置加载锁，确保能触发刷新
        # 复刻 DEV 版：文件夹变化时强制刷新缓存
        refresh_session_dropdown_async(force_refresh=True)

    work_dir_input = ft.TextField(
        label=L['work_dir'],
        value=current_work_dir,
        expand=True,
    )
    work_dir_menu = ft.PopupMenuButton(
        icon=ft.Icons.ARROW_DROP_DOWN,
        items=build_workdir_menu_items(),
        tooltip=L.get('history', '历史记录'),
    )

    def save_work_dir(path):
        if not path:
            return
        state.settings['work_dir'] = path
        if path in work_dir_history:
            work_dir_history.remove(path)
        work_dir_history.append(path)
        state.settings['work_dir_history'] = work_dir_history[-10:]
        save_settings(state.settings)

    # 后台初始化工作目录历史（不阻塞 UI）
    def init_workdir_history_bg():
        if work_dir_history or not history_manager:
            return
        for pname in history_manager.list_projects(limit=10):
            cwd = history_manager.get_project_cwd(pname)
            if cwd and Path(cwd).is_dir() and cwd not in work_dir_history:
                work_dir_history.append(cwd)
            if len(work_dir_history) >= 5:
                break
        if work_dir_history:
            state.settings['work_dir_history'] = work_dir_history
            state.settings['work_dir'] = work_dir_history[-1]
            save_settings(state.settings)
            # 更新 UI
            def update_ui():
                work_dir_input.value = work_dir_history[-1]
                work_dir_menu.items = build_workdir_menu_items()
                page.update()
            page.run_thread(update_ui)
    import threading
    threading.Thread(target=init_workdir_history_bg, daemon=True).start()

    def clear_workdir_history(e):
        current = work_dir_input.value
        if not current or current not in work_dir_history:
            return
        def do_clear(_):
            page.close(dlg)
            cnt = history_manager.delete_sessions_by_cwd(current) if history_manager else 0
            # 1. 从历史列表中删除
            work_dir_history.remove(current)
            state.settings['work_dir_history'] = work_dir_history[-10:]
            save_settings(state.settings)
            # 2. 更新下拉菜单
            work_dir_menu.items = build_workdir_menu_items()
            # 3. 清空地址栏，切换到上一个目录
            work_dir_input.value = work_dir_history[-1] if work_dir_history else ''
            state.settings['work_dir'] = work_dir_input.value
            save_settings(state.settings)
            # 4. 刷新会话下拉框
            _session_loaded[0] = False
            refresh_session_dropdown_async(force_refresh=True)
            show_snackbar(page, L.get('history_cleared_with_sessions', '已删除: {} ({}个会话移到回收站)').format(current[-30:], cnt))
            page.update()
        dlg = ft.AlertDialog(
            title=ft.Text(L.get('confirm_delete', '确认删除')),
            content=ft.Text(L.get('confirm_clear_folder_history', '是否要删除本文件夹历史记录？')),
            actions=[ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: page.close(dlg)), ft.TextButton(L.get('confirm', '确认'), on_click=do_clear)]
        )
        page.open(dlg)

    # 会话恢复下拉框
    def get_selected_cli_type():
        """获取当前选中 KEY 的 cli_type"""
        if state.selected_config is not None and state.selected_config < len(state.configs):
            return get_cli_type(state.configs[state.selected_config])
        return 'claude'

    def build_session_options(cwd, force_refresh=False):
        """构建会话选项列表 - 带二级缓存

        流程:
        1. 检查二级缓存（非强制刷新时）
        2. 如果 Rust 模块可用，使用缓存机制
        3. 否则回退到 Python 实现
        """
        cli_type = get_selected_cli_type()

        # 检查二级缓存
        if not force_refresh:
            cached_opts, cached_sessions = _get_cached_session_options(cli_type, cwd)
            if cached_opts is not None:
                state._sessions_cache = cached_sessions
                return cached_opts

        opts = []
        state._current_project = None

        if not cwd:
            opts.append(ft.dropdown.Option(key='__none__', text=L.get('no_old_session', '不加载旧对话')))
            return opts

        # gemini 暂不支持会话历史
        if cli_type == 'gemini':
            opts.append(ft.dropdown.Option(key='__none__', text=L.get('no_old_session', '不加载旧对话')))
            return opts

        try:
            raw_sessions = []

            # 优先使用 Rust 缓存模块
            if lh is not None:
                if force_refresh:
                    # 强制刷新：扫描文件系统 -> 更新缓存 -> 返回会话列表
                    raw_sessions = lh.refresh_and_load_sessions(cli_type, cwd)
                else:
                    # 快速模式：优先从缓存查找
                    project = lh.find_project_by_cwd_cached(cli_type, cwd)
                    if project:
                        state._current_project = project.id
                        raw_sessions = lh.load_project_from_cache(cli_type, project.id)
                        if not raw_sessions:
                            # 缓存为空，回退到文件系统
                            raw_sessions = lh.load_project(cli_type, project.id)
                    else:
                        # 缓存没有，尝试文件系统查找
                        project = lh.find_project_by_cwd(cli_type, cwd)
                        if project:
                            state._current_project = project.id
                            raw_sessions = lh.refresh_and_load_sessions(cli_type, cwd)
            else:
                # 回退到 Python 实现
                hm = codex_history_manager if cli_type == 'codex' else history_manager
                if hm:
                    project = hm.find_project_by_cwd(cwd)
                    if project:
                        state._current_project = project
                        raw_sessions = hm.load_project(project) or []

            # 缓存会话列表供预览使用
            state._sessions_cache = raw_sessions

            # 转换为下拉选项（反转顺序：最新的在最下面）
            for s in reversed(raw_sessions):
                # 兼容 Rust SessionInfo 和 Python dict
                if hasattr(s, 'last_timestamp'):
                    ts = (s.last_timestamp or '')[:16].replace('T', ' ')
                    sid = s.id
                    fpath = s.file_path
                    turns = getattr(s, 'user_turn_count', 0)
                else:
                    ts = (s.get('last_timestamp') or '')[:16].replace('T', ' ')
                    sid = s.get('id', '')
                    fpath = s.get('file_path', '')
                    turns = s.get('user_turn_count', s.get('message_count', 0))

                # 格式: 时间 | 轮数 | ID
                turn_text = f"{turns}轮" if turns else ""
                if cli_type == 'codex':
                    display = f"{ts} | {turn_text} | {sid[:12]}" if turn_text else f"{ts} | {sid[:12]}"
                    opts.append(ft.dropdown.Option(key=fpath, text=display[:50]))
                else:
                    display = f"{ts} | {turn_text} | {sid[:12]}" if turn_text else f"{ts} | {sid[:12]}"
                    opts.append(ft.dropdown.Option(key=sid, text=display[:50]))
                    if not state._current_project:
                        state._current_project = sid  # 记录用于预览

        except Exception as e:
            print(f"[build_session_options] 错误: {e}")

        opts.append(ft.dropdown.Option(key='__none__', text=L.get('no_old_session', '不加载旧对话')))

        # 保存到二级缓存
        if cwd and hasattr(state, '_sessions_cache'):
            _set_session_options_cache(cli_type, cwd, opts, state._sessions_cache)

        return opts

    session_dropdown = ft.Dropdown(
        label=L.get('session_resume', '恢复会话'),
        options=[ft.dropdown.Option(key='__none__', text=L.get('no_old_session', '不加载旧对话'))],
        value='__none__',
        width=400,
    )

    # 预览状态 - 复刻 DEV 版的分页加载机制
    _preview_paginated = [None]  # PaginatedMessages
    _preview_all_messages = [[]]  # 当没有中间部分时的全部消息
    _preview_first_turns = [3]  # 当前加载的前段轮数
    _preview_last_turns = [3]   # 当前加载的后段轮数

    def show_session_preview(_):
        """显示会话预览 - 复刻 DEV 版的分页预览"""
        sid = session_dropdown.value
        if sid == '__none__':
            show_snackbar(page, L.get('no_session_selected', '请先选择一个会话'))
            return

        cli_type = get_selected_cli_type()

        # 获取会话文件路径
        file_path = None
        if hasattr(state, '_sessions_cache') and state._sessions_cache:
            for s in state._sessions_cache:
                s_id = s.id if hasattr(s, 'id') else s.get('id', '')
                s_path = s.file_path if hasattr(s, 'file_path') else s.get('file_path', '')
                if s_id == sid or s_path == sid:
                    file_path = s_path
                    break

        if not file_path:
            show_snackbar(page, L.get('session_not_found', '会话文件未找到'))
            return

        # 使用 Rust 分页加载（首尾各3轮）
        _preview_first_turns[0] = 3
        _preview_last_turns[0] = 3

        try:
            if lh is not None:
                paginated = lh.load_session_paginated(cli_type, file_path, 3, 3)
                if paginated is None:
                    show_snackbar(page, L.get('load_failed', '加载失败'))
                    return
                _preview_paginated[0] = paginated
                _preview_all_messages[0] = []
                if not paginated.has_middle:
                    _preview_all_messages[0] = list(paginated.first)
                _show_preview_dialog(file_path)
            else:
                # 回退到旧的预览方式
                _show_legacy_preview(sid)
        except Exception as e:
            print(f"[show_session_preview] 错误: {e}")
            show_snackbar(page, f"预览失败: {e}")

    def _show_legacy_preview(sid):
        """旧版预览（Python 实现）"""
        if not getattr(state, '_current_project', None):
            show_snackbar(page, L.get('no_project_found', '未找到匹配的项目'))
            return
        sessions = history_manager.load_project(state._current_project) if history_manager else {}
        info = sessions.get(sid)
        if not info:
            return
        messages = info.get('messages', [])
        last_user_txt, last_ai_txt = '', ''
        for m in reversed(messages):
            msg_type = m.get('type')
            msg_obj = m.get('message', {})
            if isinstance(msg_obj, dict):
                for x in msg_obj.get('content', []):
                    if isinstance(x, dict) and x.get('type') == 'text':
                        txt = x.get('text', '')
                        if msg_type == 'assistant' and not last_ai_txt:
                            last_ai_txt = txt[:500]
                        elif msg_type == 'user' and not last_user_txt and not txt.startswith('<'):
                            last_user_txt = txt[:500]
            if last_user_txt and last_ai_txt:
                break
        dlg = ft.AlertDialog(
            title=ft.Text(f"会话: {sid[:30]}"),
            content=ft.Container(
                ft.Column([
                    ft.Text("👤 用户:", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
                    ft.Text(last_user_txt or '(无)', selectable=True),
                    ft.Divider(),
                    ft.Text("🤖 AI:", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN),
                    ft.Text(last_ai_txt or '(无)', selectable=True),
                ], scroll=ft.ScrollMode.AUTO),
                width=550, height=350,
            ),
            actions=[ft.TextButton(L.get('close', '关闭'), on_click=lambda _: page.close(dlg))],
        )
        page.open(dlg)

    def _render_message(msg, step):
        """渲染单条消息 - 复刻 DEV 版气泡设计（无头像）"""
        role = msg.role if hasattr(msg, 'role') else msg.get('role', '')
        # 检查是否是真实用户消息（排除工具结果返回的假用户消息）
        is_real_user = getattr(msg, 'is_real_user', True) if hasattr(msg, 'is_real_user') else True
        is_user = role == 'user' and is_real_user
        is_tool_result = role == 'user' and not is_real_user

        # 获取文本内容
        if hasattr(msg, 'content_blocks') and msg.content_blocks:
            text_parts = []
            for b in msg.content_blocks:
                t = b.text if hasattr(b, 'text') else None
                if t:
                    text_parts.append(t)
            text = '\n'.join(text_parts)[:800]
        elif hasattr(msg, 'get_text'):
            # 使用 Rust 的 get_text 方法
            text = msg.get_text()[:800]
        else:
            text = msg.get('text', '')[:800]

        # 工具结果不显示文本内容（通常很长），只显示标记
        if is_tool_result:
            label_text = "Tool Result"
            label_bg = ft.Colors.ORANGE_500
            border_color = ft.Colors.ORANGE_500
            bg_color = ft.Colors.with_opacity(0.04, ft.Colors.ORANGE)
            text = f"[工具返回结果 - {len(text)} 字符]" if text else "[工具返回]"
        elif is_user:
            label_text = "User"
            label_bg = ft.Colors.BLUE_500
            border_color = ft.Colors.BLUE_500
            bg_color = ft.Colors.with_opacity(0.06, ft.Colors.BLUE)
        else:
            label_text = "Assistant"
            label_bg = ft.Colors.GREEN_500
            border_color = ft.Colors.GREEN_500
            bg_color = ft.Colors.with_opacity(0.06, ft.Colors.GREEN)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"#{step}", size=10, color=ft.Colors.GREY_500),
                    ft.Container(
                        ft.Text(label_text, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                        bgcolor=label_bg, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=4,
                    ),
                ], spacing=8),
                ft.Text(text or '(无内容)', selectable=True, size=13),
            ], spacing=4),
            bgcolor=bg_color,
            padding=ft.padding.only(left=10, top=8, bottom=8, right=10),
            border=ft.border.only(left=ft.BorderSide(4, border_color)),
            border_radius=8,
            margin=ft.margin.only(bottom=8),
        )

    def _show_preview_dialog(file_path):
        """显示分页预览对话框 - 复刻 DEV 版"""
        paginated = _preview_paginated[0]
        if paginated is None:
            return

        cli_type = get_selected_cli_type()

        def load_more_down(_):
            """向下展开（加载更多前面的消息）"""
            nonlocal paginated
            _preview_first_turns[0] += 10
            try:
                new_paginated = lh.load_session_paginated(cli_type, file_path, _preview_first_turns[0], _preview_last_turns[0])
                if new_paginated:
                    _preview_paginated[0] = new_paginated
                    paginated = new_paginated
                    if not new_paginated.has_middle:
                        _preview_all_messages[0] = list(new_paginated.first) + list(new_paginated.last)
                    _refresh_preview_content()
            except Exception as e:
                print(f"[load_more_down] 错误: {e}")

        def load_more_up(_):
            """向上展开（加载更多后面的消息）"""
            nonlocal paginated
            _preview_last_turns[0] += 10
            try:
                new_paginated = lh.load_session_paginated(cli_type, file_path, _preview_first_turns[0], _preview_last_turns[0])
                if new_paginated:
                    _preview_paginated[0] = new_paginated
                    paginated = new_paginated
                    if not new_paginated.has_middle:
                        _preview_all_messages[0] = list(new_paginated.first) + list(new_paginated.last)
                    _refresh_preview_content()
            except Exception as e:
                print(f"[load_more_up] 错误: {e}")

        def _refresh_preview_content():
            """刷新预览内容"""
            paginated = _preview_paginated[0]
            content_col.controls.clear()

            if paginated.has_middle:
                # 有中间部分：显示前段 + 展开按钮 + 后段
                step = 1
                for msg in paginated.first:
                    content_col.controls.append(_render_message(msg, step))
                    step += 1

                # 中间展开区域
                first_user_count = sum(1 for m in paginated.first if (m.role if hasattr(m, 'role') else m.get('role', '')) == 'user')
                last_user_count = sum(1 for m in paginated.last if (m.role if hasattr(m, 'role') else m.get('role', '')) == 'user')
                hidden_turns = paginated.total_turns - first_user_count - last_user_count

                content_col.controls.append(ft.Container(
                    content=ft.Row([
                        ft.ElevatedButton(f"↓ {L.get('expand_down', '向下展开')} +10", on_click=load_more_down),
                        ft.Text(f"{L.get('hidden', '隐藏')} {hidden_turns} {L.get('turns', '轮')}", color=ft.Colors.GREY_500),
                        ft.ElevatedButton(f"↑ {L.get('expand_up', '向上展开')} +10", on_click=load_more_up),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    padding=ft.padding.symmetric(vertical=15),
                ))

                # 后段消息
                start_step = paginated.total_messages - len(paginated.last) + 1
                for i, msg in enumerate(paginated.last):
                    content_col.controls.append(_render_message(msg, start_step + i))
            else:
                # 没有中间部分：显示全部消息
                messages = _preview_all_messages[0] if _preview_all_messages[0] else list(paginated.first)
                for i, msg in enumerate(messages):
                    content_col.controls.append(_render_message(msg, i + 1))

            page.update()

        # 初始化内容
        content_col = ft.Column([], scroll=ft.ScrollMode.AUTO, spacing=0)
        _refresh_preview_content()

        dlg = ft.AlertDialog(
            title=ft.Text(f"{L.get('preview', '预览')} ({paginated.total_turns} {L.get('turns', '轮')})"),
            content=ft.Container(
                content_col,
                width=650, height=450,
            ),
            actions=[ft.TextButton(L.get('close', '关闭'), on_click=lambda _: page.close(dlg))],
        )
        page.open(dlg)

    session_preview_btn = ft.IconButton(ft.Icons.PREVIEW, tooltip=L.get('preview_session', '预览会话'), on_click=show_session_preview)

    _session_loaded = [False]
    _session_loading = [False]  # 防止重复加载
    _initial_load_done = [False]  # 启动延迟加载标记

    def refresh_session_dropdown_async(force_refresh=False):
        """后台异步加载会话列表 - 复刻 DEV 版的延迟加载机制"""
        if _session_loading[0]:
            return
        _session_loading[0] = True
        cwd = work_dir_input.value

        def do_load():
            opts = build_session_options(cwd, force_refresh=force_refresh)
            # 在后台线程中计算默认选中值，减少主线程工作
            default_value = '__none__'
            if len(opts) > 1:
                last_session = state.settings.get('last_session', '')
                opt_keys = {opt.key for opt in opts}
                if last_session in opt_keys:
                    default_value = last_session
                else:
                    default_value = opts[-2].key  # 最新会话
            def update_ui():
                session_dropdown.options = opts
                session_dropdown.value = default_value
                _session_loaded[0] = True
                _session_loading[0] = False
                page.update()
            page.run_thread(update_ui)

        import threading
        threading.Thread(target=do_load, daemon=True).start()

    def save_selected_session(e):
        """保存选中的会话到 settings"""
        if e.control.value and e.control.value != '__none__':
            state.settings['last_session'] = e.control.value
            save_settings(state.settings)

    # 给 session_dropdown 添加 on_change
    session_dropdown.on_change = save_selected_session

    # 工作目录变化时刷新会话列表 - 复刻 DEV 版强制刷新
    def on_workdir_change(e):
        save_work_dir(e.control.value)
        _session_loaded[0] = False  # 重置加载状态
        _session_loading[0] = False  # 重置加载锁
        refresh_session_dropdown_async(force_refresh=True)  # 强制刷新缓存

    work_dir_input.on_submit = on_workdir_change
    work_dir_input.on_blur = on_workdir_change

    # 懒加载：点击会话下拉框时才加载
    def on_session_focus(e):
        if not _session_loaded[0]:
            refresh_session_dropdown_async()
    session_dropdown.on_focus = on_session_focus

    # 提示词下拉 - 带缓存
    _prompt_options_cache = [None, None]  # [options, prompts_hash]

    def build_prompt_options():
        """构建提示词选项（带缓存）"""
        # 检查缓存
        current_hash = hash(tuple(sorted(state.prompts.keys())))
        if _prompt_options_cache[0] is not None and _prompt_options_cache[1] == current_hash:
            return _prompt_options_cache[0]

        by_cat = {}
        for pid, p in state.prompts.items():
            if p.get('prompt_type') == 'system':
                continue
            cat = p.get('category', '其他')
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append((pid, p))
        order = ['编程', '写作', '分析', '绘画', '用户', '其他']
        sorted_cats = [c for c in order if c in by_cat] + [c for c in by_cat if c not in order]
        options = []
        for cat in sorted_cats:
            options.append(ft.dropdown.Option(key=f"__cat_{cat}", text=f"── {cat} ──", disabled=True))
            for pid, p in by_cat[cat]:
                options.append(ft.dropdown.Option(key=pid, text=f"  {p.get('name', pid)}"))

        # 更新缓存
        _prompt_options_cache[0] = options
        _prompt_options_cache[1] = current_hash
        return options

    prompt_dropdown = ft.Dropdown(label=L['prompts'], options=build_prompt_options(), width=220)

    # MCP 预设下拉框
    def build_mcp_preset_options():
        presets = mcp_skill_library.get_all_mcp_presets()
        opts = [ft.dropdown.Option(key='', text=L.get('preset_none', '无预设'))]
        for p in presets:
            label = f"★ {p['name']}" if p.get('is_default') else p['name']
            opts.append(ft.dropdown.Option(key=p['name'], text=label))
        return opts

    mcp_preset_dropdown = ft.Dropdown(
        label=L.get('preset_mcp', 'MCP预设'), options=build_mcp_preset_options(), width=140
    )

    # Skill 预设下拉框
    def build_skill_preset_options():
        presets = mcp_skill_library.get_all_skill_presets()
        opts = [ft.dropdown.Option(key='', text=L.get('preset_none', '无预设'))]
        for p in presets:
            label = f"★ {p['name']}" if p.get('is_default') else p['name']
            opts.append(ft.dropdown.Option(key=p['name'], text=label))
        return opts

    skill_preset_dropdown = ft.Dropdown(
        label=L.get('preset_skill', 'Skill预设'), options=build_skill_preset_options(), width=140
    )

    def apply_mcp_preset(e):
        """应用 MCP 预设到当前工作目录"""
        if not work_dir_input.value:
            show_snackbar(page, L['prompt_select_workdir'])
            return
        preset_name = mcp_preset_dropdown.value
        if not preset_name:
            return
        presets = mcp_skill_library.get_all_mcp_presets()
        preset = next((p for p in presets if p['name'] == preset_name), None)
        if not preset:
            return
        # 构建 MCP 配置
        mcp_servers = {}
        for mcp_name in preset.get('mcp_names', []):
            mcp = mcp_skill_library.get_mcp(mcp_name)
            if mcp:
                server_config = {'command': mcp.get('command', 'npx')}
                if mcp.get('args'):
                    server_config['args'] = mcp['args'].split()
                if mcp.get('env'):
                    env_dict = {}
                    for part in mcp['env'].split():
                        if '=' in part:
                            k, v = part.split('=', 1)
                            env_dict[k] = v
                    if env_dict:
                        server_config['env'] = env_dict
                mcp_servers[mcp_name] = server_config
        # 写入工作目录
        cwd = Path(work_dir_input.value)
        mcp_path = cwd / '.claude' / '.mcp.json'
        mcp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mcp_path, 'w', encoding='utf-8') as f:
            json.dump({'mcpServers': mcp_servers}, f, indent=2, ensure_ascii=False)
        show_snackbar(page, L.get('preset_applied', '预设已应用'))
        page.update()

    def apply_skill_preset(e):
        """应用 Skill 预设到当前工作目录"""
        if not work_dir_input.value:
            show_snackbar(page, L['prompt_select_workdir'])
            return
        preset_name = skill_preset_dropdown.value
        if not preset_name:
            return
        presets = mcp_skill_library.get_all_skill_presets()
        preset = next((p for p in presets if p['name'] == preset_name), None)
        if not preset:
            return
        # 复制 Skill 文件到工作目录
        cwd = Path(work_dir_input.value)
        skill_dir = cwd / '.claude' / 'skills'
        skill_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for skill_name in preset.get('skill_names', []):
            skill = mcp_skill_library.get_skill(skill_name)
            if skill:
                # 优先从文件路径复制
                if skill.get('file_path') and Path(skill['file_path']).exists():
                    shutil.copy2(skill['file_path'], skill_dir / f"{skill_name}.md")
                    copied += 1
                elif skill.get('content'):
                    (skill_dir / f"{skill_name}.md").write_text(skill['content'], encoding='utf-8')
                    copied += 1
        show_snackbar(page, L.get('preset_applied', '预设已应用') + f" ({copied})")
        page.update()

    mcp_preset_dropdown.on_change = apply_mcp_preset
    skill_preset_dropdown.on_change = apply_skill_preset

    # 工作目录 MCP 状态
    workdir_mcp_enabled = {}

    def _on_cli_click(cli_key):
        if state.selected_cli == cli_key and state.selected_endpoint is None and state.selected_config is None:
            state.toggle_cli(cli_key)
            refresh_config_list()
        else:
            state.select_cli(cli_key)
            _update_selection()
        page.update()

    def _on_endpoint_click(ep_key):
        if state.selected_endpoint == ep_key and state.selected_config is None:
            state.toggle_endpoint(ep_key)
            refresh_config_list()
        else:
            state.select_endpoint(ep_key)
            _update_selection()
        page.update()

    def _on_config_click(idx):
        now = time.time()
        # 双击检测：同一项 400ms 内再次点击
        if _last_click["config"] == idx and (now - _last_click["time"]) < 0.4:
            show_config_dialog(idx)
            _last_click["config"] = None
            return
        _last_click["config"] = idx
        _last_click["time"] = now
        state.select_config(idx)
        # 保存选中的配置索引
        state.settings['last_selected_config'] = idx
        save_settings(state.settings)
        # 根据 cli_type 刷新会话列表
        _session_loaded[0] = False
        refresh_session_dropdown_async()
        _update_selection()
        page.update()

    # 上次选中状态（用于增量更新）
    _last_selection = {'cli': None, 'endpoint': None, 'config': None}

    def _update_selection():
        """增量更新选中状态 - 只更新改变的项"""
        theme = state.get_theme()
        old_cli, old_ep, old_cfg = _last_selection['cli'], _last_selection['endpoint'], _last_selection['config']
        new_cli = state.selected_cli if state.selected_endpoint is None and state.selected_config is None else None
        new_ep = state.selected_endpoint if state.selected_config is None else None
        new_cfg = state.selected_config

        # 更新 CLI 级别
        if old_cli != new_cli:
            if old_cli and old_cli in _tree_refs["cli"]:
                ref = _tree_refs["cli"][old_cli]
                ref["c"].bgcolor = theme['header_bg']
                ref["t"].color = theme['text']
            if new_cli and new_cli in _tree_refs["cli"]:
                ref = _tree_refs["cli"][new_cli]
                ref["c"].bgcolor = theme['selection_bg']
                ref["t"].color = theme['text_selected']

        # 更新 Endpoint 级别
        if old_ep != new_ep:
            if old_ep and old_ep in _tree_refs["endpoint"]:
                ref = _tree_refs["endpoint"][old_ep]
                ref["c"].bgcolor = None
                ref["t"].color = theme['text']
            if new_ep and new_ep in _tree_refs["endpoint"]:
                ref = _tree_refs["endpoint"][new_ep]
                ref["c"].bgcolor = theme['selection_bg']
                ref["t"].color = theme['text_selected']

        # 更新 Config 级别
        if old_cfg != new_cfg:
            if old_cfg is not None and old_cfg in _tree_refs["config"]:
                ref = _tree_refs["config"][old_cfg]
                ref["c"].bgcolor = None
                ref["t"].weight = None
                ref["t"].color = theme['text']
                ref["i"].color = ft.Colors.GREY_600
            if new_cfg is not None and new_cfg in _tree_refs["config"]:
                ref = _tree_refs["config"][new_cfg]
                ref["c"].bgcolor = theme['selection_bg']
                ref["t"].weight = ft.FontWeight.BOLD
                ref["t"].color = theme['text_selected']
                ref["i"].color = theme['icon_key_selected']

        # 记录当前状态
        _last_selection['cli'] = new_cli
        _last_selection['endpoint'] = new_ep
        _last_selection['config'] = new_cfg

    def refresh_config_list():
        config_tree.controls.clear()
        _tree_refs["cli"].clear()
        _tree_refs["endpoint"].clear()
        _tree_refs["config"].clear()
        tree = state.build_tree_structure()
        theme = state.get_theme()

        for cli_type in tree:
            cli_name = CLI_TOOLS.get(cli_type, {}).get('name', cli_type)
            is_exp = state.expanded_cli.get(cli_type, True)
            is_sel = state.selected_cli == cli_type and state.selected_endpoint is None and state.selected_config is None

            cli_text = ft.Text(cli_name, weight=ft.FontWeight.BOLD, color=theme['text_selected'] if is_sel else theme['text'])
            cli_container = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_exp else ft.Icons.ARROW_RIGHT, size=20, color=theme['text']),
                    ft.Icon(ft.Icons.TERMINAL, color=theme['icon_cli']),
                    cli_text,
                    ft.Text(f"({sum(len(v) for v in tree[cli_type].values())})", color=theme['text_sec']),
                ], spacing=5),
                padding=ft.padding.only(left=5, top=8, bottom=8),
                bgcolor=theme['selection_bg'] if is_sel else theme['header_bg'],
                border_radius=4, ink=True,
                on_click=lambda e, k=cli_type: _on_cli_click(k),
            )
            _tree_refs["cli"][cli_type] = {"c": cli_container, "t": cli_text}
            config_tree.controls.append(cli_container)

            if is_exp:
                for endpoint in tree[cli_type]:
                    ep_key = f"{cli_type}:{endpoint}"
                    ep_exp = state.expanded_endpoint.get(ep_key, True)
                    short_ep = endpoint[:40] + "..." if len(endpoint) > 40 else endpoint
                    ep_sel = state.selected_endpoint == ep_key and state.selected_config is None

                    ep_text = ft.Text(short_ep, size=13, color=theme['text_selected'] if ep_sel else theme['text'])
                    ep_container = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN if ep_exp else ft.Icons.ARROW_RIGHT, size=18, color=theme['text']),
                            ft.Icon(ft.Icons.LINK, size=16, color=theme['icon_endpoint']),
                            ep_text,
                            ft.Text(f"({len(tree[cli_type][endpoint])})", color=theme['text_sec'], size=12),
                        ], spacing=5),
                        padding=ft.padding.only(left=30, top=6, bottom=6),
                        bgcolor=theme['selection_bg'] if ep_sel else None,
                        border_radius=4, ink=True,
                        on_click=lambda e, k=ep_key: _on_endpoint_click(k),
                    )
                    _tree_refs["endpoint"][ep_key] = {"c": ep_container, "t": ep_text}
                    config_tree.controls.append(ep_container)

                    if ep_exp:
                        for idx, cfg in tree[cli_type][endpoint]:
                            is_selected = state.selected_config == idx
                            cfg_icon = ft.Icon(ft.Icons.KEY, size=16, color=theme['icon_key_selected'] if is_selected else ft.Colors.GREY_600)
                            cfg_label = cfg.get('label', 'Unnamed')
                            cfg_tags = cfg.get('tags', '')
                            cfg_text = ft.Text(cfg_label,
                                               weight=ft.FontWeight.BOLD if is_selected else None,
                                               color=theme['text_selected'] if is_selected else theme['text'])
                            row_items = [cfg_icon, cfg_text]
                            if cfg_tags:
                                row_items.append(ft.Text(f"[{cfg_tags}]", size=10, color=ft.Colors.PURPLE_300))
                            cfg_container = ft.Container(
                                content=ft.Row(row_items, spacing=5),
                                padding=ft.padding.only(left=60, top=5, bottom=5),
                                bgcolor=theme['selection_bg'] if is_selected else None,
                                border_radius=4, ink=True,
                                on_click=lambda e, i=idx: _on_config_click(i),
                            )
                            _tree_refs["config"][idx] = {"c": cfg_container, "t": cfg_text, "i": cfg_icon}
                            config_tree.controls.append(cfg_container)
        # 底部留白，确保展开后最后一项可见
        config_tree.controls.append(ft.Container(height=80))
        page.update()

    def show_config_dialog(idx):
        is_edit = idx is not None
        cfg = state.configs[idx] if is_edit else {}
        provider_data = cfg.get('provider', {})

        name_field = ft.TextField(label=L['name'], value=cfg.get('label', ''), expand=True)
        # provider 名称字段：默认跟随厂商下拉框，但用户可自定义
        provider_name_field = ft.TextField(
            label=L.get('provider_name', '厂商名称'),
            value=provider_data.get('type', 'anthropic'),
            expand=True,
        )

        # CLI 下拉
        cli_dropdown = ft.Dropdown(
            label=L.get('cli_tool', 'CLI 工具'),
            value=cfg.get('cli_type', 'claude'),
            options=[ft.dropdown.Option(k, v['name']) for k, v in CLI_TOOLS.items()],
            expand=True,
        )

        # 提供商下拉（如果保存的 type 不在预设列表中，使用 openai 作为默认）
        saved_type = provider_data.get('type', 'anthropic')
        provider_value = saved_type if saved_type in PROVIDER_DEFAULTS else 'openai'
        provider_dropdown = ft.Dropdown(
            label=L.get('provider', '提供商'),
            value=provider_value,
            options=[ft.dropdown.Option(k, k.upper()) for k in PROVIDER_DEFAULTS.keys()],
            expand=True,
        )

        # 模型下拉
        model_dropdown = ft.Dropdown(label=L.get('model', '模型'), expand=True)
        custom_model_field = ft.TextField(label=L.get('custom_model', '自定义模型'), expand=True, visible=False)

        endpoint_field = ft.TextField(
            label=L['api_addr'], value=provider_data.get('endpoint', PROVIDER_DEFAULTS['anthropic']['endpoint']), expand=True,
        )
        key_name_field = ft.TextField(
            label=L['key_name'], value=provider_data.get('key_name', PROVIDER_DEFAULTS['anthropic']['key_name']), expand=True,
        )
        # 获取默认的 base_url_env
        init_cli = cfg.get('cli_type', 'claude')
        default_base_url_env = CLI_TOOLS.get(init_cli, CLI_TOOLS['claude']).get('base_url_env', 'API_BASE_URL')
        base_url_env_field = ft.TextField(
            label=L.get('base_url_env', 'API地址环境变量'),
            value=provider_data.get('base_url_env', default_base_url_env), expand=True,
        )
        api_key_field = ft.TextField(
            label=L['api_key'], value=provider_data.get('credentials', {}).get('api_key', ''),
            password=True, can_reveal_password=True, expand=True,
        )
        quota_url_field = ft.TextField(
            label=L.get('quota_url', '流量查询地址'), value=provider_data.get('quota_url', ''), expand=True,
            keyboard_type=ft.KeyboardType.URL,
        )
        enable_clipboard_paste(quota_url_field)

        def open_quota_url(e):
            if quota_url_field.value:
                page.set_clipboard(api_key_field.value)
                page.launch_url(quota_url_field.value)
        quota_btn = ft.IconButton(ft.Icons.OPEN_IN_NEW, tooltip=L.get('check_quota', '查询'), on_click=open_quota_url)
        max_tokens_field = ft.TextField(
            label=L.get('max_tokens', '单次响应最大'), value=str(provider_data.get('max_tokens', 32000)), expand=True,
        )
        token_limit_field = ft.TextField(
            label=L.get('token_limit', '上下文窗口'), value=str(provider_data.get('token_limit_per_request', 200000)), expand=True,
        )

        # 验证状态显示
        validate_status = ft.Text('', size=12)

        def do_validate(e):
            """验证 API 并获取模型列表"""
            api_key = api_key_field.value
            endpoint = endpoint_field.value
            provider = provider_dropdown.value
            if not api_key or not endpoint:
                validate_status.value = L.get('fill_required', '请填写必填项')
                validate_status.color = ft.Colors.ORANGE
                validate_status.update()
                return

            validate_status.value = L.get('validating', '验证中...')
            validate_status.color = ft.Colors.BLUE
            validate_status.update()

            import threading
            def run_validate():
                from core.api_validator import validate_api_key, fetch_models
                model = custom_model_field.value if model_dropdown.value == '__custom__' else model_dropdown.value
                valid, msg = validate_api_key(provider, api_key, endpoint, model)
                validate_status.value = msg
                validate_status.color = ft.Colors.GREEN if valid else ft.Colors.RED
                validate_status.update()

                # 如果验证成功，获取模型列表并补全
                if valid:
                    fetched = fetch_models(provider, api_key, endpoint)
                    if fetched:
                        # 合并现有模型和获取的模型
                        current_keys = {opt.key for opt in model_dropdown.options if opt.key != '__custom__'}
                        new_models = [m for m in fetched if m not in current_keys]
                        if new_models:
                            # 在 __custom__ 之前插入新模型
                            opts = [opt for opt in model_dropdown.options if opt.key != '__custom__']
                            for m in new_models:
                                opts.append(ft.dropdown.Option(key=m, text=m))
                            opts.append(ft.dropdown.Option(key='__custom__', text=L.get('custom', '自定义...')))
                            model_dropdown.options = opts
                            model_dropdown.update()
                            validate_status.value = f"{msg} | +{len(new_models)} 模型"
                            validate_status.update()

            threading.Thread(target=run_validate, daemon=True).start()

        validate_btn = ft.ElevatedButton(
            L.get('validate', '验证'), icon=ft.Icons.VERIFIED,
            on_click=do_validate, style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=16, vertical=8))
        )

        def build_model_options(provider):
            defaults = PROVIDER_DEFAULTS.get(provider, {})
            models = defaults.get('available_models', [])
            options = []
            for m in models:
                if isinstance(m, dict):
                    options.append(ft.dropdown.Option(key=m.get('name', ''), text=m.get('label', m.get('name', ''))))
                else:
                    options.append(ft.dropdown.Option(key=m, text=m))
            options.append(ft.dropdown.Option(key='__custom__', text=L.get('custom', '自定义...')))
            return options

        def on_model_change(e):
            custom_model_field.visible = (model_dropdown.value == '__custom__')
            custom_model_field.update()

        model_dropdown.on_change = on_model_change

        def on_provider_change(e):
            provider = provider_dropdown.value
            defaults = PROVIDER_DEFAULTS.get(provider, {})
            endpoint_field.value = defaults.get('endpoint', '')
            key_name_field.value = defaults.get('key_name', 'API_KEY')
            base_url_env_field.value = defaults.get('base_url_env', 'API_BASE_URL')
            provider_name_field.value = provider  # 同步更新厂商名称
            model_dropdown.options = build_model_options(provider)
            if defaults.get('default_model'):
                model_dropdown.value = defaults['default_model']
            else:
                model_dropdown.value = None
            custom_model_field.visible = False
            custom_model_field.value = ''
            # 只更新变化的控件，不刷新整个页面
            endpoint_field.update()
            key_name_field.update()
            base_url_env_field.update()
            provider_name_field.update()
            model_dropdown.update()
            custom_model_field.update()

        def on_cli_change(e):
            cli = cli_dropdown.value
            cli_info = CLI_TOOLS.get(cli, CLI_TOOLS['claude'])
            base_url_env_field.value = cli_info.get('base_url_env', 'API_BASE_URL')
            base_url_env_field.update()

        provider_dropdown.on_change = on_provider_change
        cli_dropdown.on_change = on_cli_change

        # 初始化模型列表（使用下拉框的值，而不是保存的 type）
        init_provider = provider_dropdown.value or 'anthropic'
        model_dropdown.options = build_model_options(init_provider)
        saved_model = provider_data.get('selected_model')
        if saved_model:
            # 检查是否在预设列表中
            preset_keys = [opt.key for opt in model_dropdown.options if opt.key != '__custom__']
            if saved_model in preset_keys:
                model_dropdown.value = saved_model
            else:
                model_dropdown.value = '__custom__'
                custom_model_field.value = saved_model
                custom_model_field.visible = True
        elif PROVIDER_DEFAULTS.get(init_provider, {}).get('default_model'):
            model_dropdown.value = PROVIDER_DEFAULTS[init_provider]['default_model']

        def save_config(e):
            if not name_field.value or not api_key_field.value:
                show_snackbar(page, L['fill_required'])
                return

            provider_type = provider_dropdown.value
            selected_model = custom_model_field.value if model_dropdown.value == '__custom__' else model_dropdown.value

            # 获取GLM的thinking_mode
            thinking_mode = None
            if provider_type == 'glm' and selected_model:
                for opt in model_dropdown.options:
                    if opt.key == selected_model:
                        for mm in PROVIDER_DEFAULTS['glm']['available_models']:
                            if isinstance(mm, dict) and mm.get('label') == opt.text:
                                thinking_mode = mm.get('mode')
                                break
                        break

            try:
                max_tokens = int(max_tokens_field.value)
                token_limit = int(token_limit_field.value)
            except ValueError:
                max_tokens = 32000
                token_limit = 200000

            # custom 类型自动检测协议
            detected_protocol = None
            if provider_type == 'custom' and endpoint_field.value and api_key_field.value:
                from core.api_validator import detect_api_protocol
                detected_protocol = detect_api_protocol(api_key_field.value, endpoint_field.value)

            new_cfg = {
                'id': cfg.get('id', f"{name_field.value}-{int(datetime.now().timestamp())}"),
                'label': name_field.value,
                'cli_type': cli_dropdown.value,
                'tags': '',
                'provider': {
                    'type': provider_name_field.value or provider_type,
                    'endpoint': endpoint_field.value,
                    'key_name': key_name_field.value or CLI_TOOLS.get(cli_dropdown.value, CLI_TOOLS['claude'])['default_key_name'],
                    'base_url_env': base_url_env_field.value or CLI_TOOLS.get(cli_dropdown.value, CLI_TOOLS['claude'])['base_url_env'],
                    'credentials': {'api_key': api_key_field.value},
                    'selected_model': selected_model,
                    'available_models': [selected_model] if selected_model else [],
                    'max_tokens': max_tokens,
                    'token_limit_per_request': token_limit,
                    'quota_url': quota_url_field.value,
                },
                'createdAt': cfg.get('createdAt', datetime.now().isoformat()),
                'updatedAt': datetime.now().isoformat(),
            }
            if thinking_mode:
                new_cfg['provider']['thinking_mode'] = thinking_mode

            if is_edit:
                state.configs[idx] = new_cfg
            else:
                state.configs.append(new_cfg)
            state.save_configs()
            refresh_config_list()
            page.close(dlg)
            show_snackbar(page, L['saved'])

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Text(L['edit'] if is_edit else L['add']),
                ft.Container(expand=True),
                validate_btn,
                validate_status,
            ], alignment=ft.MainAxisAlignment.START),
            content=ft.Column([
                ft.Row([cli_dropdown, provider_dropdown]),
                ft.Row([name_field, provider_name_field]),
                model_dropdown,
                custom_model_field,
                base_url_env_field,
                endpoint_field,
                key_name_field,
                api_key_field,
                ft.Row([quota_url_field, quota_btn]),
                ft.Row([max_tokens_field, token_limit_field]),
            ], spacing=10, width=500, height=750),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: page.close(dlg)),
                ft.TextButton(L['save'], on_click=save_config),
            ],
        )
        page.open(dlg)

    def add_config(e): show_config_dialog(None)

    def edit_config(e):
        if state.selected_config is not None:
            show_config_dialog(state.selected_config)
        else:
            show_snackbar(page, L['no_selection'])
            page.update()

    def delete_config(e):
        if state.selected_config is not None:
            cfg = state.configs[state.selected_config]
            def confirm_delete(e):
                if e.control.text == L['delete']:
                    state.configs.pop(state.selected_config)
                    state.save_configs()
                    state.selected_config = None
                    refresh_config_list()
                    show_snackbar(page, L['deleted'])
                page.close(dlg)
            dlg = ft.AlertDialog(
                title=ft.Text(L['confirm_delete']),
                content=ft.Text(L['confirm_delete_msg'].format(cfg.get('label', ''))),
                actions=[ft.TextButton(L['cancel'], on_click=confirm_delete), ft.TextButton(L['delete'], on_click=confirm_delete)],
            )
            page.open(dlg)

    def copy_config_key(e):
        if state.selected_config is not None:
            key = state.configs[state.selected_config].get('provider', {}).get('credentials', {}).get('api_key', '')
            page.set_clipboard(key)
            show_snackbar(page, L['copied'])

    def move_up(e):
        if state.selected_config is not None:
            cli, ep = state.selected_endpoint.split(':', 1) if state.selected_endpoint else (None, None)
            same_ep = [i for i, c in enumerate(state.configs) if get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == ep]
            pos = same_ep.index(state.selected_config) if state.selected_config in same_ep else -1
            if pos > 0:
                prev_idx = same_ep[pos - 1]
                state.configs[state.selected_config], state.configs[prev_idx] = state.configs[prev_idx], state.configs[state.selected_config]
                state.selected_config = prev_idx
                state.save_configs()
                refresh_config_list()
        elif state.selected_endpoint:
            cli, ep = state.selected_endpoint.split(':', 1)
            eps = list(dict.fromkeys(c.get('provider', {}).get('endpoint') for c in state.configs if get_cli_type(c) == cli))
            pos = eps.index(ep) if ep in eps else -1
            if pos > 0:
                prev_ep = eps[pos - 1]
                ep_items = [c for c in state.configs if get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == ep]
                other_items = [c for c in state.configs if not (get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == ep)]
                insert_pos = next((i for i, c in enumerate(other_items) if get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == prev_ep), 0)
                state.configs[:] = other_items[:insert_pos] + ep_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()
        elif state.selected_cli:
            clis = list(dict.fromkeys(get_cli_type(c) for c in state.configs))
            pos = clis.index(state.selected_cli) if state.selected_cli in clis else -1
            if pos > 0:
                prev_cli = clis[pos - 1]
                cli_items = [c for c in state.configs if get_cli_type(c) == state.selected_cli]
                other_items = [c for c in state.configs if get_cli_type(c) != state.selected_cli]
                insert_pos = next((i for i, c in enumerate(other_items) if get_cli_type(c) == prev_cli), 0)
                state.configs[:] = other_items[:insert_pos] + cli_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()

    def move_down(e):
        if state.selected_config is not None:
            cli, ep = state.selected_endpoint.split(':', 1) if state.selected_endpoint else (None, None)
            same_ep = [i for i, c in enumerate(state.configs) if get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == ep]
            pos = same_ep.index(state.selected_config) if state.selected_config in same_ep else -1
            if pos >= 0 and pos < len(same_ep) - 1:
                next_idx = same_ep[pos + 1]
                state.configs[state.selected_config], state.configs[next_idx] = state.configs[next_idx], state.configs[state.selected_config]
                state.selected_config = next_idx
                state.save_configs()
                refresh_config_list()
        elif state.selected_endpoint:
            cli, ep = state.selected_endpoint.split(':', 1)
            eps = list(dict.fromkeys(c.get('provider', {}).get('endpoint') for c in state.configs if get_cli_type(c) == cli))
            pos = eps.index(ep) if ep in eps else -1
            if pos >= 0 and pos < len(eps) - 1:
                next_ep = eps[pos + 1]
                ep_items = [c for c in state.configs if get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == ep]
                other_items = [c for c in state.configs if not (get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == ep)]
                last_next = -1
                for i, c in enumerate(other_items):
                    if get_cli_type(c) == cli and c.get('provider', {}).get('endpoint') == next_ep:
                        last_next = i
                insert_pos = last_next + 1 if last_next >= 0 else len(other_items)
                state.configs[:] = other_items[:insert_pos] + ep_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()
        elif state.selected_cli:
            clis = list(dict.fromkeys(get_cli_type(c) for c in state.configs))
            pos = clis.index(state.selected_cli) if state.selected_cli in clis else -1
            if pos >= 0 and pos < len(clis) - 1:
                next_cli = clis[pos + 1]
                cli_items = [c for c in state.configs if get_cli_type(c) == state.selected_cli]
                other_items = [c for c in state.configs if get_cli_type(c) != state.selected_cli]
                insert_pos = len([c for c in other_items if clis.index(get_cli_type(c)) <= clis.index(next_cli)])
                state.configs[:] = other_items[:insert_pos] + cli_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()

    def export_configs(e):
        def on_result(result):
            if result.path:
                with open(result.path, 'w', encoding='utf-8') as f:
                    json.dump({'configs': state.configs}, f, ensure_ascii=False, indent=2)
                show_snackbar(page, L['exported_to'].format(result.path))
        file_picker.on_result = on_result
        file_picker.save_file(file_name='api_configs.json', allowed_extensions=['json'])

    def import_configs(e):
        def on_result(result):
            if result.files:
                try:
                    with open(result.files[0].path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    imported = data.get('configs', [])
                    state.configs.extend(imported)
                    state.save_configs()
                    refresh_config_list()
                    show_snackbar(page, L['imported_count'].format(len(imported)))
                except Exception as ex:
                    show_snackbar(page, str(ex))
        file_picker.on_result = on_result
        file_picker.pick_files(allowed_extensions=['json'])

    def show_sync_dialog(e):
        """显示云同步对话框"""
        from core.gist_sync import GistSync, load_sync_settings, save_sync_settings
        settings = load_sync_settings()
        token_field = ft.TextField(label=L.get('sync_token', 'GitHub Token'), value=settings.get('token', ''), password=True, can_reveal_password=True, expand=True)
        gist_id_field = ft.TextField(label=L.get('sync_gist_id', 'Gist ID'), value=settings.get('gist_id', ''), expand=True)

        def do_upload(e):
            if not token_field.value:
                show_snackbar(page, L.get('sync_no_token', '请先设置 GitHub Token'))
                return
            save_sync_settings({'token': token_field.value, 'gist_id': gist_id_field.value})
            show_snackbar(page, L.get('sync_uploading', '正在上传...'))
            import threading
            def run():
                sync = GistSync(token_field.value, gist_id_field.value or None)
                mcp_list = mcp_skill_library.get_all_mcp()
                ok, result = sync.upload(state.configs, state.prompts, mcp_list)
                if ok:
                    gist_id_field.value = result
                    save_sync_settings({'token': token_field.value, 'gist_id': result})
                    show_snackbar(page, L.get('sync_upload_ok', '上传成功，Gist ID: {}').format(result))
                else:
                    show_snackbar(page, L.get('sync_fail', '同步失败: {}').format(result))
                page.update()
            threading.Thread(target=run, daemon=True).start()

        def do_download(e):
            if not token_field.value or not gist_id_field.value:
                show_snackbar(page, L.get('sync_no_token', '请先设置 GitHub Token'))
                return
            save_sync_settings({'token': token_field.value, 'gist_id': gist_id_field.value})
            show_snackbar(page, L.get('sync_downloading', '正在下载...'))
            import threading
            def run():
                sync = GistSync(token_field.value, gist_id_field.value)
                ok, data = sync.download()
                if ok:
                    configs = data.get('configs', [])
                    state.configs.extend(configs)
                    state.save_configs()
                    refresh_config_list()
                    show_snackbar(page, L.get('sync_download_ok', '下载成功，已导入 {} 个配置').format(len(configs)))
                else:
                    show_snackbar(page, L.get('sync_fail', '同步失败: {}').format(data.get('error', '')))
                page.update()
            threading.Thread(target=run, daemon=True).start()

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('sync_settings', '云同步设置')),
            content=ft.Column([token_field, gist_id_field], tight=True, spacing=10, width=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: page.close(dlg)),
                ft.OutlinedButton(L.get('sync_download', '下载'), icon=ft.Icons.CLOUD_DOWNLOAD, on_click=do_download),
                ft.ElevatedButton(L.get('sync_upload', '上传'), icon=ft.Icons.CLOUD_UPLOAD, on_click=do_upload),
            ],
        )
        page.open(dlg)

    def browse_folder(e):
        def on_result(result):
            if result.path:
                work_dir_input.value = result.path
                save_work_dir(result.path)
                work_dir_menu.items = build_workdir_menu_items()
                _session_loaded[0] = False
                _session_loading[0] = False  # 重置加载锁
                # 复刻 DEV 版：浏览选择新文件夹时强制刷新缓存
                refresh_session_dropdown_async(force_refresh=True)
        file_picker.on_result = on_result
        # 如果当前目录不存在，向上查找存在的父目录
        initial_dir = work_dir_input.value or None
        if initial_dir:
            p = Path(initial_dir)
            while p and not p.is_dir():
                p = p.parent if p.parent != p else None
            initial_dir = str(p) if p and p.is_dir() else None
        file_picker.get_directory_path(initial_directory=initial_dir)

    def refresh_terminals_click(e):
        state.terminals = detect_terminals()
        state.settings['terminals_cache'] = state.terminals
        save_settings(state.settings)
        terminal_dropdown.options = [ft.dropdown.Option(k) for k in state.terminals.keys()]
        if state.terminals:
            terminal_dropdown.value = list(state.terminals.keys())[0]
        show_snackbar(page, L['terminals_refreshed'])

    def delete_terminal_click(e):
        """删除当前选中的终端"""
        name = terminal_dropdown.value
        if not name or name not in state.terminals:
            return
        del state.terminals[name]
        state.settings['terminals_cache'] = state.terminals
        save_settings(state.settings)
        terminal_dropdown.options = [ft.dropdown.Option(k) for k in state.terminals.keys()]
        terminal_dropdown.value = list(state.terminals.keys())[0] if state.terminals else ''
        page.update()
        show_snackbar(page, L.get('terminal_deleted', '已删除终端: {}').format(name))

    def refresh_envs_click(e):
        state.python_envs = detect_python_envs()
        state.settings['envs_cache'] = state.python_envs
        save_settings(state.settings)
        python_env_dropdown.options = [ft.dropdown.Option(k) for k in state.python_envs.keys()]
        if state.python_envs:
            python_env_dropdown.value = list(state.python_envs.keys())[0]
        show_snackbar(page, L['envs_refreshed'].format(len(state.python_envs)))

    def delete_env_click(e):
        """删除当前选中的 Python 环境"""
        name = python_env_dropdown.value
        if not name or name not in state.python_envs:
            return
        del state.python_envs[name]
        state.settings['envs_cache'] = state.python_envs
        save_settings(state.settings)
        python_env_dropdown.options = [ft.dropdown.Option(k) for k in state.python_envs.keys()]
        python_env_dropdown.value = list(state.python_envs.keys())[0] if state.python_envs else ''
        page.update()
        show_snackbar(page, L.get('env_deleted', '已删除环境: {}').format(name))

    def open_terminal(e):
        if state.selected_config is None:
            show_snackbar(page, L['no_selection'])
            page.update()
            return
        cfg = state.configs[state.selected_config]
        # 优先使用配置中保存的 cli_type
        cli_type = cfg.get('cli_type') or state.selected_cli or 'claude'
        cli_info = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
        api_key = cfg.get('provider', {}).get('credentials', {}).get('api_key', '')
        key_name = cfg.get('provider', {}).get('key_name', cli_info['default_key_name'])
        endpoint = cfg.get('provider', {}).get('endpoint', '')
        base_url_env = cfg.get('provider', {}).get('base_url_env', cli_info['base_url_env'])
        selected_model = cfg.get('provider', {}).get('selected_model', '')
        env = os.environ.copy()
        env[key_name] = api_key
        if endpoint:
            env[base_url_env] = endpoint
        terminal_cmd = state.terminals.get(terminal_dropdown.value, 'cmd')
        cwd = work_dir_input.value or None
        # 验证工作目录是否存在
        if cwd and not Path(cwd).is_dir():
            show_snackbar(page, L.get('invalid_workdir', '工作目录不存在: {}').format(cwd))
            return
        cli_cmd = cli_info.get('command', 'claude')
        # 如果配置了模型，添加 --model 参数
        if selected_model:
            cli_cmd = f"{cli_cmd} --model {selected_model}"
        # 如果选择了会话，添加 --resume 参数（仅 claude CLI）
        session_id = session_dropdown.value
        if cli_type == 'claude' and session_id and session_id != '__none__':
            cli_cmd = f"{cli_cmd} --resume {session_id}"
        if sys.platform == 'win32':
            # 安全处理环境变量值
            safe_key = _safe_env_value(api_key)
            safe_endpoint = _safe_env_value(endpoint)
            safe_model = _safe_env_value(selected_model)
            # 设置环境变量
            env[key_name] = safe_key
            if endpoint:
                env[base_url_env] = safe_endpoint
            if selected_model:
                model_env = cfg.get('provider', {}).get('model_env', '')
                if model_env:
                    env[model_env] = safe_model

            # 检测是否有 Windows Terminal（作为终端宿主）
            use_wt = has_windows_terminal()
            term_lower = terminal_cmd.lower()

            # Codex: 写入全局 ~/.codex/auth.json（Codex 不支持项目级配置）
            if cli_type == 'codex':
                if api_key:
                    codex_dir = Path.home() / '.codex'
                    codex_dir.mkdir(exist_ok=True)
                    auth_file = codex_dir / 'auth.json'
                    auth_file.write_text(json.dumps({key_name: api_key}, indent=2), encoding='utf-8')
                cli_cmd = cli_cmd.replace('codex', 'npx @openai/codex', 1)

            # 构建 shell 启动命令
            if 'pwsh' in term_lower or 'powershell' in term_lower:
                # PowerShell 需要在命令中显式设置环境变量
                safe_key_ps = safe_key.replace("'", "''")
                ps_env_cmds = [f"$env:{key_name} = '{safe_key_ps}'"]
                if endpoint:
                    safe_endpoint_ps = safe_endpoint.replace("'", "''")
                    ps_env_cmds.append(f"$env:{base_url_env} = '{safe_endpoint_ps}'")
                if selected_model:
                    model_env = cfg.get('provider', {}).get('model_env', '')
                    if model_env:
                        safe_model_ps = safe_model.replace("'", "''")
                        ps_env_cmds.append(f"$env:{model_env} = '{safe_model_ps}'")
                ps_full_cmd = '; '.join(ps_env_cmds + [cli_cmd])
                # 使用 EncodedCommand 避免引号嵌套问题
                import base64
                encoded_cmd = base64.b64encode(ps_full_cmd.encode('utf-16-le')).decode('ascii')
                shell_cmd = f'pwsh -NoExit -EncodedCommand {encoded_cmd}'
            elif 'wsl' in term_lower:
                # WSL - 使用 base64 编码避免引号转义问题
                bash_env_cmds = [f"export {key_name}='{safe_key}'"]
                if endpoint:
                    bash_env_cmds.append(f"export {base_url_env}='{safe_endpoint}'")
                if selected_model:
                    model_env = cfg.get('provider', {}).get('model_env', '')
                    if model_env:
                        bash_env_cmds.append(f"export {model_env}='{safe_model}'")
                bash_full_cmd = '; '.join(bash_env_cmds + [cli_cmd])
                # 处理工作目录：Windows 路径转 WSL 路径
                if cwd:
                    wsl_cwd = cwd.replace('\\', '/')
                    if len(wsl_cwd) >= 2 and wsl_cwd[1] == ':':
                        wsl_cwd = f'/mnt/{wsl_cwd[0].lower()}{wsl_cwd[2:]}'
                    bash_full_cmd = f'cd "{wsl_cwd}" && {bash_full_cmd}'
                bash_full_cmd += '; exec bash'
                # 用 base64 编码命令，避免所有引号转义问题
                import base64
                encoded_cmd = base64.b64encode(bash_full_cmd.encode('utf-8')).decode('ascii')
                shell_cmd = f'wsl.exe bash -c "eval $(echo {encoded_cmd} | base64 -d)"'
            elif 'bash' in term_lower:
                # Bash 也需要显式设置环境变量（使用单引号）
                safe_key_bash = safe_key.replace("'", "'\\''")  # Bash 单引号转义: ' -> '\''
                bash_env_cmds = [f"export {key_name}='{safe_key_bash}'"]
                if endpoint:
                    safe_endpoint_bash = safe_endpoint.replace("'", "'\\''")
                    bash_env_cmds.append(f"export {base_url_env}='{safe_endpoint_bash}'")
                if selected_model:
                    model_env = cfg.get('provider', {}).get('model_env', '')
                    if model_env:
                        safe_model_bash = safe_model.replace("'", "'\\''")
                        bash_env_cmds.append(f"export {model_env}='{safe_model_bash}'")
                bash_full_cmd = '; '.join(bash_env_cmds + [cli_cmd])
                # Bash -c 需要整个命令用引号包裹，这里内部用了单引号，外部用双引号应该安全（除非值里有特殊字符）
                # 为了保险，对双引号进行转义
                bash_full_cmd_escaped = bash_full_cmd.replace('"', '\\"')
                shell_cmd = f'bash -c "{bash_full_cmd_escaped}; exec bash"'
            else:
                # CMD
                if cli_type == 'gemini':
                    setx_cmds = [f'setx {key_name} {safe_key}']
                    if endpoint:
                        setx_cmds.append(f'setx {base_url_env} {safe_endpoint}')
                    model_env = cfg.get('provider', {}).get('model_env', '')
                    if selected_model and model_env:
                        setx_cmds.append(f'setx {model_env} {safe_model}')
                    set_cmds = [f'set {key_name}={safe_key}']
                    if endpoint:
                        set_cmds.append(f'set {base_url_env}={safe_endpoint}')
                    if selected_model and model_env:
                        set_cmds.append(f'set {model_env}={safe_model}')
                    full_cmd = ' && '.join(setx_cmds + set_cmds + [cli_cmd])
                else:
                    set_cmds = [f'set {key_name}={safe_key}']
                    if endpoint:
                        set_cmds.append(f'set {base_url_env}={safe_endpoint}')
                    if selected_model:
                        model_env = cfg.get('provider', {}).get('model_env', '')
                        if model_env:
                            set_cmds.append(f'set {model_env}={safe_model}')
                    full_cmd = ' && '.join(set_cmds + [cli_cmd])
                shell_cmd = f'cmd /k "{full_cmd}"'

            # 启动终端
            if use_wt:
                # 通过 Windows Terminal 启动（多标签页）
                wt_cmd = 'wt -w 0 nt'
                if cwd:
                    wt_cmd += f' -d "{cwd}"'
                    # 用工作目录最后一级作为标签页标题，并阻止应用程序覆盖
                    tab_title = Path(cwd).name
                    wt_cmd += f' --title "{tab_title}" --suppressApplicationTitle'
                # 使用 -- 分隔 WT 参数和要执行的命令
                wt_cmd += f' -- {shell_cmd}'
                # DEBUG: 记录生成的命令到文件
                try:
                    with open(r"D:\Dropbox\AI_tools\31.AI CLI Manager\debug_cmd.txt", "w", encoding="utf-8") as f:
                        f.write(f"Shell CMD: {shell_cmd}\n")
                        f.write(f"WT CMD: {wt_cmd}\n")
                        f.write(f"Env Keys: {list(env.keys())}\n")
                except Exception as e:
                    print(f"Debug write failed: {e}")
                subprocess.Popen(wt_cmd, shell=True, env=env)
            else:
                # 直接启动终端（新窗口）
                if 'pwsh' in term_lower or 'powershell' in term_lower:
                    args = [terminal_cmd, '-NoExit']
                    if cwd:
                        args.extend(['-WorkingDirectory', cwd])
                    args.extend(['-Command', cli_cmd])
                    subprocess.Popen(args, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
                elif 'wsl' in term_lower:
                    # WSL 直接启动（无 Windows Terminal）- 使用 base64 编码
                    subprocess.Popen(['wsl.exe', 'bash', '-c', f'eval $(echo {encoded_cmd} | base64 -d)'],
                                    creationflags=subprocess.CREATE_NEW_CONSOLE)
                elif 'bash' in term_lower:
                    subprocess.Popen([terminal_cmd, '-c', f'{cli_cmd}; exec bash'], cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(['cmd', '/k', full_cmd], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            # Linux / macOS
            tab_title = Path(cwd).name if cwd else 'Terminal'
            term_lower = terminal_cmd.lower()

            if 'gnome-terminal' in term_lower:
                # GNOME Terminal - 支持多标签页
                args = ['gnome-terminal', '--tab']
                if cwd:
                    args.extend(['--working-directory', cwd])
                args.extend(['--title', tab_title, '--', 'bash', '-c', f'{cli_cmd}; exec bash'])
                subprocess.Popen(args, env=env)
            elif 'konsole' in term_lower:
                # Konsole (KDE) - 支持多标签页
                args = ['konsole', '--new-tab']
                if cwd:
                    args.extend(['--workdir', cwd])
                args.extend(['-p', f'tabtitle={tab_title}', '-e', 'bash', '-c', f'{cli_cmd}; exec bash'])
                subprocess.Popen(args, env=env)
            elif 'xfce4-terminal' in term_lower:
                # XFCE Terminal
                args = ['xfce4-terminal', '--tab']
                if cwd:
                    args.extend(['--working-directory', cwd])
                args.extend(['--title', tab_title, '-e', f'bash -c "{cli_cmd}; exec bash"'])
                subprocess.Popen(args, env=env)
            elif sys.platform == 'darwin':
                # macOS - 检测 iTerm 或 Terminal.app
                if 'iterm' in term_lower:
                    # iTerm2 - 通过 AppleScript
                    script = f'''
                    tell application "iTerm"
                        activate
                        tell current window
                            create tab with default profile
                            tell current session
                                write text "cd \\"{cwd or '~'}\\" && {cli_cmd}"
                            end tell
                        end tell
                    end tell
                    '''
                else:
                    # Terminal.app
                    script = f'''
                    tell application "Terminal"
                        activate
                        tell application "System Events" to keystroke "t" using command down
                        delay 0.3
                        do script "cd \\"{cwd or '~'}\\" && {cli_cmd}" in front window
                        set custom title of front window to "{tab_title}"
                    end tell
                    '''
                subprocess.Popen(['osascript', '-e', script], env=env)
            else:
                # 其他终端 - 回退到新窗口 (xterm 等)
                subprocess.Popen([terminal_cmd, '-e', 'bash', '-c', f'{cli_cmd}; exec bash'], env=env, cwd=cwd)
        # 记录启动日志
        from core.cli_logger import log_cli_launch
        log_cli_launch(cfg.get('label', ''), cli_type, cli_cmd, cwd)

    def apply_selected_prompt(e=None):
        """应用选中的提示词"""
        if not prompt_dropdown.value:
            return
        if not work_dir_input.value:
            show_snackbar(page, L['prompt_select_workdir'])
            return
        cli_type = 'claude'
        if state.selected_config is not None:
            cli_type = get_cli_type(state.configs[state.selected_config])
        system_prompt = state.prompt_db.get_system_prompt()
        system_content = system_prompt.get('content', '') if system_prompt else ''
        user_prompt = state.prompts.get(prompt_dropdown.value, {})
        user_content = user_prompt.get('content', '')
        user_id = prompt_dropdown.value
        try:
            file_path = write_prompt_to_cli(cli_type, system_content, user_content, user_id, work_dir_input.value)
            show_snackbar(page, L['prompt_written'].format(file_path))
        except Exception as ex:
            show_snackbar(page, L['prompt_write_fail'].format(ex))

    def on_prompt_change(e):
        """提示词选择变化时自动应用"""
        apply_selected_prompt()

    prompt_dropdown.on_change = on_prompt_change

    # MCP 服务器选择状态 - 从数据库获取
    from ..database import generate_mcp_config
    selected_mcp_servers = set()
    for m in mcp_skill_library.get_all_mcp():
        if m.get('is_default'):
            selected_mcp_servers.add(m.get('name', ''))

    def show_mcp_selector(e):
        """显示 MCP 服务器选择弹窗"""
        mcp_checkboxes = []

        def toggle_mcp(name, checked):
            if checked:
                selected_mcp_servers.add(name)
            else:
                selected_mcp_servers.discard(name)

        def save_mcp_selection(e):
            # 更新数据库中的 is_default 状态
            for m in mcp_skill_library.get_all_mcp():
                name = m.get('name', '')
                is_selected = name in selected_mcp_servers
                if m.get('is_default') != is_selected:
                    mcp_skill_library.set_mcp_default(name, is_selected)
            # 同步到全局配置
            global_mcp_path = Path.home() / '.claude' / '.mcp.json'
            generate_mcp_config(global_mcp_path)
            page.close(dlg)
            show_snackbar(page, L.get('mcp_saved', 'MCP 配置已保存'))

        # 按分类组织
        by_cat = {}
        for m in mcp_skill_library.get_all_mcp():
            cat = m.get('category', '其他')
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(m)

        content_controls = []
        for cat, items in by_cat.items():
            content_controls.append(ft.Text(cat, weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.GREY_600))
            for m in items:
                name = m.get('name', '')
                cb = ft.Checkbox(
                    label=name,
                    value=name in selected_mcp_servers,
                    on_change=lambda e, n=name: toggle_mcp(n, e.control.value)
                )
                mcp_checkboxes.append(cb)
                content_controls.append(cb)

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('mcp_select', 'MCP 服务器')),
            content=ft.Container(
                ft.Column(content_controls, scroll=ft.ScrollMode.AUTO, spacing=5),
                width=300, height=400
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton(L['save'], on_click=save_mcp_selection),
            ],
        )
        page.open(dlg)

    # 截图功能
    screenshot_btn = ft.ElevatedButton(L.get('screenshot', '截图'), icon=ft.Icons.SCREENSHOT, width=100, tooltip=L.get('screenshot_tooltip', '截图保留一周'))

    def take_screenshot(e):
        """启动截图工具 - 直接调用避免子进程问题"""
        import threading
        import time as _time
        from ..tools.screenshot_tool import ScreenshotTool

        old_title = page.title
        page.title = L.get('screenshot_in_progress', '截图中...')
        page.update()

        save_dir = str(Path(__file__).parent.parent.parent / "screenshots")

        # 清理过期截图
        def cleanup_old():
            try:
                d = Path(save_dir)
                if d.exists():
                    cleanup_days = state.settings.get('screenshot_cleanup_days', 7)
                    cutoff = _time.time() - cleanup_days * 86400
                    for f in d.glob("screenshot_*.png"):
                        if f.stat().st_mtime < cutoff:
                            f.unlink()
            except Exception:
                pass

        def run():
            cleanup_old()
            tool = ScreenshotTool(save_dir)
            path = tool.start()
            page.title = old_title
            page.window.to_front()
            page.update()
            if path and Path(path).exists():
                page.set_clipboard(path)
                show_snackbar(page, L.get('screenshot_saved', f'截图已保存: {path}'))

        threading.Thread(target=run, daemon=True).start()

    screenshot_btn.on_click = take_screenshot

    # 路径抓取功能
    pick_path_btn = ft.ElevatedButton(L.get('pick_path', '复制路径'), icon=ft.Icons.LINK, width=110, tooltip=L.get('pick_path_tooltip', '选择文件复制绝对路径'))

    def pick_path(e):
        """启动路径抓取工具"""
        import subprocess
        import threading

        old_title = page.title
        in_progress_text = L.get('pick_path_in_progress', '复制路径中...')
        pick_path_btn.text = in_progress_text
        page.title = in_progress_text
        page.window.minimized = True
        page.update()

        script = str(Path(__file__).parent.parent / "tools" / "path_picker.py")

        def run():
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True
            )
            pick_path_btn.text = L.get('pick_path', '复制路径')
            page.title = old_title
            page.update()
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    page.set_clipboard(path)
                    show_snackbar(page, L.get('path_copied', f'路径已复制: {path}'))

        threading.Thread(target=run, daemon=True).start()

    pick_path_btn.on_click = pick_path

    # 快捷键设置
    from ..hotkey import load_hotkey, update_hotkey, update_copypath_hotkey

    def format_hotkey(hk: str) -> str:
        """格式化快捷键显示：alt+s -> Alt+S"""
        return '+'.join(p.capitalize() for p in hk.split('+'))

    current_hotkey_display = format_hotkey(load_hotkey("screenshot"))
    hotkey_btn = ft.OutlinedButton(f"截图 {current_hotkey_display}", on_click=lambda e: show_hotkey_dialog(e, "screenshot"), width=120)

    current_copypath_display = format_hotkey(load_hotkey("copy_path"))
    copypath_btn = ft.OutlinedButton(f"路径 {current_copypath_display}", on_click=lambda e: show_hotkey_dialog(e, "copy_path"), width=120)

    def show_hotkey_dialog(e, key_type="screenshot"):
        """显示快捷键设置对话框"""
        try:
            import keyboard as kb
        except ImportError:
            show_snackbar(page, "需要安装 keyboard 库")
            return

        captured_keys = []
        current_hk = format_hotkey(load_hotkey(key_type))
        title = "设置截图快捷键" if key_type == "screenshot" else "设置复制路径快捷键"
        key_display = ft.Text("请按下快捷键...", size=16, weight=ft.FontWeight.BOLD)
        hook_id = [None]

        # 截图清理周期（仅截图对话框显示）
        cleanup_days = state.settings.get('screenshot_cleanup_days', 7)
        cleanup_field = ft.TextField(
            label=L.get('screenshot_cleanup_days', '截图清理周期(天)'),
            value=str(cleanup_days), width=180, keyboard_type=ft.KeyboardType.NUMBER
        ) if key_type == "screenshot" else None

        def on_key(event):
            if event.event_type != 'down':
                return
            parts = []
            if kb.is_pressed('ctrl'):
                parts.append("Ctrl")
            if kb.is_pressed('alt'):
                parts.append("Alt")
            if kb.is_pressed('shift'):
                parts.append("Shift")
            key = event.name
            if key and key.lower() not in ('ctrl', 'alt', 'shift', 'left ctrl', 'right ctrl', 'left alt', 'right alt', 'left shift', 'right shift'):
                parts.append(key.upper() if len(key) == 1 else key.capitalize())
            if parts:
                captured_keys.clear()
                captured_keys.extend(parts)
                key_display.value = "+".join(parts)
                page.update()

        hook_id[0] = kb.hook(on_key)

        def save_key(e):
            if hook_id[0]:
                kb.unhook(hook_id[0])
            if captured_keys:
                new_key = "+".join(p.lower() for p in captured_keys)
                if key_type == "screenshot":
                    update_hotkey(new_key, work_dir_input.value, page)
                    hotkey_btn.text = f"截图 {'+'.join(captured_keys)}"
                else:
                    update_copypath_hotkey(new_key)
                    copypath_btn.text = f"路径 {'+'.join(captured_keys)}"
                show_snackbar(page, f'快捷键已设置: {"+".join(captured_keys)}')
            # 保存清理周期
            if cleanup_field:
                try:
                    days = int(cleanup_field.value)
                    if days > 0:
                        state.settings['screenshot_cleanup_days'] = days
                        save_settings(state.settings)
                except ValueError:
                    pass
            page.close(dlg)

        def cancel(e):
            if hook_id[0]:
                kb.unhook(hook_id[0])
            page.close(dlg)

        content_items = [
            ft.Text(f"当前快捷键为：{current_hk}", size=14),
            key_display,
        ]
        if cleanup_field:
            content_items.append(ft.Divider())
            content_items.append(cleanup_field)

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Container(
                ft.Column(content_items, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=250, height=150 if key_type == "screenshot" else 80,
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=cancel),
                ft.ElevatedButton(L['save'], on_click=save_key),
            ],
        )
        page.open(dlg)

    # 初始化列表
    refresh_config_list()

    # 恢复上次选中的 KEY（不加载会话，懒加载）
    last_idx = state.settings.get('last_selected_config')
    if last_idx is not None and 0 <= last_idx < len(state.configs):
        state.select_config(last_idx)
        _update_selection()

    # 复刻 DEV 版：启动时延迟刷新历史缓存（800ms 后后台刷新）
    def delayed_startup_refresh():
        import time as _time
        _time.sleep(0.8)  # 800ms 延迟
        if work_dir_input.value and not _initial_load_done[0]:
            _initial_load_done[0] = True
            # 后台刷新缓存
            if lh is not None:
                try:
                    cli_type = get_selected_cli_type()
                    lh.refresh_history_on_startup(cli_type)
                except Exception as e:
                    print(f"[delayed_startup_refresh] 错误: {e}")
            # 刷新会话列表
            refresh_session_dropdown_async(force_refresh=False)

    threading.Thread(target=delayed_startup_refresh, daemon=True).start()

    # 构建页面
    api_page = ft.Column([
        ft.Row([
            ft.Container(config_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE),
            ft.Column([
                ft.OutlinedButton(L['add'], icon=ft.Icons.ADD, on_click=add_config, width=130),
                ft.OutlinedButton(L['edit'], icon=ft.Icons.EDIT, on_click=edit_config, width=130),
                ft.OutlinedButton(L['delete'], icon=ft.Icons.DELETE, on_click=delete_config, width=130),
                ft.OutlinedButton(L['copy_key'], icon=ft.Icons.COPY, on_click=copy_config_key, width=130),
                ft.OutlinedButton(L['move_up'], icon=ft.Icons.ARROW_UPWARD, on_click=move_up, width=130),
                ft.OutlinedButton(L['move_down'], icon=ft.Icons.ARROW_DOWNWARD, on_click=move_down, width=130),
                ft.OutlinedButton(L['export'], icon=ft.Icons.UPLOAD, on_click=export_configs, width=130),
                ft.OutlinedButton(L['import'], icon=ft.Icons.DOWNLOAD, on_click=import_configs, width=130),
                ft.OutlinedButton(L.get('sync', '同步'), icon=ft.Icons.CLOUD_SYNC, on_click=show_sync_dialog, width=130),
            ], spacing=5, alignment=ft.MainAxisAlignment.START),
        ], expand=1, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
        ft.Divider(),
        ft.Text(L['terminal'], size=16, weight=ft.FontWeight.BOLD),
        ft.Row([
            terminal_dropdown,
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=L.get('delete_terminal', '删除终端'), on_click=delete_terminal_click),
            ft.TextButton(L['refresh_terminals'], icon=ft.Icons.REFRESH, on_click=refresh_terminals_click),
            python_env_dropdown,
            ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=L.get('delete_env', '删除环境'), on_click=delete_env_click),
            ft.TextButton(L['refresh_envs'], icon=ft.Icons.REFRESH, on_click=refresh_envs_click),
            ft.Text(L['current_key']), current_key_label,
        ], wrap=True, spacing=5),
        ft.Row([work_dir_input, work_dir_menu, ft.ElevatedButton(L['browse'], icon=ft.Icons.FOLDER_OPEN, on_click=browse_folder),
                ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip=L.get('clear_folder_history', '清空本文件夹历史记录'), on_click=clear_workdir_history)]),
        ft.Row([session_dropdown, session_preview_btn, ft.ElevatedButton(L['open_terminal'], icon=ft.Icons.TERMINAL, on_click=open_terminal)]),
        ft.Row([
            prompt_dropdown,
            mcp_preset_dropdown,
            skill_preset_dropdown,
            ft.ElevatedButton(L.get('mcp_select', 'MCP 服务器'), icon=ft.Icons.EXTENSION, on_click=show_mcp_selector, width=130),
            screenshot_btn,
            hotkey_btn,
            pick_path_btn,
            copypath_btn,
        ], spacing=10),
    ], expand=True, spacing=10)

    return api_page, refresh_config_list
