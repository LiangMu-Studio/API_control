# AI CLI Manager - MCP Page
import flet as ft
import json
import threading
import sys
import os
from pathlib import Path
from ..common import THEMES, OFFICIAL_MCP_SERVERS, MCP_MARKETPLACES, show_snackbar
from ..database import mcp_registry, tool_usage_db, mcp_skill_library, generate_mcp_config


MCP_CATEGORIES = ['常用', '文件', '网络', '数据', '其他']


def create_mcp_page(state):
    """创建 MCP 页面"""
    L = state.L
    theme = state.get_theme()
    mcp_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    expanded_mcp_categories = {}
    selected_mcp_name = None  # 改为存储 MCP 名称而非索引
    mcp_fetch_log = []
    # 控件引用缓存，用于增量更新
    _mcp_item_refs = {}  # name -> {'container': Container, 'name_text': Text, 'icon': Icon}

    # 共享 FilePicker
    file_picker = ft.FilePicker()
    state.page.overlay.append(file_picker)

    def get_mcp_list():
        """从数据库获取 MCP 列表"""
        return mcp_skill_library.get_all_mcp()

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
        """同步默认 MCP 到全局配置文件"""
        global_mcp_path = Path.home() / '.claude' / '.mcp.json'
        generate_mcp_config(global_mcp_path)

    def toggle_mcp_default(name, is_default):
        mcp_skill_library.set_mcp_default(name, is_default)
        sync_default_mcp_to_global()
        refresh_mcp_tree()

    def build_mcp_item(m, mcp_usage_by_server, is_global_section):
        """构建单个 MCP 项目控件"""
        name = m.get('name', '')
        is_selected = selected_mcp_name == name
        is_default = m.get('is_default', False)
        call_count = mcp_usage_by_server.get(name.lower(), 0)

        name_text = ft.Text(name,
                           weight=ft.FontWeight.BOLD if is_selected else None,
                           color=ft.Colors.BLUE if is_selected else None)
        icon = ft.Icon(ft.Icons.EXTENSION, size=16,
                      color=ft.Colors.BLUE if is_selected else ft.Colors.GREY_600)

        subtitle_parts = [f"{m.get('command', '')} {m.get('args', '')}"]
        if call_count > 0:
            subtitle_parts.append(f"  [{L.get('calls', '调用')}: {call_count}]")

        # 根据所在区域显示不同的操作按钮
        if is_global_section:
            # 全局区域：显示移除按钮（向下箭头）
            action_btn = ft.IconButton(
                ft.Icons.ARROW_DOWNWARD, icon_size=16,
                tooltip=L.get('remove_from_global', '移出全局'),
                on_click=lambda e, n=name: toggle_mcp_default(n, False)
            )
        else:
            # 库区域：显示添加按钮（向上箭头）
            action_btn = ft.IconButton(
                ft.Icons.ARROW_UPWARD, icon_size=16,
                tooltip=L.get('add_to_global', '添加到全局'),
                on_click=lambda e, n=name: toggle_mcp_default(n, True)
            )

        item = ft.Container(
            content=ft.Row([
                icon,
                ft.Column([
                    name_text,
                    ft.Text(''.join(subtitle_parts), size=10, color=ft.Colors.GREY_500),
                ], spacing=0, expand=True),
                action_btn,
                ft.IconButton(ft.Icons.LABEL, on_click=lambda e, n=name: edit_mcp_category(n),
                             tooltip=L.get('edit_category', '编辑分类'), icon_size=16),
            ], spacing=5),
            padding=ft.padding.only(left=10, top=5, bottom=5),
            on_click=lambda e, n=name: select_mcp(n),
            bgcolor=ft.Colors.BLUE_50 if is_selected else None, border_radius=4,
        )
        _mcp_item_refs[name] = {'container': item, 'name_text': name_text, 'icon': icon}
        return item

    def refresh_mcp_tree():
        nonlocal selected_mcp_name
        mcp_tree.controls.clear()
        _mcp_item_refs.clear()
        theme = state.get_theme()
        mcp_list = get_mcp_list()

        # 分离全局和普通 MCP
        global_mcps = [m for m in mcp_list if m.get('is_default', False)]
        library_mcps = [m for m in mcp_list if not m.get('is_default', False)]

        # 获取 MCP 使用统计
        mcp_usage_raw = tool_usage_db.get_all_mcp()
        mcp_usage_by_server = {}
        for stat in mcp_usage_raw:
            tool_name = stat['tool_name'].lower()
            parts = tool_name.split('__')
            if len(parts) >= 2:
                server = parts[1]
                mcp_usage_by_server[server] = mcp_usage_by_server.get(server, 0) + stat['total_calls']

        # === 全局 MCP 区域 ===
        global_header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.GREEN),
                ft.Text(L.get('global_mcp', '全局 MCP'), weight=ft.FontWeight.BOLD),
                ft.Text(f"({len(global_mcps)})", color=ft.Colors.GREY_600),
            ], spacing=5),
            padding=ft.padding.only(left=5, top=8, bottom=8),
            bgcolor=theme['header_bg'], border_radius=4,
        )
        mcp_tree.controls.append(global_header)

        if global_mcps:
            for m in global_mcps:
                item = build_mcp_item(m, mcp_usage_by_server, is_global_section=True)
                mcp_tree.controls.append(item)
        else:
            mcp_tree.controls.append(ft.Container(
                content=ft.Text(L.get('no_global_mcp', '暂无全局 MCP，从下方库中添加'), color=ft.Colors.GREY_500, size=12),
                padding=ft.padding.only(left=20, top=10, bottom=10),
            ))

        # === 分隔线 ===
        mcp_tree.controls.append(ft.Divider(height=20))

        # === MCP 库区域（按分类） ===
        library_header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.INVENTORY_2, color=ft.Colors.AMBER),
                ft.Text(L.get('mcp_library', 'MCP 库'), weight=ft.FontWeight.BOLD),
                ft.Text(f"({len(library_mcps)})", color=ft.Colors.GREY_600),
            ], spacing=5),
            padding=ft.padding.only(left=5, top=8, bottom=8),
            bgcolor=theme['header_bg'], border_radius=4,
        )
        mcp_tree.controls.append(library_header)

        # 按分类组织库中的 MCP
        tree = {}
        for m in library_mcps:
            cat = m.get('category', '其他')
            if cat not in tree:
                tree[cat] = []
            tree[cat].append(m)
        tree = {k: tree[k] for k in MCP_CATEGORIES if k in tree} | {k: v for k, v in tree.items() if k not in MCP_CATEGORIES}

        for cat, items in tree.items():
            is_expanded = expanded_mcp_categories.get(cat, True)
            cat_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER, size=16),
                    ft.Text(cat, size=13),
                    ft.Text(f"({len(items)})", color=ft.Colors.GREY_600, size=12),
                ], spacing=5),
                padding=ft.padding.only(left=15, top=5, bottom=5),
                on_click=lambda e, c=cat: toggle_mcp_category(c),
            )
            mcp_tree.controls.append(cat_header)
            if is_expanded:
                for m in items:
                    item = build_mcp_item(m, mcp_usage_by_server, is_global_section=False)
                    item.padding = ft.padding.only(left=35, top=5, bottom=5)
                    mcp_tree.controls.append(item)

        state.page.update()

    def toggle_mcp_category(cat):
        expanded_mcp_categories[cat] = not expanded_mcp_categories.get(cat, True)
        refresh_mcp_tree()

    def select_mcp(name):
        nonlocal selected_mcp_name
        old_selected = selected_mcp_name
        selected_mcp_name = name
        # 增量更新：只更新旧选中项和新选中项的样式
        if old_selected is not None and old_selected in _mcp_item_refs:
            ref = _mcp_item_refs[old_selected]
            ref['container'].bgcolor = None
            ref['name_text'].weight = None
            ref['name_text'].color = None
            ref['icon'].color = ft.Colors.GREY_600
        if name is not None and name in _mcp_item_refs:
            ref = _mcp_item_refs[name]
            ref['container'].bgcolor = ft.Colors.BLUE_50
            ref['name_text'].weight = ft.FontWeight.BOLD
            ref['name_text'].color = ft.Colors.BLUE
            ref['icon'].color = ft.Colors.BLUE
        state.page.update()

    def edit_mcp_category(name):
        """编辑 MCP 分类"""
        m = mcp_skill_library.get_mcp(name)
        if not m:
            return
        category_dropdown = ft.Dropdown(
            label=L.get('mcp_category', '分类'),
            value=m.get('category', '其他'),
            options=[ft.dropdown.Option(c) for c in MCP_CATEGORIES],
            width=200,
        )

        def save_category(e):
            new_cat = category_dropdown.value or '其他'
            mcp_skill_library.update_mcp(name, category=new_cat)
            refresh_mcp_tree()
            state.page.close(dlg)
            show_snackbar(state.page, L.get('category_updated', '分类已更新'))

        dlg = ft.AlertDialog(
            title=ft.Text(f"{L.get('edit_category', '编辑分类')}: {name}"),
            content=category_dropdown,
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg)),
                ft.ElevatedButton(L['save'], on_click=save_category),
            ],
        )
        state.page.open(dlg)

    def add_mcp(e):
        show_mcp_dialog(None)

    def edit_mcp(e):
        if selected_mcp_name is not None:
            show_mcp_dialog(selected_mcp_name)

    def delete_mcp(e):
        nonlocal selected_mcp_name
        if selected_mcp_name is not None:
            mcp_skill_library.delete_mcp(selected_mcp_name)
            selected_mcp_name = None
            sync_default_mcp_to_global()
            refresh_mcp_tree()

    def show_mcp_dialog(name):
        is_edit = name is not None
        m = mcp_skill_library.get_mcp(name) if is_edit else {}
        if is_edit and not m:
            return
        name_field = ft.TextField(label=L['name'], value=m.get('name', ''), expand=True, disabled=is_edit)
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
            new_name = name_field.value
            new_cat = category_field.value or '其他'
            if is_edit:
                mcp_skill_library.update_mcp(name, command=command_field.value, args=args_field.value,
                                            env=env_field.value, category=new_cat)
            else:
                mcp_skill_library.add_mcp(new_name, command=command_field.value, args=args_field.value,
                                         env=env_field.value, category=new_cat, source='manual')
            sync_default_mcp_to_global()
            refresh_mcp_tree()
            state.page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([name_field, category_field, command_field, args_field, env_field], tight=True, spacing=10, width=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg)),
                ft.TextButton(L['save'], on_click=save_mcp_item),
            ],
        )
        state.page.open(dlg)

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
            mcp_skill_library.add_mcp(
                name=server['name'], command='npx',
                args=f"-y {server['package']}" + (f" {args_hint}" if args_hint else ""),
                env=env_hint, source='official'
            )
            sync_default_mcp_to_global()
            refresh_mcp_tree()
            state.page.close(dlg)
            show_snackbar(state.page, L['mcp_added'].format(1))

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_select_official']),
            content=ft.Container(official_list, width=450, height=400),
            actions=[ft.TextButton(L['cancel'], on_click=lambda _: state.page.close(dlg))],
        )
        state.page.open(dlg)

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
            actions=[ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg))],
        )
        state.page.open(dlg)

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
            })
        return results

    def import_mcp_items(items: list) -> int:
        """导入 MCP 项目到数据库"""
        added = 0
        for item in items:
            if mcp_skill_library.add_mcp(
                name=item['name'], command=item.get('command', 'npx'),
                args=item.get('args', ''), env=item.get('env', ''),
                category=item.get('category', '其他'), source='imported'
            ):
                added += 1
        return added

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
                    added = import_mcp_items(items)
                    sync_default_mcp_to_global()
                    refresh_mcp_tree()
                    show_snackbar(state.page, L['mcp_added'].format(added))
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
                    added = import_mcp_items(items)
                    sync_default_mcp_to_global()
                    refresh_mcp_tree()
                    show_snackbar(state.page, L['mcp_added'].format(added))
                else:
                    show_snackbar(state.page, L['mcp_no_valid_config'])
            except Exception as ex:
                show_snackbar(state.page, L['mcp_import_fail'].format(ex))
        file_picker.on_result = on_result
        file_picker.pick_files(allowed_extensions=['json'], dialog_title=L['mcp_import_file'])

    def import_from_text(e):
        text_field = ft.TextField(label=L['mcp_import_text_desc'], multiline=True, min_lines=10, max_lines=15, expand=True)

        def do_import(ev):
            try:
                data = json.loads(text_field.value or '{}')
                items = parse_mcp_json(data)
                if items:
                    added = import_mcp_items(items)
                    sync_default_mcp_to_global()
                    refresh_mcp_tree()
                    state.page.close(dlg)
                    show_snackbar(state.page, L['mcp_added'].format(added))
                else:
                    show_snackbar(state.page, L['mcp_no_valid_config'])
            except json.JSONDecodeError:
                show_snackbar(state.page, L['mcp_invalid_json'])
            except Exception as ex:
                show_snackbar(state.page, L['mcp_import_fail'].format(ex))

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_import_text']),
            content=ft.Container(ft.Column([
                ft.Text(L['mcp_import_format'], size=12, color=ft.Colors.GREY_600), text_field
            ], tight=True), width=500, height=350),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda _: state.page.close(dlg)),
                ft.ElevatedButton(L['import'], on_click=do_import),
            ],
        )
        state.page.open(dlg)

    def show_import_menu(e):
        def close_and_run(func):
            state.page.close(dlg)
            func(e)

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_import_title']),
            content=ft.Column([
                ft.ListTile(leading=ft.Icon(ft.Icons.COMPUTER, color=ft.Colors.TEAL),
                           title=ft.Text(L['mcp_import_installed']),
                           subtitle=ft.Text(L['mcp_import_installed_desc']),
                           on_click=lambda _: close_and_run(import_from_installed)),
                ft.ListTile(leading=ft.Icon(ft.Icons.CONTENT_PASTE, color=ft.Colors.BLUE),
                           title=ft.Text(L['mcp_import_clipboard']),
                           subtitle=ft.Text(L['mcp_import_clipboard_desc']),
                           on_click=lambda _: close_and_run(import_from_clipboard)),
                ft.ListTile(leading=ft.Icon(ft.Icons.FILE_OPEN, color=ft.Colors.GREEN),
                           title=ft.Text(L['mcp_import_file']),
                           subtitle=ft.Text(L['mcp_import_file_desc']),
                           on_click=lambda _: close_and_run(import_from_file)),
                ft.ListTile(leading=ft.Icon(ft.Icons.TEXT_FIELDS, color=ft.Colors.ORANGE),
                           title=ft.Text(L['mcp_import_text']),
                           subtitle=ft.Text(L['mcp_import_text_desc']),
                           on_click=lambda _: close_and_run(import_from_text)),
            ], tight=True, spacing=0),
            actions=[ft.TextButton(L['cancel'], on_click=lambda _: state.page.close(dlg))],
        )
        state.page.open(dlg)

    def scan_installed_mcp():
        """扫描已安装的 MCP 配置"""
        results = []
        home = Path.home()

        # MCP 配置文件位置
        mcp_sources = [
            ('claude', home / '.claude' / 'settings.json'),
            ('claude', home / '.claude.json'),
            ('codex', home / '.codex' / 'config.json'),
            ('codex', home / '.codex.json'),
            ('gemini', home / '.gemini' / 'settings.json'),
        ]

        # VSCode Claude Code 插件
        if sys.platform == 'win32':
            vscode_path = Path(os.environ.get('APPDATA', '')) / 'Code' / 'User' / 'globalStorage' / 'anthropic.claude-code' / 'settings.json'
        elif sys.platform == 'darwin':
            vscode_path = home / 'Library' / 'Application Support' / 'Code' / 'User' / 'globalStorage' / 'anthropic.claude-code' / 'settings.json'
        else:
            vscode_path = home / '.config' / 'Code' / 'User' / 'globalStorage' / 'anthropic.claude-code' / 'settings.json'
        mcp_sources.append(('vscode', vscode_path))

        for source, path in mcp_sources:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                servers = data.get('mcpServers', {})
                for name, cfg in servers.items():
                    if not isinstance(cfg, dict):
                        continue
                    args = cfg.get('args', [])
                    env = cfg.get('env', {})
                    results.append({
                        'name': name,
                        'source': source,
                        'command': cfg.get('command', 'npx'),
                        'args': ' '.join(args) if isinstance(args, list) else str(args),
                        'env': ' '.join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else '',
                    })
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def import_from_installed(e):
        """从已安装的 CLI 工具导入 MCP"""
        installed = scan_installed_mcp()
        if not installed:
            show_snackbar(state.page, L['mcp_no_installed'])
            return

        source_names = {
            'claude': L['mcp_source_claude'],
            'codex': L['mcp_source_codex'],
            'gemini': L['mcp_source_gemini'],
            'vscode': L['mcp_source_vscode'],
        }

        selected_items = set()
        result_list = ft.ListView(expand=True, spacing=2)
        selected_count = ft.Text(L['mcp_selected'].format(0), color=ft.Colors.GREY_600)

        def build_list():
            result_list.controls.clear()
            for i, item in enumerate(installed):
                is_selected = i in selected_items
                source_label = source_names.get(item['source'], item['source'])
                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_selected, on_change=lambda e, idx=i: toggle_item(idx, e.control.value)),
                        ft.Column([
                            ft.Row([
                                ft.Text(item['name'], weight=ft.FontWeight.BOLD if is_selected else None),
                                ft.Container(ft.Text(source_label, size=10, color=ft.Colors.WHITE),
                                           bgcolor=ft.Colors.TEAL, padding=ft.padding.symmetric(2, 6), border_radius=8),
                            ], spacing=5),
                            ft.Text(f"{item['command']} {item['args']}"[:60], size=11, color=ft.Colors.GREY_600),
                        ], spacing=2, expand=True),
                    ], spacing=10),
                    padding=8, bgcolor=ft.Colors.TEAL_50 if is_selected else None, border_radius=4,
                )
                result_list.controls.append(tile)
            state.page.update()

        def toggle_item(idx, checked):
            if checked:
                selected_items.add(idx)
            else:
                selected_items.discard(idx)
            selected_count.value = L['mcp_selected'].format(len(selected_items))
            build_list()

        def add_selected(ev):
            added = 0
            existing_names = {m.get('name', '').lower() for m in get_mcp_list()}
            for idx in selected_items:
                item = installed[idx]
                if item['name'].lower() in existing_names:
                    continue
                if mcp_skill_library.add_mcp(
                    name=item['name'], command=item['command'],
                    args=item['args'], env=item['env'],
                    category='其他', source='installed'
                ):
                    added += 1
            if added:
                sync_default_mcp_to_global()
                refresh_mcp_tree()
                state.page.close(dlg)
                show_snackbar(state.page, L['mcp_added'].format(added))

        build_list()
        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_found_installed'].format(len(installed))),
            content=ft.Container(result_list, width=500, height=350),
            actions=[
                selected_count,
                ft.TextButton(L['cancel'], on_click=lambda _: state.page.close(dlg)),
                ft.ElevatedButton(L['mcp_add_selected'], on_click=add_selected),
            ],
        )
        state.page.open(dlg)

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
            content=ft.Column([
                progress, status_text,
                ft.Text(L['mcp_sync_sources'], size=12, color=ft.Colors.GREY_600)
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            modal=True,
        )
        state.page.open(loading_dlg)

        def do_sync():
            mcp_fetch_log.clear()
            def on_progress(msg):
                mcp_fetch_log.append(msg)
                status_text.value = msg
                state.page.update()
            new_count, errors = mcp_registry.fetch_all(callback=on_progress)
            state.page.close(loading_dlg)
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
            content=ft.Container(ft.TextField(
                value=log_text, multiline=True, read_only=True, min_lines=15, max_lines=20, expand=True
            ), width=600, height=400),
            actions=[ft.TextButton(L['close'], on_click=lambda _: state.page.close(dlg))],
        )
        state.page.open(dlg)

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
        # 缓存控件引用，用于增量更新
        _item_refs = {}  # name -> {'tile': Container, 'name_text': Text}

        def filter_list(e=None):
            result_list.controls.clear()
            _item_refs.clear()
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
                name_text = ft.Text(name, weight=ft.FontWeight.BOLD if is_selected else None, expand=True)
                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_selected, on_change=lambda e, n=name: toggle_select(n, e.control.value)),
                        ft.Column([
                            ft.Row([
                                name_text,
                                ft.Container(ft.Text(cat_disp, size=10, color=ft.Colors.WHITE), bgcolor=ft.Colors.BLUE_400, padding=ft.padding.symmetric(2, 6), border_radius=8),
                                ft.Text(source, size=9, color=ft.Colors.GREY_400),
                            ], spacing=5),
                            ft.Text(desc[:100] + ('...' if len(desc) > 100 else ''), size=11, color=ft.Colors.GREY_600),
                        ], spacing=2, expand=True),
                    ], spacing=10),
                    padding=8, bgcolor=ft.Colors.BLUE_50 if is_selected else None, border_radius=4,
                )
                _item_refs[name] = {'tile': tile, 'name_text': name_text}
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
            # 只更新该项的样式，不重建列表
            if name in _item_refs:
                ref = _item_refs[name]
                ref['tile'].bgcolor = ft.Colors.BLUE_50 if checked else None
                ref['name_text'].weight = ft.FontWeight.BOLD if checked else None
                state.page.update()

        def add_selected(e):
            added = 0
            for name in selected_items:
                items = mcp_registry.search(name, limit=1)
                if items:
                    item = items[0]
                    pkg = item.get('package', item['name'])
                    if mcp_skill_library.add_mcp(
                        name=item['name'], command=item.get('command', 'npx'),
                        args=item.get('args') or f"-y {pkg}", env='',
                        category=item.get('category', '其他'), source='registry'
                    ):
                        added += 1
            if added:
                sync_default_mcp_to_global()
                refresh_mcp_tree()
                state.page.close(dlg)
                show_snackbar(state.page, L['mcp_added'].format(added))

        def close_and_resync(e):
            state.page.close(dlg)
            sync_mcp_repository(e)

        search_field.on_change = filter_list
        category_dropdown.on_change = filter_list
        filter_list()
        updated = stats.get('updated_at', '')[:16].replace('T', ' ') if stats.get('updated_at') else L['mcp_not_synced']

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Text(L['mcp_repo_title'].format(stats['total']), weight=ft.FontWeight.BOLD),
                ft.Text(L['mcp_updated'].format(updated), size=11, color=ft.Colors.GREY_500),
                ft.IconButton(ft.Icons.REFRESH, on_click=close_and_resync, tooltip=L['mcp_resync']),
            ], spacing=10),
            content=ft.Container(ft.Column([
                ft.Row([search_field, category_dropdown], spacing=10),
                ft.Container(result_list, expand=True)
            ], spacing=10), width=650, height=500),
            actions=[
                selected_count_text,
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg)),
                ft.ElevatedButton(L['mcp_add_selected'], on_click=add_selected)
            ],
        )
        state.page.open(dlg)

    # 启动时检查自动更新
    def check_auto_update():
        if mcp_registry.needs_update(days=7):
            threading.Thread(target=lambda: mcp_registry.fetch_all(), daemon=True).start()
    check_auto_update()

    def check_mcp_status(e):
        """检测 MCP 服务器状态"""
        from core.mcp_checker import check_npm_version, get_all_mcp_status
        show_snackbar(state.page, L.get('mcp_checking', '正在检测...'))
        def run():
            npm_ok, npm_ver = check_npm_version()
            statuses = get_all_mcp_status(get_mcp_list())
            results = [f"npm: {'v' + npm_ver if npm_ok else 'not found'}"]
            for s in statuses:
                icon = '✓' if s['installed'] else '✗'
                ver = f" v{s['version']}" if s['version'] else ''
                results.append(f"{icon} {s['name']}{ver}")
            show_snackbar(state.page, ' | '.join(results[:5]))
        threading.Thread(target=run, daemon=True).start()

    def show_preset_manager(e):
        """显示 MCP 预设管理对话框 - 左右分栏布局"""
        selected_preset = [None]  # 当前选中的预设名称
        preset_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=2, expand=True)
        content_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=2, expand=True)
        content_title = ft.Text(L.get('preset_select_group', '请选择分组'), weight=ft.FontWeight.BOLD)

        def refresh_preset_list():
            preset_list.controls.clear()
            presets = mcp_skill_library.get_all_mcp_presets()
            for p in presets:
                is_default = p.get('is_default', False)
                is_selected = selected_preset[0] == p['name']
                preset_list.controls.append(ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.STAR if is_default else ft.Icons.STAR_BORDER,
                               color=ft.Colors.AMBER if is_default else ft.Colors.GREY, size=18),
                        ft.Text(p['name'], expand=True, weight=ft.FontWeight.BOLD if is_selected else None),
                        ft.Text(f"({len(p.get('mcp_names', []))})", color=ft.Colors.GREY_600, size=12),
                    ], spacing=5),
                    padding=ft.padding.symmetric(5, 8), border_radius=4,
                    bgcolor=ft.Colors.BLUE_100 if is_selected else (ft.Colors.BLUE_50 if is_default else None),
                    on_click=lambda ev, n=p['name']: select_preset(n),
                ))
            state.page.update()

        def refresh_content_list():
            content_list.controls.clear()
            if not selected_preset[0]:
                content_title.value = L.get('preset_select_group', '请选择分组')
                state.page.update()
                return
            preset = next((p for p in mcp_skill_library.get_all_mcp_presets() if p['name'] == selected_preset[0]), None)
            if not preset:
                return
            content_title.value = f"{L.get('preset_content', '分组内容')}: {preset['name']}"
            selected_names = set(preset.get('mcp_names', []))
            all_mcps = mcp_skill_library.get_all_mcp()

            # 按分类分组
            by_category = {}
            for m in all_mcps:
                cat = m.get('category', '其他')
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(m)

            # 遍历所有分类（先按 MCP_CATEGORIES 顺序，再显示其他分类）
            all_cats = list(MCP_CATEGORIES) + [c for c in by_category.keys() if c not in MCP_CATEGORIES]
            for cat in all_cats:
                if cat not in by_category:
                    continue
                items = by_category[cat]
                # 分类标题
                content_list.controls.append(ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER, size=16),
                        ft.Text(cat, weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(f"({len(items)})", color=ft.Colors.GREY_600, size=11),
                    ], spacing=5),
                    padding=ft.padding.only(top=8, bottom=4),
                ))
                # MCP 列表
                for m in items:
                    mcp_name = m['name']
                    cb = ft.Checkbox(
                        value=mcp_name in selected_names, label=mcp_name,
                        on_change=lambda ev, n=mcp_name: toggle_mcp_in_preset(n, ev.control.value)
                    )
                    content_list.controls.append(ft.Container(cb, padding=ft.padding.only(left=20)))
            state.page.update()

        def select_preset(name):
            selected_preset[0] = name
            refresh_preset_list()
            refresh_content_list()

        def toggle_mcp_in_preset(mcp_name, checked):
            if not selected_preset[0]:
                return
            preset = next((p for p in mcp_skill_library.get_all_mcp_presets() if p['name'] == selected_preset[0]), None)
            if not preset:
                return
            names = set(preset.get('mcp_names', []))
            if checked:
                names.add(mcp_name)
            else:
                names.discard(mcp_name)
            mcp_skill_library.add_mcp_preset(selected_preset[0], list(names), preset.get('is_default', False))
            refresh_preset_list()

        def create_preset(ev):
            name = name_field.value.strip()
            if not name:
                return
            mcp_skill_library.add_mcp_preset(name, [])
            name_field.value = ''
            selected_preset[0] = name
            refresh_preset_list()
            refresh_content_list()
            show_snackbar(state.page, L.get('preset_created', '预设已创建'))

        def set_default_preset(ev):
            if not selected_preset[0]:
                return
            preset = next((p for p in mcp_skill_library.get_all_mcp_presets() if p['name'] == selected_preset[0]), None)
            if preset:
                mcp_skill_library.add_mcp_preset(selected_preset[0], preset.get('mcp_names', []), is_default=True)
                refresh_preset_list()
                show_snackbar(state.page, L.get('preset_default_set', '已设为默认预设'))

        def delete_preset(ev):
            if not selected_preset[0]:
                return
            mcp_skill_library.delete_mcp_preset(selected_preset[0])
            selected_preset[0] = None
            refresh_preset_list()
            refresh_content_list()
            show_snackbar(state.page, L.get('preset_deleted', '预设已删除'))

        name_field = ft.TextField(label=L.get('preset_name', '预设名称'), width=140, dense=True)
        refresh_preset_list()

        # 左侧面板：分组列表
        left_panel = ft.Container(
            ft.Column([
                ft.Row([name_field, ft.IconButton(ft.Icons.ADD, on_click=create_preset, tooltip=L['add'])], spacing=5),
                ft.Divider(height=10),
                preset_list,
                ft.Divider(height=10),
                ft.Row([
                    ft.IconButton(ft.Icons.STAR_BORDER, on_click=set_default_preset, tooltip=L.get('set_default', '设为默认')),
                    ft.IconButton(ft.Icons.DELETE, on_click=delete_preset, tooltip=L['delete']),
                ], spacing=5),
            ], spacing=5),
            width=200, padding=10, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8,
        )

        # 右侧面板：分组内容
        right_panel = ft.Container(
            ft.Column([content_title, ft.Divider(height=10), content_list], spacing=5),
            width=280, padding=10, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8,
        )

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('preset_manage', '管理预设')),
            content=ft.Container(ft.Row([left_panel, right_panel], spacing=10), height=400),
            actions=[ft.TextButton(L['close'], on_click=lambda ev: state.page.close(dlg))],
        )
        state.page.open(dlg)

    def add_to_library(e):
        """将当前 MCP 列表添加到库（已废弃，数据库已是唯一数据源）"""
        show_snackbar(state.page, L.get('mcp_already_in_library', '所有 MCP 已在库中'))

    def show_source_menu(e):
        """显示获取来源菜单"""
        def close_menu():
            state.page.close(menu_dlg)

        def on_import(ev):
            close_menu()
            show_import_menu(ev)

        def on_official(ev):
            close_menu()
            add_from_official(ev)

        def on_market(ev):
            close_menu()
            browse_mcp_market(ev)

        def on_browse(ev):
            close_menu()
            show_mcp_repository(ev)

        menu_dlg = ft.AlertDialog(
            title=ft.Text(L.get('mcp_source', '获取来源')),
            content=ft.Column([
                ft.ListTile(leading=ft.Icon(ft.Icons.DOWNLOAD), title=ft.Text(L['mcp_import']), on_click=on_import),
                ft.ListTile(leading=ft.Icon(ft.Icons.CLOUD_DOWNLOAD), title=ft.Text(L['mcp_official']), on_click=on_official),
                ft.ListTile(leading=ft.Icon(ft.Icons.STORE), title=ft.Text(L['mcp_market']), on_click=on_market),
                ft.ListTile(leading=ft.Icon(ft.Icons.INVENTORY_2), title=ft.Text(L['mcp_browse']), on_click=on_browse),
            ], spacing=0, tight=True),
            actions=[ft.TextButton(L['close'], on_click=lambda ev: close_menu())],
        )
        state.page.open(menu_dlg)

    def show_more_menu(e):
        """显示更多操作菜单"""
        def close_menu():
            state.page.close(menu_dlg)

        def on_preset(ev):
            close_menu()
            show_preset_manager(ev)

        def on_check(ev):
            close_menu()
            check_mcp_status(ev)

        def on_sync(ev):
            close_menu()
            add_to_library(ev)

        menu_dlg = ft.AlertDialog(
            title=ft.Text(L.get('more', '更多')),
            content=ft.Column([
                ft.ListTile(leading=ft.Icon(ft.Icons.BOOKMARKS), title=ft.Text(L.get('preset_manage', '管理预设')), on_click=on_preset),
                ft.ListTile(leading=ft.Icon(ft.Icons.HEALTH_AND_SAFETY), title=ft.Text(L.get('mcp_check_status', '检测状态')), on_click=on_check),
                ft.ListTile(leading=ft.Icon(ft.Icons.LIBRARY_ADD), title=ft.Text(L.get('add_to_library', '同步到库')), on_click=on_sync),
            ], spacing=0, tight=True),
            actions=[ft.TextButton(L['close'], on_click=lambda ev: close_menu())],
        )
        state.page.open(menu_dlg)

    mcp_page = ft.Column([
        ft.Row([
            ft.Text(L['mcp'], size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.BOOKMARKS, on_click=show_preset_manager, tooltip=L.get('preset_manage', '管理预设')),
            ft.IconButton(ft.Icons.ADD, on_click=add_mcp, tooltip=L['add']),
            ft.IconButton(ft.Icons.CLOUD_DOWNLOAD, on_click=show_source_menu, tooltip=L.get('mcp_source', '获取来源')),
            ft.IconButton(ft.Icons.HEALTH_AND_SAFETY, on_click=check_mcp_status, tooltip=L.get('mcp_check_status', '检测状态')),
            ft.IconButton(ft.Icons.EDIT, on_click=edit_mcp, tooltip=L['edit']),
            ft.IconButton(ft.Icons.DELETE, on_click=delete_mcp, tooltip=L['delete']),
        ]),
        ft.Text(L['mcp_default_hint'], size=12, color=ft.Colors.GREY_600),
        ft.Container(mcp_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
    ], expand=True, spacing=10)

    return mcp_page, refresh_mcp_tree
