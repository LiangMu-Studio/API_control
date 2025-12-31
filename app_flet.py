# LiangMu-Studio API Key Manager - Flet Version
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3

VERSION = "2.1"

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
from datetime import datetime
import time  # DEBUG

DEBUG = False  # 调试开关

def debug_print(msg):
    if DEBUG:
        print(f"[{time.time():.3f}] {msg}")

# 配置文件路径
CONFIG_DIR = Path(__file__).parent / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
MCP_FILE = CONFIG_DIR / "mcp.json"
MCP_REGISTRY_FILE = CONFIG_DIR / "mcp_registry.json"  # 本地 MCP 仓库缓存
DB_FILE = CONFIG_DIR / "prompts.db"
CONFIG_DIR.mkdir(exist_ok=True)

# ========== SQLite 提示词数据库 ==========
class PromptDB:
    """提示词数据库管理"""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT '用户',
                prompt_type TEXT DEFAULT 'user',  -- 'system' 或 'user'
                is_builtin INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )''')
            conn.commit()

    def get_all(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM prompts ORDER BY prompt_type DESC, name').fetchall()
        return {r['id']: dict(r) for r in rows}

    def get_by_type(self, prompt_type: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM prompts WHERE prompt_type=? ORDER BY name', (prompt_type,)).fetchall()
        return {r['id']: dict(r) for r in rows}

    def get_system_prompt(self) -> dict | None:
        """获取系统/全局提示词（只有一个）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM prompts WHERE prompt_type="system" LIMIT 1').fetchone()
        return dict(row) if row else None

    def save(self, prompt: dict):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''INSERT OR REPLACE INTO prompts
                (id, name, content, category, prompt_type, is_builtin, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM prompts WHERE id=?), ?), ?)''',
                (prompt['id'], prompt['name'], prompt.get('content', ''),
                 prompt.get('category', '用户'), prompt.get('prompt_type', 'user'),
                 1 if prompt.get('is_builtin') else 0, prompt['id'], now, now))
            conn.commit()

    def delete(self, prompt_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM prompts WHERE id=? AND is_builtin=0', (prompt_id,))
            conn.commit()

    def migrate_from_json(self, json_prompts: dict):
        """从旧 JSON 格式迁移数据"""
        for pid, p in json_prompts.items():
            if not self.get_all().get(pid):
                self.save({
                    'id': pid,
                    'name': p.get('name', pid),
                    'content': p.get('content', ''),
                    'category': p.get('category', '用户'),
                    'prompt_type': 'user',
                    'is_builtin': p.get('is_builtin', False),
                })

# ========== MCP 本地仓库管理 (SQLite + FTS5) ==========
MCP_DATA_DIR = Path(__file__).parent / "mcp_data"  # 单独文件夹，可同步
MCP_DATA_DIR.mkdir(exist_ok=True)
MCP_DB_FILE = MCP_DATA_DIR / "mcp_registry.db"

class MCPRegistry:
    """MCP 本地仓库 - SQLite + FTS5 全文搜索"""

    CATEGORY_MAP = {
        # 文件系统 - 文件读写、格式转换
        'file': '文件', 'filesystem': '文件', 'storage': '文件', 'pdf': '文件', 'excel': '文件',
        'document': '文件', 'csv': '文件', 'xml': '文件', 'markdown': '文件', 'docx': '文件',
        'word': '文件', 'zip': '文件', 'archive': '文件', 'txt': '文件', 'read': '文件', 'write': '文件',
        # 网络 - 网页抓取、HTTP请求
        'web': '网络', 'http': '网络', 'fetch': '网络', 'scrape': '网络', 'url': '网络',
        'rest': '网络', 'webhook': '网络', 'proxy': '网络', 'crawler': '网络', 'spider': '网络',
        # 数据库 - 各类数据库连接
        'database': '数据库', 'sql': '数据库', 'postgres': '数据库', 'mysql': '数据库', 'mongo': '数据库',
        'supabase': '数据库', 'graphql': '数据库', 'redis': '数据库', 'sqlite': '数据库', 'prisma': '数据库',
        'firebase': '数据库', 'dynamodb': '数据库', 'cassandra': '数据库', 'elastic': '数据库', 'neo4j': '数据库',
        'airtable': '数据库', 'notion': '数据库', 'coda': '数据库',
        # 知识库 - RAG、向量、记忆、知识管理
        'memory': '知识库', 'rag': '知识库', 'embedding': '知识库', 'vector': '知识库', 'knowledge': '知识库',
        'pinecone': '知识库', 'weaviate': '知识库', 'chroma': '知识库', 'qdrant': '知识库', 'milvus': '知识库',
        # 模型服务 - 调用其他AI模型
        'openai': '模型', 'anthropic': '模型', 'gemini': '模型', 'ollama': '模型', 'huggingface': '模型',
        'gpt': '模型', 'llama': '模型', 'mistral': '模型', 'cohere': '模型', 'replicate': '模型',
        # 开发工具 - 代码、Git、测试
        'git': '开发', 'github': '开发', 'gitlab': '开发', 'bitbucket': '开发', 'eslint': '开发',
        'prettier': '开发', 'lint': '开发', 'debug': '开发', 'jest': '开发', 'typescript': '开发',
        'compiler': '开发', 'webpack': '开发', 'vite': '开发', 'npm': '开发', 'yarn': '开发',
        'code': '开发', 'ide': '开发', 'vscode': '开发', 'cursor': '开发',
        # 搜索 - 搜索引擎、信息检索
        'search': '搜索', 'google': '搜索', 'bing': '搜索', 'duckduckgo': '搜索', 'brave': '搜索',
        'tavily': '搜索', 'serp': '搜索', 'exa': '搜索', 'perplexity': '搜索',
        # 工具 - 通用小工具
        'util': '工具', 'translate': '工具', 'time': '工具', 'date': '工具', 'weather': '工具',
        'currency': '工具', 'calculator': '工具', 'convert': '工具', 'regex': '工具', 'hash': '工具',
        'random': '工具', 'uuid': '工具', 'qr': '工具', 'barcode': '工具', 'clipboard': '工具',
        # 云服务 - 云平台、DevOps
        'kubernetes': '云服务', 'k8s': '云服务', 'docker': '云服务', 'aws': '云服务', 'azure': '云服务',
        'terraform': '云服务', 'sentry': '云服务', 'datadog': '云服务', 'heroku': '云服务', 'vercel': '云服务',
        'netlify': '云服务', 'cloudflare': '云服务', 'gcp': '云服务', 'jenkins': '云服务', 'serverless': '云服务',
        # 通讯 - 即时通讯、邮件
        'slack': '通讯', 'discord': '通讯', 'telegram': '通讯', 'wechat': '通讯', 'email': '通讯',
        'dingtalk': '通讯', 'whatsapp': '通讯', 'sms': '通讯', 'twilio': '通讯', 'teams': '通讯',
        'matrix': '通讯', 'zoom': '通讯', 'mail': '通讯',
        # 浏览器 - 浏览器自动化
        'browser': '浏览器', 'playwright': '浏览器', 'puppeteer': '浏览器', 'selenium': '浏览器',
        'chrome': '浏览器', 'firefox': '浏览器', 'webdriver': '浏览器', 'headless': '浏览器',
        # 设计 - UI设计工具
        'figma': '设计', 'design': '设计', 'sketch': '设计', 'adobe': '设计', 'canva': '设计',
        'ui': '设计', 'ux': '设计', 'prototype': '设计',
        # 媒体 - 图片、音视频处理
        'youtube': '媒体', 'video': '媒体', 'audio': '媒体', 'image': '媒体', 'music': '媒体',
        'spotify': '媒体', 'podcast': '媒体', 'ffmpeg': '媒体', 'photo': '媒体', 'camera': '媒体',
        'screenshot': '媒体', 'ocr': '媒体', 'tts': '媒体', 'stt': '媒体', 'speech': '媒体',
        # 地图 - 地理位置服务
        'map': '地图', 'location': '地图', 'geo': '地图', 'mapbox': '地图', 'gps': '地图',
        'osm': '地图', 'coordinates': '地图', 'address': '地图', 'route': '地图', 'navigation': '地图',
        # 安全 - 认证、加密
        'security': '安全', 'auth': '安全', 'oauth': '安全', 'jwt': '安全', 'password': '安全',
        'encrypt': '安全', 'ssl': '安全', 'certificate': '安全', 'vault': '安全', 'secret': '安全',
        # 电商 - 支付、商城
        'payment': '电商', 'stripe': '电商', 'paypal': '电商', 'shop': '电商', 'cart': '电商',
        'ecommerce': '电商', 'order': '电商', 'invoice': '电商', 'shopify': '电商',
        # 社交 - 社交媒体平台
        'twitter': '社交', 'facebook': '社交', 'instagram': '社交', 'linkedin': '社交', 'reddit': '社交',
        'tiktok': '社交', 'bluesky': '社交', 'mastodon': '社交',
        # 项目管理 - 任务、项目协作
        'jira': '项目', 'asana': '项目', 'trello': '项目', 'monday': '项目', 'clickup': '项目',
        'linear': '项目', 'basecamp': '项目', 'todoist': '项目', 'task': '项目',
        # 游戏
        'game': '游戏', 'unity': '游戏', 'unreal': '游戏', 'godot': '游戏', 'minecraft': '游戏',
        'steam': '游戏', 'roblox': '游戏',
        # 金融 - 股票、加密货币
        'stock': '金融', 'crypto': '金融', 'bitcoin': '金融', 'trading': '金融', 'finance': '金融',
        'coinbase': '金融', 'binance': '金融',
        # 新闻 - 新闻、RSS
        'news': '新闻', 'rss': '新闻', 'feed': '新闻', 'hackernews': '新闻',
        # 日历 - 日程管理
        'calendar': '日历', 'schedule': '日历', 'meeting': '日历', 'event': '日历',
        # 笔记 - 笔记应用
        'note': '笔记', 'obsidian': '笔记', 'roam': '笔记', 'logseq': '笔记', 'evernote': '笔记',
    }

    @staticmethod
    def _generate_npm_urls():
        urls = []
        for kw in ['mcp-server', 'mcp']:
            for i in range(0, 3000, 250):
                urls.append(f'https://registry.npmjs.org/-/v1/search?text={kw}&size=250&from={i}')
        for kw in ['modelcontextprotocol', '@modelcontextprotocol', 'claude-mcp', 'mcp-tool',
                   'mcp-client', 'mcp-plugin', 'mcp-connector', 'anthropic-mcp']:
            for i in range(0, 1000, 250):
                urls.append(f'https://registry.npmjs.org/-/v1/search?text={kw}&size=250&from={i}')
        return urls

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                package TEXT,
                command TEXT DEFAULT 'npx',
                args TEXT,
                category TEXT DEFAULT '其他',
                source TEXT,
                updated_at TEXT
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
            # FTS5 全文搜索表（某些 SQLite 版本可能不支持）
            try:
                conn.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS servers_fts USING fts5(
                    name, description, content='servers', content_rowid='rowid'
                )''')
                # 触发器：自动同步 FTS
                conn.executescript('''
                    CREATE TRIGGER IF NOT EXISTS servers_ai AFTER INSERT ON servers BEGIN
                        INSERT INTO servers_fts(rowid, name, description) VALUES (new.rowid, new.name, new.description);
                    END;
                    CREATE TRIGGER IF NOT EXISTS servers_ad AFTER DELETE ON servers BEGIN
                        INSERT INTO servers_fts(servers_fts, rowid, name, description) VALUES('delete', old.rowid, old.name, old.description);
                    END;
                    CREATE TRIGGER IF NOT EXISTS servers_au AFTER UPDATE ON servers BEGIN
                        INSERT INTO servers_fts(servers_fts, rowid, name, description) VALUES('delete', old.rowid, old.name, old.description);
                        INSERT INTO servers_fts(rowid, name, description) VALUES (new.rowid, new.name, new.description);
                    END;
                ''')
            except Exception:
                pass  # FTS5 不可用时降级为普通 LIKE 搜索
            conn.commit()

    def _guess_category(self, name: str, desc: str) -> str:
        text = (name + ' ' + desc).lower()
        for kw, cat in self.CATEGORY_MAP.items():
            if kw in text:
                return cat
        return '其他'

    def _normalize_npm(self, obj: dict) -> dict | None:
        """从 npm 搜索结果中提取 MCP 服务器信息"""
        pkg = obj.get('package', {})
        name = pkg.get('name', '')
        desc = pkg.get('description', '') or ''

        # 严格过滤：必须是真正的 MCP 服务器
        name_lower = name.lower()
        desc_lower = desc.lower()

        # 必须包含 mcp 相关关键词
        is_mcp = ('mcp' in name_lower or 'model context protocol' in desc_lower or
                  'modelcontextprotocol' in name_lower)
        if not is_mcp:
            return None

        # 排除测试包、示例包、无效包
        skip_keywords = ['test', 'example', 'demo', 'sample', 'template', 'boilerplate',
                        'hello-world', 'starter', 'skeleton', 'malicious']
        if any(kw in name_lower for kw in skip_keywords):
            return None

        # 放宽下载量限制，只过滤完全没人用的
        downloads = obj.get('downloads', {}).get('monthly', 0)
        if downloads < 1:
            return None

        return {
            'id': name.lower().replace('@', '').replace('/', '-'),
            'name': name,
            'description': str(desc)[:500],
            'package': name,
            'command': 'npx',
            'args': f'-y {name}',
            'category': self._guess_category(name, str(desc)),
            'source': 'npm',
        }

    def fetch_all(self, callback=None, quick=True) -> tuple[int, list[str]]:
        """同步 MCP 仓库。quick=True 获取最新发布的，quick=False 获取全部"""
        import urllib.request
        errors, new_count = [], 0
        now = datetime.now().isoformat()

        if quick:
            # 快速同步：按最新发布排序（quality/popularity/maintenance=0 让时间权重最高）
            urls = [
                'https://registry.npmjs.org/-/v1/search?text=mcp-server&size=250&quality=0.0&popularity=0.0&maintenance=0.0',
                'https://registry.npmjs.org/-/v1/search?text=mcp&size=250&quality=0.0&popularity=0.0&maintenance=0.0',
            ]
        else:
            urls = self._generate_npm_urls()

        for i, url in enumerate(urls):
            if callback:
                callback(f"获取 npm ({i+1}/{len(urls)})...")
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = json.loads(resp.read().decode('utf-8'))
                    items = raw.get('objects', [])
                    hit_existing = 0  # 连续遇到已存在的计数

                    with sqlite3.connect(self.db_path) as conn:
                        for item in items:
                            s = self._normalize_npm(item)
                            if not s:
                                continue
                            cur = conn.execute('SELECT 1 FROM servers WHERE id=?', (s['id'],))
                            if cur.fetchone():
                                hit_existing += 1
                                # 快速模式：连续遇到 5 个已存在的就停止（允许少量重叠避免遗漏）
                                if quick and hit_existing >= 5:
                                    break
                            else:
                                hit_existing = 0  # 重置计数
                                conn.execute('''INSERT INTO servers (id,name,description,package,command,args,category,source,updated_at)
                                    VALUES (?,?,?,?,?,?,?,?,?)''',
                                    (s['id'], s['name'], s['description'], s['package'], s['command'], s['args'], s['category'], s['source'], now))
                                new_count += 1
                        conn.commit()
            except Exception as ex:
                errors.append(f"npm: {ex}")

        if callback:
            callback(f"完成：新增 {new_count} 个 MCP")

        # 更新元数据
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('updated_at', now))
            conn.commit()

        return new_count, errors

    def search(self, keyword: str = '', category: str = '全部', limit: int = 200) -> list[dict]:
        """全文搜索（FTS5 不可用时降级为 LIKE）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if keyword:
                # 尝试 FTS5 搜索
                try:
                    sql = '''SELECT s.* FROM servers s
                        JOIN servers_fts f ON s.rowid = f.rowid
                        WHERE servers_fts MATCH ?'''
                    params: list = [f'"{keyword}"*']
                    if category and category != '全部':
                        sql += ' AND s.category = ?'
                        params.append(category)
                    sql += f' LIMIT {limit}'
                    rows = conn.execute(sql, params).fetchall()
                except Exception:
                    # FTS5 不可用，降级为 LIKE
                    sql = 'SELECT * FROM servers WHERE (name LIKE ? OR description LIKE ?)'
                    params = [f'%{keyword}%', f'%{keyword}%']
                    if category and category != '全部':
                        sql += ' AND category = ?'
                        params.append(category)
                    sql += f' LIMIT {limit}'
                    rows = conn.execute(sql, params).fetchall()
            else:
                sql = 'SELECT * FROM servers'
                params = []
                if category and category != '全部':
                    sql += ' WHERE category = ?'
                    params.append(category)
                sql += f' LIMIT {limit}'
                rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_servers(self, limit: int = 10000) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f'SELECT * FROM servers LIMIT {limit}').fetchall()
        return [dict(r) for r in rows]

    def get_categories(self) -> list[tuple[str, int]]:
        """获取所有分类及数量"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('SELECT category, COUNT(*) FROM servers GROUP BY category ORDER BY COUNT(*) DESC').fetchall()
        return rows

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute('SELECT COUNT(*) FROM servers').fetchone()[0]
            updated = conn.execute('SELECT value FROM meta WHERE key="updated_at"').fetchone()
        return {'total': total, 'updated_at': updated[0] if updated else None}

    def needs_update(self, days: int = 7) -> bool:
        stats = self.get_stats()
        if not stats.get('updated_at'):
            return True
        try:
            last = datetime.fromisoformat(stats['updated_at'])
            return (datetime.now() - last).days >= days
        except:
            return True

# 全局 MCP 仓库实例
mcp_registry = MCPRegistry(MCP_DB_FILE)

# 提示词标识符（用于检测和同步）
SYSTEM_PROMPT_START = "<!-- GLOBAL_PROMPT_START -->"
SYSTEM_PROMPT_END = "<!-- GLOBAL_PROMPT_END -->"
USER_PROMPT_START = "<!-- USER_PROMPT_START:{id} -->"
USER_PROMPT_END = "<!-- USER_PROMPT_END -->"

# 内置提示词（来自 AI_talk）
BUILTIN_PROMPTS = {
    'blank': {'name': '空白', 'content': '', 'category': '用户', 'is_builtin': True, 'prompt_type': 'user'},
    'coding_general': {
        'name': '通用编程',
        'content': '你是一个专业的编程助手。提供高质量的代码示例和解释。遵循最佳实践和设计模式。考虑性能、安全性和可维护性。提供完整的、可运行的代码。',
        'category': '编程', 'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_debug': {
        'name': '代码调试',
        'content': '你是一个代码调试专家。帮助用户找出代码中的问题。提供清晰的错误分析和解决方案。逐步解释问题的原因和修复方法。',
        'category': '编程', 'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_review': {
        'name': '代码审查',
        'content': '你是一个资深的代码审查员。分析代码质量、可读性和性能。提供具体的改进建议。指出潜在的问题和优化机会。',
        'category': '编程', 'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_article': {
        'name': '文章写作',
        'content': '你是一个专业的文章写手。帮助用户撰写高质量的文章。确保逻辑清晰、表达准确。提供结构建议和内容优化。',
        'category': '写作', 'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_creative': {
        'name': '创意写作',
        'content': '你是一个创意写作专家。帮助用户创作故事、诗歌或其他创意内容。提供灵感和创意建议。确保内容生动有趣。',
        'category': '写作', 'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_data': {
        'name': '数据分析',
        'content': '你是一个数据分析专家。深入分析数据和趋势。提供数据支持的观点和结论。用清晰的方式解释复杂的数据。',
        'category': '分析', 'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_summary': {
        'name': '内容总结',
        'content': '你是一个内容总结专家。快速提取关键信息。用简洁的方式总结复杂内容。突出重点和核心观点。',
        'category': '分析', 'is_builtin': True, 'prompt_type': 'user'
    },
    'image_prompt': {
        'name': '绘画提示词',
        'content': '你是AI绘画提示词专家。根据用户提供的文案，生成适合AI绘图的英文提示词。\n\n风格要求：治愈系、卡通漫画、线条画、扁平插画\n\n直接输出英文提示词，不需要解释。\n\n输出格式：[主体描述], [风格], [色彩], [氛围], [细节]',
        'category': '绘画', 'is_builtin': True, 'prompt_type': 'user'
    },
}

# CLI 工具定义
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

# 官方 MCP 服务器列表 (精选)
OFFICIAL_MCP_SERVERS = [
    {'name': 'Filesystem', 'package': '@modelcontextprotocol/server-filesystem', 'desc': '文件系统读写', 'args_hint': '/path/to/dir'},
    {'name': 'Fetch', 'package': '@modelcontextprotocol/server-fetch', 'desc': '网页内容获取'},
    {'name': 'Memory', 'package': '@modelcontextprotocol/server-memory', 'desc': '长期记忆存储'},
    {'name': 'Sequential Thinking', 'package': '@modelcontextprotocol/server-sequential-thinking', 'desc': '深度思考推理'},
]

# MCP 市场/目录链接
MCP_MARKETPLACES = [
    {'name': 'Smithery', 'url': 'https://smithery.ai/', 'desc': '最大的 MCP 服务器市场'},
    {'name': 'MCP.so', 'url': 'https://mcp.so/', 'desc': 'MCP 服务器目录'},
    {'name': 'Glama', 'url': 'https://glama.ai/mcp/servers', 'desc': 'MCP 服务器列表'},
    {'name': 'GitHub Official', 'url': 'https://github.com/modelcontextprotocol/servers', 'desc': '官方服务器仓库'},
]

def get_prompt_file_path(cli_type: str) -> Path:
    """获取 CLI 工具的提示词文件路径"""
    cli = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
    home = Path.home()
    if cli['prompt_dir']:
        return home / cli['prompt_dir'] / cli['prompt_file']
    return home / cli['prompt_file']

def write_prompt_to_cli(cli_type: str, system_content: str, user_content: str, user_id: str, workdir: str | None = None) -> Path:
    """将提示词写入 CLI 配置文件，系统提示词 + 用户提示词

    Args:
        cli_type: CLI 工具类型
        system_content: 全局/系统提示词内容
        user_content: 用户提示词内容
        user_id: 用户提示词 ID
        workdir: 工作目录，如果指定则写入工作目录，否则写入全局配置

    Returns:
        写入的文件路径
    """
    cli = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])

    if workdir:
        file_path = Path(workdir) / cli['prompt_file']
    else:
        file_path = get_prompt_file_path(cli_type)

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 构建带标识符的提示词
    parts = []
    if system_content.strip():
        parts.append(f"{SYSTEM_PROMPT_START}\n{system_content}\n{SYSTEM_PROMPT_END}")
    if user_content.strip():
        user_start = USER_PROMPT_START.format(id=user_id)
        parts.append(f"{user_start}\n{user_content}\n{USER_PROMPT_END}")

    wrapped = "\n\n".join(parts)

    # 读取现有内容
    existing = ""
    if file_path.exists():
        existing = file_path.read_text(encoding='utf-8')

    # 移除旧的标记内容
    for marker_start, marker_end in [
        (SYSTEM_PROMPT_START, SYSTEM_PROMPT_END),
        (r'<!-- USER_PROMPT_START:[^>]+ -->', USER_PROMPT_END),
        (r'【LiangMu 用户提示词 Start - ID:[^】]+】', r'【LiangMu 用户提示词 End】'),  # 兼容旧格式
        (r'【LiangMu-Studio Prompt Start】', r'【LiangMu-Studio Prompt End】'),  # 兼容旧格式
    ]:
        pattern = re.escape(marker_start) if marker_start.startswith('<!--') and '[' not in marker_start else marker_start
        pattern += r'.*?'
        pattern += re.escape(marker_end) if marker_end.startswith('<!--') else marker_end
        existing = re.sub(pattern, '', existing, flags=re.DOTALL)

    # 清理多余空行
    existing = re.sub(r'\n{3,}', '\n\n', existing.strip())

    # 追加新内容
    new_content = (existing + "\n\n" + wrapped).strip() + "\n"
    file_path.write_text(new_content, encoding='utf-8')
    return file_path

def detect_prompt_from_file(file_path: Path) -> tuple[str | None, str | None, str | None]:
    """从文件中检测提示词内容

    Returns:
        (system_content, user_content, user_id)
    """
    if not file_path.exists():
        return None, None, None

    content = file_path.read_text(encoding='utf-8')
    system_content = None
    user_content = None
    user_id = None

    # 检测系统提示词
    sys_pattern = re.escape(SYSTEM_PROMPT_START) + r'(.*?)' + re.escape(SYSTEM_PROMPT_END)
    sys_match = re.search(sys_pattern, content, re.DOTALL)
    if sys_match:
        system_content = sys_match.group(1).strip()

    # 检测用户提示词
    user_pattern = r'<!-- USER_PROMPT_START:([^>]+) -->(.*?)' + re.escape(USER_PROMPT_END)
    user_match = re.search(user_pattern, content, re.DOTALL)
    if user_match:
        user_id = user_match.group(1).strip()
        user_content = user_match.group(2).strip()

    return system_content, user_content, user_id

# 多语言支持
LANG = {
    'zh': {
        'title': 'LiangMu-Studio API Key v{}',
        'api_config': 'API 密钥配置',
        'prompts': '提示词',
        'mcp': 'MCP 服务器',
        'add': '新增',
        'edit': '编辑',
        'delete': '删除',
        'copy': '复制',
        'save': '保存',
        'cancel': '取消',
        'name': '名称',
        'cli_type': 'CLI工具',
        'api_addr': 'API地址',
        'key_name': 'KEY名称',
        'api_key': 'API密钥',
        'terminal': '集成终端',
        'select_terminal': '选择终端',
        'python_env': 'Python环境',
        'work_dir': '工作目录',
        'browse': '浏览',
        'open_terminal': '打开终端',
        'copied': '已复制到剪贴板',
        'saved': '保存成功',
        'deleted': '删除成功',
        'confirm_delete': '确认删除',
        'confirm_delete_msg': '确定要删除 "{}" 吗？',
        'no_selection': '请先选择一项',
        'fill_required': '请填写必填项',
        'prompt_content': '提示词内容',
        'prompt_hint': '选择提示词后点击复制，可粘贴到任意位置使用',
        'mcp_command': '命令',
        'mcp_args': '参数',
        'mcp_env': '环境变量',
        'add_terminal': '+ 添加终端',
        'refresh_terminals': '刷新终端',
        'refresh_envs': '刷新环境',
        'current_key': '当前KEY:',
        'not_selected': '未选择',
        'terminals_refreshed': '终端列表已刷新',
        'envs_refreshed': 'Python环境已刷新，发现 {} 个环境',
        'move_up': '上移',
        'move_down': '下移',
        'export': '导出',
        'import': '导入',
        'feedback': '反馈: GitHub Issues',
        'copy_key': '复制KEY',
        'exported_to': '配置已导出到: {}',
        'imported_count': '已导入 {} 个配置',
    },
    'en': {
        'title': 'LiangMu-Studio API Key v{}',
        'api_config': 'API Key Config',
        'prompts': 'Prompts',
        'mcp': 'MCP Servers',
        'add': 'Add',
        'edit': 'Edit',
        'delete': 'Delete',
        'copy': 'Copy',
        'save': 'Save',
        'cancel': 'Cancel',
        'name': 'Name',
        'cli_type': 'CLI Tool',
        'api_addr': 'API Address',
        'key_name': 'KEY Name',
        'api_key': 'API Key',
        'terminal': 'Terminal',
        'select_terminal': 'Select Terminal',
        'python_env': 'Python Env',
        'work_dir': 'Work Directory',
        'browse': 'Browse',
        'open_terminal': 'Open Terminal',
        'copied': 'Copied to clipboard',
        'saved': 'Saved successfully',
        'deleted': 'Deleted successfully',
        'confirm_delete': 'Confirm Delete',
        'confirm_delete_msg': 'Are you sure to delete "{}"?',
        'no_selection': 'Please select an item first',
        'fill_required': 'Please fill in required fields',
        'prompt_content': 'Prompt Content',
        'prompt_hint': 'Select a prompt and click copy to use it anywhere',
        'mcp_command': 'Command',
        'mcp_args': 'Arguments',
        'mcp_env': 'Environment',
        'add_terminal': '+ Add Terminal',
        'refresh_terminals': 'Refresh Terminals',
        'refresh_envs': 'Refresh Envs',
        'current_key': 'Current KEY:',
        'not_selected': 'Not Selected',
        'terminals_refreshed': 'Terminal list refreshed',
        'envs_refreshed': 'Python envs refreshed, found {} envs',
        'move_up': 'Up',
        'move_down': 'Down',
        'export': 'Export',
        'import': 'Import',
        'feedback': 'Feedback: GitHub Issues',
        'copy_key': 'Copy',
        'exported_to': 'Config exported to: {}',
        'imported_count': 'Imported {} configs',
    }
}

# 数据加载/保存函数
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

def load_prompts():
    """加载提示词，合并内置和自定义"""
    custom = {}
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            custom = json.load(f)
    # 合并：内置 + 自定义
    all_prompts = {}
    for pid, p in BUILTIN_PROMPTS.items():
        all_prompts[pid] = {**p, 'id': pid}
    for pid, p in custom.items():
        all_prompts[pid] = {**p, 'id': pid}
    return all_prompts

def save_prompts(prompts):
    """只保存自定义提示词"""
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
    return {'lang': 'zh', 'terminal': '', 'python_env': '', 'work_dir': '', 'terminals_cache': {}, 'envs_cache': {}}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def detect_terminals():
    """检测可用终端"""
    terminals = {}
    if sys.platform == 'win32':
        if shutil.which('pwsh'):
            terminals['PowerShell 7'] = 'pwsh'
        if shutil.which('powershell'):
            terminals['PowerShell 5'] = 'powershell'
        if shutil.which('cmd'):
            terminals['CMD'] = 'cmd'
    elif sys.platform == 'darwin':
        terminals['Terminal'] = 'Terminal'
        if shutil.which('zsh'):
            terminals['zsh'] = 'zsh'
    else:
        if shutil.which('gnome-terminal'):
            terminals['GNOME Terminal'] = 'gnome-terminal'
        if shutil.which('bash'):
            terminals['bash'] = 'bash'
    return terminals

def detect_python_envs():
    """检测 Python 环境，base 排最后"""
    debug_print("detect_python_envs 开始")
    envs = {}
    try:
        result = subprocess.run(['conda', 'env', 'list'], capture_output=True, text=True, check=True, timeout=5)
        for line in result.stdout.split('\n'):
            if line.strip() and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    envs[parts[0]] = {'type': 'conda', 'path': parts[-1]}
    except:
        pass
    debug_print(f"detect_python_envs 结束，找到 {len(envs)} 个环境")
    # 排序：base 放最后
    sorted_envs = {}
    for k in sorted(envs.keys(), key=lambda x: (x == 'base', x)):
        sorted_envs[k] = envs[k]
    return sorted_envs


def main(page: ft.Page):
    debug_print("main 函数开始")
    # 初始化
    debug_print("加载设置...")
    settings = load_settings()
    lang = settings.get('lang', 'zh')
    L = LANG[lang]

    page.title = L['title'].format(VERSION)
    page.window.width = 1100
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(font_family="Microsoft YaHei UI, Segoe UI, sans-serif")

    # 设置窗口图标
    icon_path = Path(__file__).parent / "icon.ico"
    if icon_path.exists():
        page.window.icon = str(icon_path)

    debug_print("加载配置...")
    configs = load_configs()
    debug_print("加载提示词...")
    prompt_db = PromptDB(DB_FILE)
    # 迁移旧数据并初始化内置提示词
    for pid, p in BUILTIN_PROMPTS.items():
        if not prompt_db.get_all().get(pid):
            prompt_db.save({'id': pid, **p})
    # 从旧 JSON 迁移
    if PROMPTS_FILE.exists():
        old_prompts = load_prompts()
        prompt_db.migrate_from_json(old_prompts)
    prompts = prompt_db.get_all()
    debug_print("加载MCP...")
    mcp_list = load_mcp()

    # 使用缓存的终端和环境
    debug_print("加载终端和环境缓存...")
    terminals = settings.get('terminals_cache', {})
    python_envs = settings.get('envs_cache', {})
    first_run = not terminals or not python_envs

    debug_print("初始化完成，开始构建UI...")

    selected_config = None
    selected_prompt = None
    selected_mcp = None

    # ========== API 密钥页面 ==========
    config_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0, alignment=ft.MainAxisAlignment.START)
    current_key_label = ft.Text(L['not_selected'], color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD)

    def build_tree_structure():
        """构建三级树形结构：CLI工具 → API端点 → 配置项"""
        tree = {}  # {cli_type: {endpoint: [configs]}}
        for i, cfg in enumerate(configs):
            cli_type = cfg.get('cli_type', 'claude')
            endpoint = cfg.get('provider', {}).get('endpoint', '未知端点')
            if cli_type not in tree:
                tree[cli_type] = {}
            if endpoint not in tree[cli_type]:
                tree[cli_type][endpoint] = []
            tree[cli_type][endpoint].append((i, cfg))
        return tree

    # 展开状态
    expanded_cli = {}
    expanded_endpoint = {}

    def refresh_config_list():
        config_tree.controls.clear()
        tree = build_tree_structure()

        for cli_type in tree:
            cli_name = CLI_TOOLS.get(cli_type, {}).get('name', cli_type)
            cli_key = cli_type
            is_cli_expanded = expanded_cli.get(cli_key, True)

            # CLI 工具层（第一级）
            cli_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_cli_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.TERMINAL, color=ft.Colors.BLUE),
                    ft.Text(cli_name, weight=ft.FontWeight.BOLD),
                    ft.Text(f"({sum(len(v) for v in tree[cli_type].values())})", color=ft.Colors.GREY_600),
                ], spacing=5),
                padding=ft.padding.only(left=5, top=8, bottom=8),
                on_click=lambda e, k=cli_key: toggle_cli(k),
                bgcolor=ft.Colors.GREY_100,
                border_radius=4,
            )
            config_tree.controls.append(cli_header)

            if is_cli_expanded:
                for endpoint in tree[cli_type]:
                    endpoint_key = f"{cli_type}:{endpoint}"
                    is_endpoint_expanded = expanded_endpoint.get(endpoint_key, True)
                    short_endpoint = endpoint[:40] + "..." if len(endpoint) > 40 else endpoint

                    # API 端点层（第二级）
                    endpoint_header = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_endpoint_expanded else ft.Icons.ARROW_RIGHT, size=18),
                            ft.Icon(ft.Icons.LINK, size=16, color=ft.Colors.GREEN),
                            ft.Text(short_endpoint, size=13),
                            ft.Text(f"({len(tree[cli_type][endpoint])})", color=ft.Colors.GREY_600, size=12),
                        ], spacing=5),
                        padding=ft.padding.only(left=30, top=6, bottom=6),
                        on_click=lambda e, k=endpoint_key: toggle_endpoint(k),
                    )
                    config_tree.controls.append(endpoint_header)

                    if is_endpoint_expanded:
                        for idx, cfg in tree[cli_type][endpoint]:
                            # 配置项层（第三级）
                            is_selected = selected_config == idx
                            config_item = ft.GestureDetector(
                                content=ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.KEY, size=16, color=ft.Colors.ORANGE if is_selected else ft.Colors.GREY_600),
                                        ft.Text(cfg.get('label', 'Unnamed'),
                                               weight=ft.FontWeight.BOLD if is_selected else None,
                                               color=ft.Colors.BLUE if is_selected else None),
                                    ], spacing=5),
                                    padding=ft.padding.only(left=60, top=5, bottom=5),
                                    bgcolor=ft.Colors.BLUE_50 if is_selected else None,
                                    border_radius=4,
                                ),
                                on_tap=lambda e, i=idx: select_config(i),
                                on_double_tap=lambda e, i=idx: (select_config(i), show_config_dialog(i)),
                            )
                            config_tree.controls.append(config_item)

        page.update()

    def toggle_cli(cli_key):
        expanded_cli[cli_key] = not expanded_cli.get(cli_key, True)
        refresh_config_list()

    def toggle_endpoint(endpoint_key):
        expanded_endpoint[endpoint_key] = not expanded_endpoint.get(endpoint_key, True)
        refresh_config_list()

    def select_config(idx):
        nonlocal selected_config
        selected_config = idx
        # 更新当前KEY显示
        if selected_config is not None and selected_config < len(configs):
            current_key_label.value = configs[selected_config].get('label', L['not_selected'])
        else:
            current_key_label.value = L['not_selected']
        refresh_config_list()

    def add_config(e):
        show_config_dialog(None)

    def edit_config(e):
        if selected_config is not None:
            show_config_dialog(selected_config)
        else:
            page.open(ft.SnackBar(ft.Text(L['no_selection'])))
            page.update()

    def delete_config(e):
        nonlocal selected_config
        if selected_config is not None:
            cfg = configs[selected_config]
            def confirm_delete(e):
                if e.control.text == L['delete']:
                    configs.pop(selected_config)
                    save_configs(configs)
                    selected_config = None
                    refresh_config_list()
                    page.open(ft.SnackBar(ft.Text(L['deleted'])))
                dlg.open = False
                page.update()

            dlg = ft.AlertDialog(
                title=ft.Text(L['confirm_delete']),
                content=ft.Text(L['confirm_delete_msg'].format(cfg.get('label', ''))),
                actions=[
                    ft.TextButton(L['cancel'], on_click=confirm_delete),
                    ft.TextButton(L['delete'], on_click=confirm_delete),
                ],
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

    def copy_config_key(e):
        if selected_config is not None:
            key = configs[selected_config].get('provider', {}).get('credentials', {}).get('api_key', '')
            page.set_clipboard(key)
            page.open(ft.SnackBar(ft.Text(L['copied'])))
            page.update()

    def move_up(e):
        nonlocal selected_config
        if selected_config is not None and selected_config > 0:
            configs[selected_config], configs[selected_config - 1] = configs[selected_config - 1], configs[selected_config]
            selected_config -= 1
            save_configs(configs)
            refresh_config_list()

    def move_down(e):
        nonlocal selected_config
        if selected_config is not None and selected_config < len(configs) - 1:
            configs[selected_config], configs[selected_config + 1] = configs[selected_config + 1], configs[selected_config]
            selected_config += 1
            save_configs(configs)
            refresh_config_list()

    def export_configs(e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                with open(result.path, 'w', encoding='utf-8') as f:
                    json.dump({'configs': configs}, f, ensure_ascii=False, indent=2)
                page.open(ft.SnackBar(ft.Text(L['exported_to'].format(result.path))))
                page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.save_file(file_name='api_configs.json', allowed_extensions=['json'])

    def import_configs(e):
        nonlocal configs
        def on_result(result: ft.FilePickerResultEvent):
            nonlocal configs
            if result.files:
                try:
                    with open(result.files[0].path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    imported = data.get('configs', [])
                    configs.extend(imported)
                    save_configs(configs)
                    refresh_config_list()
                    page.open(ft.SnackBar(ft.Text(L['imported_count'].format(len(imported)))))
                    page.update()
                except Exception as ex:
                    page.open(ft.SnackBar(ft.Text(str(ex))))
                    page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.pick_files(allowed_extensions=['json'])

    def open_feedback(e):
        import webbrowser
        webbrowser.open('https://github.com/LiangMu-Studio/API_control/issues')

    def show_config_dialog(idx):
        is_edit = idx is not None
        cfg = configs[idx] if is_edit else {}

        name_field = ft.TextField(label=L['name'], value=cfg.get('label', ''), expand=True)
        cli_dropdown = ft.Dropdown(
            label=L['cli_type'],
            value=cfg.get('cli_type', 'claude'),
            options=[ft.dropdown.Option(k, v['name']) for k, v in CLI_TOOLS.items()],
            expand=True,
        )
        endpoint_field = ft.TextField(
            label=L['api_addr'],
            value=cfg.get('provider', {}).get('endpoint', CLI_TOOLS['claude']['default_endpoint']),
            expand=True,
        )
        key_name_field = ft.TextField(
            label=L['key_name'],
            value=cfg.get('provider', {}).get('key_name', CLI_TOOLS['claude']['default_key_name']),
            expand=True,
        )
        api_key_field = ft.TextField(
            label=L['api_key'],
            value=cfg.get('provider', {}).get('credentials', {}).get('api_key', ''),
            password=True,
            can_reveal_password=True,
            expand=True,
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
                'label': name_field.value,
                'cli_type': cli_dropdown.value,
                'provider': {
                    'endpoint': endpoint_field.value,
                    'key_name': key_name_field.value,
                    'credentials': {'api_key': api_key_field.value}
                },
                'createdAt': cfg.get('createdAt', datetime.now().isoformat()),
                'updatedAt': datetime.now().isoformat(),
            }

            if is_edit:
                configs[idx] = new_cfg
            else:
                configs.append(new_cfg)

            save_configs(configs)
            refresh_config_list()
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(L['saved'])))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([
                name_field,
                cli_dropdown,
                endpoint_field,
                key_name_field,
                api_key_field,
            ], tight=True, spacing=10, width=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.TextButton(L['save'], on_click=save_config),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # 终端区域
    terminal_dropdown = ft.Dropdown(
        label=L['select_terminal'],
        value=list(terminals.keys())[0] if terminals else '',
        options=[ft.dropdown.Option(k) for k in terminals.keys()],
        width=180,
    )
    python_env_dropdown = ft.Dropdown(
        label=L['python_env'],
        value=list(python_envs.keys())[0] if python_envs else '',
        options=[ft.dropdown.Option(k) for k in python_envs.keys()],
        width=220,
    )

    # 提示词下拉菜单（按分类分组，只显示用户提示词）
    def build_prompt_options():
        # 按分类分组
        by_cat = {}
        for pid, p in prompts.items():
            if p.get('prompt_type') == 'system':
                continue
            cat = p.get('category', '其他')
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append((pid, p))
        # 排序
        order = ['编程', '写作', '分析', '绘画', '用户', '其他']
        sorted_cats = [c for c in order if c in by_cat] + [c for c in by_cat if c not in order]
        # 构建选项（分类标题 + 提示词）
        options = []
        for cat in sorted_cats:
            options.append(ft.dropdown.Option(key=f"__cat_{cat}", text=f"── {cat} ──", disabled=True))
            for pid, p in by_cat[cat]:
                options.append(ft.dropdown.Option(key=pid, text=f"  {p.get('name', pid)}"))
        return options

    prompt_dropdown = ft.Dropdown(
        label=L['prompts'],
        options=build_prompt_options(),
        width=220,
    )

    def refresh_prompt_dropdown():
        """刷新提示词下拉菜单"""
        prompt_dropdown.options = build_prompt_options()
        page.update()

    def apply_selected_prompt(e):
        """应用选中的提示词到工作目录"""
        if not prompt_dropdown.value:
            page.open(ft.SnackBar(ft.Text(L['no_selection'])))
            page.update()
            return
        if not work_dir_field.value:
            page.open(ft.SnackBar(ft.Text("请先选择工作目录")))
            page.update()
            return

        cli_type = 'claude'
        if selected_config is not None:
            cli_type = configs[selected_config].get('cli_type', 'claude')

        # 获取系统提示词和用户提示词
        system_prompt = prompt_db.get_system_prompt()
        system_content = system_prompt.get('content', '') if system_prompt else ''
        user_prompt = prompts.get(prompt_dropdown.value, {})
        user_content = user_prompt.get('content', '')
        user_id = prompt_dropdown.value

        try:
            file_path = write_prompt_to_cli(cli_type, system_content, user_content, user_id, work_dir_field.value)
            page.open(ft.SnackBar(ft.Text(f"已写入: {file_path}")))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(f"写入失败: {ex}")))
        page.update()

    work_dir_field = ft.TextField(label=L['work_dir'], value=settings.get('work_dir', ''), expand=True)
    workdir_mcp_enabled = {}  # 当前工作目录的 MCP 启用状态 {name: True/False}

    def show_mcp_selector(e):
        """显示 MCP 选择弹窗（非默认的 MCP）"""
        if not work_dir_field.value:
            page.open(ft.SnackBar(ft.Text("请先选择工作目录")))
            page.update()
            return

        mcp_selector_list = ft.ListView(expand=True, spacing=2)
        local_enabled = dict(workdir_mcp_enabled)  # 本地副本

        def build_selector_list():
            mcp_selector_list.controls.clear()
            for i, m in enumerate(mcp_list):
                if m.get('is_default'):
                    continue  # 跳过默认 MCP
                key = m.get('name', '').lower().replace(' ', '-')
                is_checked = local_enabled.get(key, False)
                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_checked, on_change=lambda e, k=key: toggle_local(k, e.control.value)),
                        ft.Icon(ft.Icons.EXTENSION, color=ft.Colors.GREEN if is_checked else ft.Colors.GREY_400),
                        ft.Column([
                            ft.Text(m.get('name', 'Unnamed'), weight=ft.FontWeight.BOLD if is_checked else None),
                            ft.Text(f"{m.get('category', '其他')} | {m.get('command', '')} {m.get('args', '')[:30]}", size=10, color=ft.Colors.GREY_500),
                        ], spacing=0, expand=True),
                    ], spacing=10),
                    padding=8,
                    bgcolor=ft.Colors.GREEN_50 if is_checked else None,
                    border_radius=4,
                )
                mcp_selector_list.controls.append(tile)
            page.update()

        def toggle_local(key, checked):
            local_enabled[key] = checked
            build_selector_list()

        def apply_selection(e):
            nonlocal workdir_mcp_enabled
            workdir_mcp_enabled = local_enabled
            # 同步到工作目录（需要在 MCP 页面定义后调用）
            sync_mcp_to_workdir_from_api()
            dlg.open = False
            page.open(ft.SnackBar(ft.Text("MCP 配置已更新")))
            page.update()

        build_selector_list()
        dlg = ft.AlertDialog(
            title=ft.Text("选择额外 MCP（默认 MCP 已自动加载）"),
            content=ft.Container(mcp_selector_list, width=500, height=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.ElevatedButton("应用", on_click=apply_selection),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def sync_mcp_to_workdir_from_api():
        """从 API 页面同步 MCP（调用 MCP 页面的函数）"""
        sync_mcp_to_workdir()

    def load_workdir_config(workdir: str):
        """加载工作目录的 MCP 和提示词配置"""
        nonlocal workdir_mcp_enabled
        workdir_path = Path(workdir)

        # 加载 .mcp.json 中的 MCP 启用状态
        workdir_mcp_enabled = {}
        mcp_path = workdir_path / '.mcp.json'
        if mcp_path.exists():
            try:
                with open(mcp_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for name in data.get('mcpServers', {}).keys():
                    workdir_mcp_enabled[name] = True
            except:
                pass

        # 加载 CLAUDE.md 中的提示词（使用新的检测函数）
        prompt_path = workdir_path / 'CLAUDE.md'
        sys_content, user_content, user_id = detect_prompt_from_file(prompt_path)
        if sys_content or user_content:
            preview = (user_content or sys_content or '')[:50]
            if len(preview) == 50:
                preview += '...'
            page.open(ft.SnackBar(ft.Text(f"已加载工作目录配置 | 提示词: {preview}")))
        elif prompt_path.exists():
            page.open(ft.SnackBar(ft.Text("已加载工作目录配置")))
        else:
            page.open(ft.SnackBar(ft.Text("已选择工作目录（无现有配置）")))

    def browse_folder(e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                work_dir_field.value = result.path
                settings['work_dir'] = result.path
                save_settings(settings)
                load_workdir_config(result.path)
                page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.get_directory_path()

    def refresh_terminals_click(e):
        nonlocal terminals
        terminals = detect_terminals()
        settings['terminals_cache'] = terminals
        save_settings(settings)
        terminal_dropdown.options = [ft.dropdown.Option(k) for k in terminals.keys()]
        if terminals:
            terminal_dropdown.value = list(terminals.keys())[0]
        page.open(ft.SnackBar(ft.Text(L['terminals_refreshed'])))
        page.update()

    def add_terminal_click(e):
        """添加自定义终端 - 选择可执行文件"""
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                file_path = result.files[0].path
                # 用文件名（不含扩展名）作为终端名称
                name = Path(file_path).stem
                terminals[name] = file_path
                settings['terminals_cache'] = terminals
                save_settings(settings)
                terminal_dropdown.options = [ft.dropdown.Option(k) for k in terminals.keys()]
                terminal_dropdown.value = name
                page.update()

        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.pick_files(
            dialog_title=L['add_terminal'],
            allowed_extensions=['exe'] if sys.platform == 'win32' else None,
        )

    def refresh_envs_click(e):
        nonlocal python_envs
        python_envs = detect_python_envs()
        settings['envs_cache'] = python_envs
        save_settings(settings)
        python_env_dropdown.options = [ft.dropdown.Option(k) for k in python_envs.keys()]
        if python_envs:
            python_env_dropdown.value = list(python_envs.keys())[0]
        page.open(ft.SnackBar(ft.Text(L['envs_refreshed'].format(len(python_envs)))))
        page.update()

    def validate_mcp_config(work_dir: str) -> list[str]:
        """验证 MCP 配置，返回错误列表"""
        errors = []
        mcp_path = Path(work_dir) / '.mcp.json'
        if not mcp_path.exists():
            return []  # 没有 MCP 配置不算错误

        try:
            with open(mcp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            servers = data.get('mcpServers', {})
            for name, cfg in servers.items():
                cmd = cfg.get('command', '')
                if not cmd:
                    errors.append(f"[{name}] 缺少 command")
                    continue
                # 检查命令是否存在
                if cmd == 'npx':
                    if not shutil.which('npx'):
                        errors.append(f"[{name}] npx 未安装，请先安装 Node.js")
                elif cmd == 'uvx':
                    if not shutil.which('uvx'):
                        errors.append(f"[{name}] uvx 未安装，请先安装 uv")
                elif not shutil.which(cmd) and not Path(cmd).exists():
                    errors.append(f"[{name}] 命令不存在: {cmd}")
        except json.JSONDecodeError:
            errors.append(".mcp.json 格式错误")
        except Exception as ex:
            errors.append(f"读取配置失败: {ex}")
        return errors

    def open_terminal(e):
        if selected_config is None:
            page.open(ft.SnackBar(ft.Text(L['no_selection'])))
            page.update()
            return

        cwd = work_dir_field.value or None

        # 验证 MCP 配置
        if cwd:
            mcp_errors = validate_mcp_config(cwd)
            if mcp_errors:
                error_text = "\n".join(mcp_errors)
                def continue_anyway(ev):
                    dlg.open = False
                    page.update()
                    do_open_terminal()
                dlg = ft.AlertDialog(
                    title=ft.Text("MCP 配置问题", color=ft.Colors.ORANGE),
                    content=ft.Column([
                        ft.Text("检测到以下问题："),
                        ft.Text(error_text, size=12, color=ft.Colors.RED),
                        ft.Text("\n是否仍要启动终端？", size=12),
                    ], tight=True),
                    actions=[
                        ft.TextButton("取消", on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                        ft.ElevatedButton("继续启动", on_click=continue_anyway),
                    ],
                )
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
                return

        do_open_terminal()

    def do_open_terminal():
        """实际启动终端"""
        if selected_config is None:
            return
        cfg = configs[selected_config]
        cli_type = cfg.get('cli_type', 'claude')
        cli_info = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
        api_key = cfg.get('provider', {}).get('credentials', {}).get('api_key', '')
        key_name = cfg.get('provider', {}).get('key_name', cli_info['default_key_name'])
        endpoint = cfg.get('provider', {}).get('endpoint', '')

        env = os.environ.copy()
        env[key_name] = api_key
        if endpoint:
            env[cli_info['base_url_env']] = endpoint

        terminal_cmd = terminals.get(terminal_dropdown.value, 'cmd')
        cwd = work_dir_field.value or None

        if sys.platform == 'win32':
            if terminal_cmd in ('pwsh', 'powershell'):
                subprocess.Popen([terminal_cmd, '-NoExit'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(['cmd', '/k'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([terminal_cmd], env=env, cwd=cwd)

    def switch_lang(e):
        nonlocal lang, L
        lang = 'en' if lang == 'zh' else 'zh'
        L = LANG[lang]
        settings['lang'] = lang
        save_settings(settings)
        # 重新加载页面
        if page.controls:
            page.controls.clear()
        page.update()
        main(page)

    api_page = ft.Column([
        # 上部：配置树 + 右侧按钮列
        ft.Row([
            # 左侧：配置树
            ft.Container(config_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
            # 右侧：按钮列
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
        # 集成终端标题
        ft.Text(L['terminal'], size=16, weight=ft.FontWeight.BOLD),
        # 第一行：终端选择、刷新终端、添加终端、Python环境、刷新环境、当前KEY
        ft.Row([
            terminal_dropdown,
            ft.TextButton(L['refresh_terminals'], icon=ft.Icons.REFRESH, on_click=refresh_terminals_click),
            ft.TextButton(L['add_terminal'], on_click=add_terminal_click),
            python_env_dropdown,
            ft.TextButton(L['refresh_envs'], icon=ft.Icons.REFRESH, on_click=refresh_envs_click),
            ft.Text(L['current_key']),
            current_key_label,
        ], wrap=True, spacing=5),
        # 第二行：工作目录、浏览、打开终端
        ft.Row([
            work_dir_field,
            ft.ElevatedButton(L['browse'], icon=ft.Icons.FOLDER_OPEN, on_click=browse_folder),
            ft.ElevatedButton(L['open_terminal'], icon=ft.Icons.TERMINAL, on_click=open_terminal),
        ]),
        # 第三行：提示词和 MCP 选择
        ft.Row([
            prompt_dropdown,
            ft.ElevatedButton("应用提示词", icon=ft.Icons.SEND, on_click=apply_selected_prompt),
            ft.ElevatedButton("选择 MCP", icon=ft.Icons.EXTENSION, on_click=show_mcp_selector),
        ]),
    ], expand=True, spacing=10)

    # ========== 提示词页面 ==========
    prompt_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0, alignment=ft.MainAxisAlignment.START)
    prompt_content = ft.TextField(
        label=L['prompt_content'],
        multiline=True,
        min_lines=12,
        expand=True,
        border_radius=8,
    )
    # 全局提示词编辑区
    system_prompt = prompt_db.get_system_prompt()
    global_prompt_content = ft.TextField(
        label="全局提示词内容（始终附加在所有提示词前面）",
        multiline=True,
        min_lines=4,
        value=system_prompt.get('content', '') if system_prompt else '',
        border_radius=8,
    )
    expanded_categories = {}

    def save_global_prompt(e):
        """保存全局提示词"""
        nonlocal system_prompt
        if not system_prompt:
            system_prompt = {'id': 'system_global', 'name': '全局提示词', 'prompt_type': 'system', 'category': '全局'}
        system_prompt['content'] = global_prompt_content.value or ''
        prompt_db.save(system_prompt)
        page.open(ft.SnackBar(ft.Text("全局提示词已保存")))
        page.update()

    def build_prompt_tree():
        """按分类构建提示词树（只显示用户提示词）"""
        tree = {}  # {category: [(id, prompt), ...]}
        for pid, p in prompts.items():
            # 跳过系统提示词
            if p.get('prompt_type') == 'system':
                continue
            cat = p.get('category', '其他')
            if cat not in tree:
                tree[cat] = []
            tree[cat].append((pid, p))
        # 排序：编程 > 写作 > 分析 > 绘画 > 用户 > 其他
        order = ['编程', '写作', '分析', '绘画', '用户', '其他']
        return {k: tree[k] for k in order if k in tree} | {k: v for k, v in tree.items() if k not in order}

    def refresh_prompt_list():
        prompt_tree.controls.clear()
        tree = build_prompt_tree()
        for cat, items in tree.items():
            is_expanded = expanded_categories.get(cat, True)
            # 分类头
            cat_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER),
                    ft.Text(cat, weight=ft.FontWeight.BOLD),
                    ft.Text(f"({len(items)})", color=ft.Colors.GREY_600),
                ], spacing=5),
                padding=ft.padding.only(left=5, top=8, bottom=8),
                on_click=lambda e, c=cat: toggle_category(c),
                bgcolor=ft.Colors.GREY_100,
                border_radius=4,
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
                            ft.Text("(内置)" if is_builtin else "", size=10, color=ft.Colors.GREY_500),
                        ], spacing=5),
                        padding=ft.padding.only(left=30, top=5, bottom=5),
                        on_click=lambda e, i=pid: select_prompt(i),
                        bgcolor=ft.Colors.BLUE_50 if is_selected else None,
                        border_radius=4,
                    )
                    prompt_tree.controls.append(item)
        page.update()

    def toggle_category(cat):
        expanded_categories[cat] = not expanded_categories.get(cat, True)
        refresh_prompt_list()

    def select_prompt(pid):
        nonlocal selected_prompt
        selected_prompt = pid
        p = prompts.get(pid, {})
        prompt_content.value = p.get('content', '')
        prompt_content.read_only = p.get('is_builtin', False)
        refresh_prompt_list()

    def add_prompt(e):
        show_prompt_dialog(None)

    def edit_prompt(e):
        if selected_prompt and not prompts.get(selected_prompt, {}).get('is_builtin'):
            show_prompt_dialog(selected_prompt)
        elif selected_prompt:
            page.open(ft.SnackBar(ft.Text("内置提示词不可编辑")))
            page.update()

    def delete_prompt(e):
        nonlocal selected_prompt, prompts
        if selected_prompt and not prompts.get(selected_prompt, {}).get('is_builtin'):
            prompt_db.delete(selected_prompt)
            prompts = prompt_db.get_all()
            selected_prompt = None
            prompt_content.value = ''
            refresh_prompt_list()
            refresh_prompt_dropdown()

    def copy_prompt(e):
        if selected_prompt:
            page.set_clipboard(prompts[selected_prompt].get('content', ''))
            page.open(ft.SnackBar(ft.Text(L['copied'])))
            page.update()

    def save_prompt_content(e):
        """保存编辑的提示词内容"""
        nonlocal prompts
        if selected_prompt and not prompts.get(selected_prompt, {}).get('is_builtin'):
            prompts[selected_prompt]['content'] = prompt_content.value or ''
            prompt_db.save(prompts[selected_prompt])
            refresh_prompt_dropdown()
            page.open(ft.SnackBar(ft.Text(L['saved'])))
            page.update()

    def show_prompt_dialog(pid):
        is_edit = pid is not None
        p = prompts.get(pid, {}) if is_edit else {}

        name_field = ft.TextField(label=L['name'], value=p.get('name', ''), expand=True)
        category_field = ft.Dropdown(
            label='分类',
            value=p.get('category', '其他'),
            options=[ft.dropdown.Option(c) for c in ['编程', '写作', '分析', '绘画', '用户', '其他']],
            expand=True,
        )
        content_field = ft.TextField(
            label=L['prompt_content'],
            value=p.get('content', ''),
            multiline=True,
            min_lines=5,
            expand=True,
        )

        def save_prompt(e):
            nonlocal prompts
            if not name_field.value:
                return
            new_id = pid if is_edit else f"custom_{int(datetime.now().timestamp())}"
            new_prompt = {
                'id': new_id,
                'name': name_field.value,
                'content': content_field.value or '',
                'category': category_field.value or '用户',
                'prompt_type': 'user',
                'is_builtin': False,
            }
            prompt_db.save(new_prompt)
            prompts = prompt_db.get_all()
            refresh_prompt_list()
            refresh_prompt_dropdown()
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([name_field, category_field, content_field], tight=True, spacing=10, width=500, height=350),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.TextButton(L['save'], on_click=save_prompt),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    prompt_page = ft.Column([
        # 全局提示词区域
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.PURPLE),
                    ft.Text("全局提示词", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text("（始终附加在所有用户提示词前面）", size=12, color=ft.Colors.GREY_600),
                ], spacing=5),
                global_prompt_content,
                ft.Row([ft.ElevatedButton("保存全局提示词", icon=ft.Icons.SAVE, on_click=save_global_prompt)]),
            ], spacing=5),
            padding=10,
            border=ft.border.all(1, ft.Colors.PURPLE_200),
            border_radius=8,
            bgcolor=ft.Colors.PURPLE_50,
        ),
        ft.Divider(),
        # 用户提示词区域
        ft.Row([
            ft.Text("用户提示词", size=16, weight=ft.FontWeight.BOLD),
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
                ft.Row([
                    ft.ElevatedButton(L['save'], icon=ft.Icons.SAVE, on_click=save_prompt_content),
                ]),
            ], expand=2),
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
    ], expand=True, spacing=10)

    # ========== MCP 页面 ==========
    mcp_tree = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
    expanded_mcp_categories = {}
    MCP_CATEGORIES = ['常用', '文件', '网络', '数据', '其他']

    def get_mcp_key(m):
        """获取 MCP 的唯一标识"""
        return m.get('name', '').lower().replace(' ', '-')

    def build_mcp_server_config(m):
        """构建 MCP 服务器配置"""
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

    def sync_mcp_to_workdir():
        """同步 MCP 到工作目录：默认 MCP + 选中的 MCP"""
        work_dir = work_dir_field.value
        if not work_dir:
            return

        mcp_path = Path(work_dir) / '.mcp.json'
        mcp_servers = {}
        for m in mcp_list:
            key = get_mcp_key(m)
            # 默认 MCP 或选中的 MCP
            if m.get('is_default') or workdir_mcp_enabled.get(key, False):
                mcp_servers[key] = build_mcp_server_config(m)

        with open(mcp_path, 'w', encoding='utf-8') as f:
            json.dump({'mcpServers': mcp_servers}, f, indent=2, ensure_ascii=False)

    def sync_default_mcp_to_global():
        """同步默认 MCP 到全局配置目录"""
        global_mcp_path = Path.home() / '.claude' / '.mcp.json'
        global_mcp_path.parent.mkdir(parents=True, exist_ok=True)
        mcp_servers = {}
        for m in mcp_list:
            if m.get('is_default'):
                mcp_servers[get_mcp_key(m)] = build_mcp_server_config(m)
        with open(global_mcp_path, 'w', encoding='utf-8') as f:
            json.dump({'mcpServers': mcp_servers}, f, indent=2, ensure_ascii=False)

    def toggle_mcp_default(idx, is_default):
        """切换 MCP 默认状态"""
        mcp_list[idx]['is_default'] = is_default
        save_mcp(mcp_list)
        sync_default_mcp_to_global()
        if work_dir_field.value:
            sync_mcp_to_workdir()
        refresh_mcp_tree()

    def build_mcp_tree():
        """按分类构建 MCP 树"""
        tree = {}
        for m in mcp_list:
            cat = m.get('category', '其他')
            if cat not in tree:
                tree[cat] = []
            tree[cat].append(m)
        return {k: tree[k] for k in MCP_CATEGORIES if k in tree} | {k: v for k, v in tree.items() if k not in MCP_CATEGORIES}

    def refresh_mcp_tree():
        mcp_tree.controls.clear()
        tree = build_mcp_tree()
        for cat, items in tree.items():
            is_expanded = expanded_mcp_categories.get(cat, True)
            cat_header = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN if is_expanded else ft.Icons.ARROW_RIGHT, size=20),
                    ft.Icon(ft.Icons.FOLDER, color=ft.Colors.AMBER),
                    ft.Text(cat, weight=ft.FontWeight.BOLD),
                    ft.Text(f"({len(items)})", color=ft.Colors.GREY_600),
                ], spacing=5),
                padding=ft.padding.only(left=5, top=8, bottom=8),
                on_click=lambda e, c=cat: toggle_mcp_category(c),
                bgcolor=ft.Colors.GREY_100,
                border_radius=4,
            )
            mcp_tree.controls.append(cat_header)
            if is_expanded:
                for i, m in enumerate(mcp_list):
                    if m.get('category', '其他') != cat:
                        continue
                    is_selected = selected_mcp == i
                    is_default = m.get('is_default', False)
                    item = ft.Container(
                        content=ft.Row([
                            ft.Checkbox(value=is_default, on_change=lambda e, idx=i: toggle_mcp_default(idx, e.control.value),
                                       tooltip="设为默认（始终加载）"),
                            ft.Icon(ft.Icons.STAR if is_default else ft.Icons.EXTENSION, size=16,
                                   color=ft.Colors.ORANGE if is_default else (ft.Colors.BLUE if is_selected else ft.Colors.GREY_600)),
                            ft.Column([
                                ft.Text(m.get('name', 'Unnamed'),
                                       weight=ft.FontWeight.BOLD if is_selected else None,
                                       color=ft.Colors.BLUE if is_selected else None),
                                ft.Text(f"{m.get('command', '')} {m.get('args', '')}", size=10, color=ft.Colors.GREY_500),
                            ], spacing=0, expand=True),
                        ], spacing=5),
                        padding=ft.padding.only(left=30, top=5, bottom=5),
                        on_click=lambda e, idx=i: select_mcp(idx),
                        bgcolor=ft.Colors.BLUE_50 if is_selected else None,
                        border_radius=4,
                    )
                    mcp_tree.controls.append(item)
        page.update()

    def toggle_mcp_category(cat):
        expanded_mcp_categories[cat] = not expanded_mcp_categories.get(cat, True)
        refresh_mcp_tree()

    def select_mcp(idx):
        nonlocal selected_mcp
        selected_mcp = idx
        refresh_mcp_tree()

    def add_mcp(e):
        show_mcp_dialog(None)

    def edit_mcp(e):
        if selected_mcp is not None:
            show_mcp_dialog(selected_mcp)

    def delete_mcp(e):
        nonlocal selected_mcp
        if selected_mcp is not None:
            mcp_list.pop(selected_mcp)
            save_mcp(mcp_list)
            selected_mcp = None
            refresh_mcp_tree()

    def add_from_official(e):
        """从官方 MCP 列表选择添加"""
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
            # 预填充并打开编辑对话框
            args_hint = server.get('args_hint', '')
            env_hint = server.get('env_hint', '')
            new_m = {
                'name': server['name'],
                'command': 'npx',
                'args': f"-y {server['package']}" + (f" {args_hint}" if args_hint else ""),
                'env': env_hint,
            }
            mcp_list.append(new_m)
            save_mcp(mcp_list)
            refresh_mcp_tree()
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(f"已添加 {server['name']}")))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("选择官方 MCP 服务器"),
            content=ft.Container(official_list, width=450, height=400),
            actions=[ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update())],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_mcp_dialog(idx):
        is_edit = idx is not None
        m = mcp_list[idx] if is_edit else {}

        name_field = ft.TextField(label=L['name'], value=m.get('name', ''), expand=True)
        category_field = ft.Dropdown(
            label='分类',
            value=m.get('category', '其他'),
            options=[ft.dropdown.Option(c) for c in MCP_CATEGORIES],
            expand=True,
        )
        command_field = ft.TextField(label=L['mcp_command'], value=m.get('command', 'npx'), expand=True)
        args_field = ft.TextField(label=L['mcp_args'], value=m.get('args', ''), expand=True)
        env_field = ft.TextField(label=L['mcp_env'], value=m.get('env', ''), expand=True)

        def save_mcp_item(e):
            if not name_field.value:
                return
            new_m = {
                'name': name_field.value,
                'category': category_field.value or '其他',
                'command': command_field.value,
                'args': args_field.value,
                'env': env_field.value,
                'is_default': m.get('is_default', False) if is_edit else False,
            }
            if is_edit:
                mcp_list[idx] = new_m
            else:
                mcp_list.append(new_m)
            save_mcp(mcp_list)
            refresh_mcp_tree()
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['edit'] if is_edit else L['add']),
            content=ft.Column([name_field, category_field, command_field, args_field, env_field], tight=True, spacing=10, width=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.TextButton(L['save'], on_click=save_mcp_item),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def browse_mcp_market(e):
        """浏览 MCP 市场"""
        import webbrowser
        market_list = ft.ListView(expand=True, spacing=2)
        for m in MCP_MARKETPLACES:
            tile = ft.ListTile(
                leading=ft.Icon(ft.Icons.STORE, color=ft.Colors.PURPLE),
                title=ft.Text(m['name']),
                subtitle=ft.Text(m['desc']),
                on_click=lambda e, url=m['url']: webbrowser.open(url),
            )
            market_list.controls.append(tile)

        dlg = ft.AlertDialog(
            title=ft.Text("MCP 市场"),
            content=ft.Container(market_list, width=400, height=250),
            actions=[ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update())],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def parse_mcp_json(data: dict) -> list[dict]:
        """解析 MCP JSON 配置，返回 MCP 列表"""
        results = []
        servers = data.get('mcpServers', data) if isinstance(data, dict) else {}
        for name, cfg in servers.items():
            if not isinstance(cfg, dict):
                continue
            args = cfg.get('args', [])
            env = cfg.get('env', {})
            results.append({
                'name': name,
                'category': '其他',
                'command': cfg.get('command', 'npx'),
                'args': ' '.join(args) if isinstance(args, list) else str(args),
                'env': ' '.join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else '',
                'is_default': False,
            })
        return results

    def import_from_clipboard(e):
        """从剪贴板导入 MCP"""
        async def do_import():
            try:
                clip = await page.get_clipboard_async()
                if not clip:
                    page.open(ft.SnackBar(ft.Text("剪贴板为空")))
                    page.update()
                    return
                data = json.loads(clip)
                items = parse_mcp_json(data)
                if items:
                    mcp_list.extend(items)
                    save_mcp(mcp_list)
                    refresh_mcp_tree()
                    page.open(ft.SnackBar(ft.Text(f"已导入 {len(items)} 个 MCP")))
                else:
                    page.open(ft.SnackBar(ft.Text("未找到有效配置")))
            except json.JSONDecodeError:
                page.open(ft.SnackBar(ft.Text("剪贴板内容不是有效的 JSON")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(f"导入失败: {ex}")))
            page.update()
        page.run_task(do_import)

    def import_from_file(e):
        """从文件导入 MCP"""
        def on_result(ev: ft.FilePickerResultEvent):
            if not ev.files:
                return
            try:
                with open(ev.files[0].path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = parse_mcp_json(data)
                if items:
                    mcp_list.extend(items)
                    save_mcp(mcp_list)
                    refresh_mcp_tree()
                    page.open(ft.SnackBar(ft.Text(f"已导入 {len(items)} 个 MCP")))
                else:
                    page.open(ft.SnackBar(ft.Text("未找到有效配置")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(f"导入失败: {ex}")))
            page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.pick_files(allowed_extensions=['json'], dialog_title="选择 MCP 配置文件")

    def import_from_text(e):
        """从文本输入导入 MCP"""
        text_field = ft.TextField(
            label="粘贴 JSON 配置",
            multiline=True,
            min_lines=10,
            max_lines=15,
            expand=True,
        )

        def do_import(ev):
            try:
                data = json.loads(text_field.value or '{}')
                items = parse_mcp_json(data)
                if items:
                    mcp_list.extend(items)
                    save_mcp(mcp_list)
                    refresh_mcp_tree()
                    dlg.open = False
                    page.open(ft.SnackBar(ft.Text(f"已导入 {len(items)} 个 MCP")))
                else:
                    page.open(ft.SnackBar(ft.Text("未找到有效配置")))
            except json.JSONDecodeError:
                page.open(ft.SnackBar(ft.Text("JSON 格式错误")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(f"导入失败: {ex}")))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("从文本导入 MCP"),
            content=ft.Container(
                ft.Column([
                    ft.Text("支持格式：{\"mcpServers\": {...}} 或 {\"name\": {...}}", size=12, color=ft.Colors.GREY_600),
                    text_field,
                ], tight=True),
                width=500, height=350,
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.ElevatedButton("导入", on_click=do_import),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_import_menu(e):
        """显示导入菜单"""
        dlg = ft.AlertDialog(
            title=ft.Text("导入 MCP"),
            content=ft.Column([
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CONTENT_PASTE, color=ft.Colors.BLUE),
                    title=ft.Text("从剪贴板导入"),
                    subtitle=ft.Text("直接粘贴 JSON 配置"),
                    on_click=lambda e: (setattr(dlg, 'open', False), page.update(), import_from_clipboard(e)),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.FILE_OPEN, color=ft.Colors.GREEN),
                    title=ft.Text("从文件导入"),
                    subtitle=ft.Text("选择 .mcp.json 或其他 JSON 文件"),
                    on_click=lambda e: (setattr(dlg, 'open', False), page.update(), import_from_file(e)),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.TEXT_FIELDS, color=ft.Colors.ORANGE),
                    title=ft.Text("从文本导入"),
                    subtitle=ft.Text("手动粘贴 JSON 文本"),
                    on_click=lambda e: (setattr(dlg, 'open', False), page.update(), import_from_text(e)),
                ),
            ], tight=True, spacing=0),
            actions=[ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update())],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # MCP 本地仓库浏览器
    mcp_fetch_log = []  # 调试日志

    def show_mcp_repository(e):
        """显示本地 MCP 仓库浏览器"""
        stats = mcp_registry.get_stats()

        # 如果本地仓库为空，先同步
        if stats['total'] == 0:
            sync_mcp_repository(e)
            return

        show_repository_browser(stats)

    def sync_mcp_repository(e):
        """同步 MCP 仓库（从多个源获取）"""
        status_text = ft.Text("准备同步...")
        progress = ft.ProgressBar(width=400)

        loading_dlg = ft.AlertDialog(
            title=ft.Text("同步 MCP 仓库"),
            content=ft.Column([
                progress,
                status_text,
                ft.Text("从 PulseMCP、Smithery、GitHub 等源获取...", size=12, color=ft.Colors.GREY_600),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            modal=True,
        )
        page.overlay.append(loading_dlg)
        loading_dlg.open = True
        page.update()

        def do_sync():
            mcp_fetch_log.clear()

            def on_progress(msg):
                mcp_fetch_log.append(msg)
                status_text.value = msg
                page.update()

            new_count, errors = mcp_registry.fetch_all(callback=on_progress)

            loading_dlg.open = False
            page.update()

            stats = mcp_registry.get_stats()
            if errors:
                mcp_fetch_log.extend(errors)

            # 显示结果
            if stats['total'] > 0:
                page.open(ft.SnackBar(ft.Text(f"同步完成：共 {stats['total']} 个 MCP，新增 {new_count} 个")))
                show_repository_browser(stats)
            else:
                show_sync_debug()

        import threading
        threading.Thread(target=do_sync, daemon=True).start()

    def show_sync_debug():
        """显示同步调试信息"""
        log_text = "\n".join(mcp_fetch_log)
        dlg = ft.AlertDialog(
            title=ft.Text("同步失败 - 调试信息", color=ft.Colors.RED),
            content=ft.Container(
                ft.TextField(value=log_text, multiline=True, read_only=True, min_lines=15, max_lines=20, expand=True),
                width=600, height=400,
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: setattr(dlg, 'open', False) or page.update())],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_repository_browser(stats: dict):
        """显示 MCP 仓库浏览器（使用 SQLite FTS5 搜索）"""
        search_field = ft.TextField(label="搜索", prefix_icon=ft.Icons.SEARCH, expand=True)
        category_dropdown = ft.Dropdown(
            label="分类",
            value="全部",
            options=[ft.dropdown.Option("全部")] + [ft.dropdown.Option(c) for c in ['文件', '网络', '数据', 'AI', '开发', '工具', '其他']],
            width=120,
        )
        result_list = ft.ListView(expand=True, spacing=2)
        selected_items = set()
        selected_count_text = ft.Text("已选: 0", color=ft.Colors.GREY_600)

        def filter_list(e=None):
            result_list.controls.clear()
            keyword = search_field.value or ''
            cat_filter = category_dropdown.value or '全部'

            # 使用 SQLite FTS5 搜索
            servers = mcp_registry.search(keyword, cat_filter, limit=200)

            for item in servers:
                name = item.get('name', '')
                desc = item.get('description', '') or ''
                cat = item.get('category', '其他')
                source = item.get('source', '')
                is_selected = name in selected_items

                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_selected, on_change=lambda e, n=name: toggle_select(n, e.control.value)),
                        ft.Column([
                            ft.Row([
                                ft.Text(name, weight=ft.FontWeight.BOLD if is_selected else None, expand=True),
                                ft.Container(
                                    ft.Text(cat, size=10, color=ft.Colors.WHITE),
                                    bgcolor=ft.Colors.BLUE_400, padding=ft.padding.symmetric(2, 6), border_radius=8,
                                ),
                                ft.Text(source, size=9, color=ft.Colors.GREY_400),
                            ], spacing=5),
                            ft.Text(desc[:100] + ('...' if len(desc) > 100 else ''), size=11, color=ft.Colors.GREY_600),
                        ], spacing=2, expand=True),
                    ], spacing=10),
                    padding=8,
                    bgcolor=ft.Colors.BLUE_50 if is_selected else None,
                    border_radius=4,
                )
                result_list.controls.append(tile)

            if len(servers) >= 200:
                result_list.controls.append(ft.Text("... 还有更多，请使用搜索缩小范围", color=ft.Colors.GREY_500, italic=True))
            page.update()

        def toggle_select(name, checked):
            if checked:
                selected_items.add(name)
            else:
                selected_items.discard(name)
            selected_count_text.value = f"已选: {len(selected_items)}"
            filter_list()

        def add_selected(e):
            added = 0
            # 从数据库获取选中的服务器详情
            for name in selected_items:
                items = mcp_registry.search(name, limit=1)
                if items:
                    item = items[0]
                    pkg = item.get('package', item['name'])
                    mcp_list.append({
                        'name': item['name'],
                        'category': item.get('category', '其他'),
                        'command': item.get('command', 'npx'),
                        'args': item.get('args') or f"-y {pkg}",
                        'env': '',
                        'is_default': False,
                    })
                    added += 1
            if added:
                save_mcp(mcp_list)
                refresh_mcp_tree()
                dlg.open = False
                page.open(ft.SnackBar(ft.Text(f"已添加 {added} 个 MCP")))
            page.update()

        # 绑定事件
        search_field.on_change = filter_list
        category_dropdown.on_change = filter_list

        # 初始加载
        filter_list()

        # 更新时间显示
        updated = stats.get('updated_at', '未知')[:16].replace('T', ' ') if stats.get('updated_at') else '未同步'

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Text(f"MCP 仓库 ({stats['total']} 个)", weight=ft.FontWeight.BOLD),
                ft.Text(f"更新: {updated}", size=11, color=ft.Colors.GREY_500),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: (setattr(dlg, 'open', False), page.update(), sync_mcp_repository(e)), tooltip="重新同步"),
            ], spacing=10),
            content=ft.Container(
                ft.Column([
                    ft.Row([search_field, category_dropdown], spacing=10),
                    ft.Container(result_list, expand=True),
                ], spacing=10),
                width=650, height=500,
            ),
            actions=[
                selected_count_text,
                ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                ft.ElevatedButton("添加选中", on_click=add_selected),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # 启动时检查是否需要自动更新
    def check_auto_update():
        if mcp_registry.needs_update(days=7):
            # 后台静默更新
            import threading
            def bg_update():
                mcp_registry.fetch_all()
            threading.Thread(target=bg_update, daemon=True).start()

    check_auto_update()

    mcp_page = ft.Column([
        ft.Row([
            ft.Text(L['mcp'], size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(ft.Icons.ADD, on_click=add_mcp, tooltip=L['add']),
            ft.IconButton(ft.Icons.DOWNLOAD, on_click=show_import_menu, tooltip="导入"),
            ft.IconButton(ft.Icons.CLOUD_SYNC, on_click=show_mcp_repository, tooltip="MCP 仓库"),
            ft.IconButton(ft.Icons.CLOUD_DOWNLOAD, on_click=add_from_official, tooltip="官方推荐"),
            ft.IconButton(ft.Icons.STORE, on_click=browse_mcp_market, tooltip="MCP市场"),
            ft.IconButton(ft.Icons.EDIT, on_click=edit_mcp, tooltip=L['edit']),
            ft.IconButton(ft.Icons.DELETE, on_click=delete_mcp, tooltip=L['delete']),
        ]),
        ft.Text("勾选设为默认 MCP（始终加载到全局和工作目录）", size=12, color=ft.Colors.GREY_600),
        ft.Container(mcp_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
    ], expand=True, spacing=10)

    # ========== 导航和页面切换 ==========
    content_area = ft.Container(api_page, expand=True, padding=20)

    def switch_page(e):
        idx = e.control.selected_index
        if idx == 0:
            content_area.content = api_page
            refresh_config_list()
        elif idx == 1:
            content_area.content = prompt_page
            refresh_prompt_list()
        elif idx == 2:
            content_area.content = mcp_page
            refresh_mcp_tree()
        page.update()

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.KEY, label=L['api_config']),
            ft.NavigationRailDestination(icon=ft.Icons.CHAT, label=L['prompts']),
            ft.NavigationRailDestination(icon=ft.Icons.EXTENSION, label=L['mcp']),
        ],
        on_change=switch_page,
        trailing=ft.Container(
            content=ft.Column([
                ft.TextButton("中/EN", icon=ft.Icons.LANGUAGE, on_click=switch_lang),
                ft.TextButton(L['feedback'], on_click=open_feedback),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(bottom=20),
        ),
    )

    # 主布局
    page.add(
        ft.Row([
            nav_rail,
            ft.VerticalDivider(width=1),
            content_area,
        ], expand=True)
    )

    # 初始化列表
    refresh_config_list()

    # 首次启动：后台自动刷新终端和环境
    if first_run:
        async def background_refresh():
            nonlocal terminals, python_envs
            terminals = detect_terminals()
            python_envs = detect_python_envs()
            settings['terminals_cache'] = terminals
            settings['envs_cache'] = python_envs
            save_settings(settings)
            terminal_dropdown.options = [ft.dropdown.Option(k) for k in terminals.keys()]
            python_env_dropdown.options = [ft.dropdown.Option(k) for k in python_envs.keys()]
            if terminals:
                terminal_dropdown.value = list(terminals.keys())[0]
            if python_envs:
                python_env_dropdown.value = list(python_envs.keys())[0]
            page.update()
        page.run_task(background_refresh)


if __name__ == "__main__":
    ft.app(target=main)
