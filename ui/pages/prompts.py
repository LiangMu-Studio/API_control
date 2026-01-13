# AI CLI Manager - Prompts Page
import flet as ft
from datetime import datetime
from ..common import THEMES, show_snackbar
from ..clipboard_paste import enable_clipboard_paste


def create_prompts_page(state):
    """创建提示词页面"""
    L = state.L
    theme = state.get_theme()

    # UI 组件
    prompt_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    system_prompt = state.prompt_db.get_system_prompt()
    global_prompt_content = ft.TextField(
        label=L['prompt_global'], multiline=True, min_lines=4,
        value=system_prompt.get('content', '') if system_prompt else '', border_radius=8,
    )
    global_icon = ft.Icon(ft.Icons.PUBLIC, color=theme['global_icon'])
    global_container = ft.Container(
        content=ft.Column([
            ft.Row([global_icon, ft.Text(L['prompt_global'], size=16, weight=ft.FontWeight.BOLD)], spacing=5),
            global_prompt_content,
            ft.Row([ft.ElevatedButton(L['prompt_save_global'], icon=ft.Icons.SAVE, on_click=lambda e: save_global_prompt(e))]),
        ], spacing=5),
        padding=10, border=ft.border.all(1, theme['global_border']), border_radius=8, bgcolor=theme['global_bg'],
    )
    prompt_content = ft.TextField(
        label=L['prompt_content'], multiline=True, min_lines=12, expand=True, border_radius=8,
    )
    enable_clipboard_paste(global_prompt_content)
    enable_clipboard_paste(prompt_content)
    expanded_categories = {}
    selected_prompt = None

    def save_global_prompt(e):
        nonlocal system_prompt
        if not system_prompt:
            system_prompt = {'id': 'system_global', 'name': L['prompt_global'], 'prompt_type': 'system', 'category': L['prompt_global']}
        system_prompt['content'] = global_prompt_content.value or ''
        state.prompt_db.save(system_prompt)
        show_snackbar(state.page, L['prompt_global_saved'])

    def build_prompt_tree():
        tree = {}
        for pid, p in state.prompts.items():
            if p.get('prompt_type') == 'system':
                continue
            cat = p.get('category', '其他')
            if cat not in tree:
                tree[cat] = []
            tree[cat].append((pid, p))
        order = ['编程', '写作', '分析', '绘画', '用户', '其他']
        return {k: tree[k] for k in order if k in tree} | {k: v for k, v in tree.items() if k not in order}

    def refresh_prompt_list():
        prompt_tree.controls.clear()
        tree = build_prompt_tree()
        theme = state.get_theme()
        # 更新全局提示词容器样式
        global_container.bgcolor = theme['global_bg']
        global_container.border = ft.border.all(1, theme['global_border'])
        global_icon.color = theme['global_icon']
        for cat, items in tree.items():
            is_expanded = expanded_categories.get(cat, True)
            cat_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER),
                    ft.Text(cat, weight=ft.FontWeight.BOLD),
                    ft.Text(f"({len(items)})", color=ft.Colors.GREY_600),
                ], spacing=5),
                padding=ft.padding.only(left=5, top=8, bottom=8),
                on_click=lambda e, c=cat: toggle_category(c),
                bgcolor=theme['header_bg'], border_radius=4,
            )
            prompt_tree.controls.append(cat_header)
            if is_expanded:
                for pid, p in items:
                    is_selected = selected_prompt == pid
                    is_builtin = p.get('is_builtin', False)
                    item = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.LOCK if is_builtin else ft.Icons.CHAT, size=16,
                                   color=ft.Colors.ORANGE if is_selected else ft.Colors.GREY_600),
                            ft.Text(p.get('name', 'Unnamed'),
                                   weight=ft.FontWeight.BOLD if is_selected else None,
                                   color=ft.Colors.BLUE if is_selected else None),
                            ft.Text(L['prompt_builtin'] if is_builtin else "", size=10, color=ft.Colors.GREY_500),
                        ], spacing=5),
                        padding=ft.padding.only(left=30, top=5, bottom=5),
                        on_click=lambda e, i=pid: select_prompt(i),
                        bgcolor=ft.Colors.BLUE_50 if is_selected else None, border_radius=4,
                    )
                    prompt_tree.controls.append(item)
        state.page.update()

    def toggle_category(cat):
        expanded_categories[cat] = not expanded_categories.get(cat, True)
        refresh_prompt_list()

    def select_prompt(pid):
        nonlocal selected_prompt
        selected_prompt = pid
        p = state.prompts.get(pid, {})
        prompt_content.value = p.get('content', '')
        prompt_content.read_only = p.get('is_builtin', False)
        refresh_prompt_list()

    def add_prompt(e):
        show_prompt_dialog(None)

    def edit_prompt(e):
        if selected_prompt and not state.prompts.get(selected_prompt, {}).get('is_builtin'):
            show_prompt_dialog(selected_prompt)
        elif selected_prompt:
            show_snackbar(state.page, L['prompt_builtin_readonly'])

    def delete_prompt(e):
        nonlocal selected_prompt
        if selected_prompt and not state.prompts.get(selected_prompt, {}).get('is_builtin'):
            state.prompt_db.delete(selected_prompt)
            state.refresh_prompts()
            selected_prompt = None
            prompt_content.value = ''
            refresh_prompt_list()

    def copy_prompt(e):
        if selected_prompt:
            state.page.set_clipboard(state.prompts[selected_prompt].get('content', ''))
            show_snackbar(state.page, L['copied'])

    def save_prompt_content(e):
        if selected_prompt and not state.prompts.get(selected_prompt, {}).get('is_builtin'):
            state.prompts[selected_prompt]['content'] = prompt_content.value or ''
            state.prompt_db.save(state.prompts[selected_prompt])
            show_snackbar(state.page, L['saved'])

    def show_prompt_dialog(pid):
        is_edit = pid is not None
        p = state.prompts.get(pid, {}) if is_edit else {}
        name_field = ft.TextField(label=L['name'], value=p.get('name', ''), expand=True)
        # 获取现有分类作为建议
        existing_cats = sorted(set(pr.get('category', '') for pr in state.prompts.values() if pr.get('category')))
        category_field = ft.Dropdown(
            label=L.get('category', '分类'), value=p.get('category', ''),
            options=[ft.dropdown.Option(c) for c in existing_cats] if existing_cats else [ft.dropdown.Option('')],
            expand=True,
        )
        new_cat_field = ft.TextField(label=L.get('new_category', '新分类'), hint_text=L.get('new_category_hint', '留空使用上方选择'), expand=True)
        content_field = ft.TextField(
            label=L['prompt_content'], value=p.get('content', ''), multiline=True, min_lines=5, expand=True,
        )
        enable_clipboard_paste(name_field)
        enable_clipboard_paste(content_field)
        enable_clipboard_paste(new_cat_field)

        def save_prompt(e):
            if not name_field.value:
                return
            new_id = pid if is_edit else f"custom_{int(datetime.now().timestamp())}"
            # 新分类优先，否则用下拉选择
            cat = new_cat_field.value.strip() if new_cat_field.value and new_cat_field.value.strip() else category_field.value
            new_prompt = {
                'id': new_id, 'name': name_field.value, 'content': content_field.value or '',
                'category': cat or '用户', 'prompt_type': 'user', 'is_builtin': False,
            }
            state.prompt_db.save(new_prompt)
            state.refresh_prompts()
            refresh_prompt_list()
            state.page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([name_field, category_field, new_cat_field, content_field], tight=True, spacing=10, width=500, height=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg)),
                ft.TextButton(L['save'], on_click=save_prompt),
            ],
        )
        state.page.open(dlg)

    prompt_page = ft.Column([
        global_container,
        ft.Divider(),
        ft.Row([
            ft.Text(L['prompt_user'], size=16, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.ADD, on_click=add_prompt, tooltip=L['add']),
            ft.IconButton(ft.Icons.EDIT, on_click=edit_prompt, tooltip=L['edit']),
            ft.IconButton(ft.Icons.DELETE, on_click=delete_prompt, tooltip=L['delete']),
            ft.IconButton(ft.Icons.COPY, on_click=copy_prompt, tooltip=L['copy']),
        ]),
        ft.Text(L['prompt_hint'], size=12, color=ft.Colors.GREY_600),
        ft.Row([
            ft.Container(prompt_tree, expand=1, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
            ft.Column([
                prompt_content,
                ft.Row([ft.ElevatedButton(L['save'], icon=ft.Icons.SAVE, on_click=save_prompt_content)]),
            ], expand=2),
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
    ], expand=True, spacing=10)

    return prompt_page, refresh_prompt_list
