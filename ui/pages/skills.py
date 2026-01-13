# AI CLI Manager - Skills Page
import flet as ft
import os
import shutil
from pathlib import Path
from datetime import datetime
from ..common import show_snackbar
from ..database import tool_usage_db, mcp_skill_library


SKILL_CATEGORIES = ['常用', '开发', 'Git', '文档', '其他']


def create_skills_page(state):
    """创建 Skill 管理页面"""
    L = state.L
    theme = state.get_theme()
    skills_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    selected_skill_name = None
    expanded_categories = {}
    _skill_item_refs = {}  # name -> {'container': Container, 'name_text': Text, 'icon': Icon}

    # Skill 数据
    all_skills = []  # [{name, source, path, call_count, last_used, content}, ...]

    def scan_skills():
        """扫描所有 Skill"""
        nonlocal all_skills
        all_skills = []
        home = Path.home()
        claude_dir = home / '.claude'

        # 1. 扫描全局 Skill
        for skill_dir in [claude_dir / 'skills', claude_dir / 'commands']:
            if skill_dir.exists():
                for f in skill_dir.rglob('*.md'):
                    name = f.stem
                    rel_path = f.relative_to(skill_dir)
                    if len(rel_path.parts) > 1:
                        name = ':'.join(rel_path.parts[:-1]) + ':' + f.stem
                    all_skills.append({
                        'name': name, 'source': 'global', 'path': f,
                        'call_count': 0, 'last_used': '', 'content': ''
                    })

        # 2. 扫描项目级 Skill (当前工作目录)
        cwd = state.settings.get('cwd', '')
        if cwd:
            project_claude = Path(cwd) / '.claude'
            for skill_dir in [project_claude / 'skills', project_claude / 'commands']:
                if skill_dir.exists():
                    for f in skill_dir.rglob('*.md'):
                        name = f.stem
                        rel_path = f.relative_to(skill_dir)
                        if len(rel_path.parts) > 1:
                            name = ':'.join(rel_path.parts[:-1]) + ':' + f.stem
                        all_skills.append({
                            'name': name, 'source': 'project', 'path': f,
                            'call_count': 0, 'last_used': '', 'content': ''
                        })

        # 3. 从历史记录获取使用统计
        usage_stats = tool_usage_db.get_all_skills()
        usage_map = {s['tool_name']: s for s in usage_stats}

        # 更新已知 Skill 的统计
        known_names = {s['name'] for s in all_skills}
        for skill in all_skills:
            if skill['name'] in usage_map:
                stat = usage_map[skill['name']]
                skill['call_count'] = stat['total_calls']
                skill['last_used'] = stat['last_used']

        # 4. 添加历史发现的 Skill (用过但无配置文件)
        for name, stat in usage_map.items():
            if name not in known_names:
                all_skills.append({
                    'name': name, 'source': 'discovered', 'path': None,
                    'call_count': stat['total_calls'], 'last_used': stat['last_used'],
                    'content': ''
                })

        # 按调用次数排序
        all_skills.sort(key=lambda x: (-x['call_count'], x['name']))

    def format_time(ts: str) -> str:
        """格式化时间显示"""
        if not ts:
            return '-'
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            delta = now - dt
            if delta.days == 0:
                return L.get('today', '今天')
            elif delta.days == 1:
                return L.get('yesterday', '昨天')
            elif delta.days < 7:
                return L.get('days_ago', '{}天前').format(delta.days)
            else:
                return dt.strftime('%m-%d')
        except:
            return ts[:10]

    def get_source_label(source: str) -> tuple[str, str]:
        """获取来源标签和颜色"""
        labels = {
            'global': (L.get('skill_global', '全局'), ft.Colors.BLUE),
            'project': (L.get('skill_project', '项目级'), ft.Colors.GREEN),
            'discovered': (L.get('skill_discovered', '历史发现'), ft.Colors.ORANGE),
        }
        return labels.get(source, (source, ft.Colors.GREY))

    def add_to_global(name):
        """将 Skill 添加到全局（复制文件）"""
        skill = next((s for s in all_skills if s['name'] == name), None)
        if not skill or not skill['path']:
            return
        home = Path.home()
        if ':' in name:
            parts = name.split(':')
            target_dir = home / '.claude' / 'commands' / parts[0]
            target_file = target_dir / f"{parts[-1]}.md"
        else:
            target_dir = home / '.claude' / 'skills'
            target_file = target_dir / f"{name}.md"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill['path'], target_file)
            show_snackbar(state.page, L.get('skill_copied', 'Skill 已复制到全局'))
            scan_skills()
            refresh_skills_tree()
        except Exception as ex:
            show_snackbar(state.page, f"{L.get('skill_copy_fail', '复制失败')}: {ex}")

    def remove_from_global(name):
        """从全局移除 Skill（删除文件）"""
        skill = next((s for s in all_skills if s['name'] == name and s['source'] == 'global'), None)
        if not skill or not skill['path']:
            return
        try:
            skill['path'].unlink()
            show_snackbar(state.page, L.get('skill_removed', 'Skill 已从全局移除'))
            scan_skills()
            refresh_skills_tree()
        except Exception as ex:
            show_snackbar(state.page, f"{L.get('skill_remove_fail', '移除失败')}: {ex}")

    def build_skill_item(skill, is_global_section):
        """构建单个 Skill 项目控件"""
        name = skill['name']
        is_selected = selected_skill_name == name
        call_count = skill['call_count']

        name_text = ft.Text(name,
                           weight=ft.FontWeight.BOLD if is_selected else None,
                           color=ft.Colors.BLUE if is_selected else None)
        icon = ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=16,
                      color=ft.Colors.BLUE if is_selected else ft.Colors.GREY_600)

        subtitle_parts = []
        if call_count > 0:
            subtitle_parts.append(f"{L.get('calls', '调用')}: {call_count}")
        if skill['last_used']:
            subtitle_parts.append(f"{L.get('last_used', '最后使用')}: {format_time(skill['last_used'])}")

        # 根据所在区域显示不同的操作按钮
        if is_global_section:
            action_btn = ft.IconButton(
                ft.Icons.ARROW_DOWNWARD, icon_size=16,
                tooltip=L.get('remove_from_global', '移出全局'),
                on_click=lambda e, n=name: remove_from_global(n)
            )
        else:
            # 只有有文件的 Skill 才能添加到全局
            action_btn = ft.IconButton(
                ft.Icons.ARROW_UPWARD, icon_size=16,
                tooltip=L.get('add_to_global', '添加到全局'),
                on_click=lambda e, n=name: add_to_global(n),
                visible=skill['path'] is not None
            )

        item = ft.Container(
            content=ft.Row([
                icon,
                ft.Column([
                    name_text,
                    ft.Text('  |  '.join(subtitle_parts) if subtitle_parts else '-', size=10, color=ft.Colors.GREY_500),
                ], spacing=0, expand=True),
                action_btn,
                ft.IconButton(ft.Icons.EDIT, on_click=lambda e, n=name: edit_skill(n),
                             tooltip=L['edit'], icon_size=16, visible=skill['path'] is not None),
            ], spacing=5),
            padding=ft.padding.only(left=10, top=5, bottom=5),
            on_click=lambda e, n=name: select_skill(n),
            bgcolor=ft.Colors.BLUE_50 if is_selected else None, border_radius=4,
        )
        _skill_item_refs[name] = {'container': item, 'name_text': name_text, 'icon': icon}
        return item

    def refresh_skills_tree():
        """刷新 Skill 树形列表"""
        nonlocal selected_skill_name
        skills_tree.controls.clear()
        _skill_item_refs.clear()
        theme = state.get_theme()

        # 分离全局和库中的 Skill
        global_skills = [s for s in all_skills if s['source'] == 'global']
        library_skills = [s for s in all_skills if s['source'] != 'global']

        # === 全局 Skill 区域 ===
        global_header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.GREEN),
                ft.Text(L.get('global_skill', '全局 Skill'), weight=ft.FontWeight.BOLD),
                ft.Text(f"({len(global_skills)})", color=ft.Colors.GREY_600),
            ], spacing=5),
            padding=ft.padding.only(left=5, top=8, bottom=8),
            bgcolor=theme['header_bg'], border_radius=4,
        )
        skills_tree.controls.append(global_header)

        if global_skills:
            for skill in global_skills:
                item = build_skill_item(skill, is_global_section=True)
                skills_tree.controls.append(item)
        else:
            skills_tree.controls.append(ft.Container(
                content=ft.Text(L.get('no_global_skill', '暂无全局 Skill，从下方库中添加'), color=ft.Colors.GREY_500, size=12),
                padding=ft.padding.only(left=20, top=10, bottom=10),
            ))

        # === 分隔线 ===
        skills_tree.controls.append(ft.Divider(height=20))

        # === Skill 库区域（按来源分类） ===
        library_header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.INVENTORY_2, color=ft.Colors.AMBER),
                ft.Text(L.get('skill_library', 'Skill 库'), weight=ft.FontWeight.BOLD),
                ft.Text(f"({len(library_skills)})", color=ft.Colors.GREY_600),
            ], spacing=5),
            padding=ft.padding.only(left=5, top=8, bottom=8),
            bgcolor=theme['header_bg'], border_radius=4,
        )
        skills_tree.controls.append(library_header)

        # 按来源分组
        source_order = ['project', 'discovered']
        source_labels = {
            'project': L.get('skill_project', '项目级'),
            'discovered': L.get('skill_discovered', '历史发现'),
        }
        tree = {}
        for s in library_skills:
            src = s['source']
            if src not in tree:
                tree[src] = []
            tree[src].append(s)

        for src in source_order:
            if src not in tree:
                continue
            items = tree[src]
            is_expanded = expanded_categories.get(src, True)
            cat_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER, size=16),
                    ft.Text(source_labels.get(src, src), size=13),
                    ft.Text(f"({len(items)})", color=ft.Colors.GREY_600, size=12),
                ], spacing=5),
                padding=ft.padding.only(left=15, top=5, bottom=5),
                on_click=lambda e, c=src: toggle_category(c),
            )
            skills_tree.controls.append(cat_header)
            if is_expanded:
                for skill in items:
                    item = build_skill_item(skill, is_global_section=False)
                    item.padding = ft.padding.only(left=35, top=5, bottom=5)
                    skills_tree.controls.append(item)

        state.page.update()

    def toggle_category(cat):
        expanded_categories[cat] = not expanded_categories.get(cat, True)
        refresh_skills_tree()

    def select_skill(name):
        nonlocal selected_skill_name
        old_selected = selected_skill_name
        selected_skill_name = name
        # 增量更新：只更新旧选中项和新选中项的样式
        if old_selected is not None and old_selected in _skill_item_refs:
            ref = _skill_item_refs[old_selected]
            ref['container'].bgcolor = None
            ref['name_text'].weight = None
            ref['name_text'].color = None
            ref['icon'].color = ft.Colors.GREY_600
        if name is not None and name in _skill_item_refs:
            ref = _skill_item_refs[name]
            ref['container'].bgcolor = ft.Colors.BLUE_50
            ref['name_text'].weight = ft.FontWeight.BOLD
            ref['name_text'].color = ft.Colors.BLUE
            ref['icon'].color = ft.Colors.BLUE
        state.page.update()

    def edit_skill(name):
        """编辑 Skill 文件"""
        skill = next((s for s in all_skills if s['name'] == name), None)
        if not skill or not skill['path']:
            show_snackbar(state.page, L.get('skill_no_file', '该 Skill 无配置文件'))
            return

        try:
            content = skill['path'].read_text(encoding='utf-8')
        except:
            content = ''

        content_field = ft.TextField(
            value=content, multiline=True, min_lines=15, max_lines=20, expand=True
        )

        def save_skill(e):
            try:
                skill['path'].write_text(content_field.value, encoding='utf-8')
                show_snackbar(state.page, L.get('skill_saved', 'Skill 已保存'))
                state.page.close(dlg)
            except Exception as ex:
                show_snackbar(state.page, f"{L.get('skill_save_fail', '保存失败')}: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text(f"{L['edit']}: {skill['name']}"),
            content=ft.Container(
                ft.Column([
                    ft.Text(str(skill['path']), size=11, color=ft.Colors.GREY_600),
                    content_field
                ], spacing=10),
                width=600, height=450
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg)),
                ft.ElevatedButton(L['save'], on_click=save_skill),
            ],
        )
        state.page.open(dlg)

    def create_skill(e):
        """创建新 Skill"""
        name_field = ft.TextField(label=L['name'], hint_text='my-skill')
        scope_dropdown = ft.Dropdown(
            label=L.get('skill_scope', '作用域'),
            value='global',
            options=[
                ft.dropdown.Option('global', L.get('skill_global', '全局')),
                ft.dropdown.Option('project', L.get('skill_project', '项目级')),
            ],
            width=150
        )
        content_field = ft.TextField(
            label=L.get('skill_content', 'Skill 内容'),
            multiline=True, min_lines=10, max_lines=15, expand=True,
            value='# My Skill\n\nDescribe what this skill does...\n'
        )

        def save_new_skill(ev):
            name = name_field.value.strip()
            if not name:
                show_snackbar(state.page, L.get('skill_name_required', '请输入 Skill 名称'))
                return

            home = Path.home()
            if scope_dropdown.value == 'global':
                target_dir = home / '.claude' / 'skills'
            else:
                cwd = state.settings.get('cwd', '')
                if not cwd:
                    show_snackbar(state.page, L.get('skill_no_cwd', '请先设置工作目录'))
                    return
                target_dir = Path(cwd) / '.claude' / 'skills'

            target_file = target_dir / f"{name}.md"
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content_field.value, encoding='utf-8')
                show_snackbar(state.page, L.get('skill_created', 'Skill 已创建'))
                state.page.close(dlg)
                scan_skills()
                refresh_skills_tree()
            except Exception as ex:
                show_snackbar(state.page, f"{L.get('skill_create_fail', '创建失败')}: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('skill_new', '新建 Skill')),
            content=ft.Container(
                ft.Column([
                    ft.Row([name_field, scope_dropdown], spacing=10),
                    content_field
                ], spacing=10),
                width=500, height=400
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(dlg)),
                ft.ElevatedButton(L['save'], on_click=save_new_skill),
            ],
        )
        state.page.open(dlg)

    def delete_skill(e):
        """删除选中的 Skill"""
        if selected_skill_name is None:
            return
        skill = next((s for s in all_skills if s['name'] == selected_skill_name), None)
        if not skill or not skill['path']:
            show_snackbar(state.page, L.get('skill_no_file', '该 Skill 无配置文件'))
            return

        def do_delete(ev):
            nonlocal selected_skill_name
            try:
                skill['path'].unlink()
                show_snackbar(state.page, L.get('skill_deleted', 'Skill 已删除'))
                state.page.close(confirm_dlg)
                selected_skill_name = None
                scan_skills()
                refresh_skills_tree()
            except Exception as ex:
                show_snackbar(state.page, f"{L.get('skill_delete_fail', '删除失败')}: {ex}")

        confirm_dlg = ft.AlertDialog(
            title=ft.Text(L.get('skill_delete_confirm', '确认删除')),
            content=ft.Text(f"{L.get('skill_delete_desc', '确定要删除')} {skill['name']}?"),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: state.page.close(confirm_dlg)),
                ft.ElevatedButton(L['delete'], on_click=do_delete, color=ft.Colors.RED),
            ],
        )
        state.page.open(confirm_dlg)

    def refresh_data(e=None):
        """刷新数据"""
        scan_skills()
        refresh_skills_tree()
        show_snackbar(state.page, L.get('skill_refreshed', '已刷新'))

    def show_preset_manager(e):
        """显示 Skill 预设管理对话框 - 左右分栏布局"""
        selected_preset = [None]  # 当前选中的预设名称
        preset_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=2, expand=True)
        content_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=2, expand=True)
        content_title = ft.Text(L.get('preset_select_group', '请选择分组'), weight=ft.FontWeight.BOLD)

        def refresh_preset_list():
            preset_list.controls.clear()
            presets = mcp_skill_library.get_all_skill_presets()
            for p in presets:
                is_default = p.get('is_default', False)
                is_selected = selected_preset[0] == p['name']
                preset_list.controls.append(ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.STAR if is_default else ft.Icons.STAR_BORDER,
                               color=ft.Colors.AMBER if is_default else ft.Colors.GREY, size=18),
                        ft.Text(p['name'], expand=True, weight=ft.FontWeight.BOLD if is_selected else None),
                        ft.Text(f"({len(p.get('skill_names', []))})", color=ft.Colors.GREY_600, size=12),
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
            preset = next((p for p in mcp_skill_library.get_all_skill_presets() if p['name'] == selected_preset[0]), None)
            if not preset:
                return
            content_title.value = f"{L.get('preset_content', '分组内容')}: {preset['name']}"
            selected_names = set(preset.get('skill_names', []))

            # 按来源分组
            by_source = {}
            for s in all_skills:
                src = s.get('source', 'other')
                if src not in by_source:
                    by_source[src] = []
                by_source[src].append(s)

            source_order = ['global', 'project', 'discovered']
            source_labels = {
                'global': L.get('skill_global', '全局'),
                'project': L.get('skill_project', '项目级'),
                'discovered': L.get('skill_discovered', '历史发现'),
            }

            for src in source_order:
                if src not in by_source:
                    continue
                items = by_source[src]
                # 来源标题
                content_list.controls.append(ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER, size=16),
                        ft.Text(source_labels.get(src, src), weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(f"({len(items)})", color=ft.Colors.GREY_600, size=11),
                    ], spacing=5),
                    padding=ft.padding.only(top=8, bottom=4),
                ))
                # Skill 列表
                for s in items:
                    skill_name = s['name']
                    cb = ft.Checkbox(
                        value=skill_name in selected_names, label=skill_name,
                        on_change=lambda ev, n=skill_name: toggle_skill_in_preset(n, ev.control.value)
                    )
                    content_list.controls.append(ft.Container(cb, padding=ft.padding.only(left=20)))
            state.page.update()

        def select_preset(name):
            selected_preset[0] = name
            refresh_preset_list()
            refresh_content_list()

        def toggle_skill_in_preset(skill_name, checked):
            if not selected_preset[0]:
                return
            preset = next((p for p in mcp_skill_library.get_all_skill_presets() if p['name'] == selected_preset[0]), None)
            if not preset:
                return
            names = set(preset.get('skill_names', []))
            if checked:
                names.add(skill_name)
            else:
                names.discard(skill_name)
            mcp_skill_library.add_skill_preset(selected_preset[0], list(names), preset.get('is_default', False))
            refresh_preset_list()

        def create_preset(ev):
            name = name_field.value.strip()
            if not name:
                return
            mcp_skill_library.add_skill_preset(name, [])
            name_field.value = ''
            selected_preset[0] = name
            refresh_preset_list()
            refresh_content_list()
            show_snackbar(state.page, L.get('preset_created', '预设已创建'))

        def set_default_preset(ev):
            if not selected_preset[0]:
                return
            preset = next((p for p in mcp_skill_library.get_all_skill_presets() if p['name'] == selected_preset[0]), None)
            if preset:
                mcp_skill_library.add_skill_preset(selected_preset[0], preset.get('skill_names', []), is_default=True)
                refresh_preset_list()
                show_snackbar(state.page, L.get('preset_default_set', '已设为默认预设'))

        def delete_preset(ev):
            if not selected_preset[0]:
                return
            mcp_skill_library.delete_skill_preset(selected_preset[0])
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
        """将当前 Skill 列表添加到库"""
        added = 0
        for s in all_skills:
            if mcp_skill_library.add_skill(
                s['name'], str(s.get('path', '')), s.get('content', ''), s['source']
            ):
                added += 1
        show_snackbar(state.page, f"已添加 {added} 个 Skill 到库")

    def show_more_menu(e):
        """显示更多操作菜单"""
        def close_menu():
            state.page.close(menu_dlg)

        def on_preset(ev):
            close_menu()
            show_preset_manager(ev)

        def on_sync(ev):
            close_menu()
            add_to_library(ev)

        menu_dlg = ft.AlertDialog(
            title=ft.Text(L.get('more', '更多')),
            content=ft.Column([
                ft.ListTile(leading=ft.Icon(ft.Icons.BOOKMARKS), title=ft.Text(L.get('preset_manage', '管理预设')), on_click=on_preset),
                ft.ListTile(leading=ft.Icon(ft.Icons.LIBRARY_ADD), title=ft.Text(L.get('add_to_library', '同步到库')), on_click=on_sync),
            ], spacing=0, tight=True),
            actions=[ft.TextButton(L['close'], on_click=lambda ev: close_menu())],
        )
        state.page.open(menu_dlg)

    # 初始扫描
    scan_skills()

    skills_page = ft.Column([
        ft.Row([
            ft.Text(L.get('skills', 'Skills'), size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.BOOKMARKS, on_click=show_preset_manager, tooltip=L.get('preset_manage', '管理预设')),
            ft.IconButton(ft.Icons.ADD, on_click=create_skill, tooltip=L.get('skill_new', '新建')),
            ft.IconButton(ft.Icons.REFRESH, on_click=refresh_data, tooltip=L.get('refresh', '刷新')),
            ft.IconButton(ft.Icons.DELETE, on_click=delete_skill, tooltip=L['delete']),
        ]),
        ft.Text(L.get('skill_hint', '上方为全局 Skill，下方为 Skill 库'), size=12, color=ft.Colors.GREY_600),
        ft.Container(skills_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
    ], expand=True, spacing=10)

    return skills_page, refresh_skills_tree
