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
    show_snackbar
)
from ..clipboard_paste import enable_clipboard_paste
from ..database import history_manager, codex_history_manager

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

    # 终端和环境下拉 - 优先使用上次选择的
    last_terminal = state.settings.get('last_terminal', '')
    last_env = state.settings.get('last_python_env', '')
    terminal_dropdown = ft.Dropdown(
        label=L['select_terminal'],
        value=last_terminal if last_terminal in state.terminals else (list(state.terminals.keys())[0] if state.terminals else ''),
        options=[ft.dropdown.Option(k) for k in state.terminals.keys()],
        width=180,
        on_change=lambda e: save_last_selection('last_terminal', e.control.value),
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
        refresh_session_dropdown_async()

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
            work_dir_history.remove(current)
            state.settings['work_dir_history'] = work_dir_history[-10:]
            save_settings(state.settings)
            work_dir_menu.items = build_workdir_menu_items()
            work_dir_input.value = work_dir_history[-1] if work_dir_history else None
            state.settings['work_dir'] = work_dir_input.value
            save_settings(state.settings)
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

    def build_session_options(cwd):
        """构建会话选项列表（根据选中 KEY 的 cli_type 加载对应历史）"""
        opts = []
        state._current_project = None
        cli_type = get_selected_cli_type()

        if cli_type == 'codex' and codex_history_manager and cwd:
            # Codex CLI 历史 - 只加载指定 cwd 的会话
            sessions = []
            for sid, info in codex_history_manager.load_project(cwd).items():
                ts = info.get('last_timestamp', '')[:16].replace('T', ' ')
                sessions.append((ts, sid, info['file']))
            sessions.sort()
            for ts, sid, fpath in sessions:
                opts.append(ft.dropdown.Option(key=str(fpath), text=f"{ts} | {sid[:12]}"[:50]))
        elif cli_type == 'claude' and history_manager and cwd:
            # Claude Code 历史
            cwd_key = Path(cwd).name.lower().replace(' ', '-').replace('.', '-').replace('_', '-')
            for pname in history_manager.list_projects(limit=30):
                if cwd_key.replace('-', '') in pname.lower().replace('-', ''):
                    state._current_project = pname
                    break
            if state._current_project:
                sessions = []
                for sid, info in history_manager.load_project(state._current_project).items():
                    ts = info.get('last_timestamp', '')[:16].replace('T', ' ')
                    sessions.append((ts, sid))
                sessions.sort()
                for ts, sid in sessions:
                    opts.append(ft.dropdown.Option(key=sid, text=f"{ts} | {sid[:12]}"[:50]))
        opts.append(ft.dropdown.Option(key='__none__', text=L.get('no_old_session', '不加载旧对话')))
        return opts

    session_dropdown = ft.Dropdown(
        label=L.get('session_resume', '恢复会话'),
        options=[ft.dropdown.Option(key='__none__', text=L.get('no_old_session', '不加载旧对话'))],
        value='__none__',
        width=400,
    )

    def show_session_preview(_):
        sid = session_dropdown.value
        if sid == '__none__':
            show_snackbar(page, L.get('no_session_selected', '请先选择一个会话'))
            return
        if not getattr(state, '_current_project', None):
            show_snackbar(page, L.get('no_project_found', '未找到匹配的项目'))
            return
        # 加载该会话的完整数据
        sessions = history_manager.load_project(state._current_project)
        info = sessions.get(sid)
        if not info:
            return
        # 提取最后一轮对话
        messages = info.get('messages', [])
        last_user_txt, last_ai_txt = '', ''
        for m in reversed(messages):
            msg_type = m.get('type')  # 'user' 或 'assistant'
            # Claude JSONL: message.content 是数组
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
        # 显示弹窗
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
            actions=[ft.TextButton("关闭", on_click=lambda _: page.close(dlg))],
        )
        page.open(dlg)

    session_preview_btn = ft.IconButton(ft.Icons.PREVIEW, tooltip="预览最后对话", on_click=show_session_preview)

    _session_loaded = [False]
    _session_loading = [False]  # 防止重复加载

    def refresh_session_dropdown_async():
        """后台异步加载会话列表"""
        if _session_loading[0]:
            return
        _session_loading[0] = True
        cwd = work_dir_input.value

        def do_load():
            opts = build_session_options(cwd)
            def update_ui():
                session_dropdown.options = opts
                session_dropdown.value = '__none__'
                if len(opts) > 1:
                    session_dropdown.value = opts[-2].key
                _session_loaded[0] = True
                _session_loading[0] = False
                page.update()
            page.run_thread(update_ui)

        import threading
        threading.Thread(target=do_load, daemon=True).start()

    def refresh_session_dropdown():
        cwd = work_dir_input.value
        session_dropdown.options = build_session_options(cwd)
        session_dropdown.value = '__none__'
        # 默认选中最新会话（最后一个非 __none__ 选项）
        if len(session_dropdown.options) > 1:
            session_dropdown.value = session_dropdown.options[-2].key
        _session_loaded[0] = True
        page.update()

    # 工作目录变化时刷新会话列表
    def on_workdir_change(e):
        save_work_dir(e.control.value)
        _session_loaded[0] = False  # 重置加载状态
        refresh_session_dropdown_async()

    work_dir_input.on_submit = on_workdir_change
    work_dir_input.on_blur = on_workdir_change

    # 懒加载：点击会话下拉框时才加载
    def on_session_focus(e):
        if not _session_loaded[0]:
            refresh_session_dropdown_async()
    session_dropdown.on_focus = on_session_focus

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
        # 保存选中的配置索引
        state.settings['last_selected_config'] = idx
        save_settings(state.settings)
        # 根据 cli_type 刷新会话列表
        _session_loaded[0] = False
        refresh_session_dropdown_async()
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
        page.update()

    def show_config_dialog(idx):
        is_edit = idx is not None
        cfg = state.configs[idx] if is_edit else {}
        provider_data = cfg.get('provider', {})

        name_field = ft.TextField(label=L['name'], value=cfg.get('label', ''), expand=True)
        tags_field = ft.TextField(label=L.get('tags', '标签'), value=cfg.get('tags', ''), expand=True, hint_text=L.get('tags_hint', '用逗号分隔'))

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
                'tags': tags_field.value,
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
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([
                ft.Row([name_field, tags_field]),
                ft.Row([cli_dropdown, provider_dropdown]),
                model_env_field,
                model_dropdown,
                custom_model_field,
                base_url_env_field,
                endpoint_field,
                key_name_field,
                api_key_field,
                ft.Row([quota_url_field, quota_btn]),
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

    def validate_config_key(e):
        """验证选中配置的 API Key"""
        if state.selected_config is None:
            show_snackbar(page, L['no_selection'])
            return
        cfg = state.configs[state.selected_config]
        provider = cfg.get('provider', {})
        provider_type = provider.get('type', 'anthropic')
        api_key = provider.get('credentials', {}).get('api_key', '')
        endpoint = provider.get('endpoint', '')

        show_snackbar(page, L.get('validating', '验证中...'))

        import threading
        def run_validate():
            from core.api_validator import validate_api_key
            valid, msg = validate_api_key(provider_type, api_key, endpoint)
            show_snackbar(page, L.get('validate_result', '验证结果: {}').format(msg))
        threading.Thread(target=run_validate, daemon=True).start()

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
                ok, result = sync.upload(state.configs, state.prompts, state.mcp_list)
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
                refresh_session_dropdown_async()  # 刷新会话列表
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
            # 根据终端类型选择启动方式
            term_lower = terminal_cmd.lower()
            if 'pwsh' in term_lower or 'powershell' in term_lower:
                # PowerShell 7 或 5 - 使用 -WorkingDirectory 参数
                args = [terminal_cmd, '-NoExit']
                if cwd:
                    args.extend(['-WorkingDirectory', cwd])
                args.extend(['-Command', cli_cmd])
                subprocess.Popen(args, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif 'bash' in term_lower:
                # Git Bash - cwd 参数已经设置工作目录
                subprocess.Popen([terminal_cmd, '-c', f'{cli_cmd}; exec bash'], cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif 'wt' in term_lower:
                # Windows Terminal - 使用 -d 参数指定工作目录
                args = [terminal_cmd]
                if cwd:
                    args.extend(['-d', cwd])
                args.extend(['pwsh', '-NoExit', '-Command', cli_cmd])
                subprocess.Popen(args, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # CMD - codex 需要用 npx 运行
                if cli_cmd.startswith('codex'):
                    cli_cmd = cli_cmd.replace('codex', 'npx @openai/codex', 1)
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
                subprocess.Popen(['cmd', '/k', full_cmd], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([terminal_cmd, '-e', cli_cmd], env=env, cwd=cwd)
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
    screenshot_btn = ft.ElevatedButton(L.get('screenshot', '截图'), icon=ft.Icons.SCREENSHOT, width=100, tooltip=L.get('screenshot_tooltip', '截图保留一周'))

    def take_screenshot(e):
        """启动截图工具 - 使用子进程避免线程问题"""
        import subprocess
        import threading
        import time as _time

        old_title = page.title
        page.title = L.get('screenshot_in_progress', '截图中...')
        page.window.to_front()
        page.update()

        save_dir = str(Path(__file__).parent.parent.parent / "screenshots")
        script = str(Path(__file__).parent.parent / "tools" / "screenshot_tool.py")

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
            result = subprocess.run(
                [sys.executable, script, save_dir],
                capture_output=True, text=True
            )
            page.title = old_title
            page.window.to_front()
            page.update()
            if result.returncode == 0:
                path = result.stdout.strip()
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

    # 构建页面
    api_page = ft.Column([
        ft.Row([
            ft.Container(config_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, clip_behavior=ft.ClipBehavior.HARD_EDGE),
            ft.Column([
                ft.OutlinedButton(L['add'], icon=ft.Icons.ADD, on_click=add_config, width=120),
                ft.OutlinedButton(L['edit'], icon=ft.Icons.EDIT, on_click=edit_config, width=120),
                ft.OutlinedButton(L['delete'], icon=ft.Icons.DELETE, on_click=delete_config, width=120),
                ft.OutlinedButton(L['copy_key'], icon=ft.Icons.COPY, on_click=copy_config_key, width=120),
                ft.OutlinedButton(L.get('validate_key', '验证'), icon=ft.Icons.VERIFIED, on_click=validate_config_key, width=130),
                ft.OutlinedButton(L['move_up'], icon=ft.Icons.ARROW_UPWARD, on_click=move_up, width=120),
                ft.OutlinedButton(L['move_down'], icon=ft.Icons.ARROW_DOWNWARD, on_click=move_down, width=120),
                ft.OutlinedButton(L['export'], icon=ft.Icons.UPLOAD, on_click=export_configs, width=120),
                ft.OutlinedButton(L['import'], icon=ft.Icons.DOWNLOAD, on_click=import_configs, width=120),
                ft.OutlinedButton(L.get('sync', '同步'), icon=ft.Icons.CLOUD_SYNC, on_click=show_sync_dialog, width=120),
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
            ft.ElevatedButton(L.get('mcp_select', 'MCP 服务器'), icon=ft.Icons.EXTENSION, on_click=show_mcp_selector, width=130),
        ], spacing=10),
        ft.Row([
            screenshot_btn,
            hotkey_btn,
            pick_path_btn,
            copypath_btn,
        ], spacing=10),
    ], expand=True, spacing=10)

    return api_page, refresh_config_list
