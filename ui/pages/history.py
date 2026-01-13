# AI CLI Manager - History Page
# 复刻 DEV 版 (Tauri) 的历史记录页面设计
import flet as ft
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from ..common import THEMES, TRASH_RETENTION_DAYS, show_snackbar
from ..database import history_manager, codex_history_manager

# 导入 Rust 历史记录模块
try:
    import liangmu_history as lh
except ImportError:
    lh = None

from collections import OrderedDict

MAX_CACHE_SIZE = 200  # 增大缓存，减少重复加载

# LRU 消息内容提取缓存 - 避免重复解析
class LRUMessageCache:
    """LRU 缓存实现，避免内存泄漏"""
    def __init__(self, max_size=1000):
        self.max_size = max_size
        self.cache = OrderedDict()

    def get(self, msg_id):
        if msg_id in self.cache:
            self.cache.move_to_end(msg_id)
            return self.cache[msg_id]
        return None

    def put(self, msg_id, value):
        if msg_id in self.cache:
            self.cache.move_to_end(msg_id)
            self.cache[msg_id] = value
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
            self.cache[msg_id] = value

    def clear(self):
        self.cache.clear()

_message_cache = LRUMessageCache(max_size=1000)


def shorten_path(path: str, max_len: int = 40) -> str:
    """缩短路径显示"""
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
    # 根据上次选中的 KEY 确定默认 CLI 类型（只支持 claude 和 codex）
    SUPPORTED_CLI = ('claude', 'codex')
    last_idx = state.settings.get('last_selected_config')
    if last_idx is not None and 0 <= last_idx < len(state.configs):
        cli_type = state.configs[last_idx].get('cli_type', 'claude')
        current_cli = cli_type if cli_type in SUPPORTED_CLI else 'claude'
    else:
        current_cli = "claude"

    selected_session_data = [None]  # 当前选中的会话数据
    loaded_projects = OrderedDict()  # LRU 缓存
    show_sidebar = [True]  # 侧边栏显示状态

    # 工具图标和颜色映射 - 复刻 DEV 版
    TOOL_ICONS = {
        'Read': ('📖', 'bg-blue-100', ft.Colors.BLUE_100),
        'Write': ('✏️', 'bg-green-100', ft.Colors.GREEN_100),
        'Edit': ('🔧', 'bg-yellow-100', ft.Colors.YELLOW_100),
        'Bash': ('💻', 'bg-purple-100', ft.Colors.PURPLE_100),
        'Glob': ('🔍', 'bg-cyan-100', ft.Colors.CYAN_100),
        'Grep': ('🔎', 'bg-teal-100', ft.Colors.TEAL_100),
        'Task': ('🚀', 'bg-pink-100', ft.Colors.PINK_100),
        'TodoWrite': ('📋', 'bg-amber-100', ft.Colors.AMBER_100),
        'WebFetch': ('🌐', 'bg-indigo-100', ft.Colors.INDIGO_100),
        'WebSearch': ('🔍', 'bg-light-blue-100', ft.Colors.LIGHT_BLUE_100),
    }

    def get_current_manager():
        if current_cli == "claude":
            return history_manager
        elif current_cli == "codex":
            return codex_history_manager
        return None

    def extract_content(msg) -> tuple:
        """提取消息内容 - 带 LRU 缓存"""
        msg_id = id(msg)
        cached = _message_cache.get(msg_id)
        if cached:
            return cached

        if current_cli == 'claude':
            role = msg.get('type', '?')
            c = msg.get('message', {}).get('content', [])
        else:
            role = msg.get('role', '?')
            c = msg.get('content', '')
        if isinstance(c, str):
            result = (role, c, [], True)
        else:
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
            is_real_user = (role == 'user' and not has_tool_result)
            result = (role, '\n'.join(texts), tool_blocks, is_real_user)

        # 使用 LRU 缓存
        _message_cache.put(msg_id, result)
        return result

    def analyze_session(messages):
        """分析会话 - 合并轮数统计和工具统计（单次遍历）"""
        tool_stats = {}
        real_turns = 0
        for msg in messages:
            role, _, tool_blocks, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                real_turns += 1
            for b in tool_blocks:
                if b.get('type') == 'tool_use':
                    name = b.get('name', 'unknown')
                    tool_stats[name] = tool_stats.get(name, 0) + 1
        return real_turns, tool_stats

    def count_real_turns(messages):
        """计算真实用户轮数（兼容旧调用）"""
        turns, _ = analyze_session(messages)
        return turns

    # ==================== 左侧边栏 - 项目树 ====================
    sidebar_container = ft.Container(width=320, visible=True)
    project_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    # 项目展开状态
    expanded_projects = {}
    selected_session_id = [None]
    # 会话项引用缓存（用于增量更新选中状态）
    session_item_refs = {}  # {session_id: Container}

    def build_project_item(project_id, display_path):
        """构建项目项 - 复刻 DEV 版 ProjectItem"""
        is_expanded = expanded_projects.get(project_id, False)
        sessions_col = ft.Column([], spacing=0, visible=is_expanded)
        theme = state.get_theme()

        # 项目标题行
        title_text = ft.Text(shorten_path(display_path, 35), size=13, weight=ft.FontWeight.W_500)
        subtitle_text = ft.Text(L.get('click_to_load', '点击加载...') if not is_expanded else '', size=11, color=ft.Colors.GREY_500)
        expand_icon = ft.Text('▼' if is_expanded else '▶', size=11, color=ft.Colors.GREY_500)

        def on_project_click(_):
            nonlocal is_expanded
            expanded_projects[project_id] = not expanded_projects.get(project_id, False)
            is_expanded = expanded_projects[project_id]
            expand_icon.value = '▼' if is_expanded else '▶'
            sessions_col.visible = is_expanded

            if is_expanded and not sessions_col.controls:
                # 懒加载会话列表
                load_sessions(project_id, display_path, sessions_col, subtitle_text)
            state.page.update()

        project_header = ft.Container(
            content=ft.Row([
                ft.Column([title_text, subtitle_text], spacing=2, expand=True),
                ft.Text('📁', size=14, color=ft.Colors.AMBER),
                expand_icon,
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=theme['header_bg'] if is_expanded else None,
            on_click=on_project_click,
            ink=True,
        )

        return ft.Container(
            content=ft.Column([project_header, sessions_col], spacing=0),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.GREY))),
        )

    def load_sessions(project_id, project_cwd, sessions_col, subtitle_text):
        """加载项目的会话列表"""
        if project_id in loaded_projects:
            loaded_projects.move_to_end(project_id)
            sessions = loaded_projects[project_id]
        else:
            mgr = get_current_manager()
            if not mgr or not hasattr(mgr, 'load_project'):
                return
            sessions = mgr.load_project(project_id)
            loaded_projects[project_id] = sessions
            while len(loaded_projects) > MAX_CACHE_SIZE:
                loaded_projects.popitem(last=False)

        if not sessions:
            subtitle_text.value = L.get('history_no_records', '无记录')
            sessions_col.controls.append(ft.Text(L.get('history_no_records', '无记录'), size=11, color=ft.Colors.GREY_500))
            return

        subtitle_text.value = f"{len(sessions)} {L.get('history_sessions', '会话')}"

        for sid, info in sorted(sessions.items(), key=lambda x: x[1].get('last_timestamp', ''), reverse=True):
            ts = info.get('last_timestamp', '')
            try:
                time_str = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%m-%d %H:%M') if ts else ''
            except (ValueError, AttributeError):
                time_str = ts[:16] if ts else ''
            turns = count_real_turns(info.get('messages', []))

            is_selected = selected_session_id[0] == sid
            session_item = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(time_str, size=11, color=ft.Colors.GREY_600),
                        ft.Text(f"{turns} {L.get('history_turns', '轮')}", size=10, color=ft.Colors.GREY_500),
                    ], spacing=2, expand=True),
                ], expand=True),
                padding=ft.padding.only(left=24, top=6, bottom=6, right=8),
                border=ft.border.only(left=ft.BorderSide(2, ft.Colors.BLUE_500 if is_selected else ft.Colors.TRANSPARENT)),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE) if is_selected else None,
                on_click=lambda e, s=sid, i=info, p=project_id, cwd=project_cwd: on_session_click(s, i, p, cwd),
                ink=True,
                expand=True,
            )
            sessions_col.controls.append(session_item)
            # 保存引用用于增量更新
            session_item_refs[sid] = session_item

    def on_session_click(session_id, info, project_id, project_cwd):
        """点击会话 - 增量更新选中状态"""
        old_session_id = selected_session_id[0]
        selected_session_id[0] = session_id
        selected_session_data[0] = {'session_id': session_id, 'info': info, 'group': project_id}
        show_session_detail(info, session_id, project_cwd)

        # 增量更新选中状态（不重建整个列表）
        # 取消旧的选中
        if old_session_id and old_session_id in session_item_refs:
            old_item = session_item_refs[old_session_id]
            old_item.border = ft.border.only(left=ft.BorderSide(2, ft.Colors.TRANSPARENT))
            old_item.bgcolor = None

        # 设置新的选中
        if session_id in session_item_refs:
            new_item = session_item_refs[session_id]
            new_item.border = ft.border.only(left=ft.BorderSide(2, ft.Colors.BLUE_500))
            new_item.bgcolor = ft.Colors.with_opacity(0.05, ft.Colors.BLUE)

        state.page.update()

    # ==================== 右侧面板 - 会话详情 ====================
    detail_panel = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=8)
    detail_header = ft.Row([], spacing=8, wrap=True)
    tool_stats_row = ft.Row([], spacing=4, wrap=True)
    messages_container = ft.Column([], spacing=8, expand=True)

    # 分页状态
    load_state = {'head': 3, 'tail': 3}

    def toggle_sidebar(_):
        """切换侧边栏显示"""
        show_sidebar[0] = not show_sidebar[0]
        sidebar_container.visible = show_sidebar[0]
        toggle_btn.text = '← ' + L.get('collapse', '收起') if show_sidebar[0] else L.get('expand', '展开') + ' →'
        state.page.update()

    toggle_btn = ft.TextButton('← ' + L.get('collapse', '收起'), on_click=toggle_sidebar)

    def show_session_detail(info, session_id, project_cwd=''):
        """显示会话详情 - 复刻 DEV 版"""
        messages = info.get('messages', [])
        # 优先使用项目路径，其次使用会话的 cwd
        folder_path = project_cwd or info.get('cwd', '')

        # 构建操作栏
        detail_header.controls = [
            toggle_btn,
            ft.TextButton('📄 HTML', on_click=lambda _: export_session('html')),
            ft.TextButton('📝 MD', on_click=lambda _: export_session('md')),
            ft.TextButton('📂 ' + L.get('open_folder', '打开'), on_click=lambda _: open_folder(folder_path)) if folder_path else ft.Container(),
            ft.TextButton('🗑️ ' + L.get('delete', '删除'), on_click=lambda _: confirm_del_session()),
        ]

        # 使用合并后的分析函数（单次遍历）
        real_turns, tool_stats = analyze_session(messages)

        # 工具统计芯片
        tool_stats_row.controls = [
            ft.Text(f"{real_turns} {L.get('history_turns', '轮')}", size=12, color=ft.Colors.GREY_600),
        ]
        for name, count in sorted(tool_stats.items(), key=lambda x: -x[1])[:6]:
            icon, _, bgcolor = TOOL_ICONS.get(name, ('🔧', '', ft.Colors.GREY_100))
            tool_stats_row.controls.append(ft.Container(
                ft.Text(f"{icon} {name}: {count}", size=10),
                bgcolor=bgcolor, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=8,
            ))

        # 构建消息时间线
        build_message_timeline(messages)
        state.page.update()

    def build_message_timeline(messages):
        """构建消息时间线 - 复刻 DEV 版分页机制"""
        messages_container.controls.clear()

        # 将消息按轮次分组
        rounds = []
        current_round = None
        orphan_msgs = []
        for msg in messages:
            role, _, _, is_real_user = extract_content(msg)
            if role == 'user' and is_real_user:
                if current_round:
                    rounds.append(current_round)
                current_round = (msg, [])
            elif current_round:
                current_round[1].append(msg)
            else:
                orphan_msgs.append(msg)
        if current_round:
            rounds.append(current_round)
        if orphan_msgs:
            rounds.insert(0, (None, orphan_msgs))

        total = len(rounds)
        if total == 0:
            messages_container.controls.append(ft.Text(L.get('history_no_records', '无记录'), color=ft.Colors.GREY_500))
            return

        head_n, tail_n = load_state['head'], load_state['tail']

        if head_n + tail_n >= total:
            # 全部显示
            for i, rd in enumerate(rounds):
                messages_container.controls.extend(render_round(rd, i + 1, i, messages))
        else:
            # 显示前 head_n 轮
            for i in range(head_n):
                messages_container.controls.extend(render_round(rounds[i], i + 1, i, messages))

            # 展开按钮
            hidden = total - head_n - tail_n
            messages_container.controls.append(ft.Container(
                ft.Row([
                    ft.ElevatedButton(f"↓ +10", on_click=lambda _: expand_more('head', messages), bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE),
                    ft.Text(f"{L.get('hidden', '隐藏')} {hidden} {L.get('history_turns', '轮')}", size=12, color=ft.Colors.GREY_500),
                    ft.ElevatedButton(f"↑ +10", on_click=lambda _: expand_more('tail', messages), bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
                padding=ft.padding.symmetric(vertical=16),
            ))

            # 显示后 tail_n 轮
            for i in range(total - tail_n, total):
                messages_container.controls.extend(render_round(rounds[i], i + 1, i, messages))

    def expand_more(direction, messages):
        if direction == 'head':
            load_state['head'] += 10
        else:
            load_state['tail'] += 10
        build_message_timeline(messages)
        # 使用 run_thread 确保 UI 更新在正确的线程中执行
        def do_update():
            state.page.update()
        state.page.run_thread(do_update)

    def render_round(round_data, round_num, round_idx, all_messages):
        """渲染一轮对话 - 复刻 DEV 版时间线样式"""
        user_msg, ai_msgs = round_data
        controls = []

        # 用户消息
        if user_msg:
            _, txt, _, _ = extract_content(user_msg)
            controls.append(render_timeline_message(txt, 'user', round_num, round_idx, all_messages))

        # AI 响应
        for msg in ai_msgs:
            role, txt, tool_blocks, _ = extract_content(msg)
            if role == 'assistant':
                if txt and txt.strip():
                    controls.append(render_timeline_message(txt, 'assistant'))
                # 工具调用
                for block in tool_blocks:
                    if block.get('type') == 'tool_use':
                        controls.append(render_tool_call(block))

        return controls

    def render_timeline_message(text, role, round_num=None, round_idx=None, all_messages=None):
        """渲染时间线消息 - 复刻 DEV 版 TimelineMessageItem"""
        is_user = role == 'user'
        theme = state.get_theme()

        # 颜色配置
        avatar_bg = ft.Colors.BLUE_500 if is_user else ft.Colors.GREEN_500
        bubble_bg = ft.Colors.with_opacity(0.06, ft.Colors.BLUE if is_user else ft.Colors.GREEN)
        border_color = ft.Colors.BLUE_500 if is_user else ft.Colors.GREEN_500
        line_color = ft.Colors.with_opacity(0.3, ft.Colors.BLUE if is_user else ft.Colors.GREEN)
        label = 'User' if is_user else 'Assistant'

        # 头像圆点
        avatar = ft.Container(
            ft.Text('👤' if is_user else '🤖', size=12),
            width=28, height=28, border_radius=14,
            bgcolor=avatar_bg, alignment=ft.alignment.center,
        )

        # 竖线连接
        line = ft.Container(width=2, height=40, bgcolor=line_color)

        # 消息气泡
        display_text = text[:500] if len(text) > 500 else text
        prefix = f"[{L.get('round', '轮')}{round_num}] " if round_num else ""

        # 标签行（包含删除按钮）
        label_row_items = [
            ft.Container(
                ft.Text(label, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                bgcolor=avatar_bg, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=4,
            ),
        ]

        # 只有 User 消息才显示删除按钮
        if is_user and round_idx is not None and all_messages is not None:
            def on_delete_round(e, idx=round_idx, msgs=all_messages):
                delete_round(idx, msgs)

            label_row_items.append(ft.Container(expand=True))
            label_row_items.append(ft.IconButton(
                ft.Icons.DELETE_OUTLINE,
                icon_size=16,
                icon_color=ft.Colors.RED_400,
                tooltip=L.get('delete_round', '删除本轮'),
                on_click=on_delete_round,
            ))

        bubble = ft.Container(
            ft.Column([
                ft.Row(label_row_items, spacing=4),
                ft.Text(prefix + display_text, size=12, selectable=True),
            ], spacing=6),
            bgcolor=bubble_bg, padding=12, border_radius=8,
            border=ft.border.only(left=ft.BorderSide(4, border_color)),
            expand=True,
        )

        return ft.Row([
            ft.Column([avatar, line], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bubble,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    def delete_round(round_idx, all_messages):
        """删除指定轮次的对话"""
        if not selected_session_data[0]:
            return

        data = selected_session_data[0]
        file_path = data['info'].get('file')
        if not file_path:
            show_snackbar(state.page, "无法获取会话文件路径")
            return

        def do_delete(_):
            state.page.close(dlg)
            try:
                import json

                # 读取原文件 - 支持 .jsonl 格式（每行一个 JSON）
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                # 判断文件格式
                if content.startswith('['):
                    original_messages = json.loads(content)
                    is_jsonl = False
                else:
                    original_messages = []
                    for line in content.split('\n'):
                        line = line.strip()
                        if line:
                            try:
                                original_messages.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
                    is_jsonl = True

                # 使用与 UI 完全相同的逻辑计算轮次（元组结构）
                rounds_in_ui = []
                current_round = None
                orphan_msgs = []
                for msg in all_messages:
                    role, _, _, is_real_user = extract_content(msg)
                    if role == 'user' and is_real_user:
                        if current_round:
                            rounds_in_ui.append(current_round)
                        current_round = (msg, [])
                    elif current_round:
                        current_round[1].append(msg)
                    else:
                        orphan_msgs.append(msg)
                if current_round:
                    rounds_in_ui.append(current_round)
                if orphan_msgs:
                    rounds_in_ui.insert(0, (None, orphan_msgs))

                if round_idx >= len(rounds_in_ui):
                    show_snackbar(state.page, "轮次索引无效")
                    return

                # 获取轮次起始 UUID
                user_msg, _ = rounds_in_ui[round_idx]
                if not user_msg:
                    show_snackbar(state.page, "无法删除孤儿消息")
                    return
                start_uuid = user_msg.get('uuid')
                if not start_uuid:
                    show_snackbar(state.page, "消息缺少 UUID")
                    return

                # 构建 parentUuid 索引（一次遍历）
                children_map = {}  # {parent_uuid: [child_uuids]}
                for msg in original_messages:
                    parent = msg.get('parentUuid')
                    if parent:
                        children_map.setdefault(parent, []).append(msg.get('uuid'))

                # 递归收集所有后代 UUID
                uuids_to_delete = set()
                def collect_descendants(uuid):
                    if uuid and uuid not in uuids_to_delete:
                        uuids_to_delete.add(uuid)
                        for child in children_map.get(uuid, []):
                            collect_descendants(child)

                collect_descendants(start_uuid)

                # 过滤消息（删除后代 + 关联的 file-history-snapshot，保留 system）
                new_messages = [
                    msg for msg in original_messages
                    if msg.get('uuid') not in uuids_to_delete
                    and not (msg.get('type') == 'file-history-snapshot'
                             and (msg.get('messageId') or msg.get('snapshot', {}).get('messageId')) in uuids_to_delete)
                ]

                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    if is_jsonl:
                        for msg in new_messages:
                            f.write(json.dumps(msg, ensure_ascii=False) + '\n')
                    else:
                        json.dump(new_messages, f, ensure_ascii=False, indent=2)

                show_snackbar(state.page, L.get('round_deleted', '已删除第 {} 轮对话').format(round_idx + 1))

                # 刷新显示 - 直接从 CC 系统文件重新读取
                loaded_projects.pop(data['group'], None)  # 清除本地缓存

                # 清除 Rust 内存缓存
                if lh is not None:
                    lh.clear_memory_cache()

                    # 刷新 Rust SQLite 缓存数据库（会自动检测文件修改并更新缓存）
                    cwd = data['info'].get('cwd', '')
                    if cwd:
                        lh.refresh_and_load_sessions(current_cli, cwd)

                # 直接从 CC 系统文件重新读取会话内容用于 UI 显示
                new_messages = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content.startswith('['):
                    new_messages = json.loads(content)
                else:
                    for line in content.split('\n'):
                        line = line.strip()
                        if line:
                            try:
                                new_messages.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass

                # 更新选中的会话信息并刷新右侧面板
                new_info = dict(data['info'])
                new_info['messages'] = new_messages
                selected_session_data[0]['info'] = new_info
                load_state['head'], load_state['tail'] = 3, 3  # 重置分页
                show_session_detail(new_info, data['session_id'])

                refresh_project_list()

            except Exception as ex:
                print(f"[delete_round] 错误: {ex}")
                show_snackbar(state.page, f"删除失败: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('confirm_delete', '确认删除')),
            content=ft.Text(L.get('confirm_delete_round', '确定要删除第 {} 轮对话吗？\n此操作不可恢复。').format(round_idx + 1)),
            actions=[
                ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: state.page.close(dlg)),
                ft.TextButton(L.get('delete', '删除'), on_click=do_delete, style=ft.ButtonStyle(color=ft.Colors.RED), autofocus=True),
            ],
        )
        state.page.open(dlg)

    def render_tool_call(block):
        """渲染工具调用 - 复刻 DEV 版 ToolCallItem"""
        name = block.get('name', 'unknown')
        inp = block.get('input', {})
        icon, _, bgcolor = TOOL_ICONS.get(name, ('🔧', '', ft.Colors.GREY_100))

        # 获取工具详情
        detail = ''
        if name in ('Read', 'Write', 'Edit'):
            detail = inp.get('file_path', '')
        elif name == 'Bash':
            detail = inp.get('command', '')[:60]
        elif name in ('Glob', 'Grep'):
            detail = inp.get('pattern', '')
        elif name == 'Task':
            detail = inp.get('description', '')

        expand_state = {'open': False}
        detail_col = ft.Column([], visible=False)

        def toggle_expand(_):
            expand_state['open'] = not expand_state['open']
            detail_col.visible = expand_state['open']
            if expand_state['open'] and not detail_col.controls:
                # 展开时显示详细内容
                if name == 'Edit':
                    old = inp.get('old_string', '')[:300]
                    new = inp.get('new_string', '')[:300]
                    detail_col.controls.append(ft.Column([
                        ft.Text("- " + old, size=10, color=ft.Colors.RED_400),
                        ft.Text("+ " + new, size=10, color=ft.Colors.GREEN_400),
                    ], spacing=4))
                else:
                    detail_col.controls.append(ft.Text(str(inp)[:500], size=10, selectable=True))
            state.page.update()

        return ft.Container(
            ft.Column([
                ft.Row([
                    ft.Text('▶' if not expand_state['open'] else '▼', size=10, color=ft.Colors.GREY_500),
                    ft.Text(f"{icon} {name}", size=11, weight=ft.FontWeight.W_500),
                    ft.Text(shorten_path(detail, 50), size=10, color=ft.Colors.GREY_600, expand=True),
                ], spacing=8),
                detail_col,
            ], spacing=4),
            bgcolor=bgcolor, padding=8, border_radius=6,
            margin=ft.margin.only(left=40, bottom=4),
            on_click=toggle_expand, ink=True,
        )

    # ==================== 辅助函数 ====================
    def open_folder(path):
        import subprocess, sys
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', path.replace('/', '\\')])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def export_session(fmt):
        if not selected_session_data[0]:
            show_snackbar(state.page, L.get('no_selection', '请先选择会话'))
            return
        from core.session_export import export_session_html, export_session_md
        data = selected_session_data[0]
        sid = data['session_id'][:12]
        def on_result(result):
            if result.path:
                try:
                    if fmt == 'html':
                        export_session_html(data, result.path)
                    else:
                        export_session_md(data, result.path)
                    show_snackbar(state.page, L.get('export_success', '导出成功'))
                except Exception as ex:
                    show_snackbar(state.page, str(ex))
        file_picker.on_result = on_result
        file_picker.save_file(file_name=f'session_{sid}.{fmt}', allowed_extensions=[fmt])

    def del_session():
        if not selected_session_data[0]:
            return
        data = selected_session_data[0]
        mgr = get_current_manager()
        if mgr and hasattr(mgr, 'delete_session'):
            mgr.delete_session(data['group'], data['session_id'], data['info'])
            loaded_projects.pop(data['group'], None)
            show_snackbar(state.page, L.get('history_moved', '已移至回收站'))
            refresh_project_list()

    def confirm_del_session():
        """删除会话前弹出确认对话框"""
        if not selected_session_data[0]:
            return
        data = selected_session_data[0]
        session_name = data.get('info', {}).get('cwd', data.get('session_id', ''))[:40]

        def do_delete(_):
            state.page.close(dlg)
            del_session()

        dlg = ft.AlertDialog(
            title=ft.Text(L.get('confirm_delete', '确认删除')),
            content=ft.Text(L.get('confirm_delete_msg', '确定要删除 "{}" 吗？').format(session_name)),
            actions=[
                ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: state.page.close(dlg)),
                ft.TextButton(L.get('delete', '删除'), on_click=do_delete, style=ft.ButtonStyle(color=ft.Colors.RED), autofocus=True),
            ],
        )
        state.page.open(dlg)

    # 共享 FilePicker
    file_picker = ft.FilePicker()
    state.page.overlay.append(file_picker)

    # ==================== 刷新函数 ====================
    def refresh_project_list(filter_text=''):
        project_list.controls.clear()
        expanded_projects.clear()
        loaded_projects.clear()
        session_item_refs.clear()  # 清空会话项引用缓存

        mgr = get_current_manager()
        if current_cli in ('gemini', 'aider'):
            project_list.controls.append(ft.Text(f'{current_cli.title()} 暂不支持', color=ft.Colors.ORANGE))
            state.page.update()
            return
        if not mgr:
            project_list.controls.append(ft.Text(f'{current_cli.title()} 目录不存在', color=ft.Colors.RED))
            state.page.update()
            return

        projects_data = mgr.list_projects(with_cwd=True, limit=50) if hasattr(mgr, 'list_projects') else []
        if not projects_data:
            project_list.controls.append(ft.Text(L.get('history_no_records', '无记录'), color=ft.Colors.GREY_500))
            state.page.update()
            return

        stats_text.value = f"{len(projects_data)} {L.get('history_projects', '项目')}"

        for item in projects_data:
            if isinstance(item, tuple):
                project_id, real_cwd = item
            else:
                project_id, real_cwd = item, ''
            display_path = real_cwd or project_id
            if filter_text and filter_text.lower() not in display_path.lower():
                continue
            project_list.controls.append(build_project_item(project_id, display_path))

        state.page.update()

    # ==================== 顶部控件 ====================
    cli_dropdown = ft.Dropdown(
        value=current_cli,
        options=[ft.dropdown.Option('claude', 'Claude'), ft.dropdown.Option('codex', 'Codex')],
        width=120,
    )

    def on_cli_change(_):
        nonlocal current_cli
        nc = cli_dropdown.value or 'claude'
        if nc != current_cli:
            current_cli = nc
            load_state['head'], load_state['tail'] = 3, 3
            # 清空右侧面板
            messages_container.controls.clear()
            detail_header.controls.clear()
            tool_stats_row.controls.clear()
            # 清空左侧缓存（关键修复）
            expanded_projects.clear()
            loaded_projects.clear()
            session_item_refs.clear()
            selected_session_id[0] = None
            selected_session_data[0] = None
        refresh_project_list(search_field.value or '')

    cli_dropdown.on_change = on_cli_change

    search_field = ft.TextField(hint_text=L.get('history_search', '搜索'), width=200, prefix_icon=ft.Icons.SEARCH)

    def do_search(keyword: str):
        """搜索会话内容"""
        if not keyword.strip():
            refresh_project_list('')
            return

        project_list.controls.clear()
        expanded_projects.clear()
        loaded_projects.clear()
        session_item_refs.clear()

        try:
            import liangmu_history as lh
            kw = keyword.strip()
            results = lh.search(current_cli, kw, 50)
            if not results:
                project_list.controls.append(ft.Text(f"未找到 '{keyword}'", color=ft.Colors.GREY_500))
                state.page.update()
                return

            stats_text.value = f"找到 {len(results)} 个会话"

            # 只显示会话列表，不加载内容（避免卡顿）
            for r in results:
                fp = Path(r.file_path)
                pid = fp.parent.name if fp.parent else r.id
                cwd = r.cwd or pid

                def make_click_handler(project_id, session_id, cwd_path, search_kw):
                    def handler(_):
                        # 点击后加载会话
                        mgr = get_current_manager()
                        if mgr:
                            sessions = mgr.load_project(project_id)
                            if session_id in sessions:
                                info = sessions[session_id]
                                selected_session_id[0] = session_id
                                selected_session_data[0] = info
                                load_state['head'], load_state['tail'] = 100, 100
                                build_message_timeline(info['messages'])
                                detail_header.controls.clear()
                                detail_header.controls.append(ft.Text(f"📁 {cwd_path} (搜索: {search_kw})", size=12, color=ft.Colors.GREY_600))
                                state.page.update()
                    return handler

                display = cwd[-60:] if len(cwd) > 60 else cwd
                project_list.controls.append(ft.Container(
                    ft.Text(display, size=12, color=ft.Colors.BLUE_400),
                    padding=8,
                    border_radius=4,
                    bgcolor=ft.Colors.GREY_900,
                    on_click=make_click_handler(pid, r.id, cwd, kw),
                    ink=True
                ))

            state.page.update()
        except Exception as e:
            project_list.controls.append(ft.Text(f"搜索失败: {e}", color=ft.Colors.RED))
            state.page.update()

    search_field.on_submit = lambda e: do_search(e.control.value or '')

    stats_text = ft.Text('', size=12, color=ft.Colors.GREY_600)

    def clear_empty_sessions(_):
        """深度清理：空会话、空文件夹、孤儿子代理等"""
        import json
        import os
        import shutil

        def count_user_turns_jsonl(file_path: str) -> int:
            """计算 JSONL 会话文件中的真实用户轮数"""
            try:
                turns = 0
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except:
                            continue
                        # Claude 格式
                        if msg.get('type') == 'user':
                            content = msg.get('message', {}).get('content', [])
                            has_tool_result = any(
                                isinstance(b, dict) and b.get('type') == 'tool_result'
                                for b in (content if isinstance(content, list) else [])
                            )
                            if not has_tool_result:
                                turns += 1
                        # Codex 格式
                        elif msg.get('role') == 'user':
                            content = msg.get('content', '')
                            if isinstance(content, str) or not any(
                                isinstance(b, dict) and b.get('type') == 'tool_result'
                                for b in (content if isinstance(content, list) else [])
                            ):
                                turns += 1
                return turns
            except Exception:
                return -1

        def get_agent_parent_session(agent_file: Path) -> str | None:
            """从 agent 文件获取父会话 ID"""
            try:
                with open(agent_file, 'r', encoding='utf-8') as f:
                    line = f.readline().strip()
                    if line:
                        msg = json.loads(line)
                        return msg.get('sessionId')
            except:
                pass
            return None

        def do_clear(_):
            state.page.close(dlg)
            stats = {
                'empty_sessions': 0,
                'orphan_agents': 0,
                'empty_folders': 0,
                'agent_only_folders': 0,
                'scanned': 0
            }

            try:
                # 获取存储目录
                if current_cli == 'claude':
                    base_dir = Path.home() / '.claude' / 'projects'
                elif current_cli == 'codex':
                    # Codex 使用 sessions 目录
                    base_dir = Path.home() / '.codex' / 'sessions'
                else:
                    base_dir = Path.home() / '.claude' / 'projects'

                if not base_dir.exists():
                    show_snackbar(state.page, f"目录不存在: {base_dir}")
                    return

                # ========== 单遍扫描：收集文件信息并记录轮数 ==========
                # 优化：避免重复计算轮数
                all_valid_session_ids = set()  # 有效会话 ID（跨项目）
                session_turns_cache = {}  # {file_path: turns} 缓存轮数
                project_dirs = [d for d in base_dir.iterdir() if d.is_dir()]

                for project_dir in project_dirs:
                    for f in project_dir.glob('*.jsonl'):
                        if f.name.startswith('agent-'):
                            continue  # 跳过 agent 文件
                        stats['scanned'] += 1

                        # 计算轮数并缓存
                        size = f.stat().st_size
                        if size == 0:
                            session_turns_cache[f] = 0
                        else:
                            turns = count_user_turns_jsonl(str(f))
                            session_turns_cache[f] = turns
                            if turns > 0:
                                all_valid_session_ids.add(f.stem)

                # ========== 执行清理（使用缓存的轮数） ==========
                folders_to_remove = []

                for project_dir in project_dirs:
                    session_files = []
                    agent_files = []

                    for f in project_dir.glob('*.jsonl'):
                        if f.name.startswith('agent-'):
                            agent_files.append(f)
                        else:
                            session_files.append(f)

                    # 1. 清理空会话文件（使用缓存的轮数，不再重复计算）
                    for sf in session_files:
                        turns = session_turns_cache.get(sf, -1)
                        if turns == 0:
                            sf.unlink()
                            stats['empty_sessions'] += 1
                            print(f"[清理] 删除空会话: {sf}")

                    # 2. 清理孤儿子代理（父会话不存在或无法解析）
                    for af in agent_files:
                        parent_id = get_agent_parent_session(af)
                        # parent_id 为 None（解析失败）或不在全局有效会话中，都视为孤儿
                        if not parent_id or parent_id not in all_valid_session_ids:
                            af.unlink()
                            stats['orphan_agents'] += 1
                            reason = "无法解析" if not parent_id else f"父会话 {parent_id} 不存在"
                            print(f"[清理] 删除孤儿子代理: {af} ({reason})")

                    # 3. 检查文件夹状态
                    remaining_files = list(project_dir.glob('*.jsonl'))
                    if not remaining_files:
                        folders_to_remove.append(('empty', project_dir))
                    elif all(f.name.startswith('agent-') for f in remaining_files):
                        # 只有子代理文件（理论上不会走到这里，因为上面已经删除了孤儿）
                        for f in remaining_files:
                            f.unlink()
                            stats['orphan_agents'] += 1
                            print(f"[清理] 删除无主子代理: {f}")
                        folders_to_remove.append(('agent_only', project_dir))

                # 4. 删除标记的空文件夹
                for folder_type, folder in folders_to_remove:
                    try:
                        remaining = list(folder.iterdir())
                        if not remaining:
                            folder.rmdir()
                            if folder_type == 'empty':
                                stats['empty_folders'] += 1
                            else:
                                stats['agent_only_folders'] += 1
                            print(f"[清理] 删除空文件夹: {folder}")
                        else:
                            print(f"[清理] 跳过非空文件夹: {folder} (剩余 {len(remaining)} 个文件)")
                    except Exception as e:
                        print(f"[清理] 删除文件夹失败: {folder}, {e}")

                # 5. 同步清理 Rust 缓存
                if lh:
                    try:
                        lh.clear_memory_cache()
                        print("[清理] 已清除 Rust 内存缓存")
                    except Exception as e:
                        print(f"[清理] 清除 Rust 缓存失败: {e}")

                # 显示结果
                msg = L.get('deep_clean_result', '深度清理完成').format(
                    empty=stats['empty_sessions'],
                    orphan=stats['orphan_agents'],
                    folders=stats['empty_folders'] + stats['agent_only_folders']
                )
                show_snackbar(state.page, msg)
                refresh_project_list()

            except Exception as ex:
                import traceback
                traceback.print_exc()
                show_snackbar(state.page, f"清理失败: {ex}")
        dlg = ft.AlertDialog(
            title=ft.Text(L.get('confirm_deep_clean', '确认深度清理')),
            content=ft.Text(L.get('confirm_deep_clean_desc',
                '将清理以下内容：\n'
                '• 空会话文件（0轮对话）\n'
                '• 孤儿子代理（父对话已删除）\n'
                '• 只有子代理的空文件夹\n'
                '• 完全空的项目文件夹\n\n'
                '此操作不可恢复，是否继续？')),
            actions=[
                ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: state.page.close(dlg)),
                ft.TextButton(L.get('confirm', '确认'), on_click=do_clear, autofocus=True)
            ],
        )
        state.page.open(dlg)

    def show_trash(_):
        """显示回收站"""
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

        def build_list():
            trash_list.controls.clear()
            for i, item in enumerate(items):
                deleted_at = datetime.fromtimestamp(item['deleted_at'])
                days_left = max(0, TRASH_RETENTION_DAYS - (now - item['deleted_at']) / 86400)
                is_sel = i in selected_trash
                tile = ft.Container(
                    ft.Row([
                        ft.Checkbox(value=is_sel, on_change=lambda e, idx=i: toggle(idx, e.control.value)),
                        ft.Column([
                            ft.Text(f"{item['session_id'][:12]}...", weight=ft.FontWeight.BOLD if is_sel else None),
                            ft.Text(f"{deleted_at.strftime('%m-%d %H:%M')} | {days_left:.0f}天", size=11, color=ft.Colors.GREY_500),
                        ], spacing=2, expand=True),
                    ], spacing=8),
                    padding=8, bgcolor=ft.Colors.RED_50 if is_sel else None, border_radius=4,
                )
                trash_list.controls.append(tile)
            state.page.update()

        def toggle(idx, checked):
            if checked:
                selected_trash.add(idx)
            else:
                selected_trash.discard(idx)
            build_list()

        def restore(_):
            for idx in selected_trash:
                mgr.trash_manager.restore_from_trash(items[idx])
            state.page.close(dlg)
            refresh_project_list()

        def perm_delete(_):
            for idx in selected_trash:
                mgr.trash_manager.permanently_delete(items[idx])
            state.page.close(dlg)

        build_list()
        dlg = ft.AlertDialog(
            title=ft.Text(L.get('history_trash', '回收站')),
            content=ft.Container(trash_list, width=400, height=300),
            actions=[
                ft.TextButton(L.get('history_restore', '恢复'), on_click=restore),
                ft.TextButton(L.get('history_perm_delete', '永久删除'), on_click=perm_delete),
                ft.TextButton(L.get('cancel', '取消'), on_click=lambda _: state.page.close(dlg)),
            ],
        )
        state.page.open(dlg)

    # ==================== 构建页面布局 ====================
    # 左侧边栏
    sidebar_container.content = ft.Container(
        project_list,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY)),
        border_radius=8, padding=0,
    )

    # 右侧详情面板
    detail_panel.controls = [
        detail_header,
        tool_stats_row,
        ft.Divider(height=1),
        messages_container,
    ]

    right_panel = ft.Container(
        detail_panel,
        expand=True,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY)),
        border_radius=8, padding=12,
    )

    # 主布局
    history_page = ft.Column([
        # 标题栏
        ft.Row([
            ft.Text(L.get('history', '历史记录'), size=18, weight=ft.FontWeight.BOLD),
            cli_dropdown,
            search_field,
            ft.TextButton(L.get('refresh', '刷新'), icon=ft.Icons.REFRESH, on_click=lambda _: refresh_project_list()),
            stats_text,
            ft.Container(expand=True),
            ft.TextButton(L.get('deep_clean', '深度清理'), icon=ft.Icons.CLEANING_SERVICES, on_click=clear_empty_sessions),
            ft.TextButton(L.get('history_trash', '回收站'), icon=ft.Icons.DELETE_OUTLINE, on_click=show_trash),
        ], spacing=12),
        # 主内容区
        ft.Row([
            sidebar_container,
            right_panel,
        ], expand=True, spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
    ], expand=True, spacing=12)

    return history_page, refresh_project_list
