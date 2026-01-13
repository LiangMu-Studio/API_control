# AI CLI Manager - State Management
import flet as ft
import json
from pathlib import Path
from .common import (
    VERSION, THEMES, CONFIG_FILE, SETTINGS_FILE, DB_FILE, PROMPTS_FILE,
    CLI_TOOLS, BUILTIN_PROMPTS, OFFICIAL_MCP_SERVERS, MCP_MARKETPLACES,
    load_configs, save_configs, load_prompts, save_prompts,
    load_settings, save_settings, detect_terminals, detect_python_envs,
    get_localized, get_prompt_file_path, write_prompt_to_cli, detect_prompt_from_file,
    SYSTEM_PROMPT_START, SYSTEM_PROMPT_END, USER_PROMPT_START, USER_PROMPT_END
)
from .lang import LANG
from .database import PromptDB, mcp_registry, history_manager, codex_history_manager, history_cache, migrate_mcp_list_to_library, load_mcp_from_json


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
        self.prompts = self.prompt_db.get_by_lang(self.lang)
        # 迁移旧 MCP JSON 数据到数据库（仅首次运行时执行）
        old_mcp_list = load_mcp_from_json()
        if old_mcp_list:
            migrate_mcp_list_to_library(old_mcp_list)

        # 终端和环境缓存（确保是字典类型，兼容旧版列表格式）
        terminals_cache = self.settings.get('terminals_cache', {})
        terminals_cache = terminals_cache if isinstance(terminals_cache, dict) else {}
        # 过滤掉 Windows Terminal（它是终端管理器，不是终端）
        self.terminals = {k: v for k, v in terminals_cache.items() if 'windows terminal' not in k.lower()}
        envs_cache = self.settings.get('envs_cache', {})
        self.python_envs = envs_cache if isinstance(envs_cache, dict) else {}

        # 选择状态
        self.selected_config = None
        self.selected_endpoint = None
        self.selected_cli = None
        self.selected_prompt = None

        # 展开状态
        self.expanded_cli = {}
        self.expanded_endpoint = {}

        # 树结构缓存
        self._tree_cache = None
        self._tree_cache_hash = None

        # UI 组件引用（由页面设置）
        self.config_tree = None
        self.current_key_label = None
        self.prompt_list = None
        self.prompt_content = None

    def _init_builtin_prompts(self):
        """初始化内置提示词 - 中英文分离存储"""
        for pid, p in BUILTIN_PROMPTS.items():
            # 为每种语言创建独立的提示词
            for lang in ['zh', 'en']:
                lang_pid = f"{pid}_{lang}"
                self.prompt_db.save({
                    'id': lang_pid,
                    'name': get_localized(p.get('name', ''), lang),
                    'content': get_localized(p.get('content', ''), lang),
                    'category': get_localized(p.get('category', ''), lang),
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
        self.refresh_prompts()

    def save_configs(self):
        """保存配置并使缓存失效"""
        save_configs(self.configs)
        self._tree_cache = None  # 使缓存失效

    def refresh_prompts(self):
        """刷新提示词（按当前语言）"""
        self.prompts = self.prompt_db.get_by_lang(self.lang)

    def build_tree_structure(self):
        """构建三级树形结构：CLI工具 → API端点 → 配置项（带缓存）"""
        # 简单缓存：configs 长度和内容 hash
        cache_key = (len(self.configs), id(self.configs))
        if self._tree_cache is not None and self._tree_cache_hash == cache_key:
            return self._tree_cache

        tree = {}
        for i, cfg in enumerate(self.configs):
            # 兼容新旧配置格式：优先从 provider.type 映射
            cli_type = cfg.get('cli_type')
            if not cli_type:
                provider_type = cfg.get('provider', {}).get('type', 'anthropic')
                type_to_cli = {'anthropic': 'claude', 'glm': 'claude', 'gemini': 'gemini', 'openai': 'codex', 'deepseek': 'codex'}
                cli_type = type_to_cli.get(provider_type, 'claude')
            endpoint = cfg.get('provider', {}).get('endpoint', '未知端点')
            if cli_type not in tree:
                tree[cli_type] = {}
            if endpoint not in tree[cli_type]:
                tree[cli_type][endpoint] = []
            tree[cli_type][endpoint].append((i, cfg))

        self._tree_cache = tree
        self._tree_cache_hash = cache_key
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
