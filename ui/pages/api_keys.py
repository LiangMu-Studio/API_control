# AI CLI Manager - API Keys Page
import flet as ft
import json
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from ..common import (
    THEMES, CLI_TOOLS, save_configs, save_settings,
    detect_terminals, detect_python_envs, write_prompt_to_cli, detect_prompt_from_file
)


def create_api_page(state):
    """创建 API 密钥页面"""
    page = state.page
    L = state.L
    theme = state.get_theme()

    # UI 组件
    config_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    current_key_label = ft.Text(L['not_selected'], color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD)
    state.config_tree = config_tree
    state.current_key_label = current_key_label

    # 终端和环境下拉
    terminal_dropdown = ft.Dropdown(
        label=L['select_terminal'],
        value=list(state.terminals.keys())[0] if state.terminals else '',
        options=[ft.dropdown.Option(k) for k in state.terminals.keys()],
        width=180,
    )
    python_env_dropdown = ft.Dropdown(
        label=L['python_env'],
        value=list(state.python_envs.keys())[0] if state.python_envs else '',
        options=[ft.dropdown.Option(k) for k in state.python_envs.keys()],
        width=220,
    )
    work_dir_field = ft.TextField(label=L['work_dir'], value=state.settings.get('work_dir', ''), expand=True)

    # 提示词下拉
    def build_prompt_options():
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
        return options

    prompt_dropdown = ft.Dropdown(label=L['prompts'], options=build_prompt_options(), width=220)

    # 工作目录 MCP 状态
    workdir_mcp_enabled = {}

    def refresh_config_list():
        config_tree.controls.clear()
        tree = state.build_tree_structure()
        theme = state.get_theme()

        for cli_type in tree.keys():
            cli_name = CLI_TOOLS.get(cli_type, {}).get('name', cli_type)
            cli_key = cli_type
            is_cli_expanded = state.expanded_cli.get(cli_key, True)
            is_cli_selected = state.selected_cli == cli_key and state.selected_endpoint is None and state.selected_config is None

            cli_header = ft.GestureDetector(
                content=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_cli_expanded else ft.Icons.ARROW_RIGHT, size=20, color=theme['text']),
                        ft.Icon(ft.Icons.TERMINAL, color=theme['icon_cli']),
                        ft.Text(cli_name, weight=ft.FontWeight.BOLD, color=theme['text_selected'] if is_cli_selected else theme['text']),
                        ft.Text(f"({sum(len(v) for v in tree[cli_type].values())})", color=theme['text_sec']),
                    ], spacing=5),
                    padding=ft.padding.only(left=5, top=8, bottom=8),
                    bgcolor=theme['selection_bg'] if is_cli_selected else theme['header_bg'],
                    border_radius=4,
                ),
                on_tap=lambda e, k=cli_key: (state.select_cli(k), refresh_config_list(), page.update()),
                on_double_tap=lambda e, k=cli_key: (state.toggle_cli(k), refresh_config_list(), page.update()),
            )
            config_tree.controls.append(cli_header)

            if is_cli_expanded:
                for endpoint in tree[cli_type].keys():
                    endpoint_key = f"{cli_type}:{endpoint}"
                    is_endpoint_expanded = state.expanded_endpoint.get(endpoint_key, True)
                    short_endpoint = endpoint[:40] + "..." if len(endpoint) > 40 else endpoint
                    is_ep_selected = state.selected_endpoint == endpoint_key and state.selected_config is None

                    endpoint_header = ft.GestureDetector(
                        content=ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_endpoint_expanded else ft.Icons.ARROW_RIGHT, size=18, color=theme['text']),
                                ft.Icon(ft.Icons.LINK, size=16, color=theme['icon_endpoint']),
                                ft.Text(short_endpoint, size=13, color=theme['text_selected'] if is_ep_selected else theme['text']),
                                ft.Text(f"({len(tree[cli_type][endpoint])})", color=theme['text_sec'], size=12),
                            ], spacing=5),
                            padding=ft.padding.only(left=30, top=6, bottom=6),
                            bgcolor=theme['selection_bg'] if is_ep_selected else None,
                            border_radius=4,
                        ),
                        on_tap=lambda e, k=endpoint_key: (state.select_endpoint(k), refresh_config_list(), page.update()),
                        on_double_tap=lambda e, k=endpoint_key: (state.toggle_endpoint(k), refresh_config_list(), page.update()),
                    )
                    config_tree.controls.append(endpoint_header)

                    if is_endpoint_expanded:
                        for idx, cfg in tree[cli_type][endpoint]:
                            is_selected = state.selected_config == idx
                            config_item = ft.GestureDetector(
                                content=ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.KEY, size=16, color=theme['icon_key_selected'] if is_selected else ft.Colors.GREY_600),
                                        ft.Text(cfg.get('label', 'Unnamed'), weight=ft.FontWeight.BOLD if is_selected else None,
                                               color=theme['text_selected'] if is_selected else theme['text']),
                                    ], spacing=5),
                                    padding=ft.padding.only(left=60, top=5, bottom=5),
                                    bgcolor=theme['selection_bg'] if is_selected else None,
                                    border_radius=4,
                                ),
                                on_tap=lambda e, i=idx: (state.select_config(i), refresh_config_list(), page.update()),
                                on_double_tap=lambda e, i=idx: (state.select_config(i), show_config_dialog(i)),
                            )
                            config_tree.controls.append(config_item)
        page.update()

    def show_config_dialog(idx):
        is_edit = idx is not None
        cfg = state.configs[idx] if is_edit else {}

        name_field = ft.TextField(label=L['name'], value=cfg.get('label', ''), expand=True)
        cli_dropdown = ft.Dropdown(
            label=L['cli_type'], value=cfg.get('cli_type', 'claude'),
            options=[ft.dropdown.Option(k, v['name']) for k, v in CLI_TOOLS.items()], expand=True,
        )
        endpoint_field = ft.TextField(
            label=L['api_addr'], value=cfg.get('provider', {}).get('endpoint', CLI_TOOLS['claude']['default_endpoint']), expand=True,
        )
        key_name_field = ft.TextField(
            label=L['key_name'], value=cfg.get('provider', {}).get('key_name', CLI_TOOLS['claude']['default_key_name']), expand=True,
        )
        api_key_field = ft.TextField(
            label=L['api_key'], value=cfg.get('provider', {}).get('credentials', {}).get('api_key', ''),
            password=True, can_reveal_password=True, expand=True,
        )

        def on_cli_change(e):
            cli = cli_dropdown.value
            if cli in CLI_TOOLS:
                endpoint_field.value = CLI_TOOLS[cli]['default_endpoint']
                key_name_field.value = CLI_TOOLS[cli]['default_key_name']
                page.update()
        cli_dropdown.on_change = on_cli_change

        def save_config(e):
            if not name_field.value or not api_key_field.value:
                page.open(ft.SnackBar(ft.Text(L['fill_required'])))
                page.update()
                return
            new_cfg = {
                'id': cfg.get('id', f"{name_field.value}-{int(datetime.now().timestamp())}"),
                'label': name_field.value, 'cli_type': cli_dropdown.value,
                'provider': {'endpoint': endpoint_field.value, 'key_name': key_name_field.value,
                            'credentials': {'api_key': api_key_field.value}},
                'createdAt': cfg.get('createdAt', datetime.now().isoformat()),
                'updatedAt': datetime.now().isoformat(),
            }
            if is_edit:
                state.configs[idx] = new_cfg
            else:
                state.configs.append(new_cfg)
            state.save_configs()
            refresh_config_list()
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(L['saved'])))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([name_field, cli_dropdown, endpoint_field, key_name_field, api_key_field], tight=True, spacing=10, width=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.TextButton(L['save'], on_click=save_config),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def add_config(e): show_config_dialog(None)

    def edit_config(e):
        if state.selected_config is not None:
            show_config_dialog(state.selected_config)
        else:
            page.open(ft.SnackBar(ft.Text(L['no_selection'])))
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
                    page.open(ft.SnackBar(ft.Text(L['deleted'])))
                dlg.open = False
                page.update()
            dlg = ft.AlertDialog(
                title=ft.Text(L['confirm_delete']),
                content=ft.Text(L['confirm_delete_msg'].format(cfg.get('label', ''))),
                actions=[ft.TextButton(L['cancel'], on_click=confirm_delete), ft.TextButton(L['delete'], on_click=confirm_delete)],
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

    def copy_config_key(e):
        if state.selected_config is not None:
            key = state.configs[state.selected_config].get('provider', {}).get('credentials', {}).get('api_key', '')
            page.set_clipboard(key)
            page.open(ft.SnackBar(ft.Text(L['copied'])))
            page.update()

    def move_up(e):
        if state.selected_config is not None:
            cli, ep = state.selected_endpoint.split(':', 1) if state.selected_endpoint else (None, None)
            same_ep = [i for i, c in enumerate(state.configs) if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep]
            pos = same_ep.index(state.selected_config) if state.selected_config in same_ep else -1
            if pos > 0:
                prev_idx = same_ep[pos - 1]
                state.configs[state.selected_config], state.configs[prev_idx] = state.configs[prev_idx], state.configs[state.selected_config]
                state.selected_config = prev_idx
                state.save_configs()
                refresh_config_list()
        elif state.selected_endpoint:
            cli, ep = state.selected_endpoint.split(':', 1)
            eps = list(dict.fromkeys(c.get('provider', {}).get('endpoint') for c in state.configs if c.get('cli_type') == cli))
            pos = eps.index(ep) if ep in eps else -1
            if pos > 0:
                prev_ep = eps[pos - 1]
                ep_items = [c for c in state.configs if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep]
                other_items = [c for c in state.configs if not (c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep)]
                insert_pos = next((i for i, c in enumerate(other_items) if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == prev_ep), 0)
                state.configs[:] = other_items[:insert_pos] + ep_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()
        elif state.selected_cli:
            clis = list(dict.fromkeys(c.get('cli_type') for c in state.configs))
            pos = clis.index(state.selected_cli) if state.selected_cli in clis else -1
            if pos > 0:
                prev_cli = clis[pos - 1]
                cli_items = [c for c in state.configs if c.get('cli_type') == state.selected_cli]
                other_items = [c for c in state.configs if c.get('cli_type') != state.selected_cli]
                insert_pos = next((i for i, c in enumerate(other_items) if c.get('cli_type') == prev_cli), 0)
                state.configs[:] = other_items[:insert_pos] + cli_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()

    def move_down(e):
        if state.selected_config is not None:
            cli, ep = state.selected_endpoint.split(':', 1) if state.selected_endpoint else (None, None)
            same_ep = [i for i, c in enumerate(state.configs) if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep]
            pos = same_ep.index(state.selected_config) if state.selected_config in same_ep else -1
            if pos >= 0 and pos < len(same_ep) - 1:
                next_idx = same_ep[pos + 1]
                state.configs[state.selected_config], state.configs[next_idx] = state.configs[next_idx], state.configs[state.selected_config]
                state.selected_config = next_idx
                state.save_configs()
                refresh_config_list()
        elif state.selected_endpoint:
            cli, ep = state.selected_endpoint.split(':', 1)
            eps = list(dict.fromkeys(c.get('provider', {}).get('endpoint') for c in state.configs if c.get('cli_type') == cli))
            pos = eps.index(ep) if ep in eps else -1
            if pos >= 0 and pos < len(eps) - 1:
                next_ep = eps[pos + 1]
                ep_items = [c for c in state.configs if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep]
                other_items = [c for c in state.configs if not (c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep)]
                last_next = -1
                for i, c in enumerate(other_items):
                    if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == next_ep:
                        last_next = i
                insert_pos = last_next + 1 if last_next >= 0 else len(other_items)
                state.configs[:] = other_items[:insert_pos] + ep_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()
        elif state.selected_cli:
            clis = list(dict.fromkeys(c.get('cli_type') for c in state.configs))
            pos = clis.index(state.selected_cli) if state.selected_cli in clis else -1
            if pos >= 0 and pos < len(clis) - 1:
                next_cli = clis[pos + 1]
                cli_items = [c for c in state.configs if c.get('cli_type') == state.selected_cli]
                other_items = [c for c in state.configs if c.get('cli_type') != state.selected_cli]
                insert_pos = len([c for c in other_items if clis.index(c.get('cli_type')) <= clis.index(next_cli)])
                state.configs[:] = other_items[:insert_pos] + cli_items + other_items[insert_pos:]
                state.save_configs()
                refresh_config_list()

    def export_configs(e):
        def on_result(result):
            if result.path:
                with open(result.path, 'w', encoding='utf-8') as f:
                    json.dump({'configs': state.configs}, f, ensure_ascii=False, indent=2)
                page.open(ft.SnackBar(ft.Text(L['exported_to'].format(result.path))))
                page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.save_file(file_name='api_configs.json', allowed_extensions=['json'])

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
                    page.open(ft.SnackBar(ft.Text(L['imported_count'].format(len(imported)))))
                except Exception as ex:
                    page.open(ft.SnackBar(ft.Text(str(ex))))
                page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.pick_files(allowed_extensions=['json'])

    def browse_folder(e):
        def on_result(result):
            if result.path:
                work_dir_field.value = result.path
                state.settings['work_dir'] = result.path
                save_settings(state.settings)
                page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.get_directory_path()

    def refresh_terminals_click(e):
        state.terminals = detect_terminals()
        state.settings['terminals_cache'] = state.terminals
        save_settings(state.settings)
        terminal_dropdown.options = [ft.dropdown.Option(k) for k in state.terminals.keys()]
        if state.terminals:
            terminal_dropdown.value = list(state.terminals.keys())[0]
        page.open(ft.SnackBar(ft.Text(L['terminals_refreshed'])))
        page.update()

    def refresh_envs_click(e):
        state.python_envs = detect_python_envs()
        state.settings['envs_cache'] = state.python_envs
        save_settings(state.settings)
        python_env_dropdown.options = [ft.dropdown.Option(k) for k in state.python_envs.keys()]
        if state.python_envs:
            python_env_dropdown.value = list(state.python_envs.keys())[0]
        page.open(ft.SnackBar(ft.Text(L['envs_refreshed'].format(len(state.python_envs)))))
        page.update()

    def open_terminal(e):
        if state.selected_config is None:
            page.open(ft.SnackBar(ft.Text(L['no_selection'])))
            page.update()
            return
        cfg = state.configs[state.selected_config]
        cli_type = cfg.get('cli_type', 'claude')
        cli_info = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
        api_key = cfg.get('provider', {}).get('credentials', {}).get('api_key', '')
        key_name = cfg.get('provider', {}).get('key_name', cli_info['default_key_name'])
        endpoint = cfg.get('provider', {}).get('endpoint', '')
        env = os.environ.copy()
        env[key_name] = api_key
        if endpoint:
            env[cli_info['base_url_env']] = endpoint
        terminal_cmd = state.terminals.get(terminal_dropdown.value, 'cmd')
        cwd = work_dir_field.value or None
        if sys.platform == 'win32':
            subprocess.Popen(['cmd', '/k'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([terminal_cmd], env=env, cwd=cwd)

    def apply_selected_prompt(e):
        if not prompt_dropdown.value:
            page.open(ft.SnackBar(ft.Text(L['no_selection'])))
            page.update()
            return
        if not work_dir_field.value:
            page.open(ft.SnackBar(ft.Text(L['prompt_select_workdir'])))
            page.update()
            return
        cli_type = 'claude'
        if state.selected_config is not None:
            cli_type = state.configs[state.selected_config].get('cli_type', 'claude')
        system_prompt = state.prompt_db.get_system_prompt()
        system_content = system_prompt.get('content', '') if system_prompt else ''
        user_prompt = state.prompts.get(prompt_dropdown.value, {})
        user_content = user_prompt.get('content', '')
        user_id = prompt_dropdown.value
        try:
            file_path = write_prompt_to_cli(cli_type, system_content, user_content, user_id, work_dir_field.value)
            page.open(ft.SnackBar(ft.Text(L['prompt_written'].format(file_path))))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(L['prompt_write_fail'].format(ex))))
        page.update()

    # 初始化列表
    refresh_config_list()

    # 构建页面
    api_page = ft.Column([
        ft.Row([
            ft.Container(config_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
            ft.Column([
                ft.OutlinedButton(L['add'], icon=ft.Icons.ADD, on_click=add_config, width=120),
                ft.OutlinedButton(L['edit'], icon=ft.Icons.EDIT, on_click=edit_config, width=120),
                ft.OutlinedButton(L['delete'], icon=ft.Icons.DELETE, on_click=delete_config, width=120),
                ft.OutlinedButton(L['copy_key'], icon=ft.Icons.COPY, on_click=copy_config_key, width=120),
                ft.OutlinedButton(L['move_up'], icon=ft.Icons.ARROW_UPWARD, on_click=move_up, width=120),
                ft.OutlinedButton(L['move_down'], icon=ft.Icons.ARROW_DOWNWARD, on_click=move_down, width=120),
                ft.OutlinedButton(L['export'], icon=ft.Icons.UPLOAD, on_click=export_configs, width=120),
                ft.OutlinedButton(L['import'], icon=ft.Icons.DOWNLOAD, on_click=import_configs, width=120),
            ], spacing=5, alignment=ft.MainAxisAlignment.START),
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
        ft.Divider(),
        ft.Text(L['terminal'], size=16, weight=ft.FontWeight.BOLD),
        ft.Row([
            terminal_dropdown,
            ft.TextButton(L['refresh_terminals'], icon=ft.Icons.REFRESH, on_click=refresh_terminals_click),
            python_env_dropdown,
            ft.TextButton(L['refresh_envs'], icon=ft.Icons.REFRESH, on_click=refresh_envs_click),
            ft.Text(L['current_key']), current_key_label,
        ], wrap=True, spacing=5),
        ft.Row([work_dir_field, ft.ElevatedButton(L['browse'], icon=ft.Icons.FOLDER_OPEN, on_click=browse_folder),
                ft.ElevatedButton(L['open_terminal'], icon=ft.Icons.TERMINAL, on_click=open_terminal)]),
        ft.Row([prompt_dropdown, ft.ElevatedButton(L['prompt_apply'], icon=ft.Icons.SEND, on_click=apply_selected_prompt)]),
    ], expand=True, spacing=10)

    return api_page, refresh_config_list
