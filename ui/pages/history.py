# AI CLI Manager - History Page
import flet as ft
from datetime import datetime
from pathlib import Path
from ..common import THEMES, TRASH_RETENTION_DAYS, show_snackbar
from ..database import history_manager, codex_history_manager


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
    current_cli = "claude"
    selected_sessions = {}
    all_session_items = []
    last_clicked_idx = -1
    loaded_projects = {}  # 已加载的项目数据缓存

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
            sessions = loaded_projects[grp_name]
        else:
            mgr = get_current_manager()
            if not mgr or not hasattr(mgr, 'load_project'):
                return
            sessions = mgr.load_project(grp_name)
            loaded_projects[grp_name] = sessions

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
            except:
                time_str = ts[:16] if ts else L.get('unknown', '未知')
            size_str = f'{info.get("size", 0)/1024:.1f}KB'
            item_data = {'group': grp_name, 'session_id': sid, 'info': info}
            idx = len(all_session_items)
            item = ft.Container(
                content=ft.Column([ft.Text(f'{sid[:12]}...', size=13), ft.Text(f"{info['message_count']}条 | {time_str} | {size_str}", size=11, color=ft.Colors.GREY_500)], spacing=2),
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

        # 只获取项目列表（快速）
        projects = mgr.list_projects() if hasattr(mgr, 'list_projects') else []
        if not projects:
            history_stats.value = L['history_no_records']
            state.page.update()
            return

        history_stats.value = f"{L.get('history_projects', '项目')}: {len(projects)}"

        # Claude: 快速获取前10个项目的cwd
        if current_cli == 'claude' and mgr:
            projects_with_cwd = mgr.list_projects(with_cwd=True, limit=10)
            cwd_map = {name: cwd for name, cwd in projects_with_cwd}
        else:
            cwd_map = {}

        for grp_name in projects:
            if filter_text and filter_text.lower() not in grp_name.lower():
                continue
            content_col = ft.Column([], spacing=2)
            # 优先用预加载的cwd
            display_path = cwd_map.get(grp_name, '') or grp_name
            title_text = ft.Text(shorten_path(display_path, 40), size=14, weight=ft.FontWeight.W_500)
            title_text.tooltip = display_path if display_path != grp_name else grp_name
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

        state.page.update()

    def copy_cb(t):
        state.page.set_clipboard(t)
        show_snackbar(state.page, L['history_copied'].format(t[:50]))

    def render_msg(msg):
        role = msg.get('message', {}).get('role', '?') if current_cli == 'claude' else msg.get('role', '?')
        c = msg.get('message', {}).get('content', []) if current_cli == 'claude' else msg.get('content', '')
        txt = ''.join(x.get('text', '') for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c)
        if not txt.strip(): txt = '[empty]'
        bg = ft.Colors.with_opacity(0.15, ft.Colors.BLUE if role == 'user' else ft.Colors.GREEN)
        return ft.Container(ft.Column([ft.Text(role.upper(), size=12, weight=ft.FontWeight.BOLD), ft.Text(txt[:200], size=13)]), bgcolor=bg, padding=8, border_radius=6, margin=ft.margin.only(bottom=4))

    def show_detail(d):
        history_detail.controls.clear()
        if not d: return
        info, sid = d['info'], d['session_id']
        messages = info.get('messages', [])
        total = len(messages)

        history_detail.controls.append(ft.Text(L['history_session'].format(sid), size=14, weight=ft.FontWeight.BOLD))
        history_detail.controls.append(ft.Text(L['history_path'].format(info.get('cwd', '?')), size=12, color=ft.Colors.GREY_600))
        cmd = f'claude --resume {sid}' if current_cli == 'claude' else f'codex --resume {sid}'
        history_detail.controls.append(ft.Row([ft.TextButton(L['history_copy_id'], on_click=lambda _: copy_cb(sid)), ft.TextButton(L['history_copy_resume'], on_click=lambda _: copy_cb(cmd))], spacing=5))
        history_detail.controls.append(ft.Divider())

        load_state = {'head': 10, 'tail': 10}  # 已加载的头尾数量

        def rebuild_messages():
            # 清除消息区域（保留前4个：标题、路径、按钮、分隔线）
            del history_detail.controls[4:]
            head_n, tail_n = load_state['head'], load_state['tail']
            mid_start, mid_end = head_n, total - tail_n
            hidden = mid_end - mid_start

            # 渲染头部
            for msg in messages[:min(head_n, total)]:
                history_detail.controls.append(render_msg(msg))

            # 中间展开按钮
            if hidden > 0:
                def expand(_):
                    load_state['head'] += 10
                    load_state['tail'] += 10
                    rebuild_messages()
                    state.page.update()
                btn = ft.TextButton(L.get('expand_more', '展开更多 ({})').format(hidden), on_click=expand)
                history_detail.controls.append(ft.Container(btn, alignment=ft.alignment.center, margin=ft.margin.symmetric(vertical=5)))

            # 渲染尾部
            if mid_end < total:
                for msg in messages[max(mid_end, head_n):]:
                    history_detail.controls.append(render_msg(msg))

        rebuild_messages()
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

    cli_dropdown = ft.Dropdown(value='claude', options=[ft.dropdown.Option('claude', 'Claude'), ft.dropdown.Option('codex', 'Codex'), ft.dropdown.Option('gemini', 'Gemini'), ft.dropdown.Option('aider', 'Aider')], width=120)
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
