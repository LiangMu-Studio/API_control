# AI CLI Manager - Flet Version
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
import time  # DEBUG
import threading

DEBUG = False  # 调试开关
TRASH_RETENTION_DAYS = 7  # 回收站保留天数

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

# ========== Claude 历史记录管理 ==========
CLAUDE_DIR = Path(os.path.expanduser("~")) / ".claude"

class TrashManager:
    """回收站管理器"""
    def __init__(self, claude_dir: Path):
        self.claude_dir = claude_dir
        self.trash_dir = claude_dir / "trash"
        self.trash_dir.mkdir(exist_ok=True)
        self.manifest_file = self.trash_dir / "manifest.json"

    def _load_manifest(self) -> dict:
        if self.manifest_file.exists():
            try:
                return json.loads(self.manifest_file.read_text(encoding='utf-8'))
            except:
                pass
        return {"items": []}

    def _save_manifest(self, manifest: dict):
        self.manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

    def move_to_trash(self, session_id: str, project_name: str, session_file: Path, file_history_dir: Path | None = None) -> bool:
        try:
            timestamp = int(time.time())
            item_dir = self.trash_dir / f"{session_id}_{timestamp}"
            item_dir.mkdir(exist_ok=True)
            if session_file.exists():
                shutil.move(str(session_file), str(item_dir / session_file.name))
            if file_history_dir and file_history_dir.exists():
                shutil.move(str(file_history_dir), str(item_dir / "file-history"))
            manifest = self._load_manifest()
            manifest["items"].append({
                "session_id": session_id, "project_name": project_name,
                "deleted_at": timestamp, "dir_name": item_dir.name,
                "original_file": str(session_file),
                "original_file_history": str(file_history_dir) if file_history_dir else None
            })
            self._save_manifest(manifest)
            return True
        except:
            return False

    def restore_from_trash(self, item: dict) -> bool:
        try:
            item_dir = self.trash_dir / item["dir_name"]
            if not item_dir.exists():
                return False
            original_file = Path(item["original_file"])
            original_file.parent.mkdir(parents=True, exist_ok=True)
            for f in item_dir.glob("*.jsonl"):
                shutil.move(str(f), str(original_file))
                break
            if item.get("original_file_history"):
                fh_src = item_dir / "file-history"
                if fh_src.exists():
                    shutil.move(str(fh_src), item["original_file_history"])
            shutil.rmtree(item_dir, ignore_errors=True)
            manifest = self._load_manifest()
            manifest["items"] = [i for i in manifest["items"] if i["session_id"] != item["session_id"]]
            self._save_manifest(manifest)
            return True
        except:
            return False

    def cleanup_expired(self) -> int:
        manifest = self._load_manifest()
        now = time.time()
        cutoff = now - (TRASH_RETENTION_DAYS * 24 * 3600)
        removed = 0
        remaining = []
        for item in manifest["items"]:
            if item["deleted_at"] < cutoff:
                shutil.rmtree(self.trash_dir / item["dir_name"], ignore_errors=True)
                removed += 1
            else:
                remaining.append(item)
        manifest["items"] = remaining
        self._save_manifest(manifest)
        return removed

    def get_trash_items(self) -> list:
        return self._load_manifest().get("items", [])

    def permanently_delete(self, item: dict):
        shutil.rmtree(self.trash_dir / item["dir_name"], ignore_errors=True)
        manifest = self._load_manifest()
        manifest["items"] = [i for i in manifest["items"] if i["dir_name"] != item["dir_name"]]
        self._save_manifest(manifest)


class HistoryManager:
    """Claude 历史记录管理器"""
    def __init__(self, claude_dir: Path):
        self.claude_dir = claude_dir
        self.trash_manager = TrashManager(claude_dir)

    def load_sessions(self, callback=None) -> dict:
        """加载所有会话数据"""
        projects_dir = self.claude_dir / "projects"
        result = {}
        if not projects_dir.exists():
            return result
        project_dirs = list(projects_dir.iterdir())
        for project_dir in project_dirs:
            if not project_dir.is_dir():
                continue
            if callback:
                callback(f"扫描: {project_dir.name[:30]}...")
            project_name = project_dir.name
            result[project_name] = {}
            for session_file in project_dir.glob("*.jsonl"):
                if session_file.name.startswith("agent-"):
                    continue
                session_id = session_file.stem
                info = self._parse_session(session_file)
                if info:
                    result[project_name][session_id] = info
        return result

    def _parse_session(self, session_file: Path) -> dict | None:
        try:
            messages = []
            first_ts, last_ts, cwd = None, None, None
            with open(session_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if data.get('type') in ('user', 'assistant'):
                            ts = data.get('timestamp')
                            if ts:
                                if not first_ts:
                                    first_ts = ts
                                last_ts = ts
                            if not cwd:
                                cwd = data.get('cwd')
                            messages.append(data)
                    except:
                        pass
            if not messages:
                return None
            return {
                'file': session_file, 'messages': messages, 'message_count': len(messages),
                'first_timestamp': first_ts, 'last_timestamp': last_ts, 'cwd': cwd,
                'size': session_file.stat().st_size
            }
        except:
            return None

    def delete_session(self, project_name: str, session_id: str, info: dict) -> bool:
        file_history_dir = self.claude_dir / "file-history" / session_id
        success = self.trash_manager.move_to_trash(
            session_id, project_name, info['file'],
            file_history_dir if file_history_dir.exists() else None
        )
        if success:
            self._remove_from_history(session_id)
        return success

    def _remove_from_history(self, session_id: str):
        history_file = self.claude_dir / "history.jsonl"
        if not history_file.exists():
            return
        try:
            lines = []
            with open(history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get('sessionId') != session_id:
                                lines.append(line)
                        except:
                            lines.append(line)
            with open(history_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except:
            pass

    def export_to_markdown(self, session_id: str, info: dict) -> str:
        lines = [f"# 会话: {session_id}\n", f"路径: {info.get('cwd', '未知')}\n\n---\n\n"]
        for msg in info['messages']:
            role = msg.get('message', {}).get('role', '未知')
            ts = msg.get('timestamp', '')
            content = msg.get('message', {}).get('content', [])
            text = ""
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get('type') == 'text':
                        text += c.get('text', '')
            elif isinstance(content, str):
                text = content
            lines.append(f"## {role.upper()} ({ts[:19] if ts else ''})\n\n{text}\n\n---\n\n")
        return ''.join(lines)


class CodexHistoryManager:
    """Codex 历史记录管理器"""
    def __init__(self, codex_dir: Path):
        self.codex_dir = codex_dir
        self.trash_manager = TrashManager(codex_dir)

    def load_sessions(self, callback=None) -> dict:
        """加载所有会话数据，按日期分组"""
        sessions_dir = self.codex_dir / "sessions"
        result = {}
        if not sessions_dir.exists():
            return result
        # 遍历 sessions/YYYY/MM/DD/*.jsonl
        for session_file in sessions_dir.rglob("*.jsonl"):
            if callback:
                callback(f"扫描: {session_file.name[:30]}...")
            # 从路径提取日期作为分组
            parts = session_file.relative_to(sessions_dir).parts
            if len(parts) >= 3:
                date_group = f"{parts[0]}-{parts[1]}-{parts[2]}"
            else:
                date_group = "未知日期"
            if date_group not in result:
                result[date_group] = {}
            session_id = session_file.stem.replace("rollout-", "")
            info = self._parse_session(session_file)
            if info:
                result[date_group][session_id] = info
        return result

    def _parse_session(self, session_file: Path) -> dict | None:
        try:
            messages = []
            first_ts, last_ts, cwd = None, None, None
            with open(session_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        ts = data.get('timestamp')
                        if ts:
                            if not first_ts:
                                first_ts = ts
                            last_ts = ts
                        # 提取 cwd
                        if data.get('type') == 'session_meta':
                            cwd = data.get('payload', {}).get('cwd')
                        # 提取消息
                        if data.get('type') == 'response_item':
                            payload = data.get('payload', {})
                            if payload.get('type') == 'message':
                                messages.append(payload)
                        elif data.get('type') == 'event_msg':
                            payload = data.get('payload', {})
                            if payload.get('type') in ('user_message', 'agent_message'):
                                messages.append({'role': 'user' if 'user' in payload.get('type') else 'assistant',
                                                'content': payload.get('message', '')})
                    except:
                        pass
            if not messages:
                return None
            return {
                'file': session_file, 'messages': messages, 'message_count': len(messages),
                'first_timestamp': first_ts, 'last_timestamp': last_ts, 'cwd': cwd,
                'size': session_file.stat().st_size
            }
        except:
            return None

    def delete_session(self, date_group: str, session_id: str, info: dict) -> bool:
        return self.trash_manager.move_to_trash(session_id, date_group, info['file'])

    def export_to_markdown(self, session_id: str, info: dict) -> str:
        lines = [f"# Codex 会话: {session_id}\n", f"路径: {info.get('cwd', '未知')}\n\n---\n\n"]
        for msg in info['messages']:
            role = msg.get('role', '未知')
            content = msg.get('content', '')
            if isinstance(content, list):
                text = ""
                for c in content:
                    if isinstance(c, dict) and c.get('type') in ('input_text', 'output_text'):
                        text += c.get('text', '')
            else:
                text = str(content)
            lines.append(f"## {role.upper()}\n\n{text}\n\n---\n\n")
        return ''.join(lines)


# 全局历史管理器实例
CODEX_DIR = Path(os.path.expanduser("~")) / ".codex"
KIRO_DIR = Path(os.path.expanduser("~")) / ".kiro"
history_manager = HistoryManager(CLAUDE_DIR) if CLAUDE_DIR.exists() else None
codex_history_manager = CodexHistoryManager(CODEX_DIR) if CODEX_DIR.exists() else None

# 全局历史缓存（避免重复加载）
history_cache = {"claude": {}, "codex": {}}

# 提示词标识符（用于检测和同步）
SYSTEM_PROMPT_START = "<!-- GLOBAL_PROMPT_START -->"
SYSTEM_PROMPT_END = "<!-- GLOBAL_PROMPT_END -->"
USER_PROMPT_START = "<!-- USER_PROMPT_START:{id} -->"
USER_PROMPT_END = "<!-- USER_PROMPT_END -->"

# 内置提示词（来自 AI_talk）
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
        'title': 'AI CLI Manager v{}',
        'api_config': 'API 密钥配置',
        'prompts': '提示词',
        'prompt_builtin': '(内置)',
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
        'copy_key': '复制',
        'exported_to': '配置已导出到: {}',
        'imported_count': '已导入 {} 个配置',
        # 历史管理
        'history': '历史记录',
        'history_sessions': '会话数',
        'history_messages': '消息数',
        'history_size': '占用空间',
        'history_refresh': '刷新',
        'history_delete': '删除',
        'history_trash': '回收站',
        'history_export': '导出MD',
        'history_copy_resume': '复制resume',
        'history_search': '搜索会话...',
        'history_old': '30天前 ({}个)',
        'history_confirm_delete': '确定删除 {} 个会话？\n会话将移动到回收站，{}天后自动清理。',
        'history_moved': '已移动 {} 个会话到回收站',
        'history_restored': '已恢复 {} 个会话',
        'history_trash_info': '回收站中的会话将在 {} 天后自动删除',
        'history_restore': '恢复',
        'history_perm_delete': '永久删除',
        'history_clear_trash': '清空回收站',
        # MCP
        'mcp_sync': '同步仓库',
        'mcp_browse': '浏览仓库',
        'mcp_import': '导入',
        'mcp_official': '官方推荐',
        'mcp_default_hint': '勾选设为默认 MCP（始终加载到全局和工作目录）',
        'mcp_search': '搜索',
        'mcp_category': '分类',
        'mcp_all': '全部',
        'mcp_selected': '已选: {}',
        'mcp_add_selected': '添加选中',
        'mcp_added': '已添加 {} 个 MCP',
        'mcp_sync_complete': '同步完成：共 {} 个 MCP，新增 {} 个',
        'mcp_sync_fail': '同步失败 - 调试信息',
        'mcp_sync_title': '同步 MCP 仓库',
        'mcp_sync_preparing': '准备同步...',
        'mcp_sync_sources': '从 PulseMCP、Smithery、GitHub 等源获取...',
        'mcp_set_default_hint': '设为默认（始终加载）',
        'mcp_import_title': '导入 MCP',
        'mcp_import_clipboard': '从剪贴板导入',
        'mcp_import_clipboard_desc': '直接粘贴 JSON 配置',
        'mcp_import_file': '从文件导入',
        'mcp_import_file_desc': '选择 .mcp.json 或其他 JSON 文件',
        'mcp_import_text': '从文本导入',
        'mcp_import_text_desc': '手动粘贴 JSON 文本',
        'mcp_import_format': '支持格式：{"mcpServers": {...}} 或 {"name": {...}}',
        'mcp_clipboard_empty': '剪贴板为空',
        'mcp_invalid_json': '剪贴板内容不是有效的 JSON',
        'mcp_no_valid_config': '未找到有效配置',
        'mcp_import_fail': '导入失败: {}',
        'mcp_select_official': '选择官方 MCP 服务器',
        'mcp_other': '其他',
        # MCP 分类
        'mcp_cat_cloud': '云服务', 'mcp_cat_map': '地图', 'mcp_cat_media': '媒体', 'mcp_cat_security': '安全',
        'mcp_cat_tool': '工具', 'mcp_cat_dev': '开发', 'mcp_cat_search': '搜索', 'mcp_cat_db': '数据库',
        'mcp_cat_file': '文件', 'mcp_cat_news': '新闻', 'mcp_cat_calendar': '日历', 'mcp_cat_model': '模型',
        'mcp_cat_browser': '浏览器', 'mcp_cat_game': '游戏', 'mcp_cat_ecommerce': '电商', 'mcp_cat_knowledge': '知识库',
        'mcp_cat_social': '社交', 'mcp_cat_note': '笔记', 'mcp_cat_network': '网络', 'mcp_cat_design': '设计',
        'mcp_cat_comm': '通讯', 'mcp_cat_finance': '金融', 'mcp_cat_project': '项目', 'mcp_cat_other': '其他',
        # Prompts
        'prompt_global': '全局提示词',
        'prompt_user': '用户提示词',
        'prompt_save_global': '保存全局提示词',
        'prompt_global_saved': '全局提示词已保存',
        'prompt_builtin_readonly': '内置提示词不可编辑',
        'prompt_apply': '应用提示词',
        'prompt_select_mcp': '选择 MCP',
        'prompt_select_workdir': '请先选择工作目录',
        'prompt_written': '已写入: {}',
        'prompt_write_fail': '写入失败: {}',
        'prompt_loaded': '已加载工作目录配置',
        'prompt_loaded_with': '已加载工作目录配置 | 提示词: {}',
        'prompt_no_config': '已选择工作目录（无现有配置）',
        'prompt_select_extra_mcp': '选择额外 MCP（默认 MCP 已自动加载）',
        'prompt_apply_btn': '应用',
        # History detail
        'history_session': '会话: {}',
        'history_path': '路径: {}',
        'history_copy_id': '复制ID',
        'history_export_md': '导出MD',
        'history_open_location': '打开位置',
        'history_expand_middle': '▼ 展开中间 {} 条消息 ▼',
        'history_no_content': '(无文本内容)',
        'history_tool': '[工具: {}]',
        'history_tool_result': '[工具结果]',
        'history_unknown': '未知',
        'history_unknown_date': '未知日期',
        'history_no_records': '无历史记录',
        'history_copied': '已复制: {}...',
        'history_exported': '已导出: {}',
        'history_click_hint': '点击选中，支持多选',
        'history_short_sessions': '短会话:',
        'history_empty_dirs': '空目录:',
        'history_cleanup': '清理会话',
        'history_cleanup_preview': '预览:',
        'history_cleanup_hint': '清理后会话将移至回收站',
        'history_cleanup_execute': '执行清理',
        'history_cleanup_done': '已清理 {} 个会话, {} 个空目录',
        'history_trash_cleared': '回收站已清空',
        'history_perm_deleted': '已永久删除 {} 个会话',
        'history_delete_selected': '删除选中',
        'history_delete_project': '删除此项目所有会话',
        # Date filter
        'date_all': '全部',
        'date_today': '今天',
        'date_week': '本周',
        'date_month': '本月',
        'date_custom': '自定义',
        'date_from': '起始日期',
        'date_to': '结束日期',
        # Terminal
        'terminal_issues': '检测到以下问题：',
        'terminal_continue': '继续启动',
        # Theme
        'toggle_theme': '切换主题',
        'switch_lang': '中/EN',
        'close': '关闭',
        # MCP Repository
        'mcp_repo_title': 'MCP 仓库 ({} 个)',
        'mcp_updated': '更新: {}',
        'mcp_resync': '重新同步',
        'mcp_more_hint': '... 还有更多，请使用搜索缩小范围',
        'mcp_market': 'MCP市场',
        'mcp_not_synced': '未同步',
        # History cleanup
        'history_selected_count': '已选 {} 项',
        'history_short_label': '短会话（≤3条且≤150字）: {}个',
        'history_old_label': '30天前会话: {}个',
        'history_empty_label': '空项目目录: {}个',
    },
    'en': {
        'title': 'AI CLI Manager v{}',
        'api_config': 'API Key Config',
        'prompts': 'Prompts',
        'prompt_builtin': '(Built-in)',
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
        # History
        'history': 'History',
        'history_sessions': 'Sessions',
        'history_messages': 'Messages',
        'history_size': 'Size',
        'history_refresh': 'Refresh',
        'history_delete': 'Delete',
        'history_trash': 'Trash',
        'history_export': 'Export MD',
        'history_copy_resume': 'Copy Resume',
        'history_search': 'Search sessions...',
        'history_old': 'Over 30 days ({})',
        'history_confirm_delete': 'Delete {} sessions?\nThey will be moved to trash and auto-deleted after {} days.',
        'history_moved': 'Moved {} sessions to trash',
        'history_restored': 'Restored {} sessions',
        'history_trash_info': 'Sessions in trash will be auto-deleted after {} days',
        'history_restore': 'Restore',
        'history_perm_delete': 'Delete Permanently',
        'history_clear_trash': 'Empty Trash',
        # MCP
        'mcp_sync': 'Sync Repository',
        'mcp_browse': 'Browse Repository',
        'mcp_import': 'Import',
        'mcp_official': 'Official',
        'mcp_default_hint': 'Check to set as default MCP (always loaded)',
        'mcp_search': 'Search',
        'mcp_category': 'Category',
        'mcp_all': 'All',
        'mcp_selected': 'Selected: {}',
        'mcp_add_selected': 'Add Selected',
        'mcp_added': 'Added {} MCP(s)',
        'mcp_sync_complete': 'Sync complete: {} MCPs, {} new',
        'mcp_sync_fail': 'Sync Failed - Debug Info',
        'mcp_sync_title': 'Sync MCP Repository',
        'mcp_sync_preparing': 'Preparing to sync...',
        'mcp_sync_sources': 'Fetching from PulseMCP, Smithery, GitHub...',
        'mcp_set_default_hint': 'Set as default (always load)',
        'mcp_import_title': 'Import MCP',
        'mcp_import_clipboard': 'From Clipboard',
        'mcp_import_clipboard_desc': 'Paste JSON config directly',
        'mcp_import_file': 'From File',
        'mcp_import_file_desc': 'Select .mcp.json or other JSON file',
        'mcp_import_text': 'From Text',
        'mcp_import_text_desc': 'Paste JSON text manually',
        'mcp_import_format': 'Format: {"mcpServers": {...}} or {"name": {...}}',
        'mcp_clipboard_empty': 'Clipboard is empty',
        'mcp_invalid_json': 'Invalid JSON in clipboard',
        'mcp_no_valid_config': 'No valid config found',
        'mcp_import_fail': 'Import failed: {}',
        'mcp_select_official': 'Select Official MCP Servers',
        'mcp_other': 'Other',
        # MCP categories
        'mcp_cat_cloud': 'Cloud', 'mcp_cat_map': 'Map', 'mcp_cat_media': 'Media', 'mcp_cat_security': 'Security',
        'mcp_cat_tool': 'Tools', 'mcp_cat_dev': 'Dev', 'mcp_cat_search': 'Search', 'mcp_cat_db': 'Database',
        'mcp_cat_file': 'File', 'mcp_cat_news': 'News', 'mcp_cat_calendar': 'Calendar', 'mcp_cat_model': 'Model',
        'mcp_cat_browser': 'Browser', 'mcp_cat_game': 'Game', 'mcp_cat_ecommerce': 'E-commerce', 'mcp_cat_knowledge': 'Knowledge',
        'mcp_cat_social': 'Social', 'mcp_cat_note': 'Note', 'mcp_cat_network': 'Network', 'mcp_cat_design': 'Design',
        'mcp_cat_comm': 'Comm', 'mcp_cat_finance': 'Finance', 'mcp_cat_project': 'Project', 'mcp_cat_other': 'Other',
        # Prompts
        'prompt_global': 'Global Prompt',
        'prompt_user': 'User Prompts',
        'prompt_save_global': 'Save Global Prompt',
        'prompt_global_saved': 'Global prompt saved',
        'prompt_builtin_readonly': 'Built-in prompts are read-only',
        'prompt_apply': 'Apply Prompt',
        'prompt_select_mcp': 'Select MCP',
        'prompt_select_workdir': 'Please select work directory first',
        'prompt_written': 'Written to: {}',
        'prompt_write_fail': 'Write failed: {}',
        'prompt_loaded': 'Work directory config loaded',
        'prompt_loaded_with': 'Config loaded | Prompt: {}',
        'prompt_no_config': 'Work directory selected (no existing config)',
        'prompt_select_extra_mcp': 'Select extra MCP (default MCPs auto-loaded)',
        'prompt_apply_btn': 'Apply',
        # History detail
        'history_session': 'Session: {}',
        'history_path': 'Path: {}',
        'history_copy_id': 'Copy ID',
        'history_export_md': 'Export MD',
        'history_open_location': 'Open Location',
        'history_expand_middle': '▼ Expand {} messages ▼',
        'history_no_content': '(no text content)',
        'history_tool': '[Tool: {}]',
        'history_tool_result': '[Tool Result]',
        'history_unknown': 'Unknown',
        'history_unknown_date': 'Unknown Date',
        'history_no_records': 'No history records',
        'history_copied': 'Copied: {}...',
        'history_exported': 'Exported: {}',
        'history_click_hint': 'Click to select, multi-select supported',
        'history_short_sessions': 'Short sessions:',
        'history_empty_dirs': 'Empty directories:',
        'history_cleanup': 'Cleanup Sessions',
        'history_cleanup_preview': 'Preview:',
        'history_cleanup_hint': 'Sessions will be moved to trash',
        'history_cleanup_execute': 'Execute Cleanup',
        'history_cleanup_done': 'Cleaned {} sessions, {} empty dirs',
        'history_trash_cleared': 'Trash cleared',
        'history_perm_deleted': 'Permanently deleted {} sessions',
        'history_delete_selected': 'Delete Selected',
        'history_delete_project': 'Delete all sessions in project',
        # Date filter
        'date_all': 'All',
        'date_today': 'Today',
        'date_week': 'This Week',
        'date_month': 'This Month',
        'date_custom': 'Custom',
        'date_from': 'From',
        'date_to': 'To',
        # Terminal
        'terminal_issues': 'Issues detected:',
        'terminal_continue': 'Continue Anyway',
        # Theme
        'toggle_theme': 'Toggle Theme',
        'switch_lang': 'EN/中',
        'close': 'Close',
        # MCP Repository
        'mcp_repo_title': 'MCP Repository ({})',
        'mcp_updated': 'Updated: {}',
        'mcp_resync': 'Re-sync',
        'mcp_more_hint': '... more results, use search to narrow down',
        'mcp_market': 'MCP Market',
        'mcp_not_synced': 'Not synced',
        # History cleanup
        'history_selected_count': 'Selected: {}',
        'history_short_label': 'Short sessions (≤3 msgs, ≤150 chars): {}',
        'history_old_label': 'Sessions over 30 days: {}',
        'history_empty_label': 'Empty project dirs: {}',
    }
}

def get_localized(value, lang='zh'):
    """获取本地化文本，支持字典或字符串"""
    if isinstance(value, dict):
        return value.get(lang, value.get('zh', value.get('en', '')))
    return value

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

def load_prompts(lang='zh'):
    """加载提示词，合并内置和自定义"""
    custom = {}
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            custom = json.load(f)
    # 合并：内置 + 自定义
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
    theme_mode = settings.get('theme', 'light')

    page.title = L['title'].format(VERSION)
    page.window.width = 1100
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.DARK if theme_mode == 'dark' else ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        font_family="SimSun",
        tooltip_theme=ft.TooltipTheme(wait_duration=200),
    )
    page.bgcolor = THEMES[theme_mode]["bg"]

    def toggle_theme(e):
        nonlocal theme_mode
        theme_mode = "dark" if theme_mode == "light" else "light"
        settings['theme'] = theme_mode
        save_settings(settings)
        # 清理并重新加载界面
        page.clean()
        main(page)

    # 设置窗口图标
    icon_path = Path(__file__).parent / "icon.ico"
    if icon_path.exists():
        page.window.icon = str(icon_path)

    debug_print("加载配置...")
    configs = load_configs()
    debug_print("加载提示词...")
    prompt_db = PromptDB(DB_FILE)
    # 迁移旧数据并初始化内置提示词（使用当前语言）
    for pid, p in BUILTIN_PROMPTS.items():
        if not prompt_db.get_all().get(pid):
            prompt_db.save({
                'id': pid,
                'name': get_localized(p.get('name', ''), lang),
                'content': get_localized(p.get('content', ''), lang),
                'category': get_localized(p.get('category', ''), lang),
                'is_builtin': p.get('is_builtin', False),
                'prompt_type': p.get('prompt_type', 'user'),
            })
    # 从旧 JSON 迁移
    if PROMPTS_FILE.exists():
        old_prompts = load_prompts(lang)
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

    selected_config = None  # 三级配置项选择
    selected_endpoint = None  # 二级端点选择 (cli_type:endpoint)
    selected_cli = None  # 一级CLI选择
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
        theme = THEMES[theme_mode]
        cli_list = list(tree.keys())

        for cli_idx, cli_type in enumerate(cli_list):
            cli_name = CLI_TOOLS.get(cli_type, {}).get('name', cli_type)
            cli_key = cli_type
            is_cli_expanded = expanded_cli.get(cli_key, True)
            is_cli_selected = selected_cli == cli_key and selected_endpoint is None and selected_config is None

            # CLI 工具层（第一级）
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
                on_tap=lambda e, k=cli_key: select_cli(k),
                on_double_tap=lambda e, k=cli_key: toggle_cli(k),
            )
            config_tree.controls.append(cli_header)

            if is_cli_expanded:
                endpoint_list = list(tree[cli_type].keys())
                for ep_idx, endpoint in enumerate(endpoint_list):
                    endpoint_key = f"{cli_type}:{endpoint}"
                    is_endpoint_expanded = expanded_endpoint.get(endpoint_key, True)
                    short_endpoint = endpoint[:40] + "..." if len(endpoint) > 40 else endpoint
                    is_ep_selected = selected_endpoint == endpoint_key and selected_config is None

                    # API 端点层（第二级）
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
                        on_tap=lambda e, k=endpoint_key: select_endpoint(k),
                        on_double_tap=lambda e, k=endpoint_key: toggle_endpoint(k),
                    )
                    config_tree.controls.append(endpoint_header)

                    if is_endpoint_expanded:
                        for idx, cfg in tree[cli_type][endpoint]:
                            # 配置项层（第三级）
                            is_selected = selected_config == idx
                            config_item = ft.GestureDetector(
                                content=ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.KEY, size=16, color=theme['icon_key_selected'] if is_selected else ft.Colors.GREY_600),
                                        ft.Text(cfg.get('label', 'Unnamed'),
                                               weight=ft.FontWeight.BOLD if is_selected else None,
                                               color=theme['text_selected'] if is_selected else theme['text']),
                                    ], spacing=5),
                                    padding=ft.padding.only(left=60, top=5, bottom=5),
                                    bgcolor=theme['selection_bg'] if is_selected else None,
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

    def select_cli(cli_key):
        nonlocal selected_cli, selected_endpoint, selected_config
        selected_cli = cli_key
        selected_endpoint = None
        selected_config = None
        current_key_label.value = f"CLI: {CLI_TOOLS.get(cli_key, {}).get('name', cli_key)}"
        refresh_config_list()

    def select_endpoint(endpoint_key):
        nonlocal selected_cli, selected_endpoint, selected_config
        selected_cli = endpoint_key.split(':')[0]
        selected_endpoint = endpoint_key
        selected_config = None
        current_key_label.value = f"Endpoint: {endpoint_key.split(':')[1][:30]}"
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
        nonlocal selected_config, selected_endpoint, selected_cli
        if selected_config is not None:
            # 三级：配置项在同端点内移动
            cli, ep = selected_endpoint.split(':') if selected_endpoint else (None, None)
            same_ep = [i for i, c in enumerate(configs) if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep]
            pos = same_ep.index(selected_config) if selected_config in same_ep else -1
            if pos > 0:
                prev_idx = same_ep[pos - 1]
                configs[selected_config], configs[prev_idx] = configs[prev_idx], configs[selected_config]
                selected_config = prev_idx
                save_configs(configs)
                refresh_config_list()
        elif selected_endpoint:
            # 二级：端点在同CLI内移动
            cli = selected_endpoint.split(':')[0]
            eps = list(dict.fromkeys(c.get('provider', {}).get('endpoint') for c in configs if c.get('cli_type') == cli))
            ep = selected_endpoint.split(':')[1]
            pos = eps.index(ep) if ep in eps else -1
            if pos > 0:
                # 交换两个端点的所有配置项
                prev_ep = eps[pos - 1]
                for c in configs:
                    if c.get('cli_type') == cli:
                        if c.get('provider', {}).get('endpoint') == ep:
                            c['provider']['endpoint'] = '__temp__'
                for c in configs:
                    if c.get('cli_type') == cli:
                        if c.get('provider', {}).get('endpoint') == prev_ep:
                            c['provider']['endpoint'] = ep
                for c in configs:
                    if c.get('cli_type') == cli:
                        if c.get('provider', {}).get('endpoint') == '__temp__':
                            c['provider']['endpoint'] = prev_ep
                selected_endpoint = f"{cli}:{prev_ep}"
                save_configs(configs)
                refresh_config_list()
        elif selected_cli:
            # 一级：CLI组移动
            clis = list(dict.fromkeys(c.get('cli_type') for c in configs))
            pos = clis.index(selected_cli) if selected_cli in clis else -1
            if pos > 0:
                prev_cli = clis[pos - 1]
                # 重排configs：把selected_cli的项移到prev_cli之前
                cli_items = [c for c in configs if c.get('cli_type') == selected_cli]
                other_items = [c for c in configs if c.get('cli_type') != selected_cli]
                insert_pos = next((i for i, c in enumerate(other_items) if c.get('cli_type') == prev_cli), 0)
                configs[:] = other_items[:insert_pos] + cli_items + other_items[insert_pos:]
                save_configs(configs)
                refresh_config_list()

    def move_down(e):
        nonlocal selected_config, selected_endpoint, selected_cli
        if selected_config is not None:
            # 三级：配置项在同端点内移动
            cli, ep = selected_endpoint.split(':') if selected_endpoint else (None, None)
            same_ep = [i for i, c in enumerate(configs) if c.get('cli_type') == cli and c.get('provider', {}).get('endpoint') == ep]
            pos = same_ep.index(selected_config) if selected_config in same_ep else -1
            if pos >= 0 and pos < len(same_ep) - 1:
                next_idx = same_ep[pos + 1]
                configs[selected_config], configs[next_idx] = configs[next_idx], configs[selected_config]
                selected_config = next_idx
                save_configs(configs)
                refresh_config_list()
        elif selected_endpoint:
            # 二级：端点在同CLI内移动
            cli = selected_endpoint.split(':')[0]
            eps = list(dict.fromkeys(c.get('provider', {}).get('endpoint') for c in configs if c.get('cli_type') == cli))
            ep = selected_endpoint.split(':')[1]
            pos = eps.index(ep) if ep in eps else -1
            if pos >= 0 and pos < len(eps) - 1:
                next_ep = eps[pos + 1]
                for c in configs:
                    if c.get('cli_type') == cli:
                        if c.get('provider', {}).get('endpoint') == ep:
                            c['provider']['endpoint'] = '__temp__'
                for c in configs:
                    if c.get('cli_type') == cli:
                        if c.get('provider', {}).get('endpoint') == next_ep:
                            c['provider']['endpoint'] = ep
                for c in configs:
                    if c.get('cli_type') == cli:
                        if c.get('provider', {}).get('endpoint') == '__temp__':
                            c['provider']['endpoint'] = next_ep
                selected_endpoint = f"{cli}:{next_ep}"
                save_configs(configs)
                refresh_config_list()
        elif selected_cli:
            # 一级：CLI组移动
            clis = list(dict.fromkeys(c.get('cli_type') for c in configs))
            pos = clis.index(selected_cli) if selected_cli in clis else -1
            if pos >= 0 and pos < len(clis) - 1:
                next_cli = clis[pos + 1]
                # 重排configs：把selected_cli的项移到next_cli之后
                cli_items = [c for c in configs if c.get('cli_type') == selected_cli]
                other_items = [c for c in configs if c.get('cli_type') != selected_cli]
                # 找到next_cli最后一项的位置
                insert_pos = len([c for c in other_items if clis.index(c.get('cli_type')) <= clis.index(next_cli)])
                configs[:] = other_items[:insert_pos] + cli_items + other_items[insert_pos:]
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
        webbrowser.open('https://github.com/LiangMu-Studio/AI_CLI_Manager/issues')

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
            page.open(ft.SnackBar(ft.Text(L['prompt_select_workdir'])))
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
            page.open(ft.SnackBar(ft.Text(L['prompt_written'].format(file_path))))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(L['prompt_write_fail'].format(ex))))
        page.update()

    work_dir_field = ft.TextField(label=L['work_dir'], value=settings.get('work_dir', ''), expand=True)
    workdir_mcp_enabled = {}  # 当前工作目录的 MCP 启用状态 {name: True/False}

    def show_mcp_selector(e):
        """显示 MCP 选择弹窗（非默认的 MCP）"""
        if not work_dir_field.value:
            page.open(ft.SnackBar(ft.Text(L['prompt_select_workdir'])))
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
                            ft.Text(f"{m.get('category', L['mcp_other'])} | {m.get('command', '')} {m.get('args', '')[:30]}", size=10, color=ft.Colors.GREY_500),
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
            page.open(ft.SnackBar(ft.Text(L['saved'])))
            page.update()

        build_selector_list()
        dlg = ft.AlertDialog(
            title=ft.Text(L['prompt_select_extra_mcp']),
            content=ft.Container(mcp_selector_list, width=500, height=400),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update()),
                ft.ElevatedButton(L['prompt_apply_btn'], on_click=apply_selection),
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
            page.open(ft.SnackBar(ft.Text(L['prompt_loaded_with'].format(preview))))
        elif prompt_path.exists():
            page.open(ft.SnackBar(ft.Text(L['prompt_loaded'])))
        else:
            page.open(ft.SnackBar(ft.Text(L['prompt_no_config'])))

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
                    title=ft.Text("MCP Config Issue", color=ft.Colors.ORANGE),
                    content=ft.Column([
                        ft.Text(L['terminal_issues']),
                        ft.Text(error_text, size=12, color=ft.Colors.RED),
                    ], tight=True),
                    actions=[
                        ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update()),
                        ft.ElevatedButton(L['terminal_continue'], on_click=continue_anyway),
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
            ft.ElevatedButton(L['prompt_apply'], icon=ft.Icons.SEND, on_click=apply_selected_prompt),
            ft.ElevatedButton(L['prompt_select_mcp'], icon=ft.Icons.EXTENSION, on_click=show_mcp_selector),
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
        label=L['prompt_global'],
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
            system_prompt = {'id': 'system_global', 'name': L['prompt_global'], 'prompt_type': 'system', 'category': L['prompt_global']}
        system_prompt['content'] = global_prompt_content.value or ''
        prompt_db.save(system_prompt)
        page.open(ft.SnackBar(ft.Text(L['prompt_global_saved'])))
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
                bgcolor=THEMES[theme_mode]['header_bg'],
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
                            ft.Text(L['prompt_builtin'] if is_builtin else "", size=10, color=ft.Colors.GREY_500),
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
            page.open(ft.SnackBar(ft.Text(L['prompt_builtin_readonly'])))
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
                    ft.Icon(ft.Icons.PUBLIC, color=THEMES[theme_mode]['global_icon']),
                    ft.Text(L['prompt_global'], size=16, weight=ft.FontWeight.BOLD),
                ], spacing=5),
                global_prompt_content,
                ft.Row([ft.ElevatedButton(L['prompt_save_global'], icon=ft.Icons.SAVE, on_click=save_global_prompt)]),
            ], spacing=5),
            padding=10,
            border=ft.border.all(1, THEMES[theme_mode]['global_border']),
            border_radius=8,
            bgcolor=THEMES[theme_mode]['global_bg'],
        ),
        ft.Divider(),
        # 用户提示词区域
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
                bgcolor=THEMES[theme_mode]['header_bg'],
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
                                       tooltip=L['mcp_set_default_hint']),
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
            page.open(ft.SnackBar(ft.Text(L['mcp_added'].format(1))))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_select_official']),
            content=ft.Container(official_list, width=450, height=400),
            actions=[ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update())],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_mcp_dialog(idx):
        is_edit = idx is not None
        m = mcp_list[idx] if is_edit else {}

        name_field = ft.TextField(label=L['name'], value=m.get('name', ''), expand=True)
        category_field = ft.Dropdown(
            label=L['mcp_category'],
            value=m.get('category', L['mcp_other']),
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
            title=ft.Text(L['mcp_market']),
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
                    page.open(ft.SnackBar(ft.Text(L['mcp_clipboard_empty'])))
                    page.update()
                    return
                data = json.loads(clip)
                items = parse_mcp_json(data)
                if items:
                    mcp_list.extend(items)
                    save_mcp(mcp_list)
                    refresh_mcp_tree()
                    page.open(ft.SnackBar(ft.Text(L['mcp_added'].format(len(items)))))
                else:
                    page.open(ft.SnackBar(ft.Text(L['mcp_no_valid_config'])))
            except json.JSONDecodeError:
                page.open(ft.SnackBar(ft.Text(L['mcp_invalid_json'])))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(L['mcp_import_fail'].format(ex))))
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
                    page.open(ft.SnackBar(ft.Text(L['mcp_added'].format(len(items)))))
                else:
                    page.open(ft.SnackBar(ft.Text(L['mcp_no_valid_config'])))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(L['mcp_import_fail'].format(ex))))
            page.update()
        picker = ft.FilePicker(on_result=on_result)
        page.overlay.append(picker)
        page.update()
        picker.pick_files(allowed_extensions=['json'], dialog_title=L['mcp_import_file'])

    def import_from_text(e):
        """从文本输入导入 MCP"""
        text_field = ft.TextField(
            label=L['mcp_import_text_desc'],
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
                    page.open(ft.SnackBar(ft.Text(L['mcp_added'].format(len(items)))))
                else:
                    page.open(ft.SnackBar(ft.Text(L['mcp_no_valid_config'])))
            except json.JSONDecodeError:
                page.open(ft.SnackBar(ft.Text(L['mcp_invalid_json'])))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(L['mcp_import_fail'].format(ex))))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_import_text']),
            content=ft.Container(
                ft.Column([
                    ft.Text(L['mcp_import_format'], size=12, color=ft.Colors.GREY_600),
                    text_field,
                ], tight=True),
                width=500, height=350,
            ),
            actions=[
                ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update()),
                ft.ElevatedButton(L['import'], on_click=do_import),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_import_menu(e):
        """显示导入菜单"""
        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_import_title']),
            content=ft.Column([
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CONTENT_PASTE, color=ft.Colors.BLUE),
                    title=ft.Text(L['mcp_import_clipboard']),
                    subtitle=ft.Text(L['mcp_import_clipboard_desc']),
                    on_click=lambda e: (setattr(dlg, 'open', False), page.update(), import_from_clipboard(e)),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.FILE_OPEN, color=ft.Colors.GREEN),
                    title=ft.Text(L['mcp_import_file']),
                    subtitle=ft.Text(L['mcp_import_file_desc']),
                    on_click=lambda e: (setattr(dlg, 'open', False), page.update(), import_from_file(e)),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.TEXT_FIELDS, color=ft.Colors.ORANGE),
                    title=ft.Text(L['mcp_import_text']),
                    subtitle=ft.Text(L['mcp_import_text_desc']),
                    on_click=lambda e: (setattr(dlg, 'open', False), page.update(), import_from_text(e)),
                ),
            ], tight=True, spacing=0),
            actions=[ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update())],
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
        status_text = ft.Text(L['mcp_sync_preparing'])
        progress = ft.ProgressBar(width=400)

        loading_dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_sync_title']),
            content=ft.Column([
                progress,
                status_text,
                ft.Text(L['mcp_sync_sources'], size=12, color=ft.Colors.GREY_600),
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
                page.open(ft.SnackBar(ft.Text(L['mcp_sync_complete'].format(stats['total'], new_count))))
                show_repository_browser(stats)
            else:
                show_sync_debug()

        import threading
        threading.Thread(target=do_sync, daemon=True).start()

    def show_sync_debug():
        """显示同步调试信息"""
        log_text = "\n".join(mcp_fetch_log)
        dlg = ft.AlertDialog(
            title=ft.Text(L['mcp_sync_fail'], color=ft.Colors.RED),
            content=ft.Container(
                ft.TextField(value=log_text, multiline=True, read_only=True, min_lines=15, max_lines=20, expand=True),
                width=600, height=400,
            ),
            actions=[ft.TextButton(L['close'], on_click=lambda _: setattr(dlg, 'open', False) or page.update())],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_repository_browser(stats: dict):
        """显示 MCP 仓库浏览器（使用 SQLite FTS5 搜索）"""
        # 分类映射：数据库中文名 -> 翻译键
        cat_keys = ['cloud', 'map', 'media', 'security', 'tool', 'dev', 'search', 'db',
                    'file', 'news', 'calendar', 'model', 'browser', 'game', 'ecommerce', 'knowledge',
                    'social', 'note', 'network', 'design', 'comm', 'finance', 'project', 'other']
        cat_zh = ['云服务', '地图', '媒体', '安全', '工具', '开发', '搜索', '数据库',
                  '文件', '新闻', '日历', '模型', '浏览器', '游戏', '电商', '知识库',
                  '社交', '笔记', '网络', '设计', '通讯', '金融', '项目', '其他']
        cat_display = [L[f'mcp_cat_{k}'] for k in cat_keys]
        zh_to_display = dict(zip(cat_zh, cat_display))
        display_to_zh = dict(zip(cat_display, cat_zh))

        search_field = ft.TextField(label=L['mcp_search'], prefix_icon=ft.Icons.SEARCH, expand=True)
        category_dropdown = ft.Dropdown(
            label=L['mcp_category'],
            value=L['mcp_all'],
            options=[ft.dropdown.Option(L['mcp_all'])] + [ft.dropdown.Option(c) for c in cat_display],
            width=120,
        )
        result_list = ft.ListView(expand=True, spacing=2)
        selected_items = set()
        selected_count_text = ft.Text(L['mcp_selected'].format(0), color=ft.Colors.GREY_600)

        def filter_list(e=None):
            result_list.controls.clear()
            keyword = search_field.value or ''
            cat_val = category_dropdown.value or L['mcp_all']
            # 转换显示名称为数据库中文名
            cat_filter = display_to_zh.get(cat_val, '全部') if cat_val != L['mcp_all'] else '全部'

            # 使用 SQLite FTS5 搜索
            servers = mcp_registry.search(keyword, cat_filter, limit=200)

            for item in servers:
                name = item.get('name', '')
                desc = item.get('description', '') or ''
                cat = item.get('category', '其他')
                cat_disp = zh_to_display.get(cat, cat)  # 显示翻译后的分类
                source = item.get('source', '')
                is_selected = name in selected_items

                tile = ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_selected, on_change=lambda e, n=name: toggle_select(n, e.control.value)),
                        ft.Column([
                            ft.Row([
                                ft.Text(name, weight=ft.FontWeight.BOLD if is_selected else None, expand=True),
                                ft.Container(
                                    ft.Text(cat_disp, size=10, color=ft.Colors.WHITE),
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
                result_list.controls.append(ft.Text(L['mcp_more_hint'], color=ft.Colors.GREY_500, italic=True))
            page.update()

        def toggle_select(name, checked):
            if checked:
                selected_items.add(name)
            else:
                selected_items.discard(name)
            selected_count_text.value = L['mcp_selected'].format(len(selected_items))
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
                page.open(ft.SnackBar(ft.Text(L['mcp_added'].format(added))))
            page.update()

        # 绑定事件
        search_field.on_change = filter_list
        category_dropdown.on_change = filter_list

        # 初始加载
        filter_list()

        # 更新时间显示
        updated = stats.get('updated_at', '')[:16].replace('T', ' ') if stats.get('updated_at') else L['mcp_not_synced']

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Text(L['mcp_repo_title'].format(stats['total']), weight=ft.FontWeight.BOLD),
                ft.Text(L['mcp_updated'].format(updated), size=11, color=ft.Colors.GREY_500),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: (setattr(dlg, 'open', False), page.update(), sync_mcp_repository(e)), tooltip=L['mcp_resync']),
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
                ft.ElevatedButton(L['mcp_add_selected'], on_click=add_selected),
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
            ft.IconButton(ft.Icons.DOWNLOAD, on_click=show_import_menu, tooltip=L['mcp_import']),
            ft.IconButton(ft.Icons.INVENTORY_2, on_click=show_mcp_repository, tooltip=L['mcp_browse']),
            ft.IconButton(ft.Icons.CLOUD_DOWNLOAD, on_click=add_from_official, tooltip=L['mcp_official']),
            ft.IconButton(ft.Icons.STORE, on_click=browse_mcp_market, tooltip=L['mcp_market']),
            ft.IconButton(ft.Icons.EDIT, on_click=edit_mcp, tooltip=L['edit']),
            ft.IconButton(ft.Icons.DELETE, on_click=delete_mcp, tooltip=L['delete']),
        ]),
        ft.Text(L['mcp_default_hint'], size=12, color=ft.Colors.GREY_600),
        ft.Container(mcp_tree, expand=True, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8),
    ], expand=True, spacing=10)

    # ========== 历史记录管理页面（Tab 结构：Claude / Codex / Kiro）==========
    # 当前选中的 CLI 类型
    current_cli = "claude"
    current_page_idx = 0  # 跟踪当前页面索引
    selected_sessions = {}  # {session_id: data}
    all_session_items = []  # [(item, item_data), ...]
    last_clicked_idx = -1
    history_tree = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)
    history_stats = ft.Text("", size=12, color=ft.Colors.GREY_600)
    history_progress = ft.ProgressBar(visible=False, width=200)
    history_search = ft.TextField(hint_text=L['history_search'], width=250, on_submit=lambda e: refresh_history_tree(e.control.value or ""))
    history_detail = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)

    def get_current_manager():
        if current_cli == "claude":
            return history_manager
        elif current_cli == "codex":
            return codex_history_manager
        # gemini 和 aider 暂不支持
        return None

    def get_history_data():
        """获取当前CLI的历史数据（使用缓存）"""
        global history_cache
        if history_cache.get(current_cli):
            return history_cache[current_cli]
        mgr = get_current_manager()
        if mgr:
            history_cache[current_cli] = mgr.load_sessions()
        return history_cache.get(current_cli, {})

    def refresh_history_tree(filter_text: str = ""):
        nonlocal last_clicked_idx, all_session_items
        selected_sessions.clear()
        all_session_items = []
        last_clicked_idx = -1
        history_tree.controls.clear()
        history_progress.visible = True
        if current_page_idx != 3: return
        page.update()
        mgr = get_current_manager()
        if current_cli in ("gemini", "aider"):
            history_tree.controls.append(ft.Text(f"{current_cli.title()} 历史记录暂不支持（格式不兼容）", color=ft.Colors.ORANGE))
            history_stats.value = ""
            history_progress.visible = False
            if current_page_idx != 3: return
            page.update()
            return
        if not mgr:
            history_tree.controls.append(ft.Text(f"{current_cli.title()} 目录不存在", color=ft.Colors.RED))
            history_stats.value = ""
            history_progress.visible = False
            if current_page_idx != 3: return
            page.update()
            return
        # 加载数据（使用缓存）
        history_data = get_history_data()
        if not history_data:
            history_stats.value = L['history_no_records']
            history_progress.visible = False
            if current_page_idx != 3: return
            page.update()
            return
        # 统计
        total_sessions = sum(len(s) for s in history_data.values())
        total_messages = sum(info['message_count'] for grp in history_data.values() for info in grp.values())
        total_size = sum(info.get('size', 0) for grp in history_data.values() for info in grp.values())
        size_str = f"{total_size / 1024 / 1024:.1f} MB" if total_size > 1024*1024 else f"{total_size / 1024:.1f} KB"
        history_stats.value = f"{L['history_sessions']}: {total_sessions} | {L['history_messages']}: {total_messages} | {L['history_size']}: {size_str}"
        # 构建树
        filter_text = filter_text.lower()
        now = datetime.now().astimezone()
        today = now.date()
        # 日期筛选
        if date_filter == "today":
            date_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            date_cutoff_end = None
        elif date_filter == "week":
            # 从本周一开始
            date_cutoff = (now - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            date_cutoff_end = None
        elif date_filter == "month":
            # 从本月1号开始
            date_cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_cutoff_end = None
        elif date_filter == "custom" and custom_date_from:
            date_cutoff = custom_date_from.astimezone() if custom_date_from else None
            date_cutoff_end = custom_date_to.astimezone() if custom_date_to else None
        else:
            date_cutoff = None
            date_cutoff_end = None
        old_cutoff = now - timedelta(days=30)  # 30天前的归为旧会话
        old_sessions = []

        def on_item_click(e, idx, data):
            nonlocal last_clicked_idx
            theme = THEMES[theme_mode]
            ctrl = e.control
            shift = getattr(e, 'shift', False)
            ctrl_key = getattr(e, 'ctrl', False)
            if shift and last_clicked_idx >= 0:
                # Shift多选：选中范围内所有项
                start, end = min(last_clicked_idx, idx), max(last_clicked_idx, idx)
                for i in range(start, end + 1):
                    item, item_data = all_session_items[i]
                    selected_sessions[item_data['session_id']] = item_data
                    item.bgcolor = theme['selection_bg']
            elif ctrl_key:
                # Ctrl多选：切换单项选中状态
                if data['session_id'] in selected_sessions:
                    del selected_sessions[data['session_id']]
                    ctrl.bgcolor = None
                else:
                    selected_sessions[data['session_id']] = data
                    ctrl.bgcolor = theme['selection_bg']
            else:
                # 单击：清除其他选中，只选当前项
                for item, item_data in all_session_items:
                    item.bgcolor = None
                selected_sessions.clear()
                selected_sessions[data['session_id']] = data
                ctrl.bgcolor = theme['selection_bg']
            last_clicked_idx = idx
            update_selection_buttons()
            show_session_detail(data)
            page.update()

        for grp_name, sessions in sorted(history_data.items(), reverse=True):
            if not sessions:
                continue
            grp_items = []
            for sid, info in sorted(sessions.items(), key=lambda x: x[1].get('last_timestamp', ''), reverse=True):
                if filter_text and filter_text not in sid.lower() and filter_text not in (info.get('cwd') or '').lower():
                    continue
                ts = info.get('last_timestamp', '')
                dt = None
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        time_str = dt.strftime("%m-%d %H:%M")
                    except:
                        time_str = ts[:16]
                else:
                    time_str = "未知"
                # 日期筛选
                if date_cutoff and dt and dt < date_cutoff:
                    continue
                if date_cutoff_end and dt and dt > date_cutoff_end:
                    continue
                # 30天前归为旧会话
                if dt and dt < old_cutoff:
                    old_sessions.append((grp_name, sid, info, time_str))
                    continue
                # 获取首条消息预览
                preview = ""
                for msg in info.get('messages', [])[:5]:  # 只看前5条
                    role = msg.get('message', {}).get('role') if current_cli == "claude" else msg.get('role')
                    if role == 'user':
                        content = msg.get('message', {}).get('content', []) if current_cli == "claude" else msg.get('content', '')
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get('type') in ('text', 'input_text'):
                                    txt = c.get('text', '')
                                    # 跳过系统消息和XML标签
                                    if txt.startswith('<') or 'system' in txt[:50].lower():
                                        continue
                                    preview = txt[:30].replace('\n', ' ')
                                    break
                        elif isinstance(content, str):
                            if not content.startswith('<'):
                                preview = content[:30].replace('\n', ' ')
                        if preview:
                            break
                # 格式化大小
                size = info.get('size', 0)
                size_str = f"{size/1024/1024:.1f}MB" if size > 1024*1024 else f"{size/1024:.1f}KB" if size > 1024 else f"{size}B"
                display = f"{sid[:12]}... {preview}" if preview else f"{sid[:12]}..."
                item_data = {'group': grp_name, 'session_id': sid, 'info': info}
                idx = len(all_session_items)
                item = ft.Container(
                    content=ft.Column([
                        ft.Text(display, size=13, font_family="SimSun"),
                        ft.Text(f"{info['message_count']}条 | {time_str} | {size_str}", size=11, color=ft.Colors.GREY_500, font_family="SimSun"),
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START),
                    data={'idx': idx, 'item_data': item_data},
                    on_click=lambda e, i=idx, d=item_data: on_item_click(e, i, d),
                    padding=ft.padding.only(left=20, top=5, bottom=5, right=5), border_radius=4,
                    tooltip=f"ID: {sid}\n路径: {info.get('cwd', '未知')}",
                    expand=True,
                )
                row = ft.Row([item], expand=True)
                all_session_items.append((item, item_data))
                grp_items.append(row)
            if grp_items:
                # 计算项目大小
                grp_size = sum(s.get('size', 0) for s in sessions.values())
                grp_size_str = f"{grp_size/1024/1024:.1f}MB" if grp_size > 1024*1024 else f"{grp_size/1024:.1f}KB"
                grp_sessions_data = [{'group': grp_name, 'session_id': sid, 'info': info} for sid, info in sessions.items()]
                history_tree.controls.append(ft.ExpansionTile(
                    title=ft.Text(grp_name[:40], size=14, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(f"{len(grp_items)} {L['history_sessions']} | {grp_size_str}", size=11),
                    controls=[ft.Column(grp_items, horizontal_alignment=ft.CrossAxisAlignment.START)],
                    initially_expanded=len(history_data) <= 3,
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, icon_size=18,
                        tooltip=L['history_delete_project'],
                        on_click=lambda _, data=grp_sessions_data: delete_sessions(data),
                    ),
                ))
        if old_sessions:
            old_items = []
            for grp, sid, info, ts in old_sessions:
                item_data = {'group': grp, 'session_id': sid, 'info': info}
                idx = len(all_session_items)
                item = ft.Container(
                    content=ft.Column([
                        ft.Text(f"{sid[:12]}...", size=13, color=ft.Colors.GREY_600, font_family="SimSun"),
                        ft.Text(f"{grp[:20]} | {ts}", size=11, color=ft.Colors.GREY_500, font_family="SimSun"),
                    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START),
                    data={'idx': idx, 'item_data': item_data},
                    on_click=lambda e, i=idx, d=item_data: on_item_click(e, i, d),
                    padding=ft.padding.only(left=20, top=5, bottom=5, right=5), border_radius=4,
                    expand=True,
                )
                row = ft.Row([item], expand=True)
                all_session_items.append((item, item_data))
                old_items.append(row)
            history_tree.controls.append(ft.ExpansionTile(
                title=ft.Text(L['history_old'].format(len(old_sessions)), size=14, color=ft.Colors.GREY_600),
                controls=[ft.Column(old_items, horizontal_alignment=ft.CrossAxisAlignment.START)], initially_expanded=False,
            ))
        history_progress.visible = False
        if current_page_idx != 3: return
        page.update()

    def show_session_detail(data):
        history_detail.controls.clear()
        if not data:
            return
        info, sid = data['info'], data['session_id']
        history_detail.controls.append(ft.Text(L['history_session'].format(sid), size=14, weight=ft.FontWeight.BOLD))
        history_detail.controls.append(ft.Text(L['history_path'].format(info.get('cwd', L['history_unknown'])), size=12, color=ft.Colors.GREY_600))
        resume_cmd = f"claude --resume {sid}" if current_cli == "claude" else f"codex --resume {sid}"
        history_detail.controls.append(ft.Row([
            ft.TextButton(L['history_copy_id'], on_click=lambda _: copy_to_clipboard(sid)),
            ft.TextButton(L['history_copy_resume'], on_click=lambda _: copy_to_clipboard(resume_cmd)),
            ft.TextButton(L['history_export_md'], on_click=lambda _: export_session(sid, info)),
            ft.TextButton(L['history_open_location'], on_click=lambda _: open_file_location(info)),
        ], spacing=5))
        history_detail.controls.append(ft.Divider())

        # 分页加载消息：开头10条 + 结尾10条，中间折叠
        messages = info['messages']
        head_count, tail_count = 10, 10

        def render_message(msg):
            if current_cli == "claude":
                role = msg.get('message', {}).get('role', L['history_unknown'])
                ts = msg.get('timestamp', '')
                content = msg.get('message', {}).get('content', [])
                text = ""
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict):
                            t = c.get('type', '')
                            if t == 'text':
                                text += c.get('text', '')
                            elif t == 'tool_use':
                                text += L['history_tool'].format(c.get('name', ''))
                            elif t == 'tool_result':
                                text += L['history_tool_result']
                elif isinstance(content, str):
                    text = content
            else:  # codex
                role = msg.get('role', L['history_unknown'])
                ts = ""
                content = msg.get('content', '')
                if isinstance(content, list):
                    text = ""
                    for c in content:
                        if isinstance(c, dict) and c.get('type') in ('input_text', 'output_text'):
                            text += c.get('text', '')
                else:
                    text = str(content)
            if not text.strip():
                text = L['history_no_content']
            color = ft.Colors.with_opacity(0.15, ft.Colors.BLUE) if role == 'user' else ft.Colors.with_opacity(0.15, ft.Colors.GREEN)
            return ft.GestureDetector(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(f"{role.upper()} ({ts[:19] if ts else ''})", size=12, weight=ft.FontWeight.BOLD, font_family="SimSun"),
                        ft.Text(text[:500] + ('...' if len(text) > 500 else ''), size=14, font_family="SimSun"),
                    ]),
                    bgcolor=color, padding=10, border_radius=8, margin=ft.margin.only(bottom=5),
                ),
                on_double_tap=lambda _, t=text, r=role, ts_=ts: show_message_detail(t, r, ts_),
            )

        middle_count = len(messages) - head_count - tail_count
        if middle_count <= 0:
            # 消息少，全部显示
            for msg in messages:
                history_detail.controls.append(render_message(msg))
        else:
            # 显示开头
            for msg in messages[:head_count]:
                history_detail.controls.append(render_message(msg))
            # 中间折叠按钮（醒目样式）
            middle_msgs = messages[head_count:-tail_count]
            def expand_middle(_):
                idx = history_detail.controls.index(expand_btn)
                history_detail.controls.remove(expand_btn)
                for i, msg in enumerate(middle_msgs):
                    history_detail.controls.insert(idx + i, render_message(msg))
                page.update()
            expand_btn = ft.Container(
                content=ft.Column([
                    ft.Divider(color=ft.Colors.ORANGE),
                    ft.TextButton(f"▼ 展开中间 {len(middle_msgs)} 条消息 ▼", style=ft.ButtonStyle(color=ft.Colors.ORANGE), on_click=expand_middle),
                    ft.Divider(color=ft.Colors.ORANGE),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            )
            history_detail.controls.append(expand_btn)
            # 显示结尾
            for msg in messages[-tail_count:]:
                history_detail.controls.append(render_message(msg))
        page.update()

    def show_message_detail(text, role, ts):
        """双击消息显示完整内容"""
        dlg = ft.AlertDialog(
            title=ft.Text(f"{role.upper()} ({ts[:19] if ts else ''})"),
            content=ft.Column([
                ft.TextField(value=text, multiline=True, read_only=True, min_lines=10, max_lines=20),
            ], width=600, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton(L['copy'], on_click=lambda _: copy_to_clipboard(text)),
                ft.TextButton(L['close'], on_click=lambda _: setattr(dlg, 'open', False) or page.update()),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def copy_to_clipboard(text):
        page.set_clipboard(text)
        page.open(ft.SnackBar(ft.Text(L['history_copied'].format(text[:50]))))
        page.update()

    def open_file_location(info):
        file_path = info.get('file')
        if not file_path:
            return
        import subprocess, sys
        if sys.platform == 'win32':
            subprocess.run(['explorer', '/select,', str(file_path)])
        elif sys.platform == 'darwin':
            subprocess.run(['open', '-R', str(file_path)])
        else:
            subprocess.run(['xdg-open', str(Path(file_path).parent)])

    def export_session(sid, info):
        mgr = get_current_manager()
        if not mgr:
            return
        md = mgr.export_to_markdown(sid, info)
        export_path = Path.home() / "Downloads" / f"{current_cli}_{sid[:12]}.md"
        export_path.write_text(md, encoding='utf-8')
        page.open(ft.SnackBar(ft.Text(L['history_exported'].format(export_path))))
        page.update()

    def delete_sessions(sessions_data):
        mgr = get_current_manager()
        if not sessions_data or not mgr:
            return
        def do_delete(e):
            global history_cache
            dlg.open = False
            page.update()
            count = 0
            cache = history_cache.get(current_cli, {})
            for data in sessions_data:
                if mgr.delete_session(data['group'], data['session_id'], data['info']):
                    if data['group'] in cache:
                        cache[data['group']].pop(data['session_id'], None)
                    count += 1
            page.open(ft.SnackBar(ft.Text(L['history_moved'].format(count))))
            refresh_history_tree(history_search.value or "")
        dlg = ft.AlertDialog(
            title=ft.Text(L['confirm_delete']),
            content=ft.Text(L['history_confirm_delete'].format(len(sessions_data), TRASH_RETENTION_DAYS)),
            actions=[ft.TextButton(L['cancel'], on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
                     ft.TextButton(L['delete'], on_click=do_delete)],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_trash_dialog(_):
        mgr = get_current_manager()
        if not mgr:
            return
        items = mgr.trash_manager.get_trash_items()
        selected_trash = {}

        def on_trash_click(e, item):
            if item['session_id'] in selected_trash:
                del selected_trash[item['session_id']]
                e.control.bgcolor = None
            else:
                selected_trash[item['session_id']] = item
                e.control.bgcolor = ft.Colors.BLUE_100
            page.update()

        trash_list = ft.Column([
            ft.Container(
                content=ft.ListTile(
                    title=ft.Text(f"{item['session_id'][:12]}...", size=13),
                    subtitle=ft.Text(
                        f"{item['project_name']} | 删除于 {datetime.fromtimestamp(item['deleted_at']).strftime('%m-%d %H:%M')} | 剩余 {max(0, TRASH_RETENTION_DAYS - (time.time() - item['deleted_at']) / 86400):.1f} 天",
                        size=11
                    ),
                ),
                data=item,
                on_click=lambda e, it=item: on_trash_click(e, it),
                border_radius=4,
            ) for item in items
        ], scroll=ft.ScrollMode.AUTO, height=300)

        def restore_selected(_):
            global history_cache
            count = 0
            for item in selected_trash.values():
                if mgr.trash_manager.restore_from_trash(item):
                    count += 1
            if count:
                history_cache[current_cli] = {}
                refresh_history_tree()
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(L['history_restored'].format(count))))
            page.update()

        def delete_selected(_):
            for item in selected_trash.values():
                mgr.trash_manager.permanently_delete(item)
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(L['history_perm_deleted'].format(len(selected_trash)))))
            page.update()

        def clear_all(_):
            for item in items:
                mgr.trash_manager.permanently_delete(item)
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(L['history_trash_cleared'])))
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(L['history_trash']),
            content=ft.Column([
                ft.Text(L['history_trash_info'].format(TRASH_RETENTION_DAYS), size=12),
                ft.Text(L['history_click_hint'], size=11, color=ft.Colors.GREY_500),
                trash_list
            ], width=450),
            actions=[
                ft.TextButton(L['history_restore'], on_click=restore_selected),
                ft.TextButton(L['history_perm_delete'], on_click=delete_selected),
                ft.TextButton(L['history_clear_trash'], on_click=clear_all),
                ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update())
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def show_cleanup_dialog(_):
        """清理对话框：删除短会话、30天前会话、空目录"""
        mgr = get_current_manager()
        if not mgr:
            return
        history_data = get_history_data()

        def get_total_chars(info):
            total = 0
            for msg in info.get('messages', []):
                content = msg.get('message', {}).get('content', []) if current_cli == "claude" else msg.get('content', '')
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') in ('text', 'input_text'):
                            total += len(c.get('text', ''))
                elif isinstance(content, str):
                    total += len(content)
            return total

        # 短会话: ≤3条消息且≤150字
        short_sessions = []
        for grp, sessions in history_data.items():
            for sid, info in sessions.items():
                chars = get_total_chars(info)
                if info.get('message_count', 0) <= 3 and chars <= 150:
                    short_sessions.append({'group': grp, 'session_id': sid, 'info': info, 'chars': chars})

        # 30天前会话
        old_cutoff = datetime.now().astimezone() - timedelta(days=30)
        old_sessions = []
        for grp, sessions in history_data.items():
            for sid, info in sessions.items():
                ts = info.get('last_timestamp', '')
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        if dt < old_cutoff:
                            old_sessions.append({'group': grp, 'session_id': sid, 'info': info})
                    except:
                        pass

        # 空项目目录
        empty_dirs = []
        if current_cli == "claude":
            projects_dir = Path.home() / ".claude" / "projects"
            if projects_dir.exists():
                for d in projects_dir.iterdir():
                    if d.is_dir() and not any(f.suffix == '.jsonl' for f in d.iterdir() if f.is_file()):
                        empty_dirs.append(d)

        chk_short = ft.Checkbox(label=L['history_short_label'].format(len(short_sessions)), value=True)
        chk_old = ft.Checkbox(label=L['history_old_label'].format(len(old_sessions)), value=False)
        chk_empty = ft.Checkbox(label=L['history_empty_label'].format(len(empty_dirs)), value=False)

        # 预览列表
        preview_list = ft.Column([], scroll=ft.ScrollMode.AUTO, height=200)

        def update_preview(_=None):
            preview_list.controls.clear()
            if chk_short.value and short_sessions:
                preview_list.controls.append(ft.Text(L['history_short_sessions'], weight=ft.FontWeight.BOLD, size=12))
                for s in short_sessions[:10]:
                    preview_list.controls.append(ft.Text(f"  {s['session_id'][:12]}... ({s['info']['message_count']}msgs, {s['chars']}chars)", size=11, color=ft.Colors.GREY_600))
                if len(short_sessions) > 10:
                    preview_list.controls.append(ft.Text(f"  ...+{len(short_sessions)-10}", size=11, color=ft.Colors.GREY_500))
            if chk_old.value and old_sessions:
                preview_list.controls.append(ft.Text(L['history_old'], weight=ft.FontWeight.BOLD, size=12))
                for s in old_sessions[:10]:
                    preview_list.controls.append(ft.Text(f"  {s['session_id'][:12]}...", size=11, color=ft.Colors.GREY_600))
                if len(old_sessions) > 10:
                    preview_list.controls.append(ft.Text(f"  ...+{len(old_sessions)-10}", size=11, color=ft.Colors.GREY_500))
            if chk_empty.value and empty_dirs:
                preview_list.controls.append(ft.Text(L['history_empty_dirs'], weight=ft.FontWeight.BOLD, size=12))
                for d in empty_dirs[:5]:
                    preview_list.controls.append(ft.Text(f"  {d.name}", size=11, color=ft.Colors.GREY_600))
                if len(empty_dirs) > 5:
                    preview_list.controls.append(ft.Text(f"  ...+{len(empty_dirs)-5}", size=11, color=ft.Colors.GREY_500))
            page.update()

        chk_short.on_change = update_preview
        chk_old.on_change = update_preview
        chk_empty.on_change = update_preview
        update_preview()

        def do_cleanup(_):
            global history_cache
            count = 0
            if chk_short.value:
                for data in short_sessions:
                    if mgr.delete_session(data['group'], data['session_id'], data['info']):
                        count += 1
            if chk_old.value:
                for data in old_sessions:
                    if mgr.delete_session(data['group'], data['session_id'], data['info']):
                        count += 1
            dir_count = 0
            if chk_empty.value:
                import shutil
                for d in empty_dirs:
                    try:
                        shutil.rmtree(d)
                        dir_count += 1
                    except:
                        pass
            history_cache[current_cli] = {}
            dlg.open = False
            page.open(ft.SnackBar(ft.Text(L['history_cleanup_done'].format(count, dir_count))))
            refresh_history_tree()

        dlg = ft.AlertDialog(
            title=ft.Text(L['history_cleanup']),
            content=ft.Column([
                chk_short, chk_old, chk_empty,
                ft.Divider(),
                ft.Text(L['history_cleanup_preview'], size=12, weight=ft.FontWeight.BOLD),
                preview_list,
                ft.Text(L['history_cleanup_hint'], size=11, color=ft.Colors.GREY_600),
            ], width=400, spacing=5),
            actions=[
                ft.TextButton(L['history_cleanup_execute'], on_click=do_cleanup),
                ft.TextButton(L['cancel'], on_click=lambda _: setattr(dlg, 'open', False) or page.update()),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # 批量操作按钮
    batch_delete_btn = ft.TextButton(
        L['history_delete_selected'], visible=False,
        on_click=lambda e: delete_sessions(list(selected_sessions.values()))
    )
    batch_count_text = ft.Text("", size=12)

    def update_selection_buttons():
        batch_delete_btn.visible = len(selected_sessions) > 0
        batch_count_text.value = L['history_selected_count'].format(len(selected_sessions)) if selected_sessions else ""
        page.update()

    cli_dropdown = ft.Dropdown(
        value="claude",
        options=[
            ft.dropdown.Option("claude", "Claude"),
            ft.dropdown.Option("codex", "Codex"),
            ft.dropdown.Option("gemini", "Gemini"),
            ft.dropdown.Option("aider", "Aider"),
        ],
        width=120,
        on_change=lambda _: refresh_with_cli_check(),
    )

    def refresh_with_cli_check(_=None):
        nonlocal current_cli
        new_cli = cli_dropdown.value or "claude"
        if new_cli != current_cli:
            current_cli = new_cli
            history_detail.controls.clear()
        refresh_history_tree(history_search.value or "")

    # 日期筛选
    date_filter = "all"
    custom_date_from = None
    custom_date_to = None

    date_dropdown = ft.Dropdown(
        value="all",
        options=[
            ft.dropdown.Option("all", "全部"),
            ft.dropdown.Option("today", "今天"),
            ft.dropdown.Option("week", "本周"),
            ft.dropdown.Option("month", "本月"),
            ft.dropdown.Option("custom", "自定义"),
        ],
        width=100,
        on_change=lambda _: refresh_with_date_check(),
    )

    date_from_btn = ft.TextButton("起始日期", visible=False)
    date_to_btn = ft.TextButton("结束日期", visible=False)

    def on_date_from_picked(e):
        nonlocal custom_date_from
        if e.control.value:
            custom_date_from = e.control.value
            date_from_btn.text = custom_date_from.strftime("%Y-%m-%d")
            page.update()

    def on_date_to_picked(e):
        nonlocal custom_date_to
        if e.control.value:
            custom_date_to = e.control.value.replace(hour=23, minute=59, second=59)
            date_to_btn.text = custom_date_to.strftime("%Y-%m-%d")
            page.update()

    date_from_picker = ft.DatePicker(on_change=on_date_from_picked)
    date_to_picker = ft.DatePicker(on_change=on_date_to_picked)
    page.overlay.extend([date_from_picker, date_to_picker])

    date_from_btn.on_click = lambda _: page.open(date_from_picker)
    date_to_btn.on_click = lambda _: page.open(date_to_picker)

    def refresh_with_date_check(_=None):
        nonlocal date_filter
        new_filter = date_dropdown.value or "all"
        date_filter = new_filter
        if new_filter == "custom":
            date_from_btn.visible = True
            date_to_btn.visible = True
        else:
            date_from_btn.visible = False
            date_to_btn.visible = False
        refresh_with_cli_check()

    history_page = ft.Column([
        ft.Row([
            ft.Text(L['history'], size=20, weight=ft.FontWeight.BOLD),
            cli_dropdown,
            date_dropdown,
            date_from_btn,
            date_to_btn,
            history_search,
            ft.TextButton("刷新", on_click=refresh_with_date_check),
            ft.TextButton("回收站", on_click=show_trash_dialog),
            ft.TextButton("清理", on_click=show_cleanup_dialog),
            batch_count_text,
            batch_delete_btn,
            history_progress,
        ], wrap=True),
        history_stats,
        ft.Row([
            ft.Container(history_tree, expand=2, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, padding=10),
            ft.Container(history_detail, expand=3, border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8, padding=10),
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
    ], expand=True, spacing=10)

    # 键盘快捷键
    def on_keyboard(e: ft.KeyboardEvent):
        if content_area.content != history_page:
            return
        if e.key == "Delete" and selected_sessions:
            delete_sessions(list(selected_sessions.values()))
        elif e.key == "F5":
            refresh_history_tree(history_search.value or "")
    page.on_keyboard_event = on_keyboard

    # ========== 导航和页面切换 ==========
    content_area = ft.Container(api_page, expand=True, padding=20)

    def switch_page(e):
        nonlocal current_page_idx
        idx = e.control.selected_index
        current_page_idx = idx
        if idx == 0:
            content_area.content = api_page
            refresh_config_list()
        elif idx == 1:
            content_area.content = prompt_page
            refresh_prompt_list()
        elif idx == 2:
            content_area.content = mcp_page
            if not mcp_tree.controls:
                page.update()
                async def load_mcp():
                    if current_page_idx != 2: return
                    refresh_mcp_tree()
                page.run_task(load_mcp)
                return
        elif idx == 3:
            content_area.content = history_page
            if not history_cache.get(current_cli) or not history_tree.controls:
                page.update()
                async def load_history():
                    if current_page_idx != 3: return
                    refresh_history_tree()
                page.run_task(load_history)
                return
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
            ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label=L['history']),
        ],
        on_change=switch_page,
        trailing=ft.Container(
            content=ft.Column([
                ft.IconButton(ft.Icons.DARK_MODE if theme_mode == 'light' else ft.Icons.LIGHT_MODE, on_click=toggle_theme, tooltip=L['toggle_theme']),
                ft.TextButton(L['switch_lang'], icon=ft.Icons.LANGUAGE, on_click=switch_lang),
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

    # 后台预加载历史记录（使用线程池避免阻塞UI）
    import asyncio
    async def preload_history():
        global history_cache
        loop = asyncio.get_event_loop()
        if history_manager:
            history_cache["claude"] = await loop.run_in_executor(None, history_manager.load_sessions)
        if codex_history_manager:
            history_cache["codex"] = await loop.run_in_executor(None, codex_history_manager.load_sessions)
    page.run_task(preload_history)

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
