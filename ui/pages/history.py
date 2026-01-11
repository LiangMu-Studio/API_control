# AI CLI Manager - History Page
# 复刻 DEV 版 (Tauri) 的历史记录页面设计
import flet as ft
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from ..common import THEMES, TRASH_RETENTION_DAYS, show_snackbar
from ..database import history_manager, codex_history_manager

# 导入 Rust 历史记录模块
try:
    import liangmu_history as lh
except ImportError:
    lh = None

MAX_CACHE_SIZE = 50


def shorten_path(path: str, max_len: int = 40) -> str:
    """缩短路径显示"""
    if len(path) <= max_len:
        return path
    sep = '\\' if '\\' in path else '/'
    parts = path.split(sep)
    if len(parts) <= 2:
        return path[:max_len-3] + '...'
    last = parts[-1]
    suffix = sep + '...' + sep + last
    avail = max_len - len(suffix)
    prefix = sep.join(parts[:-1])
    return prefix[:avail] + suffix if avail > 0 else parts[0] + suffix


def create_history_page(state):
    L = state.L
    # 根据上次选中的 KEY 确定默认 CLI 类型
    last_idx = state.settings.get('last_selected_config')
    if last_idx is not None and 0 <= last_idx < len(state.configs):
        current_cli = state.configs[last_idx].get('cli_type', 'claude')
    else:
        current_cli = "claude"

    selected_session_data = [None]  # 当前选中的会话数据
    loaded_projects = OrderedDict()  # LRU 缓存
    show_sidebar = [True]  # 侧边栏显示状态

    # 工具图标和颜色映射 - 复刻 DEV 版
    TOOL_ICONS = {
        'Read': ('📖', 'bg-blue-100', ft.Colors.BLUE_100),
        'Write': ('✏️', 'bg-green-100', ft.Colors.GREEN_100),
        'Edit': ('🔧', 'bg-yellow-100', ft.Colors.YELLOW_100),
        'Bash': ('💻', 'bg-purple-100', ft.Colors.PURPLE_100),
        'Glob': ('🔍', 'bg-cyan-100', ft.Colors.CYAN_100),
        'Grep': ('🔎', 'bg-teal-100', ft.Colors.TEAL_100),
        'Task': ('🚀', 'bg-pink-100', ft.Colors.PINK_100),
        'TodoWrite': ('📋', 'bg-amber-100', ft.Colors.AMBER_100),
        'WebFetch': ('🌐', 'bg-indigo-100', ft.Colors.INDIGO_100),
        'WebSearch': ('🔍', 'bg-light-blue-100', ft.Colors.LIGHT_BLUE_100),
    }

    def get_current_manager():
        if current_cli == "claude":
            return history_manager
        elif current_cli == "codex":
            return codex_history_manager
        return None

    def extract_content(msg) -> tuple:
        """提取消息内容"""
        if current_cli == 'claude':
            role = msg.get('type', '?')
            c = msg.get('message', {}).get('content', [])
        else:
            role = msg.get('role', '?')
            c = msg.get('content', '')
        if isinstance(c, str):
            return role, c, [], True
        texts, tool_blocks = [], []
        has_tool_result = False
        if isinstance(c, list):
            for block in c:
                if not isinstance(block, dict):
                    continue
                btype = block.get('type', '')
                if btype == 'text':
                    texts.append(block.get('text', ''))
                elif btype == 'tool_use':
                    tool_blocks.append(block)
                elif btype == 'tool_result':
                    tool_blocks.append(block)
                    has_tool_result = True
        is_real_user = (role == 'user' and not has_tool_result)
        return role, '\n'.join(texts), tool_blocks, is_real_user

    def count_real_turns(messages):
        turns = 0
        for msg in messages:
            role, _, _, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                turns += 1
        return turns

    # ==================== 左侧边栏 - 项目树 ====================
    sidebar_container = ft.Container(width=320, visible=True)
    project_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    # 项目展开状态
    expanded_projects = {}
    selected_session_id = [None]

    def build_project_item(project_id, display_path):
        """构建项目项 - 复刻 DEV 版 ProjectItem"""
        is_expanded = expanded_projects.get(project_id, False)
        sessions_col = ft.Column([], spacing=0, visible=is_expanded)
        theme = state.get_theme()

        # 项目标题行
        title_text = ft.Text(shorten_path(display_path, 35), size=13, weight=ft.FontWeight.W_500)
        subtitle_text = ft.Text(L.get('click_to_load', '点击加载...') if not is_expanded else '', size=11, color=ft.Colors.GREY_500)
        expand_icon = ft.Text('▼' if is_expanded else '▶', size=11, color=ft.Colors.GREY_500)

        def on_project_click(_):
            nonlocal is_expanded
            expanded_projects[project_id] = not expanded_projects.get(project_id, False)
            is_expanded = expanded_projects[project_id]
            expand_icon.value = '▼' if is_expanded else '▶'
            sessions_col.visible = is_expanded

            if is_expanded and not sessions_col.controls:
                # 懒加载会话列表
                load_sessions(project_id, sessions_col, subtitle_text)
            state.page.update()

        project_header = ft.Container(
            content=ft.Row([
                ft.Column([title_text, subtitle_text], spacing=2, expand=True),
                ft.Text('📁', size=14, color=ft.Colors.AMBER),
                expand_icon,
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=theme['header_bg'] if is_expanded else None,
            on_click=on_project_click,
            ink=True,
        )

        return ft.Container(
            content=ft.Column([project_header, sessions_col], spacing=0),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.GREY))),
        )

    def load_sessions(project_id, sessions_col, subtitle_text):
        """加载项目的会话列表"""
        if project_id in loaded_projects:
            loaded_projects.move_to_end(project_id)
            sessions = loaded_projects[project_id]
        else:
            mgr = get_current_manager()
            if not mgr or not hasattr(mgr, 'load_project'):
                return
            sessions = mgr.load_project(project_id)
            loaded_projects[project_id] = sessions
            while len(loaded_projects) > MAX_CACHE_SIZE:
                loaded_projects.popitem(last=False)

        if not sessions:
            sessions_col.controls.append(ft.Text(L.get('history_no_records', '无记录'), size=11, color=ft.Colors.GREY_500))
            return

        subtitle_text.value = f"{len(sessions)} {L.get('history_sessions', '会话')}"

        for sid, info in sorted(sessions.items(), key=lambda x: x[1].get('last_timestamp', ''), reverse=True):
            ts = info.get('last_timestamp', '')
            try:
                time_str = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%m-%d %H:%M') if ts else ''
            except (ValueError, AttributeError):
                time_str = ts[:16] if ts else ''
            turns = count_real_turns(info.get('messages', []))

            is_selected = selected_session_id[0] == sid
            session_item = ft.Container(
                content=ft.Column([
                    ft.Text(time_str, size=11, color=ft.Colors.GREY_600),
                    ft.Text(f"{turns} {L.get('history_turns', '轮')}", size=10, color=ft.Colors.GREY_500),
                ], spacing=2),
                padding=ft.padding.only(left=24, top=6, bottom=6, right=8),
                border=ft.border.only(left=ft.BorderSide(2, ft.Colors.BLUE_500 if is_selected else ft.Colors.TRANSPARENT)),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE) if is_selected else None,
                on_click=lambda e, s=sid, i=info, p=project_id: on_session_click(s, i, p),
                ink=True,
            )
            sessions_col.controls.append(session_item)

    def on_session_click(session_id, info, project_id):
        """点击会话"""
        selected_session_id[0] = session_id
        selected_session_data[0] = {'session_id': session_id, 'info': info, 'group': project_id}
        show_session_detail(info, session_id)
        refresh_project_list()  # 刷新选中状态

    # ==================== 右侧面板 - 会话详情 ====================
    detail_panel = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    detail_header = ft.Row([], spacing=8, wrap=True)
    tool_stats_row = ft.Row([], spacing=4, wrap=True)
    messages_container = ft.Column([], spacing=8, expand=True)

    # 分页状态
    load_state = {'head': 3, 'tail': 3}

    def toggle_sidebar(_):
        """切换侧边栏显示"""
        show_sidebar[0] = not show_sidebar[0]
        sidebar_container.visible = show_sidebar[0]
        toggle_btn.text = '← ' + L.get('collapse', '收起') if show_sidebar[0] else L.get('expand', '展开') + ' →'
        state.page.update()

    toggle_btn = ft.TextButton('← ' + L.get('collapse', '收起'), on_click=toggle_sidebar)

    def show_session_detail(info, session_id):
        """显示会话详情 - 复刻 DEV 版"""
        messages = info.get('messages', [])
        cwd = info.get('cwd', '')

        # 构建操作栏
        detail_header.controls = [
            toggle_btn,
            ft.TextButton('📄 HTML', on_click=lambda _: export_session('html')),
            ft.TextButton('📝 MD', on_click=lambda _: export_session('md')),
            ft.TextButton('📂 ' + L.get('open_folder', '打开'), on_click=lambda _: open_folder(cwd)) if cwd else ft.Container(),
            ft.TextButton('🗑️ ' + L.get('delete', '删除'), on_click=lambda _: del_session()),
        ]

        # 统计工具使用
        tool_stats = {}
        real_turns = 0
        for msg in messages:
            role, _, tool_blocks, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                real_turns += 1
            for b in tool_blocks:
                if b.get('type') == 'tool_use':
                    name = b.get('name', 'unknown')
                    tool_stats[name] = tool_stats.get(name, 0) + 1

        # 工具统计芯片
        tool_stats_row.controls = [
            ft.Text(f"{real_turns} {L.get('history_turns', '轮')}", size=12, color=ft.Colors.GREY_600),
        ]
        for name, count in sorted(tool_stats.items(), key=lambda x: -x[1])[:6]:
            icon, _, bgcolor = TOOL_ICONS.get(name, ('🔧', '', ft.Colors.GREY_100))
            tool_stats_row.controls.append(ft.Container(
                ft.Text(f"{icon} {name}: {count}", size=10),
                bgcolor=bgcolor, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=8,
            ))

        # 构建消息时间线
        build_message_timeline(messages)
        state.page.update()

    def build_message_timeline(messages):
        """构建消息时间线 - 复刻 DEV 版分页机制"""
        messages_container.controls.clear()

        # 将消息按轮次分组
        rounds = []
        current_round = None
        orphan_msgs = []
        for msg in messages:
            role, _, _, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                if current_round:
                    rounds.append(current_round)
                current_round = (msg, [])
            elif current_round:
                current_round[1].append(msg)
            else:
                orphan_msgs.append(msg)
        if current_round:
            rounds.append(current_round)
        if orphan_msgs:
            rounds.insert(0, (None, orphan_msgs))

        total = len(rounds)
        if total == 0:
            messages_container.controls.append(ft.Text(L.get('history_no_records', '无记录'), color=ft.Colors.GREY_500))
            return

        head_n, tail_n = load_state['head'], load_state['tail']

        if head_n + tail_n >= total:
            # 全部显示
            for i, rd in enumerate(rounds):
                messages_container.controls.extend(render_round(rd, i + 1))
        else:
            # 显示前 head_n 轮
            for i in range(head_n):
                messages_container.controls.extend(render_round(rounds[i], i + 1))

            # 展开按钮
            hidden = total - head_n - tail_n
            messages_container.controls.append(ft.Container(
                ft.Row([
                    ft.ElevatedButton(f"↓ +10", on_click=lambda _: expand_more('head', messages), bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE),
                    ft.Text(f"{L.get('hidden', '隐藏')} {hidden} {L.get('history_turns', '轮')}", size=12, color=ft.Colors.GREY_500),
                    ft.ElevatedButton(f"↑ +10", on_click=lambda _: expand_more('tail', messages), bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
                padding=ft.padding.symmetric(vertical=16),
            ))

            # 显示后 tail_n 轮
            for i in range(total - tail_n, total):
                messages_container.controls.extend(render_round(rounds[i], i + 1))

    def expand_more(direction, messages):
        if direction == 'head':
            load_state['head'] += 10
        else:
            load_state['tail'] += 10
        build_message_timeline(messages)
        state.page.update()

    def render_round(round_data, round_num):
        """渲染一轮对话 - 复刻 DEV 版时间线样式"""
        user_msg, ai_msgs = round_data
        controls = []

        # 用户消息
        if user_msg:
            _, txt, _, _ = extract_content(user_msg)
            controls.append(render_timeline_message(txt, 'user', round_num))

        # AI 响应
        for msg in ai_msgs:
            role, txt, tool_blocks, _ = extract_content(msg)
            if role == 'assistant':
                if txt and txt.strip():
                    controls.append(render_timeline_message(txt, 'assistant'))
                # 工具调用
                for block in tool_blocks:
                    if block.get('type') == 'tool_use':
                        controls.append(render_tool_call(block))

        return controls

    def render_timeline_message(text, role, round_num=None):
        """渲染时间线消息 - 复刻 DEV 版 TimelineMessageItem"""
        is_user = role == 'user'
        theme = state.get_theme()

        # 颜色配置
        avatar_bg = ft.Colors.BLUE_500 if is_user else ft.Colors.GREEN_500
        bubble_bg = ft.Colors.with_opacity(0.06, ft.Colors.BLUE if is_user else ft.Colors.GREEN)
        border_color = ft.Colors.BLUE_500 if is_user else ft.Colors.GREEN_500
        line_color = ft.Colors.with_opacity(0.3, ft.Colors.BLUE if is_user else ft.Colors.GREEN)
        label = 'User' if is_user else 'Assistant'

        # 头像圆点
        avatar = ft.Container(
            ft.Text('👤' if is_user else '🤖', size=12),
            width=28, height=28, border_radius=14,
            bgcolor=avatar_bg, alignment=ft.alignment.center,
        )

        # 竖线连接
        line = ft.Container(width=2, height=40, bgcolor=line_color)

        # 消息气泡
        display_text = text[:500] if len(text) > 500 else text
        prefix = f"[{L.get('round', '轮')}{round_num}] " if round_num else ""

        bubble = ft.Container(
            ft.Column([
                ft.Container(
                    ft.Text(label, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    bgcolor=avatar_bg, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=4,
                ),
                ft.Text(prefix + display_text, size=12, selectable=True),
            ], spacing=6),
            bgcolor=bubble_bg, padding=12, border_radius=8,
            border=ft.border.only(left=ft.BorderSide(4, border_color)),
            expand=True,
        )

        return ft.Row([
            ft.Column([avatar, line], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bubble,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    def render_tool_call(block):
        """渲染工具调用 - 复刻 DEV 版 ToolCallItem"""
        name = block.get('name', 'unknown')
        inp = block.get('input', {})
        icon, _, bgcolor = TOOL_ICONS.get(name, ('🔧', '', ft.Colors.GREY_100))

        # 获取工具详情
        detail = ''
        if name in ('Read', 'Write', 'Edit'):
            detail = inp.get('file_path', '')
        elif name == 'Bash':
            detail = inp.get('command', '')[:60]
        elif name in ('Glob', 'Grep'):
            detail = inp.get('pattern', '')
        elif name == 'Task':
            detail = inp.get('description', '')

        expand_state = {'open': False}
        detail_col = ft.Column([], visible=False)

        def toggle_expand(_):
            expand_state['open'] = not expand_state['open']
            detail_col.visible = expand_state['open']
            if expand_state['open'] and not detail_col.controls:
                # 展开时显示详细内容
                if name == 'Edit':
                    old = inp.get('old_string', '')[:300]
                    new = inp.get('new_string', '')[:300]
                    detail_col.controls.append(ft.Column([
                        ft.Text("- " + old, size=10, color=ft.Colors.RED_400),
                        ft.Text("+ " + new, size=10, color=ft.Colors.GREEN_400),
                    ], spacing=4))
                else:
                    detail_col.controls.append(ft.Text(str(inp)[:500], size=10, selectable=True))
            state.page.update()

        return ft.Container(
            ft.Column([
                ft.Row([
                    ft.Text('▶' if not expand_state['open'] else '▼', size=10, color=ft.Colors.GREY_500),
                    ft.Text(f"{icon} {name}", size=11, weight=ft.FontWeight.W_500),
                    ft.Text(shorten_path(detail, 50), size=10, color=ft.Colors.GREY_600, expand=True),
                ], spacing=8),
                detail_col,
            ], spacing=4),
            bgcolor=bgcolor, padding=8, border_radius=6,
            margin=ft.margin.only(left=40, bottom=4),
            on_click=toggle_expand, ink=True,
        )

    # ==================== 辅助函数 ====================
    def open_folder(path):
        import subprocess, sys
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', path.replace('/', '\\')])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def export_session(fmt):
        if not selected_session_data[0]:
            show_snackbar(state.page, L.get('no_selection', '请先选择会话'))
            return
        from core.session_export import export_session_html, export_session_md
        data = selected_session_data[0]
        sid = data['session_id'][:12]
        def on_result(result):
            if result.path:
                try:
                    if fmt == 'html':
                        export_session_html(data, result.path)
                    else:
                        export_session_md(data, result.path)
                    show_snackbar(state.page, L.get('export_success', '导出成功'))
                except Exception as ex:
                    show_snackbar(state.page, str(ex))
        file_picker.on_result = on_result
        file_picker.save_file(file_name=f'session_{sid}.{fmt}', allowed_extensions=[fmt])

    def del_session():
        if not selected_session_data[0]:
            return
        data = selected_session_data[0]
        mgr = get_current_manager()
        if mgr and hasattr(mgr, 'delete_session'):
            mgr.delete_session(data['group'], data['session_id'], data['info'])
            loaded_projects.pop(data['group'], None)
            show_snackbar(state.page, L.get('history_moved', '已移至回收站'))
            refresh_project_list()

    # 共享 FilePicker
    file_picker = ft.FilePicker()
    state.page.overlay.append(file_picker)

    # ==================== 刷新函数 ====================
    def refresh_project_list(filter_text=''):
        project_list.controls.clear()
        expanded_projects.clear()
        loaded_projects.clear()

        mgr = get_current_manager()
        if current_cli in ('gemini', 'aider'):
            project_list.controls.append(ft.Text(f'{current_cli.title()} 暂不支持', color=ft.Colors.ORANGE))
            state.page.update()
            return
        if not mgr:
            project_list.controls.append(ft.Text(f'{current_cli.title()} 目录不存在', color=ft.Colors.RED))
            state.page.update()
            return

        projects_data = mgr.list_projects(with_cwd=True, limit=50) if hasattr(mgr, 'list_projects') else []
        if not projects_data:
            project_list.controls.append(ft.Text(L.get('history_no_records', '无记录'), color=ft.Colors.GREY_500))
            state.page.update()
            return

        stats_text.value = f"{len(projects_data)} {L.get('history_projects', '项目')}"

        for item in projects_data:
            if isinstance(item, tuple):
                project_id, real_cwd = item
            else:
                project_id, real_cwd = item, ''
            display_path = real_cwd or project_id
            if filter_text and filter_text.lower() not in display_path.lower():
                continue
            project_list.controls.append(build_project_item(project_id, display_path))

        state.page.update()

    # ==================== 顶部控件 ====================
    cli_dropdown = ft.Dropdown(
        value=current_cli,
        options=[ft.dropdown.Option('claude', 'Claude'), ft.dropdown.Option('codex', 'Codex')],
        width=120,
    )

    def on_cli_change(_):
        nonlocal current_cli
        nc = cli_dropdown.value or 'claude'
        if nc != current_cli:
            current_cli = nc
            load_state['head'], load_state['tail'] = 3, 3
            messages_container.controls.clear()
            detail_header.controls.clear()
            tool_stats_row.controls.clear()
        refresh_project_list(search_field.value or '')

    cli_dropdown.on_change = on_cli_change

    search_field = ft.TextField(hint_text=L.get('history_search', '搜索'), width=200, prefix_icon=ft.Icons.SEARCH)
    search_field.on_submit = lambda e: refresh_project_list(e.control.value or '')

    stats_text = ft.Text('', size=12, color=ft.Colors.GREY_600)

    def clear_empty_sessions(_):
        """清理空会话（0轮对话，通常由 /clear 命令产生）- 直接扫描存储目录"""
        import json
        import os

        def count_user_turns(file_path: str) -> int:
            """计算会话文件中的真实用户轮数"""
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                messages = data if isinstance(data, list) else data.get('messages', [])
                turns = 0
                for msg in messages:
                    # Claude 格式
                    if msg.get('type') == 'user':
                        content = msg.get('message', {}).get('content', [])
                        # 检查是否是真实用户消息（不是 tool_result）
                        has_tool_result = any(
                            isinstance(b, dict) and b.get('type') == 'tool_result'
                            for b in (content if isinstance(content, list) else [])
                        )
                        if not has_tool_result:
                            turns += 1
                    # Codex 格式
                    elif msg.get('role') == 'user':
                        content = msg.get('content', '')
                        if isinstance(content, str) or not any(
                            isinstance(b, dict) and b.get('type') == 'tool_result'
                            for b in (content if isinstance(content, list) else [])
                        ):
                            turns += 1
                return turns
            except Exception:
                return -1  # 无法读取，跳过

        def do_clear(_):
            state.page.close(dlg)
            deleted_count = 0
            scanned_count = 0

            try:
                # 获取 Claude Code 存储目录
                if current_cli == 'claude':
                    base_dir = Path.home() / '.claude' / 'projects'
                elif current_cli == 'codex':
                    base_dir = Path.home() / '.codex' / 'projects'
                else:
                    base_dir = Path.home() / '.claude' / 'projects'

                if not base_dir.exists():
                    show_snackbar(state.page, f"目录不存在: {base_dir}")
                    return

                # 遍历所有项目目录下的 JSON 文件
                for project_dir in base_dir.iterdir():
                    if not project_dir.is_dir():
                        continue
                    for session_file in project_dir.glob('*.jsonl'):
                        scanned_count += 1
                        turns = count_user_turns(str(session_file))
                        if turns == 0:
                            try:
                                session_file.unlink()
                                deleted_count += 1
                                print(f"[清理] 删除空会话: {session_file}")
                            except Exception as e:
                                print(f"[清理] 删除失败: {session_file}, {e}")

                show_snackbar(state.page, L.get('empty_sessions_cleared', '已清理 {} 个空会话').format(deleted_count) + f" (扫描 {scanned_count} 个)")
                # 刷新列表
                refresh_project_list()
            except Exception as ex:
                print(f"[clear_empty_sessions] 错误: {ex}")
                show_snackbar(state.page, f"清理失败: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('confirm_clear', '确认清理')),
            content=ft.Text(L.get('confirm_clear_empty_sessions', '是否要清理所有空会话（0轮对话）？\n这些通常是使用 /clear 命令后残留的文件。')),
            actions=[ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: state.page.close(dlg)), ft.TextButton(L.get('confirm', '确认'), on_click=do_clear)]
        )
        state.page.open(dlg)

    def show_trash(_):
        """显示回收站"""
        import time
        from ..common import save_settings
        mgr = get_current_manager()
        if not mgr or not hasattr(mgr, 'trash_manager'):
            show_snackbar(state.page, L.get('history_no_records', '无记录'))
            return
        items = mgr.trash_manager.get_trash_items()
        now = time.time()
        trash_list = ft.ListView(expand=True, spacing=2)
        selected_trash = set()

        def build_list():
            trash_list.controls.clear()
            for i, item in enumerate(items):
                deleted_at = datetime.fromtimestamp(item['deleted_at'])
                days_left = max(0, TRASH_RETENTION_DAYS - (now - item['deleted_at']) / 86400)
                is_sel = i in selected_trash
                tile = ft.Container(
                    ft.Row([
                        ft.Checkbox(value=is_sel, on_change=lambda e, idx=i: toggle(idx, e.control.value)),
                        ft.Column([
                            ft.Text(f"{item['session_id'][:12]}...", weight=ft.FontWeight.BOLD if is_sel else None),
                            ft.Text(f"{deleted_at.strftime('%m-%d %H:%M')} | {days_left:.0f}天", size=11, color=ft.Colors.GREY_500),
                        ], spacing=2, expand=True),
                    ], spacing=8),
                    padding=8, bgcolor=ft.Colors.RED_50 if is_sel else None, border_radius=4,
                )
                trash_list.controls.append(tile)
            state.page.update()

        def toggle(idx, checked):
            if checked:
                selected_trash.add(idx)
            else:
                selected_trash.discard(idx)
            build_list()

        def restore(_):
            for idx in selected_trash:
                mgr.trash_manager.restore_from_trash(items[idx])
            state.page.close(dlg)
            refresh_project_list()

        def perm_delete(_):
            for idx in selected_trash:
                mgr.trash_manager.permanently_delete(items[idx])
            state.page.close(dlg)

        build_list()
        dlg = ft.AlertDialog(
            title=ft.Text(L.get('history_trash', '回收站')),
            content=ft.Container(trash_list, width=400, height=300),
            actions=[
                ft.TextButton(L.get('history_restore', '恢复'), on_click=restore),
                ft.TextButton(L.get('history_perm_delete', '永久删除'), on_click=perm_delete),
                ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: state.page.close(dlg)),
            ],
        )
        state.page.open(dlg)

    # ==================== 构建页面布局 ====================
    # 左侧边栏
    sidebar_container.content = ft.Container(
        project_list,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY)),
        border_radius=8, padding=0,
    )

    # 右侧详情面板
    detail_panel.controls = [
        detail_header,
        tool_stats_row,
        ft.Divider(height=1),
        messages_container,
    ]

    right_panel = ft.Container(
        detail_panel,
        expand=True,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY)),
        border_radius=8, padding=12,
    )

    # 主布局
    history_page = ft.Column([
        # 标题栏
        ft.Row([
            ft.Text(L.get('history', '历史记录'), size=18, weight=ft.FontWeight.BOLD),
            cli_dropdown,
            search_field,
            ft.TextButton(L.get('refresh', '刷新'), icon=ft.Icons.REFRESH, on_click=lambda _: refresh_project_list()),
            stats_text,
            ft.Container(expand=True),
            ft.TextButton(L.get('clear_empty_sessions', '清理空会话'), icon=ft.Icons.CLEANING_SERVICES, on_click=clear_empty_sessions),
            ft.TextButton(L.get('history_trash', '回收站'), icon=ft.Icons.DELETE_OUTLINE, on_click=show_trash),
        ], spacing=12),
        # 主内容区
        ft.Row([
            sidebar_container,
            right_panel,
        ], expand=True, spacing=12),
    ], expand=True, spacing=12)

    return history_page, refresh_project_list
