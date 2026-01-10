# AI CLI Manager - History Page
import flet as ft
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from ..common import THEMES, TRASH_RETENTION_DAYS, show_snackbar
from ..database import history_manager, codex_history_manager

MAX_CACHE_SIZE = 50  # 最大缓存项目数


def shorten_path(path: str, max_len: int = 40) -> str:
    """缩短路径显示：D:/xxx/.../yyy，尽量多显示前面"""
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
    selected_sessions = {}
    all_session_items = []
    last_clicked_idx = -1
    loaded_projects = OrderedDict()  # LRU 缓存

    history_tree = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)
    history_stats = ft.Text("", size=12, color=ft.Colors.GREY_600)
    history_progress = ft.ProgressBar(visible=False, width=200)
    history_search = ft.TextField(hint_text=L["history_search"], width=250)
    history_detail = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)

    def get_current_manager():
        if current_cli == "claude":
            return history_manager
        elif current_cli == "codex":
            return codex_history_manager
        return None

    def on_item_click(e, idx, data):
        nonlocal last_clicked_idx
        theme = THEMES[state.theme_mode]
        for item, _ in all_session_items: item.bgcolor = None
        selected_sessions.clear()
        selected_sessions[data['session_id']] = data
        e.control.bgcolor = theme['selection_bg']
        last_clicked_idx = idx
        update_btns()
        show_detail(data)
        state.page.update()

    def load_project_content(grp_name, content_col, tile, title_text):
        """懒加载项目内容"""
        if grp_name in loaded_projects:
            loaded_projects.move_to_end(grp_name)  # LRU: 移到末尾
            sessions = loaded_projects[grp_name]
        else:
            mgr = get_current_manager()
            if not mgr or not hasattr(mgr, 'load_project'):
                return
            sessions = mgr.load_project(grp_name)
            loaded_projects[grp_name] = sessions
            # 超出限制时删除最旧的
            while len(loaded_projects) > MAX_CACHE_SIZE:
                loaded_projects.popitem(last=False)

        content_col.controls.clear()
        if not sessions:
            content_col.controls.append(ft.Text(L.get('history_no_records', '无记录'), color=ft.Colors.GREY_500))
            state.page.update()
            return

        # 用第一个 session 的 cwd 更新标题
        first_session = next(iter(sessions.values()), {})
        real_path = first_session.get('cwd', '')
        if real_path:
            title_text.value = shorten_path(real_path, 40)
            title_text.tooltip = real_path

        # 更新统计
        grp_size = sum(s.get('size', 0) for s in sessions.values())
        total_msgs = sum(s.get('message_count', 0) for s in sessions.values())
        tile.subtitle = ft.Text(f"{len(sessions)} {L['history_sessions']} | {total_msgs} {L.get('history_messages', '消息')} | {grp_size/1024:.1f}KB", size=11)

        for sid, info in sorted(sessions.items(), key=lambda x: x[1].get('last_timestamp', ''), reverse=True):
            ts = info.get('last_timestamp', '')
            try:
                time_str = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%m-%d %H:%M') if ts else L.get('unknown', '未知')
            except (ValueError, AttributeError):
                time_str = ts[:16] if ts else L.get('unknown', '未知')
            size_str = f'{info.get("size", 0)/1024:.1f}KB'
            turns = count_real_turns(info.get('messages', []))
            item_data = {'group': grp_name, 'session_id': sid, 'info': info}
            idx = len(all_session_items)
            item = ft.Container(
                content=ft.Column([ft.Text(f'{sid[:12]}...', size=13), ft.Text(f"{turns}轮 | {time_str} | {size_str}", size=11, color=ft.Colors.GREY_500)], spacing=2),
                on_click=lambda e, i=idx, d=item_data: on_item_click(e, i, d),
                padding=ft.padding.only(left=20, top=5, bottom=5, right=5), border_radius=4, expand=True,
            )
            all_session_items.append((item, item_data))
            content_col.controls.append(ft.Row([item], expand=True))
        state.page.update()

    def refresh_history_tree(filter_text=''):
        nonlocal last_clicked_idx, all_session_items
        selected_sessions.clear()
        all_session_items = []
        loaded_projects.clear()
        last_clicked_idx = -1
        history_tree.controls.clear()
        history_stats.value = ''

        mgr = get_current_manager()
        if current_cli in ('gemini', 'aider'):
            history_tree.controls.append(ft.Text(f'{current_cli.title()} 历史记录暂不支持', color=ft.Colors.ORANGE))
            state.page.update()
            return
        if not mgr:
            history_tree.controls.append(ft.Text(f'{current_cli.title()} 目录不存在', color=ft.Colors.RED))
            state.page.update()
            return

        # 显示进度条
        history_progress.visible = True
        history_progress.value = 0
        state.page.update()

        # 使用 with_cwd=True 获取项目列表和真实路径
        projects_data = mgr.list_projects(with_cwd=True, limit=50) if hasattr(mgr, 'list_projects') else []
        if not projects_data:
            history_stats.value = L['history_no_records']
            history_progress.visible = False
            state.page.update()
            return

        history_stats.value = f"{L.get('history_projects', '项目')}: {len(projects_data)}"

        # 构建 cwd_map: project_id -> real_cwd
        cwd_map = {}
        projects = []
        for item in projects_data:
            if isinstance(item, tuple):
                project_id, real_cwd = item
            else:
                project_id = item
                real_cwd = ''
            projects.append(project_id)
            cwd_map[project_id] = real_cwd or project_id

        total = len(projects)
        for i, grp_name in enumerate(projects):
            # 更新进度
            history_progress.value = (i + 1) / total
            if i % 5 == 0:  # 每5个更新一次UI
                state.page.update()

            # 使用真实路径或项目名显示
            display_path = cwd_map.get(grp_name, grp_name)
            if filter_text and filter_text.lower() not in display_path.lower() and filter_text.lower() not in grp_name.lower():
                continue
            content_col = ft.Column([], spacing=2)
            title_text = ft.Text(shorten_path(display_path, 40), size=14, weight=ft.FontWeight.W_500)
            title_text.tooltip = display_path
            folder_btn = ft.IconButton(ft.Icons.FOLDER_OPEN, icon_size=16, tooltip=title_text.tooltip)
            def open_folder(e, txt=title_text):
                import subprocess, sys
                path = txt.tooltip or txt.value
                if sys.platform == 'win32':
                    subprocess.Popen(['explorer', path.replace('/', '\\')])
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', path])
                else:
                    subprocess.Popen(['xdg-open', path])
            folder_btn.on_click = open_folder
            tile = ft.ExpansionTile(
                title=ft.Row([title_text, folder_btn], spacing=0),
                subtitle=ft.Text(L.get('click_to_load', '点击加载...'), size=11, color=ft.Colors.GREY_500),
                controls=[content_col],
                initially_expanded=False,
            )
            # 展开时加载
            def on_expand(e, g=grp_name, c=content_col, t=tile, txt=title_text):
                if str(e.data).lower() == 'true' and not c.controls:
                    load_project_content(g, c, t, txt)
            tile.on_change = on_expand
            history_tree.controls.append(tile)

        # 隐藏进度条
        history_progress.value = 1
        history_progress.visible = False
        state.page.update()

    def copy_cb(t):
        state.page.set_clipboard(t)
        show_snackbar(state.page, L['history_copied'].format(t[:50]))

    def extract_content(msg) -> tuple[str, str, list, bool]:
        """提取消息内容，返回 (role, text, tool_blocks, is_real_user)
        is_real_user: True表示真正的用户输入，False表示AI中间步骤(tool_result)
        """
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

        # 用户消息：没有tool_result = 真正用户输入
        # AI中间步骤：有tool_result = 假用户消息
        is_real_user = (role == 'user' and not has_tool_result)
        return role, '\n'.join(texts), tool_blocks, is_real_user

    def count_real_turns(messages):
        """计算真实对话轮次"""
        turns = 0
        for msg in messages:
            role, _, _, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                turns += 1
        return turns

    # 工具图标和颜色映射
    TOOL_ICONS = {
        'Read': ('📖', '读取', ft.Colors.BLUE_400),
        'Write': ('✏️', '写入', ft.Colors.GREEN_400),
        'Edit': ('📝', '编辑', ft.Colors.ORANGE_400),
        'Bash': ('💻', '命令', ft.Colors.PURPLE_400),
        'Glob': ('🔍', '搜索文件', ft.Colors.TEAL_400),
        'Grep': ('🔎', '搜索内容', ft.Colors.CYAN_400),
        'Task': ('🚀', '子任务', ft.Colors.PINK_400),
        'TodoWrite': ('📋', '待办', ft.Colors.AMBER_400),
        'WebFetch': ('🌐', '网页', ft.Colors.INDIGO_400),
        'WebSearch': ('🔍', '搜索', ft.Colors.LIGHT_BLUE_400),
    }

    def get_tool_detail(name, inp):
        """获取工具调用的详细信息"""
        if name == 'Read':
            return inp.get('file_path', '')
        elif name == 'Write':
            return inp.get('file_path', '')
        elif name == 'Edit':
            return inp.get('file_path', '')
        elif name == 'Bash':
            return inp.get('command', '')[:80].replace('\n', ' ')
        elif name in ('Glob', 'Grep'):
            return inp.get('pattern', '')
        elif name == 'Task':
            return inp.get('description', '')
        elif name == 'TodoWrite':
            todos = inp.get('todos', [])
            return ', '.join(t.get('content', '')[:15] for t in todos[:3])
        elif name == 'WebFetch':
            return inp.get('url', '')[:60]
        elif name == 'WebSearch':
            return inp.get('query', '')
        return str(inp)[:50]

    def render_edit_diff(inp):
        """渲染 Edit 工具的 diff 内容"""
        old = inp.get('old_string', '')[:500]
        new = inp.get('new_string', '')[:500]
        return ft.Column([
            ft.Text("- 旧内容:", size=11, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
            ft.Container(ft.Text(old, size=10, selectable=True), bgcolor=ft.Colors.RED_50, padding=6, border_radius=4),
            ft.Text("+ 新内容:", size=11, color=ft.Colors.GREEN_400, weight=ft.FontWeight.BOLD),
            ft.Container(ft.Text(new, size=10, selectable=True), bgcolor=ft.Colors.GREEN_50, padding=6, border_radius=4),
        ], spacing=4)

    def render_timeline_item(step_num, icon, label, detail, color, expanded_content=None):
        """渲染时间线单个步骤"""
        expand_state = {'open': False}
        detail_col = ft.Column([], visible=False)

        def toggle_expand(_):
            if expanded_content:
                expand_state['open'] = not expand_state['open']
                detail_col.visible = expand_state['open']
                if expand_state['open'] and not detail_col.controls:
                    detail_col.controls.append(expanded_content)
                state.page.update()

        return ft.Container(
            ft.Column([
                ft.Row([
                    ft.Container(ft.Text(str(step_num), size=10, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                                 width=20, height=20, bgcolor=color, border_radius=10, alignment=ft.alignment.center),
                    ft.Text(f"{icon} {label}", size=12, weight=ft.FontWeight.W_500),
                    ft.Text(shorten_path(detail, 50), size=11, color=ft.Colors.GREY_600, expand=True),
                    ft.Icon(ft.Icons.EXPAND_MORE if expanded_content else None, size=16, color=ft.Colors.GREY_400),
                ], spacing=8),
                detail_col,
            ], spacing=2),
            padding=ft.padding.symmetric(vertical=4, horizontal=8),
            border=ft.border.only(left=ft.BorderSide(2, color)),
            margin=ft.margin.only(left=10, bottom=2),
            on_click=toggle_expand if expanded_content else None,
            ink=bool(expanded_content),
        )

    def simplify_user_msg(txt):
        """简化用户消息，提取关键内容"""
        import re
        # 提取文件路径 (Windows/Unix)
        paths = re.findall(r'[A-Za-z]:[\\\/][^\s\n\'"<>|*?]+|\/[\w\-\.\/]+', txt)
        if paths:
            return ' '.join(paths[:3])  # 最多3个路径
        return txt[:200]

    def render_user_msg(txt):
        """渲染用户消息"""
        display = simplify_user_msg(txt) if txt else '[空]'
        return ft.Container(
            ft.Row([
                ft.Icon(ft.Icons.PERSON, size=18, color=ft.Colors.BLUE),
                ft.Text(display, size=13, expand=True, tooltip=txt[:500] if len(txt) > 200 else None),
            ], spacing=8),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE),
            padding=10, border_radius=8, margin=ft.margin.only(bottom=8),
        )

    def render_ai_thinking(txt):
        """渲染AI思考/回复文本"""
        if not txt or not txt.strip():
            return None
        return ft.Container(
            ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=ft.Colors.GREEN),
                ft.Text(txt[:400], size=12, color=ft.Colors.GREY_800),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=ft.padding.only(left=10, bottom=6),
        )

    def show_detail(d):
        history_detail.controls.clear()
        if not d: return
        info, sid = d['info'], d['session_id']
        messages = info.get('messages', [])

        # 头部信息
        history_detail.controls.append(ft.Text(L['history_session'].format(sid[:16]), size=14, weight=ft.FontWeight.BOLD))
        history_detail.controls.append(ft.Text(L['history_path'].format(info.get('cwd', '?')), size=12, color=ft.Colors.GREY_600))
        cmd = f'claude --resume {sid}' if current_cli == 'claude' else f'codex --resume {sid}'
        history_detail.controls.append(ft.Row([ft.TextButton(L['history_copy_id'], on_click=lambda _: copy_cb(sid)), ft.TextButton(L['history_copy_resume'], on_click=lambda _: copy_cb(cmd))], spacing=5))

        # 统计工具使用和真实对话轮次
        tool_stats = {}
        real_turns = 0  # 真实对话轮次
        for msg in messages:
            role, txt, tool_blocks, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                real_turns += 1
            for b in tool_blocks:
                if b.get('type') == 'tool_use':
                    name = b.get('name', 'unknown')
                    tool_stats[name] = tool_stats.get(name, 0) + 1

        # 显示真实对话轮次
        history_detail.controls.append(ft.Text(f"{L.get('real_turns', '对话轮次')}: {real_turns}", size=12, color=ft.Colors.GREY_600))

        if tool_stats:
            stats_chips = [ft.Container(
                ft.Text(f"{TOOL_ICONS.get(n, ('🔧', n, ft.Colors.GREY))[0]} {n}: {c}", size=11),
                bgcolor=ft.Colors.with_opacity(0.1, TOOL_ICONS.get(n, ('', '', ft.Colors.GREY))[2]),
                padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=12,
            ) for n, c in sorted(tool_stats.items(), key=lambda x: -x[1])[:8]]
            history_detail.controls.append(ft.Row(stats_chips, wrap=True, spacing=4))

        history_detail.controls.append(ft.Divider())

        # 头部控件数量：标题、路径、按钮、轮次、[工具统计]、分隔线
        header_count = 6 if tool_stats else 5

        # 将消息按"轮次"分组：一个真实用户消息 + 后续所有AI响应 = 一轮
        rounds = []  # [(user_msg, [ai_msgs...])]
        current_round = None
        orphan_ai_msgs = []  # 开头没有用户消息的AI响应
        for msg in messages:
            role, txt, tool_blocks, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                # 真实用户消息开始新一轮
                if current_round:
                    rounds.append(current_round)
                current_round = (msg, [])
            elif current_round:
                current_round[1].append(msg)
            else:
                orphan_ai_msgs.append(msg)
        if current_round:
            rounds.append(current_round)
        # 如果开头有孤立的AI消息，创建一个虚拟轮次
        if orphan_ai_msgs and not rounds:
            rounds.append((None, orphan_ai_msgs))
        elif orphan_ai_msgs and rounds:
            # 将孤立的AI消息添加到第一轮之前
            rounds.insert(0, (None, orphan_ai_msgs))

        load_state = {'head': 1, 'tail': 1}  # 初始：首尾各1轮

        def render_round(round_data, round_num):
            """渲染一轮对话"""
            user_msg, ai_msgs = round_data
            controls = []
            step = 0
            # 用户消息（可能为None）
            if user_msg:
                _, txt, _, _ = extract_content(user_msg)
                controls.append(render_user_msg(f"[轮{round_num}] {txt}"))
            # AI响应
            for msg in ai_msgs:
                role, txt, tool_blocks, _ = extract_content(msg)
                if role == 'assistant':
                    thinking = render_ai_thinking(txt)
                    if thinking:
                        controls.append(thinking)
                    for block in tool_blocks:
                        if block.get('type') == 'tool_use':
                            step += 1
                            name = block.get('name', 'unknown')
                            inp = block.get('input', {})
                            icon, label, color = TOOL_ICONS.get(name, ('🔧', name, ft.Colors.GREY))
                            detail = get_tool_detail(name, inp)
                            # Edit 工具支持展开查看 diff
                            expanded = render_edit_diff(inp) if name == 'Edit' else None
                            controls.append(render_timeline_item(step, icon, label, detail, color, expanded))
            return controls

        def build_timeline():
            del history_detail.controls[header_count:]
            total = len(rounds)
            if total == 0:
                history_detail.controls.append(ft.Text(L.get('history_no_records', '无记录'), color=ft.Colors.GREY_500))
                return

            head_n, tail_n = load_state['head'], load_state['tail']
            # 计算显示范围
            if head_n + tail_n >= total:
                # 全部显示
                for i, rd in enumerate(rounds):
                    history_detail.controls.extend(render_round(rd, i + 1))
            else:
                # 显示头部
                for i in range(head_n):
                    history_detail.controls.extend(render_round(rounds[i], i + 1))
                # 展开按钮：向上/向下两个方向
                hidden = total - head_n - tail_n
                def expand_down(_):
                    load_state['head'] += 3
                    build_timeline()
                    state.page.update()
                def expand_up(_):
                    load_state['tail'] += 3
                    build_timeline()
                    state.page.update()
                history_detail.controls.append(ft.Container(
                    ft.Row([
                        ft.ElevatedButton("⬇ 向下 +3", on_click=expand_down, bgcolor=ft.Colors.BLUE_400, color=ft.Colors.WHITE),
                        ft.Text(f"隐藏 {hidden} 轮", size=12, color=ft.Colors.GREY_600),
                        ft.ElevatedButton("⬆ 向上 +3", on_click=expand_up, bgcolor=ft.Colors.BLUE_400, color=ft.Colors.WHITE),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
                    margin=ft.margin.symmetric(vertical=12),
                ))
                # 显示尾部
                for i in range(total - tail_n, total):
                    history_detail.controls.extend(render_round(rounds[i], i + 1))

        build_timeline()
        state.page.update()

    def del_sessions(data):
        mgr = get_current_manager()
        if not data or not mgr: return
        def do_del(e):
            state.page.close(dlg)
            cnt = 0
            for d in data:
                if mgr.delete_session(d['group'], d['session_id'], d['info']): cnt += 1
                loaded_projects.pop(d['group'], None)  # 清除本地缓存
            show_snackbar(state.page, L['history_moved'].format(cnt))
            refresh_history_tree()
        dlg = ft.AlertDialog(
            title=ft.Text(L['confirm_delete']),
            content=ft.Text(L['history_confirm_delete'].format(len(data), TRASH_RETENTION_DAYS)),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda _: state.page.close(dlg)),
                ft.TextButton(L['delete'], on_click=do_del)
            ]
        )
        state.page.open(dlg)

    # 共享 FilePicker
    file_picker = ft.FilePicker()
    state.page.overlay.append(file_picker)

    def export_session(fmt='html'):
        """导出选中会话"""
        if not selected_sessions:
            show_snackbar(state.page, L['no_selection'])
            return
        from core.session_export import export_session_html, export_session_md
        data = list(selected_sessions.values())[0]
        sid = data['session_id'][:12]
        def on_result(result):
            if result.path:
                try:
                    if fmt == 'html':
                        export_session_html(data, result.path)
                    else:
                        export_session_md(data, result.path)
                    show_snackbar(state.page, L.get('export_success', '导出成功: {}').format(result.path))
                except Exception as ex:
                    show_snackbar(state.page, str(ex))
        file_picker.on_result = on_result
        file_picker.save_file(file_name=f'session_{sid}.{fmt}', allowed_extensions=[fmt])

    def export_batch(e):
        """批量导出所有会话"""
        from core.session_export import export_sessions_batch
        all_data = [d for _, d in all_session_items]
        if not all_data:
            show_snackbar(state.page, L['history_no_records'])
            return
        def on_result(result):
            if result.path:
                cnt = export_sessions_batch(all_data, result.path, 'html')
                show_snackbar(state.page, L.get('export_batch_success', '批量导出 {} 个会话到 {}').format(cnt, result.path))
        file_picker.on_result = on_result
        file_picker.get_directory_path()

    def show_trash_dialog(e):
        """显示回收站对话框"""
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
        retention_days = state.settings.get('trash_retention_days', TRASH_RETENTION_DAYS)

        retention_field = ft.TextField(value=str(retention_days), width=50, text_size=12, content_padding=5)
        def save_retention(_):
            try:
                days = int(retention_field.value)
                if 1 <= days <= 365:
                    state.settings['trash_retention_days'] = days
                    save_settings(state.settings)
                    show_snackbar(state.page, L.get('saved', '已保存'))
            except ValueError:
                pass

        def build_trash_list():
            trash_list.controls.clear()
            days_setting = state.settings.get('trash_retention_days', TRASH_RETENTION_DAYS)
            for i, item in enumerate(items):
                deleted_at = datetime.fromtimestamp(item['deleted_at'])
                days_left = max(0, days_setting - (now - item['deleted_at']) / 86400)
                is_sel = i in selected_trash
                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_sel, on_change=lambda e, idx=i: toggle_trash(idx, e.control.value)),
                        ft.Column([
                            ft.Text(f"{item['session_id'][:12]}...", weight=ft.FontWeight.BOLD if is_sel else None),
                            ft.Text(f"{item['project_name'][:20]} | {deleted_at.strftime('%m-%d %H:%M')} | {days_left:.1f}天", size=11, color=ft.Colors.GREY_600),
                        ], spacing=2, expand=True),
                    ], spacing=10),
                    padding=8, bgcolor=ft.Colors.RED_50 if is_sel else None, border_radius=4,
                )
                trash_list.controls.append(tile)
            state.page.update()

        def toggle_trash(idx, checked):
            if checked: selected_trash.add(idx)
            else: selected_trash.discard(idx)
            build_trash_list()

        def restore_selected(_):
            cnt = 0
            for idx in selected_trash:
                if mgr.trash_manager.restore_from_trash(items[idx]): cnt += 1
            state.page.close(dlg)
            show_snackbar(state.page, L.get('history_restored', '已恢复 {} 个会话').format(cnt))
            refresh_history_tree()

        def perm_delete(_):
            for idx in selected_trash:
                mgr.trash_manager.permanently_delete(items[idx])
            state.page.close(dlg)
            show_snackbar(state.page, L.get('history_perm_deleted', '已永久删除'))

        def clear_trash(_):
            for item in items:
                mgr.trash_manager.permanently_delete(item)
            state.page.close(dlg)
            show_snackbar(state.page, L.get('history_trash_cleared', '回收站已清空'))

        build_trash_list()
        dlg = ft.AlertDialog(
            title=ft.Text(L.get('history_trash', '回收站')),
            content=ft.Container(
                ft.Column([
                    ft.Row([ft.Text(L.get('trash_retention', '清理周期'), size=12), retention_field, ft.Text(L.get('days', '天'), size=12), ft.TextButton(L.get('save', '保存'), on_click=save_retention)], spacing=5),
                    trash_list
                ], expand=True),
                width=500, height=350
            ),
            actions=[
                ft.TextButton(L.get('history_restore', '恢复'), on_click=restore_selected),
                ft.TextButton(L.get('history_perm_delete', '永久删除'), on_click=perm_delete),
                ft.TextButton(L.get('history_clear_trash', '清空回收站'), on_click=clear_trash),
                ft.TextButton(L['cancel'], on_click=lambda _: state.page.close(dlg)),
            ],
        )
        state.page.open(dlg)

    batch_delete_btn = ft.TextButton(L['history_delete_selected'], visible=False, on_click=lambda _: del_sessions(list(selected_sessions.values())))
    batch_count_text = ft.Text('', size=12)

    def update_btns():
        batch_delete_btn.visible = len(selected_sessions) > 0
        batch_count_text.value = L['history_selected_count'].format(len(selected_sessions)) if selected_sessions else ''

    cli_dropdown = ft.Dropdown(value=current_cli, options=[ft.dropdown.Option('claude', 'Claude'), ft.dropdown.Option('codex', 'Codex'), ft.dropdown.Option('gemini', 'Gemini'), ft.dropdown.Option('aider', 'Aider')], width=120)
    def on_cli_change(_):
        nonlocal current_cli
        nc = cli_dropdown.value or 'claude'
        if nc != current_cli:
            current_cli = nc
            history_detail.controls.clear()
        refresh_history_tree(history_search.value or '')
    cli_dropdown.on_change = on_cli_change
    history_search.on_submit = lambda e: refresh_history_tree(e.control.value or '')

    history_page = ft.Column([
        ft.Row([ft.Text(L['history'], size=20, weight=ft.FontWeight.BOLD), cli_dropdown, history_search, ft.TextButton(L.get('refresh', '刷新'), on_click=on_cli_change), batch_count_text, batch_delete_btn,
                ft.TextButton(L.get('export_html', '导出HTML'), on_click=lambda _: export_session('html')),
                ft.TextButton(L.get('export_md', '导出MD'), on_click=lambda _: export_session('md')),
                ft.TextButton(L.get('export_batch', '批量导出'), on_click=export_batch),
                ft.TextButton(L.get('history_trash', '回收站'), icon=ft.Icons.DELETE_OUTLINE, on_click=show_trash_dialog),
                history_progress], wrap=True),
        history_stats,
        ft.Row([ft.Container(history_tree, expand=2, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, padding=10), ft.Container(history_detail, expand=3, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, padding=10)], expand=True),
    ], expand=True, spacing=10)

    return history_page, refresh_history_tree
