# AI CLI Manager - History Page
import flet as ft
from datetime import datetime, timedelta
from pathlib import Path
from ..common import THEMES, TRASH_RETENTION_DAYS, show_snackbar
from ..database import history_manager, codex_history_manager, history_cache


def create_history_page(state):
    L = state.L
    current_cli = "claude"
    selected_sessions = {}
    all_session_items = []
    last_clicked_idx = -1
    date_filter = "all"
    custom_date_from = None
    custom_date_to = None

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

    def get_history_data():
        if history_cache.get(current_cli):
            return history_cache[current_cli]
        mgr = get_current_manager()
        if mgr:
            history_cache[current_cli] = mgr.load_sessions()
        return history_cache.get(current_cli, {})

    def refresh_history_tree(filter_text=''):
        nonlocal last_clicked_idx, all_session_items
        selected_sessions.clear()
        all_session_items = []
        last_clicked_idx = -1
        history_tree.controls.clear()
        history_progress.visible = True
        state.page.update()
        
        mgr = get_current_manager()
        if current_cli in ('gemini', 'aider'):
            history_tree.controls.append(ft.Text(f'{current_cli.title()} 历史记录暂不支持', color=ft.Colors.ORANGE))
            history_stats.value = ''
            history_progress.visible = False
            state.page.update()
            return
        if not mgr:
            history_tree.controls.append(ft.Text(f'{current_cli.title()} 目录不存在', color=ft.Colors.RED))
            history_stats.value = ''
            history_progress.visible = False
            state.page.update()
            return
        
        history_data = get_history_data()
        if not history_data:
            history_stats.value = L['history_no_records']
            history_progress.visible = False
            state.page.update()
            return
        
        total_sessions = sum(len(s) for s in history_data.values())
        total_messages = sum(info['message_count'] for grp in history_data.values() for info in grp.values())
        total_size = sum(info.get('size', 0) for grp in history_data.values() for info in grp.values())
        size_str = f'{total_size / 1024 / 1024:.1f} MB' if total_size > 1024*1024 else f'{total_size / 1024:.1f} KB'
        history_stats.value = f"{L['history_sessions']}: {total_sessions} | {L['history_messages']}: {total_messages} | {L['history_size']}: {size_str}"
        
        filter_text = filter_text.lower()
        now = datetime.now().astimezone()
        today = now.date()
        
        if date_filter == 'today':
            date_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            date_cutoff_end = None
        elif date_filter == 'week':
            date_cutoff = (now - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            date_cutoff_end = None
        elif date_filter == 'month':
            date_cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_cutoff_end = None
        elif date_filter == 'custom' and custom_date_from:
            date_cutoff = custom_date_from.astimezone() if custom_date_from else None
            date_cutoff_end = custom_date_to.astimezone() if custom_date_to else None
        else:
            date_cutoff = None
            date_cutoff_end = None
        
        old_cutoff = now - timedelta(days=30)
        old_sessions = []

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

        for grp_name, sessions in sorted(history_data.items(), reverse=True):
            if not sessions: continue
            grp_items = []
            for sid, info in sorted(sessions.items(), key=lambda x: x[1].get('last_timestamp', ''), reverse=True):
                if filter_text and filter_text not in sid.lower() and filter_text not in (info.get('cwd') or '').lower(): continue
                ts = info.get('last_timestamp', '')
                dt = None
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        time_str = dt.strftime('%m-%d %H:%M')
                    except: time_str = ts[:16]
                else: time_str = '未知'
                if date_cutoff and dt and dt < date_cutoff: continue
                if date_cutoff_end and dt and dt > date_cutoff_end: continue
                if dt and dt < old_cutoff:
                    old_sessions.append((grp_name, sid, info, time_str))
                    continue
                size = info.get('size', 0)
                size_str = f'{size/1024:.1f}KB'
                item_data = {'group': grp_name, 'session_id': sid, 'info': info}
                idx = len(all_session_items)
                item = ft.Container(
                    content=ft.Column([ft.Text(f'{sid[:12]}...', size=13), ft.Text(f"{info['message_count']}条 | {time_str} | {size_str}", size=11, color=ft.Colors.GREY_500)], spacing=2),
                    on_click=lambda e, i=idx, d=item_data: on_item_click(e, i, d),
                    padding=ft.padding.only(left=20, top=5, bottom=5, right=5), border_radius=4, expand=True,
                )
                all_session_items.append((item, item_data))
                grp_items.append(ft.Row([item], expand=True))
            if grp_items:
                grp_size = sum(s.get('size', 0) for s in sessions.values())
                grp_data = [{'group': grp_name, 'session_id': sid, 'info': info} for sid, info in sessions.items()]
                history_tree.controls.append(ft.ExpansionTile(
                    title=ft.Text(grp_name[:40], size=14, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(f"{len(grp_items)} {L['history_sessions']} | {grp_size/1024:.1f}KB", size=11),
                    controls=[ft.Column(grp_items)], initially_expanded=len(history_data) <= 3,
                    trailing=ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=18, on_click=lambda _, d=grp_data: del_sessions(d)),
                ))
        if old_sessions:
            old_items = []
            for grp, sid, info, ts in old_sessions:
                item_data = {'group': grp, 'session_id': sid, 'info': info}
                idx = len(all_session_items)
                item = ft.Container(
                    content=ft.Column([ft.Text(f'{sid[:12]}...', size=13, color=ft.Colors.GREY_600), ft.Text(f'{grp[:20]} | {ts}', size=11, color=ft.Colors.GREY_500)], spacing=2),
                    on_click=lambda e, i=idx, d=item_data: on_item_click(e, i, d),
                    padding=ft.padding.only(left=20, top=5, bottom=5, right=5), border_radius=4, expand=True,
                )
                all_session_items.append((item, item_data))
                old_items.append(ft.Row([item], expand=True))
            history_tree.controls.append(ft.ExpansionTile(title=ft.Text(L['history_old'].format(len(old_sessions)), size=14, color=ft.Colors.GREY_600), controls=[ft.Column(old_items)], initially_expanded=False))
        history_progress.visible = False
        state.page.update()

    def copy_cb(t):
        state.page.set_clipboard(t)
        show_snackbar(state.page, L['history_copied'].format(t[:50]))

    def show_detail(d):
        history_detail.controls.clear()
        if not d: return
        info, sid = d['info'], d['session_id']
        history_detail.controls.append(ft.Text(L['history_session'].format(sid), size=14, weight=ft.FontWeight.BOLD))
        history_detail.controls.append(ft.Text(L['history_path'].format(info.get('cwd', '?')), size=12, color=ft.Colors.GREY_600))
        cmd = f'claude --resume {sid}' if current_cli == 'claude' else f'codex --resume {sid}'
        history_detail.controls.append(ft.Row([ft.TextButton(L['history_copy_id'], on_click=lambda _: copy_cb(sid)), ft.TextButton(L['history_copy_resume'], on_click=lambda _: copy_cb(cmd))], spacing=5))
        history_detail.controls.append(ft.Divider())
        for msg in info['messages'][:15]:
            role = msg.get('message', {}).get('role', '?') if current_cli == 'claude' else msg.get('role', '?')
            c = msg.get('message', {}).get('content', []) if current_cli == 'claude' else msg.get('content', '')
            txt = ''.join(x.get('text', '') for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c)
            if not txt.strip(): txt = '[empty]'
            bg = ft.Colors.with_opacity(0.15, ft.Colors.BLUE if role == 'user' else ft.Colors.GREEN)
            history_detail.controls.append(ft.Container(ft.Column([ft.Text(role.upper(), size=12, weight=ft.FontWeight.BOLD), ft.Text(txt[:200], size=13)]), bgcolor=bg, padding=8, border_radius=6, margin=ft.margin.only(bottom=4)))
        state.page.update()

    def del_sessions(data):
        mgr = get_current_manager()
        if not data or not mgr: return
        def do_del(e):
            dlg.open = False
            state.page.update()
            cnt = 0
            for d in data:
                if mgr.delete_session(d['group'], d['session_id'], d['info']): cnt += 1
            history_cache[current_cli] = {}
            show_snackbar(state.page, L['history_moved'].format(cnt))
            refresh_history_tree()
        dlg = ft.AlertDialog(title=ft.Text(L['confirm_delete']), content=ft.Text(L['history_confirm_delete'].format(len(data), TRASH_RETENTION_DAYS)), actions=[ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or state.page.update()), ft.TextButton(L['delete'], on_click=do_del)])
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

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
        picker = ft.FilePicker(on_result=on_result)
        state.page.overlay.append(picker)
        state.page.update()
        picker.save_file(file_name=f'session_{sid}.{fmt}', allowed_extensions=[fmt])

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
        picker = ft.FilePicker(on_result=on_result)
        state.page.overlay.append(picker)
        state.page.update()
        picker.get_directory_path()

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
        ft.Row([ft.Text(L['history'], size=20, weight=ft.FontWeight.BOLD), cli_dropdown, history_search, ft.TextButton('刷新', on_click=on_cli_change), batch_count_text, batch_delete_btn,
                ft.TextButton(L.get('export_html', '导出HTML'), on_click=lambda _: export_session('html')),
                ft.TextButton(L.get('export_md', '导出MD'), on_click=lambda _: export_session('md')),
                ft.TextButton(L.get('export_batch', '批量导出'), on_click=export_batch),
                history_progress], wrap=True),
        history_stats,
        ft.Row([ft.Container(history_tree, expand=2, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, padding=10), ft.Container(history_detail, expand=3, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, padding=10)], expand=True),
    ], expand=True, spacing=10)

    return history_page, refresh_history_tree
