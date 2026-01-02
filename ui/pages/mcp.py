# AI CLI Manager - MCP Page
import flet as ft
import json
import threading
from pathlib import Path
from ..common import THEMES, OFFICIAL_MCP_SERVERS, MCP_MARKETPLACES, save_mcp, show_snackbar
from ..database import mcp_registry


MCP_CATEGORIES = ['常用', '文件', '网络', '数据', '其他']


def create_mcp_page(state):
    """创建 MCP 页面"""
    L = state.L
    theme = state.get_theme()
    mcp_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    expanded_mcp_categories = {}
    selected_mcp = None
    mcp_fetch_log = []

    def get_mcp_key(m):
        return m.get('name', '').lower().replace(' ', '-')

    def build_mcp_server_config(m):
        server_config = {'command': m.get('command', 'npx')}
        if m.get('args'):
            server_config['args'] = m['args'].split()
        if m.get('env'):
            env_dict = {}
            for part in m['env'].split():
                if '=' in part:
                    k, v = part.split('=', 1)
                    env_dict[k] = v
            if env_dict:
                server_config['env'] = env_dict
        return server_config

    def sync_default_mcp_to_global():
        global_mcp_path = Path.home() / '.claude' / '.mcp.json'
        global_mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_servers = {}
        for m in state.mcp_list:
            if m.get('is_default'):
                mcp_servers[get_mcp_key(m)] = build_mcp_server_config(m)
        with open(global_mcp_path, 'w', encoding='utf-8') as f:
            json.dump({'mcpServers': mcp_servers}, f, indent=2, ensure_ascii=False)

    def toggle_mcp_default(idx, is_default):
        state.mcp_list[idx]['is_default'] = is_default
        state.save_mcp()
        sync_default_mcp_to_global()
        refresh_mcp_tree()

    def build_mcp_tree():
        tree = {}
        for m in state.mcp_list:
            cat = m.get('category', '其他')
            if cat not in tree:
                tree[cat] = []
            tree[cat].append(m)
        return {k: tree[k] for k in MCP_CATEGORIES if k in tree} | {k: v for k, v in tree.items() if k not in MCP_CATEGORIES}

    def refresh_mcp_tree():
        mcp_tree.controls.clear()
        tree = build_mcp_tree()
        theme = state.get_theme()
        for cat, items in tree.items():
            is_expanded = expanded_mcp_categories.get(cat, True)
            cat_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER),
                    ft.Text(cat, weight=ft.FontWeight.BOLD),
                    ft.Text(f"({len(items)})", color=ft.Colors.GREY_600),
                ], spacing=5),
                padding=ft.padding.only(left=5, top=8, bottom=8),
                on_click=lambda e, c=cat: toggle_mcp_category(c),
                bgcolor=theme['header_bg'], border_radius=4,
            )
            mcp_tree.controls.append(cat_header)
            if is_expanded:
                for i, m in enumerate(state.mcp_list):
                    if m.get('category', '其他') != cat:
                        continue
                    is_selected = selected_mcp == i
                    is_default = m.get('is_default', False)
                    item = ft.Container(
                        content=ft.Row([
                            ft.Checkbox(value=is_default, on_change=lambda e, idx=i: toggle_mcp_default(idx, e.control.value),
                                       tooltip=L['mcp_set_default_hint']),
                            ft.Icon(ft.Icons.STAR if is_default else ft.Icons.EXTENSION, size=16,
                                   color=ft.Colors.ORANGE if is_default else (ft.Colors.BLUE if is_selected else ft.Colors.GREY_600)),
                            ft.Column([
                                ft.Text(m.get('name', 'Unnamed'),
                                       weight=ft.FontWeight.BOLD if is_selected else None,
                                       color=ft.Colors.BLUE if is_selected else None),
                                ft.Text(f"{m.get('command', '')} {m.get('args', '')}", size=10, color=ft.Colors.GREY_500),
                            ], spacing=0, expand=True),
                        ], spacing=5),
                        padding=ft.padding.only(left=30, top=5, bottom=5),
                        on_click=lambda e, idx=i: select_mcp(idx),
                        bgcolor=ft.Colors.BLUE_50 if is_selected else None, border_radius=4,
                    )
                    mcp_tree.controls.append(item)
        state.page.update()

    def toggle_mcp_category(cat):
        expanded_mcp_categories[cat] = not expanded_mcp_categories.get(cat, True)
        refresh_mcp_tree()

    def select_mcp(idx):
        nonlocal selected_mcp
        selected_mcp = idx
        refresh_mcp_tree()

    def add_mcp(e):
        show_mcp_dialog(None)

    def edit_mcp(e):
        if selected_mcp is not None:
            show_mcp_dialog(selected_mcp)

    def delete_mcp(e):
        nonlocal selected_mcp
        if selected_mcp is not None:
            state.mcp_list.pop(selected_mcp)
            state.save_mcp()
            selected_mcp = None
            refresh_mcp_tree()

    def show_mcp_dialog(idx):
        is_edit = idx is not None
        m = state.mcp_list[idx] if is_edit else {}
        name_field = ft.TextField(label=L['name'], value=m.get('name', ''), expand=True)
        category_field = ft.Dropdown(
            label=L['mcp_category'], value=m.get('category', L['mcp_other']),
            options=[ft.dropdown.Option(c) for c in MCP_CATEGORIES], expand=True,
        )
        command_field = ft.TextField(label=L['mcp_command'], value=m.get('command', 'npx'), expand=True)
        args_field = ft.TextField(label=L['mcp_args'], value=m.get('args', ''), expand=True)
        env_field = ft.TextField(label=L['mcp_env'], value=m.get('env', ''), expand=True)

        def save_mcp_item(e):
            if not name_field.value:
                return
            new_m = {
                'name': name_field.value, 'category': category_field.value or '其他',
                'command': command_field.value, 'args': args_field.value, 'env': env_field.value,
                'is_default': m.get('is_default', False) if is_edit else False,
            }
            if is_edit:
                state.mcp_list[idx] = new_m
            else:
                state.mcp_list.append(new_m)
            state.save_mcp()
            refresh_mcp_tree()
            dlg.open = False
            state.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([name_field, category_field, command_field, args_field, env_field], tight=True, spacing=10, width=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or state.page.update()),
                ft.TextButton(L['save'], on_click=save_mcp_item),
            ],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    def add_from_official(e):
        official_list = ft.ListView(expand=True, spacing=2)
        for server in OFFICIAL_MCP_SERVERS:
            tile = ft.ListTile(
                leading=ft.Icon(ft.Icons.EXTENSION, color=ft.Colors.BLUE),
                title=ft.Text(server['name']),
                subtitle=ft.Text(f"{server['desc']}\n{server['package']}", size=11),
                on_click=lambda e, s=server: select_official(s),
            )
            official_list.controls.append(tile)

        def select_official(server):
            args_hint = server.get('args_hint', '')
            env_hint = server.get('env_hint', '')
            new_m = {
                'name': server['name'], 'command': 'npx',
                'args': f"-y {server['package']}" + (f" {args_hint}" if args_hint else ""),
                'env': env_hint,
            }
            state.mcp_list.append(new_m)
            state.save_mcp()
            refresh_mcp_tree()
            dlg.open = False
            show_snackbar(state.page, L['mcp_added'].format(1))

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_select_official']),
            content=ft.Container(official_list, width=450, height=400),
            actions=[ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or state.page.update())],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    def browse_mcp_market(e):
        import webbrowser
        market_list = ft.ListView(expand=True, spacing=2)
        for m in MCP_MARKETPLACES:
            tile = ft.ListTile(
                leading=ft.Icon(ft.Icons.STORE, color=ft.Colors.PURPLE),
                title=ft.Text(m['name']), subtitle=ft.Text(m['desc']),
                on_click=lambda e, url=m['url']: webbrowser.open(url),
            )
            market_list.controls.append(tile)
        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_market']),
            content=ft.Container(market_list, width=400, height=250),
            actions=[ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or state.page.update())],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    def parse_mcp_json(data: dict) -> list:
        results = []
        servers = data.get('mcpServers', data) if isinstance(data, dict) else {}
        for name, cfg in servers.items():
            if not isinstance(cfg, dict):
                continue
            args = cfg.get('args', [])
            env = cfg.get('env', {})
            results.append({
                'name': name, 'category': '其他', 'command': cfg.get('command', 'npx'),
                'args': ' '.join(args) if isinstance(args, list) else str(args),
                'env': ' '.join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else '',
                'is_default': False,
            })
        return results

    def import_from_clipboard(e):
        async def do_import():
            try:
                clip = await state.page.get_clipboard_async()
                if not clip:
                    show_snackbar(state.page, L['mcp_clipboard_empty'])
                    return
                data = json.loads(clip)
                items = parse_mcp_json(data)
                if items:
                    state.mcp_list.extend(items)
                    state.save_mcp()
                    refresh_mcp_tree()
                    show_snackbar(state.page, L['mcp_added'].format(len(items)))
                else:
                    show_snackbar(state.page, L['mcp_no_valid_config'])
            except json.JSONDecodeError:
                show_snackbar(state.page, L['mcp_invalid_json'])
            except Exception as ex:
                show_snackbar(state.page, L['mcp_import_fail'].format(ex))
            state.page.update()
        state.page.run_task(do_import)

    def import_from_file(e):
        def on_result(ev):
            if not ev.files:
                return
            try:
                with open(ev.files[0].path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = parse_mcp_json(data)
                if items:
                    state.mcp_list.extend(items)
                    state.save_mcp()
                    refresh_mcp_tree()
                    show_snackbar(state.page, L['mcp_added'].format(len(items)))
                else:
                    show_snackbar(state.page, L['mcp_no_valid_config'])
            except Exception as ex:
                show_snackbar(state.page, L['mcp_import_fail'].format(ex))
            state.page.update()
        picker = ft.FilePicker(on_result=on_result)
        state.page.overlay.append(picker)
        state.page.update()
        picker.pick_files(allowed_extensions=['json'], dialog_title=L['mcp_import_file'])

    def import_from_text(e):
        text_field = ft.TextField(label=L['mcp_import_text_desc'], multiline=True, min_lines=10, max_lines=15, expand=True)

        def do_import(ev):
            try:
                data = json.loads(text_field.value or '{}')
                items = parse_mcp_json(data)
                if items:
                    state.mcp_list.extend(items)
                    state.save_mcp()
                    refresh_mcp_tree()
                    dlg.open = False
                    show_snackbar(state.page, L['mcp_added'].format(len(items)))
                else:
                    show_snackbar(state.page, L['mcp_no_valid_config'])
            except json.JSONDecodeError:
                show_snackbar(state.page, L['mcp_invalid_json'])
            except Exception as ex:
                show_snackbar(state.page, L['mcp_import_fail'].format(ex))
            state.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_import_text']),
            content=ft.Container(ft.Column([ft.Text(L['mcp_import_format'], size=12, color=ft.Colors.GREY_600), text_field], tight=True), width=500, height=350),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or state.page.update()),
                ft.ElevatedButton(L['import'], on_click=do_import),
            ],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    def show_import_menu(e):
        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_import_title']),
            content=ft.Column([
                ft.ListTile(leading=ft.Icon(ft.Icons.CONTENT_PASTE, color=ft.Colors.BLUE), title=ft.Text(L['mcp_import_clipboard']),
                           subtitle=ft.Text(L['mcp_import_clipboard_desc']),
                           on_click=lambda e: (setattr(dlg, 'open', False), state.page.update(), import_from_clipboard(e))),
                ft.ListTile(leading=ft.Icon(ft.Icons.FILE_OPEN, color=ft.Colors.GREEN), title=ft.Text(L['mcp_import_file']),
                           subtitle=ft.Text(L['mcp_import_file_desc']),
                           on_click=lambda e: (setattr(dlg, 'open', False), state.page.update(), import_from_file(e))),
                ft.ListTile(leading=ft.Icon(ft.Icons.TEXT_FIELDS, color=ft.Colors.ORANGE), title=ft.Text(L['mcp_import_text']),
                           subtitle=ft.Text(L['mcp_import_text_desc']),
                           on_click=lambda e: (setattr(dlg, 'open', False), state.page.update(), import_from_text(e))),
            ], tight=True, spacing=0),
            actions=[ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or state.page.update())],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    def show_mcp_repository(e):
        stats = mcp_registry.get_stats()
        if stats['total'] == 0:
            sync_mcp_repository(e)
            return
        show_repository_browser(stats)

    def sync_mcp_repository(e):
        status_text = ft.Text(L['mcp_sync_preparing'])
        progress = ft.ProgressBar(width=400)
        loading_dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_sync_title']),
            content=ft.Column([progress, status_text, ft.Text(L['mcp_sync_sources'], size=12, color=ft.Colors.GREY_600)],
                             tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            modal=True,
        )
        state.page.overlay.append(loading_dlg)
        loading_dlg.open = True
        state.page.update()

        def do_sync():
            mcp_fetch_log.clear()
            def on_progress(msg):
                mcp_fetch_log.append(msg)
                status_text.value = msg
                state.page.update()
            new_count, errors = mcp_registry.fetch_all(callback=on_progress)
            loading_dlg.open = False
            state.page.update()
            stats = mcp_registry.get_stats()
            if errors:
                mcp_fetch_log.extend(errors)
            if stats['total'] > 0:
                show_snackbar(state.page, L['mcp_sync_complete'].format(stats['total'], new_count))
                show_repository_browser(stats)
            else:
                show_sync_debug()

        threading.Thread(target=do_sync, daemon=True).start()

    def show_sync_debug():
        log_text = "\n".join(mcp_fetch_log)
        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_sync_fail'], color=ft.Colors.RED),
            content=ft.Container(ft.TextField(value=log_text, multiline=True, read_only=True, min_lines=15, max_lines=20, expand=True), width=600, height=400),
            actions=[ft.TextButton(L['close'], on_click=lambda _: setattr(dlg, 'open', False) or state.page.update())],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    def show_repository_browser(stats: dict):
        cat_keys = ['cloud', 'map', 'media', 'security', 'tool', 'dev', 'search', 'db', 'file', 'news', 'calendar', 'model',
                    'browser', 'game', 'ecommerce', 'knowledge', 'social', 'note', 'network', 'design', 'comm', 'finance', 'project', 'other']
        cat_zh = ['云服务', '地图', '媒体', '安全', '工具', '开发', '搜索', '数据库', '文件', '新闻', '日历', '模型',
                  '浏览器', '游戏', '电商', '知识库', '社交', '笔记', '网络', '设计', '通讯', '金融', '项目', '其他']
        cat_display = [L[f'mcp_cat_{k}'] for k in cat_keys]
        zh_to_display = dict(zip(cat_zh, cat_display))
        display_to_zh = dict(zip(cat_display, cat_zh))

        search_field = ft.TextField(label=L['mcp_search'], prefix_icon=ft.Icons.SEARCH, expand=True)
        category_dropdown = ft.Dropdown(label=L['mcp_category'], value=L['mcp_all'],
                                        options=[ft.dropdown.Option(L['mcp_all'])] + [ft.dropdown.Option(c) for c in cat_display], width=120)
        result_list = ft.ListView(expand=True, spacing=2)
        selected_items = set()
        selected_count_text = ft.Text(L['mcp_selected'].format(0), color=ft.Colors.GREY_600)

        def filter_list(e=None):
            result_list.controls.clear()
            keyword = search_field.value or ''
            cat_val = category_dropdown.value or L['mcp_all']
            cat_filter = display_to_zh.get(cat_val, '全部') if cat_val != L['mcp_all'] else '全部'
            servers = mcp_registry.search(keyword, cat_filter, limit=200)
            for item in servers:
                name = item.get('name', '')
                desc = item.get('description', '') or ''
                cat = item.get('category', '其他')
                cat_disp = zh_to_display.get(cat, cat)
                source = item.get('source', '')
                is_selected = name in selected_items
                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_selected, on_change=lambda e, n=name: toggle_select(n, e.control.value)),
                        ft.Column([
                            ft.Row([
                                ft.Text(name, weight=ft.FontWeight.BOLD if is_selected else None, expand=True),
                                ft.Container(ft.Text(cat_disp, size=10, color=ft.Colors.WHITE), bgcolor=ft.Colors.BLUE_400, padding=ft.padding.symmetric(2, 6), border_radius=8),
                                ft.Text(source, size=9, color=ft.Colors.GREY_400),
                            ], spacing=5),
                            ft.Text(desc[:100] + ('...' if len(desc) > 100 else ''), size=11, color=ft.Colors.GREY_600),
                        ], spacing=2, expand=True),
                    ], spacing=10),
                    padding=8, bgcolor=ft.Colors.BLUE_50 if is_selected else None, border_radius=4,
                )
                result_list.controls.append(tile)
            if len(servers) >= 200:
                result_list.controls.append(ft.Text(L['mcp_more_hint'], color=ft.Colors.GREY_500, italic=True))
            state.page.update()

        def toggle_select(name, checked):
            if checked:
                selected_items.add(name)
            else:
                selected_items.discard(name)
            selected_count_text.value = L['mcp_selected'].format(len(selected_items))
            filter_list()

        def add_selected(e):
            added = 0
            for name in selected_items:
                items = mcp_registry.search(name, limit=1)
                if items:
                    item = items[0]
                    pkg = item.get('package', item['name'])
                    state.mcp_list.append({
                        'name': item['name'], 'category': item.get('category', '其他'),
                        'command': item.get('command', 'npx'), 'args': item.get('args') or f"-y {pkg}",
                        'env': '', 'is_default': False,
                    })
                    added += 1
            if added:
                state.save_mcp()
                refresh_mcp_tree()
                dlg.open = False
                show_snackbar(state.page, L['mcp_added'].format(added))
            state.page.update()

        search_field.on_change = filter_list
        category_dropdown.on_change = filter_list
        filter_list()
        updated = stats.get('updated_at', '')[:16].replace('T', ' ') if stats.get('updated_at') else L['mcp_not_synced']

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Text(L['mcp_repo_title'].format(stats['total']), weight=ft.FontWeight.BOLD),
                ft.Text(L['mcp_updated'].format(updated), size=11, color=ft.Colors.GREY_500),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: (setattr(dlg, 'open', False), state.page.update(), sync_mcp_repository(e)), tooltip=L['mcp_resync']),
            ], spacing=10),
            content=ft.Container(ft.Column([ft.Row([search_field, category_dropdown], spacing=10), ft.Container(result_list, expand=True)], spacing=10), width=650, height=500),
            actions=[selected_count_text, ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or state.page.update()), ft.ElevatedButton(L['mcp_add_selected'], on_click=add_selected)],
        )
        state.page.overlay.append(dlg)
        dlg.open = True
        state.page.update()

    # 启动时检查自动更新
    def check_auto_update():
        if mcp_registry.needs_update(days=7):
            threading.Thread(target=lambda: mcp_registry.fetch_all(), daemon=True).start()
    check_auto_update()

    mcp_page = ft.Column([
        ft.Row([
            ft.Text(L['mcp'], size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.ADD, on_click=add_mcp, tooltip=L['add']),
            ft.IconButton(ft.Icons.DOWNLOAD, on_click=show_import_menu, tooltip=L['mcp_import']),
            ft.IconButton(ft.Icons.INVENTORY_2, on_click=show_mcp_repository, tooltip=L['mcp_browse']),
            ft.IconButton(ft.Icons.CLOUD_DOWNLOAD, on_click=add_from_official, tooltip=L['mcp_official']),
            ft.IconButton(ft.Icons.STORE, on_click=browse_mcp_market, tooltip=L['mcp_market']),
            ft.IconButton(ft.Icons.EDIT, on_click=edit_mcp, tooltip=L['edit']),
            ft.IconButton(ft.Icons.DELETE, on_click=delete_mcp, tooltip=L['delete']),
        ]),
        ft.Text(L['mcp_default_hint'], size=12, color=ft.Colors.GREY_600),
        ft.Container(mcp_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
    ], expand=True, spacing=10)

    return mcp_page, refresh_mcp_tree
