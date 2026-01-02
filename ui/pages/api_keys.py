# AI CLI Manager - API Keys Page
import flet as ft
import json
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import time

from ..common import (
    THEMES, CLI_TOOLS, save_configs, save_settings,
    detect_terminals, detect_python_envs, write_prompt_to_cli, detect_prompt_from_file,
    show_snackbar
)

# 辅助函数：从配置获取 cli_type（兼容新旧格式）
def get_cli_type(cfg):
    """从配置获取 cli_type，用于树形结构分组"""
    return cfg.get('cli_type', 'claude')

# 提供商默认配置 - 完全复刻自 AI_talk
PROVIDER_DEFAULTS = {
    'openai': {
        'endpoint': 'https://api.openai.com/v1',
        'key_name': 'OPENAI_API_KEY',
        'available_models': ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 'gpt-5', 'gpt-5.1-codex-max'],
        'default_model': 'gpt-4o'
    },
    'anthropic': {
        'endpoint': 'https://api.anthropic.com',
        'key_name': 'ANTHROPIC_AUTH_TOKEN',
        'available_models': ['claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101'],
        'default_model': 'claude-haiku-4-5-20251001'
    },
    'gemini': {
        'endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'key_name': 'x-goog-api-key',
        'available_models': [
            {'name': 'gemini-2.5-pro', 'label': 'Gemini 2.5 Pro'},
            {'name': 'gemini-2.5-flash', 'label': 'Gemini 2.5 Flash'},
            {'name': 'gemini-2.5-flash-lite', 'label': 'Gemini 2.5 Flash-Lite'},
            {'name': 'gemini-3-pro-preview', 'label': 'Gemini 3 Pro Preview'},
            {'name': 'gemini-2.5-pro-preview-06-05', 'label': 'Gemini 2.5 Pro Preview'}
        ],
        'default_model': 'gemini-2.5-pro'
    },
    'deepseek': {
        'endpoint': 'https://api.deepseek.com/v1',
        'key_name': 'DEEPSEEK_API_KEY',
        'available_models': ['DeepSeek-V3.2', 'DeepSeek-V3', 'DeepSeek-R1'],
        'default_model': 'DeepSeek-V3.2'
    },
    'glm': {
        'endpoint': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key_name': 'ZHIPU_API_KEY',
        'available_models': [
            {'name': 'glm-4.6', 'label': 'glm-4.6 (快速模式)', 'mode': 'fast'},
            {'name': 'glm-4.6', 'label': 'glm-4.6 (均衡模式)', 'mode': 'balanced'},
            {'name': 'glm-4.6', 'label': 'glm-4.6 (深度思考模式)', 'mode': 'deep'},
            {'name': 'glm-4.6', 'label': 'glm-4.6 (创意模式)', 'mode': 'creative'},
            {'name': 'glm-4.6', 'label': 'glm-4.6 (精确模式)', 'mode': 'precise'},
            {'name': 'cogview-3', 'label': 'GLM 绘画 (CogView-3)', 'mode': 'image'}
        ],
        'default_model': 'glm-4.6'
    },
    'custom': {
        'endpoint': '',
        'key_name': 'API_KEY',
        'available_models': [],
        'default_model': None
    }
}


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

    # 缓存控件引用
    _tree_refs = {"cli": {}, "endpoint": {}, "config": {}}
    _last_click = {"config": None, "time": 0}  # 双击检测

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
        _update_selection()
        page.update()

    def _update_selection():
        theme = state.get_theme()
        for k, ref in _tree_refs["cli"].items():
            sel = state.selected_cli == k and state.selected_endpoint is None and state.selected_config is None
            ref["c"].bgcolor = theme['selection_bg'] if sel else theme['header_bg']
            ref["t"].color = theme['text_selected'] if sel else theme['text']
        for k, ref in _tree_refs["endpoint"].items():
            sel = state.selected_endpoint == k and state.selected_config is None
            ref["c"].bgcolor = theme['selection_bg'] if sel else None
            ref["t"].color = theme['text_selected'] if sel else theme['text']
        for i, ref in _tree_refs["config"].items():
            sel = state.selected_config == i
            ref["c"].bgcolor = theme['selection_bg'] if sel else None
            ref["t"].weight = ft.FontWeight.BOLD if sel else None
            ref["t"].color = theme['text_selected'] if sel else theme['text']
            ref["i"].color = theme['icon_key_selected'] if sel else ft.Colors.GREY_600

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
                            cfg_text = ft.Text(cfg.get('label', 'Unnamed'),
                                               weight=ft.FontWeight.BOLD if is_selected else None,
                                               color=theme['text_selected'] if is_selected else theme['text'])
                            cfg_container = ft.Container(
                                content=ft.Row([cfg_icon, cfg_text], spacing=5),
                                padding=ft.padding.only(left=60, top=5, bottom=5),
                                bgcolor=theme['selection_bg'] if is_selected else None,
                                border_radius=4, ink=True,
                                on_click=lambda e, i=idx: _on_config_click(i),
                            )
                            _tree_refs["config"][idx] = {"c": cfg_container, "t": cfg_text, "i": cfg_icon}
                            config_tree.controls.append(cfg_container)
        page.update()

    def show_config_dialog(idx):
        is_edit = idx is not None
        cfg = state.configs[idx] if is_edit else {}
        provider_data = cfg.get('provider', {})

        name_field = ft.TextField(label=L['name'], value=cfg.get('label', ''), expand=True)

        # CLI 下拉
        cli_dropdown = ft.Dropdown(
            label=L.get('cli_tool', 'CLI 工具'),
            value=cfg.get('cli_type', 'claude'),
            options=[ft.dropdown.Option(k, v['name']) for k, v in CLI_TOOLS.items()],
            expand=True,
        )

        # 提供商下拉
        provider_dropdown = ft.Dropdown(
            label=L.get('provider', '提供商'),
            value=provider_data.get('type', 'anthropic'),
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
        model_env_field = ft.TextField(
            label=L.get('model_env', '模型环境变量'),
            value=provider_data.get('model_env', ''), expand=True,
        )
        api_key_field = ft.TextField(
            label=L['api_key'], value=provider_data.get('credentials', {}).get('api_key', ''),
            password=True, can_reveal_password=True, expand=True,
        )
        max_tokens_field = ft.TextField(
            label=L.get('max_tokens', '单次响应最大'), value=str(provider_data.get('max_tokens', 32000)), expand=True,
        )
        token_limit_field = ft.TextField(
            label=L.get('token_limit', '上下文窗口'), value=str(provider_data.get('token_limit_per_request', 200000)), expand=True,
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
            page.update()

        model_dropdown.on_change = on_model_change

        def on_provider_change(e):
            provider = provider_dropdown.value
            defaults = PROVIDER_DEFAULTS.get(provider, {})
            endpoint_field.value = defaults.get('endpoint', '')
            key_name_field.value = defaults.get('key_name', 'API_KEY')
            model_dropdown.options = build_model_options(provider)
            if defaults.get('default_model'):
                model_dropdown.value = defaults['default_model']
            else:
                model_dropdown.value = None
            custom_model_field.visible = False
            custom_model_field.value = ''
            page.update()

        def on_cli_change(e):
            cli = cli_dropdown.value
            cli_info = CLI_TOOLS.get(cli, CLI_TOOLS['claude'])
            base_url_env_field.value = cli_info.get('base_url_env', 'API_BASE_URL')
            model_env_field.value = ''
            page.update()

        provider_dropdown.on_change = on_provider_change
        cli_dropdown.on_change = on_cli_change

        # 初始化模型列表
        init_provider = provider_data.get('type', 'anthropic')
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

            new_cfg = {
                'id': cfg.get('id', f"{name_field.value}-{int(datetime.now().timestamp())}"),
                'label': name_field.value,
                'cli_type': cli_dropdown.value,
                'provider': {
                    'type': provider_type,
                    'endpoint': endpoint_field.value,
                    'key_name': key_name_field.value,
                    'base_url_env': base_url_env_field.value,
                    'model_env': model_env_field.value,
                    'credentials': {'api_key': api_key_field.value},
                    'selected_model': selected_model,
                    'available_models': [selected_model] if selected_model else [],
                    'max_tokens': max_tokens,
                    'token_limit_per_request': token_limit,
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
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([
                name_field,
                ft.Row([cli_dropdown, provider_dropdown]),
                model_env_field,
                model_dropdown,
                custom_model_field,
                base_url_env_field,
                endpoint_field,
                key_name_field,
                api_key_field,
                ft.Row([max_tokens_field, token_limit_field]),
            ], tight=True, spacing=10, width=500),
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
                    show_snackbar(page, L['imported_count'].format(len(imported)))
                except Exception as ex:
                    show_snackbar(page, str(ex))
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
        picker.get_directory_path(initial_directory=work_dir_field.value or None)

    def refresh_terminals_click(e):
        state.terminals = detect_terminals()
        state.settings['terminals_cache'] = state.terminals
        save_settings(state.settings)
        terminal_dropdown.options = [ft.dropdown.Option(k) for k in state.terminals.keys()]
        if state.terminals:
            terminal_dropdown.value = list(state.terminals.keys())[0]
        show_snackbar(page, L['terminals_refreshed'])

    def refresh_envs_click(e):
        state.python_envs = detect_python_envs()
        state.settings['envs_cache'] = state.python_envs
        save_settings(state.settings)
        python_env_dropdown.options = [ft.dropdown.Option(k) for k in state.python_envs.keys()]
        if state.python_envs:
            python_env_dropdown.value = list(state.python_envs.keys())[0]
        show_snackbar(page, L['envs_refreshed'].format(len(state.python_envs)))

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
        # 调试：打印环境变量
        print(f"[DEBUG] cli_type={cli_type}, command={cli_info.get('command')}")
        print(f"[DEBUG] {key_name}={api_key[:20]}...")
        print(f"[DEBUG] {base_url_env}={endpoint}")
        print(f"[DEBUG] model={selected_model}")
        terminal_cmd = state.terminals.get(terminal_dropdown.value, 'cmd')
        cwd = work_dir_field.value or None
        cli_cmd = cli_info.get('command', 'claude')
        # 如果配置了模型，添加 --model 参数
        if selected_model:
            cli_cmd = f"{cli_cmd} --model {selected_model}"
        if sys.platform == 'win32':
            # Gemini CLI 需要永久环境变量，其他 CLI 用临时变量
            if cli_type == 'gemini':
                # 用 setx 设置永久环境变量（不加引号）
                setx_cmds = [f'setx {key_name} {api_key}']
                if endpoint:
                    setx_cmds.append(f'setx {base_url_env} {endpoint}')
                model_env = cfg.get('provider', {}).get('model_env', '')
                if selected_model and model_env:
                    setx_cmds.append(f'setx {model_env} {selected_model}')
                # 同时设置当前会话的临时变量
                set_cmds = [f'set {key_name}={api_key}']
                if endpoint:
                    set_cmds.append(f'set {base_url_env}={endpoint}')
                if selected_model and model_env:
                    set_cmds.append(f'set {model_env}={selected_model}')
                full_cmd = ' && '.join(setx_cmds + set_cmds + [cli_cmd])
            else:
                # 其他 CLI 用临时环境变量
                set_cmds = [f'set {key_name}={api_key}']
                if endpoint:
                    set_cmds.append(f'set {base_url_env}={endpoint}')
                if selected_model:
                    model_env = cfg.get('provider', {}).get('model_env', '')
                    if model_env:
                        set_cmds.append(f'set {model_env}={selected_model}')
                full_cmd = ' && '.join(set_cmds + [cli_cmd])
            subprocess.Popen(['cmd', '/k', full_cmd], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([terminal_cmd, '-e', cli_cmd], env=env, cwd=cwd)

    def apply_selected_prompt(e=None):
        """应用选中的提示词"""
        if not prompt_dropdown.value:
            return
        if not work_dir_field.value:
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
            file_path = write_prompt_to_cli(cli_type, system_content, user_content, user_id, work_dir_field.value)
            show_snackbar(page, L['prompt_written'].format(file_path))
        except Exception as ex:
            show_snackbar(page, L['prompt_write_fail'].format(ex))

    def on_prompt_change(e):
        """提示词选择变化时自动应用"""
        apply_selected_prompt()

    prompt_dropdown.on_change = on_prompt_change

    # MCP 服务器选择状态
    selected_mcp_servers = set()
    for m in state.mcp_list:
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
            # 更新 mcp_list 中的 is_default 状态
            for m in state.mcp_list:
                m['is_default'] = m.get('name', '') in selected_mcp_servers
            state.save_mcp()
            # 同步到全局配置
            from ..pages.mcp import create_mcp_page
            global_mcp_path = Path.home() / '.claude' / '.mcp.json'
            global_mcp_path.parent.mkdir(parents=True, exist_ok=True)
            mcp_servers = {}
            for m in state.mcp_list:
                if m.get('is_default'):
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
                    mcp_servers[m.get('name', '').lower().replace(' ', '-')] = server_config
            import json
            with open(global_mcp_path, 'w', encoding='utf-8') as f:
                json.dump({'mcpServers': mcp_servers}, f, indent=2, ensure_ascii=False)
            page.close(dlg)
            show_snackbar(page, L.get('mcp_saved', 'MCP 配置已保存'))

        # 按分类组织
        by_cat = {}
        for m in state.mcp_list:
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
    def take_screenshot(e):
        """启动截图工具 - 使用子进程避免线程问题"""
        import subprocess
        import threading
        import time as _time

        save_dir = work_dir_field.value or str(Path.cwd() / "screenshots")
        script = str(Path(__file__).parent.parent / "tools" / "screenshot_tool.py")

        # 清理一周前的截图
        def cleanup_old():
            try:
                d = Path(save_dir)
                if d.exists():
                    week_ago = _time.time() - 7 * 86400
                    for f in d.glob("screenshot_*.png"):
                        if f.stat().st_mtime < week_ago:
                            f.unlink()
            except Exception:
                pass

        def run():
            cleanup_old()
            result = subprocess.run(
                [sys.executable, script, save_dir],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path and Path(path).exists():
                    page.set_clipboard(path)
                    show_snackbar(page, L.get('screenshot_saved', f'截图已保存: {path}'))

        threading.Thread(target=run, daemon=True).start()

    # 路径抓取功能
    def pick_path(e):
        """启动路径抓取工具"""
        import subprocess
        import threading

        script = str(Path(__file__).parent.parent / "tools" / "path_picker.py")

        def run():
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path:
                    page.set_clipboard(path)
                    show_snackbar(page, L.get('path_copied', f'路径已复制: {path}'))

        threading.Thread(target=run, daemon=True).start()

    # 快捷键设置
    from ..hotkey import load_hotkey, update_hotkey

    def format_hotkey(hk: str) -> str:
        """格式化快捷键显示：alt+s -> Alt+S"""
        return '+'.join(p.capitalize() for p in hk.split('+'))

    current_hotkey_display = format_hotkey(load_hotkey())
    hotkey_btn = ft.OutlinedButton(f"快捷键 {current_hotkey_display}", on_click=lambda e: show_hotkey_dialog(e), width=140)

    def show_hotkey_dialog(e):
        """显示快捷键设置对话框"""
        try:
            import keyboard as kb
        except ImportError:
            show_snackbar(page, "需要安装 keyboard 库")
            return

        captured_keys = []
        current_hk = format_hotkey(load_hotkey())
        key_display = ft.Text("请按下快捷键...", size=16, weight=ft.FontWeight.BOLD)
        hook_id = [None]

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
                update_hotkey(new_key, work_dir_field.value)
                hotkey_btn.text = f"快捷键 {'+'.join(captured_keys)}"
                show_snackbar(page, f'快捷键已设置: {"+".join(captured_keys)}')
            page.close(dlg)

        def cancel(e):
            if hook_id[0]:
                kb.unhook(hook_id[0])
            page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("设置截图快捷键"),
            content=ft.Container(
                ft.Column([
                    ft.Text(f"当前快捷键为：{current_hk}", size=14),
                    key_display,
                ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=250, height=80,
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=cancel),
                ft.ElevatedButton(L['save'], on_click=save_key),
            ],
        )
        page.open(dlg)

    # 初始化列表
    refresh_config_list()

    # 构建页面
    api_page = ft.Column([
        ft.Row([
            ft.Container(config_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE),
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
        ], expand=1, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
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
        ft.Row([
            prompt_dropdown,
            ft.ElevatedButton(L.get('mcp_select', 'MCP 服务器'), icon=ft.Icons.EXTENSION, on_click=show_mcp_selector, width=130),
            ft.ElevatedButton(L.get('screenshot', '截图'), icon=ft.Icons.SCREENSHOT, on_click=take_screenshot, width=100, tooltip="截图保留一周"),
            ft.ElevatedButton(L.get('pick_path', '抓取路径'), icon=ft.Icons.LINK, on_click=pick_path, width=110, tooltip="选择文件复制绝对路径"),
            hotkey_btn,
        ], spacing=10),
    ], expand=True, spacing=10)

    return api_page, refresh_config_list
