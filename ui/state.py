# AI CLI Manager - State Management
import flet as ft
from .common import (
    VERSION, THEMES, CONFIG_FILE, SETTINGS_FILE, DB_FILE, PROMPTS_FILE,
    CLI_TOOLS, BUILTIN_PROMPTS, OFFICIAL_MCP_SERVERS, MCP_MARKETPLACES,
    load_configs, save_configs, load_prompts, save_prompts, load_mcp, save_mcp,
    load_settings, save_settings, detect_terminals, detect_python_envs,
    get_localized, get_prompt_file_path, write_prompt_to_cli, detect_prompt_from_file,
    SYSTEM_PROMPT_START, SYSTEM_PROMPT_END, USER_PROMPT_START, USER_PROMPT_END
)
from .lang import LANG
from .database import PromptDB, mcp_registry, history_manager, codex_history_manager, history_cache


class AppState:
    """应用全局状态管理"""
    def __init__(self, page: ft.Page):
        self.page = page

        # 加载设置
        self.settings = load_settings()
        self.lang = self.settings.get('lang', 'zh')
        self.L = LANG[self.lang]
        self.theme_mode = self.settings.get('theme', 'light')

        # 加载数据
        self.configs = load_configs()
        self.prompt_db = PromptDB(DB_FILE)
        self._init_builtin_prompts()
        self.prompts = self.prompt_db.get_all()
        self.mcp_list = load_mcp()

        # 终端和环境缓存
        self.terminals = self.settings.get('terminals_cache', {})
        self.python_envs = self.settings.get('envs_cache', {})

        # 选择状态
        self.selected_config = None
        self.selected_endpoint = None
        self.selected_cli = None
        self.selected_prompt = None
        self.selected_mcp = None

        # 展开状态
        self.expanded_cli = {}
        self.expanded_endpoint = {}

        # UI 组件引用（由页面设置）
        self.config_tree = None
        self.current_key_label = None
        self.prompt_list = None
        self.prompt_content = None
        self.mcp_list_view = None

    def _init_builtin_prompts(self):
        """初始化内置提示词"""
        for pid, p in BUILTIN_PROMPTS.items():
            if not self.prompt_db.get_all().get(pid):
                self.prompt_db.save({
                    'id': pid,
                    'name': get_localized(p.get('name', ''), self.lang),
                    'content': get_localized(p.get('content', ''), self.lang),
                    'category': get_localized(p.get('category', ''), self.lang),
                    'is_builtin': p.get('is_builtin', False),
                    'prompt_type': p.get('prompt_type', 'user'),
                })
        # 从旧 JSON 迁移
        if PROMPTS_FILE.exists():
            old_prompts = load_prompts(self.lang)
            self.prompt_db.migrate_from_json(old_prompts)

    def get_theme(self):
        """获取当前主题配置"""
        return THEMES[self.theme_mode]

    def toggle_theme(self):
        """切换主题"""
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        self.settings['theme'] = self.theme_mode
        save_settings(self.settings)

    def toggle_lang(self):
        """切换语言"""
        self.lang = 'en' if self.lang == 'zh' else 'zh'
        self.L = LANG[self.lang]
        self.settings['lang'] = self.lang
        save_settings(self.settings)

    def save_configs(self):
        """保存配置"""
        save_configs(self.configs)

    def save_mcp(self):
        """保存 MCP 列表"""
        save_mcp(self.mcp_list)

    def refresh_prompts(self):
        """刷新提示词"""
        self.prompts = self.prompt_db.get_all()

    def build_tree_structure(self):
        """构建三级树形结构：CLI工具 → API端点 → 配置项"""
        tree = {}
        for i, cfg in enumerate(self.configs):
            cli_type = cfg.get('cli_type', 'claude')
            endpoint = cfg.get('provider', {}).get('endpoint', '未知端点')
            if cli_type not in tree:
                tree[cli_type] = {}
            if endpoint not in tree[cli_type]:
                tree[cli_type][endpoint] = []
            tree[cli_type][endpoint].append((i, cfg))
        return tree

    def select_cli(self, cli_key):
        """选择一级 CLI"""
        self.selected_cli = cli_key
        self.selected_endpoint = None
        self.selected_config = None
        if self.current_key_label:
            self.current_key_label.value = f"CLI: {CLI_TOOLS.get(cli_key, {}).get('name', cli_key)}"

    def select_endpoint(self, endpoint_key):
        """选择二级端点"""
        self.selected_cli = endpoint_key.split(':', 1)[0]
        self.selected_endpoint = endpoint_key
        self.selected_config = None
        if self.current_key_label:
            self.current_key_label.value = f"Endpoint: {endpoint_key.split(':', 1)[1][:30]}"

    def select_config(self, idx):
        """选择三级配置项"""
        self.selected_config = idx
        if self.current_key_label:
            if idx is not None and idx < len(self.configs):
                self.current_key_label.value = self.configs[idx].get('label', self.L['not_selected'])
            else:
                self.current_key_label.value = self.L['not_selected']

    def toggle_cli(self, cli_key):
        """切换 CLI 展开状态"""
        self.expanded_cli[cli_key] = not self.expanded_cli.get(cli_key, True)

    def toggle_endpoint(self, endpoint_key):
        """切换端点展开状态"""
        self.expanded_endpoint[endpoint_key] = not self.expanded_endpoint.get(endpoint_key, True)
