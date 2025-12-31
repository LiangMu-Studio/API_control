# AI CLI Manager - UI Common Module
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3

VERSION = "2.2"

import flet as ft
import json
import os
import subprocess
import sys
import shutil
import re
import urllib.request
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import time
import threading

DEBUG = False
TRASH_RETENTION_DAYS = 7

# ========== 主题配置 ==========
THEMES = {
    "light": {
        "bg": "#f8f9fa",
        "surface": "#ffffff",
        "text": "#333333",
        "text_sec": "#666666",
        "primary": "#607d8b",
        "border": "#e0e0e0",
        "header_bg": ft.Colors.GREY_100,
        "selection_bg": ft.Colors.BLUE_50,
        "icon_cli": ft.Colors.BLUE,
        "icon_endpoint": ft.Colors.GREEN,
        "icon_key_selected": ft.Colors.ORANGE,
        "text_selected": ft.Colors.BLUE,
        "global_bg": ft.Colors.PURPLE_50,
        "global_border": ft.Colors.PURPLE_200,
        "global_icon": ft.Colors.PURPLE,
    },
    "dark": {
        "bg": "#1e1e1e",
        "surface": "#252526",
        "text": "#cccccc",
        "text_sec": "#999999",
        "primary": "#546e7a",
        "border": "#3e3e42",
        "header_bg": "#2d2d30",
        "selection_bg": "#2f3d58",
        "icon_cli": "#64b5f6",
        "icon_endpoint": "#81c784",
        "icon_key_selected": "#ffb74d",
        "text_selected": "#64b5f6",
        "global_bg": "#2d2535",
        "global_border": "#4a3d5c",
        "global_icon": "#9575cd",
    }
}

def debug_print(msg):
    if DEBUG:
        print(f"[{time.time():.3f}] {msg}")

# ========== 配置文件路径 ==========
CONFIG_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
MCP_FILE = CONFIG_DIR / "mcp.json"
MCP_REGISTRY_FILE = CONFIG_DIR / "mcp_registry.json"
DB_FILE = CONFIG_DIR / "prompts.db"
CONFIG_DIR.mkdir(exist_ok=True)

MCP_DATA_DIR = Path(__file__).parent.parent / "mcp_data"
MCP_DATA_DIR.mkdir(exist_ok=True)
MCP_DB_FILE = MCP_DATA_DIR / "mcp_registry.db"

CLAUDE_DIR = Path(os.path.expanduser("~")) / ".claude"
CODEX_DIR = Path(os.path.expanduser("~")) / ".codex"
KIRO_DIR = Path(os.path.expanduser("~")) / ".kiro"

# ========== 提示词标识符 ==========
SYSTEM_PROMPT_START = "<!-- GLOBAL_PROMPT_START -->"
SYSTEM_PROMPT_END = "<!-- GLOBAL_PROMPT_END -->"
USER_PROMPT_START = "<!-- USER_PROMPT_START:{id} -->"
USER_PROMPT_END = "<!-- USER_PROMPT_END -->"

# ========== CLI 工具定义 ==========
CLI_TOOLS = {
    'claude': {
        'name': 'Claude Code',
        'command': 'claude',
        'default_key_name': 'ANTHROPIC_API_KEY',
        'default_endpoint': 'https://api.anthropic.com',
        'base_url_env': 'ANTHROPIC_BASE_URL',
        'prompt_file': 'CLAUDE.md',
        'prompt_dir': '.claude',
    },
    'codex': {
        'name': 'Codex CLI',
        'command': 'codex',
        'default_key_name': 'OPENAI_API_KEY',
        'default_endpoint': 'https://api.openai.com/v1',
        'base_url_env': 'OPENAI_BASE_URL',
        'prompt_file': 'AGENTS.md',
        'prompt_dir': '.codex',
    },
    'gemini': {
        'name': 'Gemini CLI',
        'command': 'gemini',
        'default_key_name': 'GEMINI_API_KEY',
        'default_endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'base_url_env': 'GEMINI_BASE_URL',
        'prompt_file': 'GEMINI.md',
        'prompt_dir': '.gemini',
    },
    'aider': {
        'name': 'Aider',
        'command': 'aider',
        'default_key_name': 'OPENAI_API_KEY',
        'default_endpoint': 'https://api.openai.com/v1',
        'base_url_env': 'OPENAI_BASE_URL',
        'prompt_file': '.aider.conf.yml',
        'prompt_dir': '',
    }
}

# ========== 内置提示词 ==========
BUILTIN_PROMPTS = {
    'blank': {
        'name': {'zh': '空白', 'en': 'Blank'},
        'content': '',
        'category': {'zh': '用户', 'en': 'User'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_general': {
        'name': {'zh': '通用编程', 'en': 'General Coding'},
        'content': {
            'zh': '你是一个专业的编程助手。提供高质量的代码示例和解释。遵循最佳实践和设计模式。考虑性能、安全性和可维护性。提供完整的、可运行的代码。',
            'en': 'You are a professional coding assistant. Provide high-quality code examples and explanations. Follow best practices and design patterns. Consider performance, security, and maintainability. Provide complete, runnable code.'
        },
        'category': {'zh': '编程', 'en': 'Coding'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_debug': {
        'name': {'zh': '代码调试', 'en': 'Code Debug'},
        'content': {
            'zh': '你是一个代码调试专家。帮助用户找出代码中的问题。提供清晰的错误分析和解决方案。逐步解释问题的原因和修复方法。',
            'en': 'You are a code debugging expert. Help users find issues in their code. Provide clear error analysis and solutions. Explain the cause and fix step by step.'
        },
        'category': {'zh': '编程', 'en': 'Coding'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_review': {
        'name': {'zh': '代码审查', 'en': 'Code Review'},
        'content': {
            'zh': '你是一个资深的代码审查员。分析代码质量、可读性和性能。提供具体的改进建议。指出潜在的问题和优化机会。',
            'en': 'You are a senior code reviewer. Analyze code quality, readability, and performance. Provide specific improvement suggestions. Point out potential issues and optimization opportunities.'
        },
        'category': {'zh': '编程', 'en': 'Coding'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_article': {
        'name': {'zh': '文章写作', 'en': 'Article Writing'},
        'content': {
            'zh': '你是一个专业的文章写手。帮助用户撰写高质量的文章。确保逻辑清晰、表达准确。提供结构建议和内容优化。',
            'en': 'You are a professional article writer. Help users write high-quality articles. Ensure clear logic and accurate expression. Provide structure suggestions and content optimization.'
        },
        'category': {'zh': '写作', 'en': 'Writing'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_creative': {
        'name': {'zh': '创意写作', 'en': 'Creative Writing'},
        'content': {
            'zh': '你是一个创意写作专家。帮助用户创作故事、诗歌或其他创意内容。提供灵感和创意建议。确保内容生动有趣。',
            'en': 'You are a creative writing expert. Help users create stories, poems, or other creative content. Provide inspiration and creative suggestions. Ensure content is vivid and engaging.'
        },
        'category': {'zh': '写作', 'en': 'Writing'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_data': {
        'name': {'zh': '数据分析', 'en': 'Data Analysis'},
        'content': {
            'zh': '你是一个数据分析专家。深入分析数据和趋势。提供数据支持的观点和结论。用清晰的方式解释复杂的数据。',
            'en': 'You are a data analysis expert. Deeply analyze data and trends. Provide data-supported insights and conclusions. Explain complex data in a clear way.'
        },
        'category': {'zh': '分析', 'en': 'Analysis'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_summary': {
        'name': {'zh': '内容总结', 'en': 'Content Summary'},
        'content': {
            'zh': '你是一个内容总结专家。快速提取关键信息。用简洁的方式总结复杂内容。突出重点和核心观点。',
            'en': 'You are a content summarization expert. Quickly extract key information. Summarize complex content concisely. Highlight key points and core insights.'
        },
        'category': {'zh': '分析', 'en': 'Analysis'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'image_prompt': {
        'name': {'zh': '绘画提示词', 'en': 'Image Prompt'},
        'content': {
            'zh': '你是AI绘画提示词专家。根据用户提供的文案，生成适合AI绘图的英文提示词。\n\n风格要求：治愈系、卡通漫画、线条画、扁平插画\n\n直接输出英文提示词，不需要解释。\n\n输出格式：[主体描述], [风格], [色彩], [氛围], [细节]',
            'en': 'You are an AI image prompt expert. Generate English prompts suitable for AI image generation based on user input.\n\nStyle: healing, cartoon, line art, flat illustration\n\nOutput English prompts directly, no explanation needed.\n\nFormat: [subject], [style], [colors], [mood], [details]'
        },
        'category': {'zh': '绘画', 'en': 'Art'},
        'is_builtin': True, 'prompt_type': 'user'
    },
}

# ========== 官方 MCP 服务器 ==========
OFFICIAL_MCP_SERVERS = [
    {'name': 'Filesystem', 'package': '@modelcontextprotocol/server-filesystem', 'desc': '文件系统读写', 'args_hint': '/path/to/dir'},
    {'name': 'Fetch', 'package': '@modelcontextprotocol/server-fetch', 'desc': '网页内容获取'},
    {'name': 'Memory', 'package': '@modelcontextprotocol/server-memory', 'desc': '长期记忆存储'},
    {'name': 'Sequential Thinking', 'package': '@modelcontextprotocol/server-sequential-thinking', 'desc': '深度思考推理'},
]

MCP_MARKETPLACES = [
    {'name': 'Smithery', 'url': 'https://smithery.ai/', 'desc': '最大的 MCP 服务器市场'},
    {'name': 'MCP.so', 'url': 'https://mcp.so/', 'desc': 'MCP 服务器目录'},
    {'name': 'Glama', 'url': 'https://glama.ai/mcp/servers', 'desc': 'MCP 服务器列表'},
    {'name': 'GitHub Official', 'url': 'https://github.com/modelcontextprotocol/servers', 'desc': '官方服务器仓库'},
]

# ========== 工具函数 ==========
def get_localized(value, lang='zh'):
    if isinstance(value, dict):
        return value.get(lang, value.get('zh', value.get('en', '')))
    return value

def load_configs():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('configurations', [])
    return []

def save_configs(configs):
    data = {'version': '1.0', 'configurations': configs}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_prompts(lang='zh'):
    custom = {}
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            custom = json.load(f)
    all_prompts = {}
    for pid, p in BUILTIN_PROMPTS.items():
        all_prompts[pid] = {
            'id': pid,
            'name': get_localized(p.get('name', ''), lang),
            'content': get_localized(p.get('content', ''), lang),
            'category': get_localized(p.get('category', ''), lang),
            'is_builtin': p.get('is_builtin', False),
            'prompt_type': p.get('prompt_type', 'user'),
        }
    for pid, p in custom.items():
        all_prompts[pid] = {**p, 'id': pid}
    return all_prompts

def save_prompts(prompts):
    custom = {k: v for k, v in prompts.items() if not v.get('is_builtin')}
    with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(custom, f, indent=2, ensure_ascii=False)

def load_mcp():
    if MCP_FILE.exists():
        with open(MCP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_mcp(mcp_list):
    with open(MCP_FILE, 'w', encoding='utf-8') as f:
        json.dump(mcp_list, f, indent=2, ensure_ascii=False)

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def detect_terminals():
    terminals = []
    if sys.platform == 'win32':
        candidates = [
            ('Windows Terminal', 'wt.exe'),
            ('PowerShell', 'powershell.exe'),
            ('CMD', 'cmd.exe'),
        ]
        for name, exe in candidates:
            if shutil.which(exe):
                terminals.append({'name': name, 'command': exe})
    else:
        candidates = [
            ('GNOME Terminal', 'gnome-terminal'),
            ('Konsole', 'konsole'),
            ('xterm', 'xterm'),
            ('Terminal', 'open -a Terminal'),
        ]
        for name, cmd in candidates:
            if shutil.which(cmd.split()[0]):
                terminals.append({'name': name, 'command': cmd})
    return terminals

def detect_python_envs():
    envs = []
    try:
        result = subprocess.run(['conda', 'env', 'list', '--json'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for env_path in data.get('envs', []):
                env_name = Path(env_path).name
                envs.append({'name': f'conda: {env_name}', 'path': env_path, 'type': 'conda'})
    except:
        pass
    return envs

def get_prompt_file_path(cli_type: str) -> Path:
    cli = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
    home = Path.home()
    if cli['prompt_dir']:
        return home / cli['prompt_dir'] / cli['prompt_file']
    return home / cli['prompt_file']

def write_prompt_to_cli(cli_type: str, system_content: str, user_content: str, user_id: str, workdir: str | None = None) -> Path:
    cli = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
    if workdir:
        file_path = Path(workdir) / cli['prompt_file']
    else:
        file_path = get_prompt_file_path(cli_type)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    parts = []
    if system_content.strip():
        parts.append(f"{SYSTEM_PROMPT_START}\n{system_content}\n{SYSTEM_PROMPT_END}")
    if user_content.strip():
        user_start = USER_PROMPT_START.format(id=user_id)
        parts.append(f"{user_start}\n{user_content}\n{USER_PROMPT_END}")
    wrapped = "\n\n".join(parts)

    existing = ""
    if file_path.exists():
        existing = file_path.read_text(encoding='utf-8')

    for marker_start, marker_end in [
        (SYSTEM_PROMPT_START, SYSTEM_PROMPT_END),
        (r'<!-- USER_PROMPT_START:[^>]+ -->', USER_PROMPT_END),
        (r'【LiangMu 用户提示词 Start - ID:[^】]+】', r'【LiangMu 用户提示词 End】'),
        (r'【LiangMu-Studio Prompt Start】', r'【LiangMu-Studio Prompt End】'),
    ]:
        pattern = re.escape(marker_start) if marker_start.startswith('<!--') and '[' not in marker_start else marker_start
        pattern += r'.*?'
        pattern += re.escape(marker_end) if marker_end.startswith('<!--') else marker_end
        existing = re.sub(pattern, '', existing, flags=re.DOTALL)

    existing = re.sub(r'\n{3,}', '\n\n', existing.strip())
    new_content = (existing + "\n\n" + wrapped).strip() + "\n"
    file_path.write_text(new_content, encoding='utf-8')
    return file_path

def detect_prompt_from_file(file_path: Path) -> tuple[str | None, str | None, str | None]:
    if not file_path.exists():
        return None, None, None
    content = file_path.read_text(encoding='utf-8')
    system_content = None
    user_content = None
    user_id = None

    sys_pattern = re.escape(SYSTEM_PROMPT_START) + r'(.*?)' + re.escape(SYSTEM_PROMPT_END)
    sys_match = re.search(sys_pattern, content, re.DOTALL)
    if sys_match:
        system_content = sys_match.group(1).strip()

    user_pattern = r'<!-- USER_PROMPT_START:([^>]+) -->(.*?)' + re.escape(USER_PROMPT_END)
    user_match = re.search(user_pattern, content, re.DOTALL)
    if user_match:
        user_id = user_match.group(1).strip()
        user_content = user_match.group(2).strip()

    return system_content, user_content, user_id
