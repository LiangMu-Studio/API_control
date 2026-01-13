# AI CLI Manager - Database Module
import sqlite3
import json
import shutil
import time
from pathlib import Path
from datetime import datetime
from .common import CONFIG_DIR, DB_FILE, MCP_DATA_DIR, MCP_DB_FILE, CLAUDE_DIR, CODEX_DIR, TRASH_RETENTION_DAYS

# ========== SQLite 提示词数据库 ==========
class PromptDB:
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
                prompt_type TEXT DEFAULT 'user',
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

    def get_by_lang(self, lang: str) -> dict:
        """获取指定语言的提示词（id 以 _zh 或 _en 结尾）"""
        suffix = f"_{lang}"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM prompts WHERE id LIKE ? OR is_builtin=0 ORDER BY prompt_type DESC, name",
                (f"%{suffix}",)
            ).fetchall()
        return {r['id']: dict(r) for r in rows}

    def get_by_type(self, prompt_type: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM prompts WHERE prompt_type=? ORDER BY name', (prompt_type,)).fetchall()
        return {r['id']: dict(r) for r in rows}

    def get_system_prompt(self) -> dict | None:
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

    def update_builtin(self, prompts: dict):
        """强制更新内置提示词（覆盖已有内容）"""
        for pid, p in prompts.items():
            self.save({
                'id': pid,
                'name': p.get('name', pid),
                'content': p.get('content', ''),
                'category': p.get('category', '用户'),
                'prompt_type': 'user',
                'is_builtin': True,
            })


# ========== MCP 本地仓库管理 ==========
class MCPRegistry:
    CATEGORY_MAP = {
        'file': '文件', 'filesystem': '文件', 'storage': '文件', 'pdf': '文件', 'excel': '文件',
        'document': '文件', 'csv': '文件', 'xml': '文件', 'markdown': '文件', 'docx': '文件',
        'web': '网络', 'http': '网络', 'fetch': '网络', 'scrape': '网络', 'url': '网络',
        'database': '数据库', 'sql': '数据库', 'postgres': '数据库', 'mysql': '数据库', 'mongo': '数据库',
        'memory': '知识库', 'rag': '知识库', 'embedding': '知识库', 'vector': '知识库', 'knowledge': '知识库',
        'openai': '模型', 'anthropic': '模型', 'gemini': '模型', 'ollama': '模型', 'huggingface': '模型',
        'git': '开发', 'github': '开发', 'gitlab': '开发', 'code': '开发', 'ide': '开发',
        'search': '搜索', 'google': '搜索', 'bing': '搜索', 'tavily': '搜索',
        'util': '工具', 'translate': '工具', 'time': '工具', 'weather': '工具',
        'kubernetes': '云服务', 'docker': '云服务', 'aws': '云服务', 'azure': '云服务',
        'slack': '通讯', 'discord': '通讯', 'telegram': '通讯', 'email': '通讯',
        'browser': '浏览器', 'playwright': '浏览器', 'puppeteer': '浏览器', 'selenium': '浏览器',
        'figma': '设计', 'design': '设计',
        'youtube': '媒体', 'video': '媒体', 'audio': '媒体', 'image': '媒体',
        'map': '地图', 'location': '地图', 'geo': '地图',
        'security': '安全', 'auth': '安全', 'oauth': '安全',
        'payment': '电商', 'stripe': '电商', 'shop': '电商',
        'twitter': '社交', 'facebook': '社交', 'instagram': '社交',
        'jira': '项目', 'asana': '项目', 'trello': '项目',
        'game': '游戏',
        'stock': '金融', 'crypto': '金融', 'finance': '金融',
        'news': '新闻', 'rss': '新闻',
        'calendar': '日历', 'schedule': '日历',
        'note': '笔记', 'obsidian': '笔记',
    }

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
            try:
                conn.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS servers_fts USING fts5(
                    name, description, content='servers', content_rowid='rowid'
                )''')
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
            except sqlite3.OperationalError:
                pass  # FTS5 可能不支持，忽略
            conn.commit()

    def _guess_category(self, name: str, desc: str) -> str:
        text = (name + ' ' + desc).lower()
        for kw, cat in self.CATEGORY_MAP.items():
            if kw in text:
                return cat
        return '其他'

    def _normalize_npm(self, obj: dict) -> dict | None:
        pkg = obj.get('package', {})
        name = pkg.get('name', '')
        desc = pkg.get('description', '') or ''
        name_lower = name.lower()
        desc_lower = desc.lower()
        is_mcp = ('mcp' in name_lower or 'model context protocol' in desc_lower or 'modelcontextprotocol' in name_lower)
        if not is_mcp:
            return None
        skip_keywords = ['test', 'example', 'demo', 'sample', 'template', 'boilerplate', 'hello-world', 'starter']
        if any(kw in name_lower for kw in skip_keywords):
            return None
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
        import urllib.request
        errors, new_count = [], 0
        now = datetime.now().isoformat()
        if quick:
            urls = [
                'https://registry.npmjs.org/-/v1/search?text=mcp-server&size=250&quality=0.0&popularity=0.0&maintenance=0.0',
                'https://registry.npmjs.org/-/v1/search?text=mcp&size=250&quality=0.0&popularity=0.0&maintenance=0.0',
            ]
        else:
            urls = []
            for kw in ['mcp-server', 'mcp']:
                for i in range(0, 3000, 250):
                    urls.append(f'https://registry.npmjs.org/-/v1/search?text={kw}&size=250&from={i}')

        for i, url in enumerate(urls):
            if callback:
                callback(f"获取 npm ({i+1}/{len(urls)})...")
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = json.loads(resp.read().decode('utf-8'))
                    items = raw.get('objects', [])
                    hit_existing = 0
                    with sqlite3.connect(self.db_path) as conn:
                        for item in items:
                            s = self._normalize_npm(item)
                            if not s:
                                continue
                            cur = conn.execute('SELECT 1 FROM servers WHERE id=?', (s['id'],))
                            if cur.fetchone():
                                hit_existing += 1
                                if quick and hit_existing >= 5:
                                    break
                            else:
                                hit_existing = 0
                                conn.execute('''INSERT INTO servers (id,name,description,package,command,args,category,source,updated_at)
                                    VALUES (?,?,?,?,?,?,?,?,?)''',
                                    (s['id'], s['name'], s['description'], s['package'], s['command'], s['args'], s['category'], s['source'], now))
                                new_count += 1
                        conn.commit()
            except Exception as ex:
                errors.append(f"npm: {ex}")

        if callback:
            callback(f"完成：新增 {new_count} 个 MCP")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('updated_at', now))
            conn.commit()
        return new_count, errors

    def search(self, keyword: str = '', category: str = '全部', limit: int = 200) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if keyword:
                try:
                    sql = '''SELECT s.* FROM servers s JOIN servers_fts f ON s.rowid = f.rowid WHERE servers_fts MATCH ?'''
                    params = [f'"{keyword}"*']
                    if category and category != '全部':
                        sql += ' AND s.category = ?'
                        params.append(category)
                    sql += f' LIMIT {limit}'
                    rows = conn.execute(sql, params).fetchall()
                except sqlite3.OperationalError:
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
        except (ValueError, KeyError):
            return True


# ========== 回收站管理器 ==========
class TrashManager:
    def __init__(self, claude_dir: Path):
        self.claude_dir = claude_dir
        self.trash_dir = claude_dir / "trash"
        self.trash_dir.mkdir(exist_ok=True)
        self.manifest_file = self.trash_dir / "manifest.json"

    def _load_manifest(self) -> dict:
        if self.manifest_file.exists():
            try:
                return json.loads(self.manifest_file.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                pass  # 文件损坏或读取失败
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
        except (OSError, shutil.Error):
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
        except (OSError, shutil.Error, KeyError):
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


# ========== Claude 历史记录管理器 (使用 Rust 加速库) ==========
import liangmu_history as lh


class RustTrashManager:
    """基于 Rust 库的回收站管理器"""
    def __init__(self, cli_type: str):
        self.cli_type = cli_type

    def get_trash_items(self) -> list:
        items = lh.get_trash_items(self.cli_type)
        return [{'session_id': i.session_id, 'project_name': i.project_name,
                 'deleted_at': i.deleted_at, 'dir_name': i.dir_name,
                 'original_file': i.original_file} for i in items]

    def restore_from_trash(self, item: dict) -> bool:
        try:
            lh.restore_from_trash(self.cli_type, item['dir_name'])
            return True
        except Exception:
            return False

    def permanently_delete(self, item: dict):
        lh.permanently_delete(self.cli_type, item['dir_name'])

    def cleanup_expired(self) -> int:
        return lh.cleanup_expired_trash(self.cli_type, TRASH_RETENTION_DAYS)


class HistoryManager:
    """Claude 历史记录管理器 - 使用 Rust 加速"""
    def __init__(self, claude_dir: Path):
        self.claude_dir = claude_dir
        self.trash_manager = RustTrashManager('claude')

    def list_projects(self, with_cwd: bool = False, limit: int = 0) -> list:
        projects = lh.list_projects('claude', limit if limit > 0 else 0)
        if not with_cwd:
            return [p.id for p in projects]
        return [(p.id, p.cwd or '') for p in projects]

    def get_project_cwd(self, project_name: str) -> str:
        projects = lh.list_projects('claude', 0)
        for p in projects:
            if p.id == project_name:
                return p.cwd or ''
        return ''

    def load_project(self, project_name: str) -> dict:
        sessions = lh.load_project('claude', project_name)
        result = {}
        for s in sessions:
            full = lh.load_session('claude', s.file_path)
            if full:
                messages = self._convert_messages(full.messages)
                result[s.id] = {
                    'file': Path(s.file_path),
                    'messages': messages,
                    'message_count': s.message_count,
                    'first_timestamp': s.first_timestamp,
                    'last_timestamp': s.last_timestamp,
                    'cwd': s.cwd,
                    'size': s.file_size
                }
        return result

    def _convert_messages(self, rust_messages) -> list:
        """将 Rust Message 对象转换为 Python dict"""
        result = []
        for m in rust_messages:
            content = []
            for b in m.content_blocks:
                block = {'type': b.block_type}
                if b.text:
                    block['text'] = b.text
                if b.tool_name:
                    block['name'] = b.tool_name
                if b.tool_input:
                    try:
                        block['input'] = json.loads(b.tool_input)
                    except json.JSONDecodeError:
                        block['input'] = b.tool_input
                content.append(block)
            result.append({
                'type': m.msg_type,
                'uuid': m.uuid,
                'timestamp': m.timestamp,
                'message': {'role': m.role, 'content': content}
            })
        return result

    def load_sessions(self, callback=None) -> dict:
        """加载所有项目的会话（用于预加载）"""
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
            result[project_name] = self.load_project(project_name)
        return result

    def delete_session(self, project_name: str, session_id: str, info: dict) -> bool:
        try:
            lh.delete_session('claude', str(info['file']))
            return True
        except Exception:
            return False

    def export_to_markdown(self, session_id: str, info: dict) -> str:
        try:
            return lh.export_to_markdown('claude', str(info['file']))
        except Exception:
            return ''

    def delete_sessions_by_cwd(self, cwd: str) -> int:
        """删除指定工作目录的所有会话，返回删除数量"""
        count = 0
        projects = lh.list_projects('claude', 0)
        for p in projects:
            if p.cwd == cwd:
                sessions = lh.load_project('claude', p.id)
                for s in sessions:
                    try:
                        lh.delete_session('claude', str(s.file))
                        count += 1
                    except Exception:
                        pass
        return count


# ========== Codex 历史记录管理器 (使用 Rust 加速库) ==========
class CodexHistoryManager:
    """Codex 历史记录管理器 - 使用 Rust 加速"""
    def __init__(self, codex_dir: Path):
        self.codex_dir = codex_dir
        self.trash_manager = RustTrashManager('codex')

    def list_projects(self, with_cwd: bool = False, limit: int = 0, on_update=None) -> list:
        projects = lh.list_projects('codex', limit if limit > 0 else 0)
        if not with_cwd:
            return [p.cwd or p.id for p in projects]
        return [(p.cwd or p.id, p.cwd or p.id) for p in projects]

    def load_project(self, cwd_path: str) -> dict:
        sessions = lh.load_project('codex', cwd_path)
        result = {}
        for s in sessions:
            full = lh.load_session('codex', s.file_path)
            if full:
                messages = self._convert_messages(full.messages)
                result[s.id] = {
                    'file': Path(s.file_path),
                    'messages': messages,
                    'message_count': s.message_count,
                    'first_timestamp': s.first_timestamp,
                    'last_timestamp': s.last_timestamp,
                    'cwd': s.cwd,
                    'size': s.file_size
                }
        return result

    def _convert_messages(self, rust_messages) -> list:
        result = []
        for m in rust_messages:
            text = m.get_text() if hasattr(m, 'get_text') else ''
            result.append({
                'role': m.role,
                'content': text
            })
        return result

    def load_sessions(self, callback=None) -> dict:
        """加载所有会话（用于预加载）"""
        projects = self.list_projects(limit=0)
        result = {}
        for cwd in projects:
            if callback:
                callback(f"扫描: {cwd[:30]}...")
            result[cwd] = self.load_project(cwd)
        return result

    def delete_session(self, date_group: str, session_id: str, info: dict) -> bool:
        try:
            lh.delete_session('codex', str(info['file']))
            return True
        except Exception:
            return False

    def export_to_markdown(self, session_id: str, info: dict) -> str:
        try:
            return lh.export_to_markdown('codex', str(info['file']))
        except Exception:
            return ''


# ========== 全局实例 ==========
mcp_registry = MCPRegistry(MCP_DB_FILE)
history_manager = HistoryManager(CLAUDE_DIR) if CLAUDE_DIR.exists() else None
codex_history_manager = CodexHistoryManager(CODEX_DIR) if CODEX_DIR.exists() else None
history_cache = {"claude": None, "codex": None}


# ========== 工具使用统计数据库 ==========
class ToolUsageDB:
    """MCP 和 Skill 使用统计"""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS tool_usage (
                tool_type TEXT,
                tool_name TEXT,
                project_id TEXT,
                call_count INTEGER DEFAULT 0,
                last_used TEXT,
                PRIMARY KEY (tool_type, tool_name, project_id)
            )''')
            # 同步元数据表
            conn.execute('''CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
            conn.commit()

    def get_last_sync_time(self) -> float:
        """获取上次同步时间戳"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT value FROM sync_meta WHERE key="last_sync"').fetchone()
            return float(row[0]) if row else 0

    def set_last_sync_time(self, ts: float):
        """设置同步时间戳"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT OR REPLACE INTO sync_meta (key, value) VALUES ("last_sync", ?)', (str(ts),))
            conn.commit()

    def delete_by_session(self, project_id: str, session_id: str):
        """删除指定会话的统计（用于增量更新前清理）"""
        # 由于没有 session_id 字段，这里按 project_id 删除
        pass  # 增量更新时直接覆盖即可

    def record_usage(self, tool_type: str, tool_name: str, project_id: str, timestamp: str = None):
        """记录一次工具调用"""
        now = timestamp or datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''INSERT INTO tool_usage (tool_type, tool_name, project_id, call_count, last_used)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(tool_type, tool_name, project_id) DO UPDATE SET
                call_count = call_count + 1, last_used = ?''',
                (tool_type, tool_name, project_id, now, now))
            conn.commit()

    def batch_record(self, records: list[tuple[str, str, str, int, str]]):
        """批量记录: [(tool_type, tool_name, project_id, count, last_used), ...]"""
        with sqlite3.connect(self.db_path) as conn:
            for tool_type, tool_name, project_id, count, last_used in records:
                conn.execute('''INSERT INTO tool_usage (tool_type, tool_name, project_id, call_count, last_used)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(tool_type, tool_name, project_id) DO UPDATE SET
                    call_count = call_count + excluded.call_count,
                    last_used = CASE WHEN excluded.last_used > last_used THEN excluded.last_used ELSE last_used END''',
                    (tool_type, tool_name, project_id, count, last_used))
            conn.commit()

    def get_all_mcp(self) -> list[dict]:
        """获取所有 MCP 使用统计"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''SELECT tool_name, SUM(call_count) as total_calls,
                MAX(last_used) as last_used, COUNT(DISTINCT project_id) as project_count
                FROM tool_usage WHERE tool_type='mcp'
                GROUP BY tool_name ORDER BY total_calls DESC''').fetchall()
        return [dict(r) for r in rows]

    def get_all_skills(self) -> list[dict]:
        """获取所有 Skill 使用统计"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''SELECT tool_name, SUM(call_count) as total_calls,
                MAX(last_used) as last_used, COUNT(DISTINCT project_id) as project_count
                FROM tool_usage WHERE tool_type='skill'
                GROUP BY tool_name ORDER BY total_calls DESC''').fetchall()
        return [dict(r) for r in rows]

    def get_by_project(self, project_id: str) -> dict:
        """获取指定项目的工具使用统计"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM tool_usage WHERE project_id=?', (project_id,)).fetchall()
        return {'mcp': [dict(r) for r in rows if r['tool_type'] == 'mcp'],
                'skill': [dict(r) for r in rows if r['tool_type'] == 'skill']}

    def clear_all(self):
        """清空所有统计数据"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM tool_usage')
            conn.commit()


# 工具使用统计数据库实例
TOOL_USAGE_DB_FILE = MCP_DATA_DIR / 'tool_usage.db'
tool_usage_db = ToolUsageDB(TOOL_USAGE_DB_FILE)


# ========== MCP/Skill 库和预设管理 ==========
class MCPSkillLibrary:
    """MCP 和 Skill 的完整管理库"""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # MCP 库
            conn.execute('''CREATE TABLE IF NOT EXISTS mcp_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                command TEXT DEFAULT 'npx',
                args TEXT,
                env TEXT,
                category TEXT DEFAULT '其他',
                source TEXT DEFAULT 'manual',
                description TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TEXT
            )''')
            # 迁移：为旧表添加 is_default 字段
            try:
                conn.execute('ALTER TABLE mcp_library ADD COLUMN is_default INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass  # 字段已存在
            # Skill 库
            conn.execute('''CREATE TABLE IF NOT EXISTS skill_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                file_path TEXT,
                content TEXT,
                category TEXT DEFAULT '其他',
                source TEXT DEFAULT 'manual',
                description TEXT,
                created_at TEXT
            )''')
            # 迁移：为旧表添加 category 字段
            try:
                conn.execute('ALTER TABLE skill_library ADD COLUMN category TEXT DEFAULT "其他"')
            except sqlite3.OperationalError:
                pass  # 字段已存在
            # MCP 预设组合
            conn.execute('''CREATE TABLE IF NOT EXISTS mcp_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                mcp_names TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TEXT
            )''')
            # Skill 预设组合
            conn.execute('''CREATE TABLE IF NOT EXISTS skill_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                skill_names TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TEXT
            )''')
            conn.commit()

    # ===== MCP 库操作 =====
    def add_mcp(self, name: str, command: str = 'npx', args: str = '', env: str = '',
                category: str = '其他', source: str = 'manual', description: str = '') -> bool:
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''INSERT OR IGNORE INTO mcp_library
                    (name, command, args, env, category, source, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (name, command, args, env, category, source, description, now))
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def update_mcp(self, name: str, **kwargs) -> bool:
        fields = ['command', 'args', 'env', 'category', 'description']
        updates = [(k, v) for k, v in kwargs.items() if k in fields and v is not None]
        if not updates:
            return False
        sql = f"UPDATE mcp_library SET {', '.join(f'{k}=?' for k, _ in updates)} WHERE name=?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(sql, [v for _, v in updates] + [name])
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_mcp(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM mcp_library WHERE name=?', (name,))
            conn.commit()
        return True

    def get_all_mcp(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM mcp_library ORDER BY name').fetchall()
        return [dict(r) for r in rows]

    def get_mcp(self, name: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM mcp_library WHERE name=?', (name,)).fetchone()
        return dict(row) if row else None

    def set_mcp_default(self, name: str, is_default: bool) -> bool:
        """设置 MCP 的默认状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('UPDATE mcp_library SET is_default=? WHERE name=?',
                            (1 if is_default else 0, name))
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def get_default_mcps(self) -> list[dict]:
        """获取所有标记为默认的 MCP"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM mcp_library WHERE is_default=1 ORDER BY name').fetchall()
        return [dict(r) for r in rows]

    # ===== Skill 库操作 =====
    def add_skill(self, name: str, file_path: str = '', content: str = '',
                  category: str = '其他', source: str = 'manual', description: str = '') -> bool:
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''INSERT OR IGNORE INTO skill_library
                    (name, file_path, content, category, source, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (name, file_path, content, category, source, description, now))
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def update_skill(self, name: str, **kwargs) -> bool:
        fields = ['file_path', 'content', 'category', 'description']
        updates = [(k, v) for k, v in kwargs.items() if k in fields and v is not None]
        if not updates:
            return False
        sql = f"UPDATE skill_library SET {', '.join(f'{k}=?' for k, _ in updates)} WHERE name=?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(sql, [v for _, v in updates] + [name])
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_skill(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM skill_library WHERE name=?', (name,))
            conn.commit()
        return True

    def get_all_skills(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM skill_library ORDER BY name').fetchall()
        return [dict(r) for r in rows]

    def get_skill(self, name: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM skill_library WHERE name=?', (name,)).fetchone()
        return dict(row) if row else None

    # ===== MCP 预设操作 =====
    def add_mcp_preset(self, name: str, mcp_names: list[str], is_default: bool = False) -> bool:
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                if is_default:
                    conn.execute('UPDATE mcp_presets SET is_default=0')
                conn.execute('''INSERT OR REPLACE INTO mcp_presets
                    (name, mcp_names, is_default, created_at) VALUES (?, ?, ?, ?)''',
                    (name, json.dumps(mcp_names), 1 if is_default else 0, now))
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_mcp_preset(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM mcp_presets WHERE name=?', (name,))
            conn.commit()
        return True

    def get_all_mcp_presets(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM mcp_presets ORDER BY is_default DESC, name').fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['mcp_names'] = json.loads(d['mcp_names']) if d['mcp_names'] else []
            result.append(d)
        return result

    def get_default_mcp_preset(self) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM mcp_presets WHERE is_default=1').fetchone()
        if row:
            d = dict(row)
            d['mcp_names'] = json.loads(d['mcp_names']) if d['mcp_names'] else []
            return d
        return None

    # ===== Skill 预设操作 =====
    def add_skill_preset(self, name: str, skill_names: list[str], is_default: bool = False) -> bool:
        now = datetime.now().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                if is_default:
                    conn.execute('UPDATE skill_presets SET is_default=0')
                conn.execute('''INSERT OR REPLACE INTO skill_presets
                    (name, skill_names, is_default, created_at) VALUES (?, ?, ?, ?)''',
                    (name, json.dumps(skill_names), 1 if is_default else 0, now))
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_skill_preset(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM skill_presets WHERE name=?', (name,))
            conn.commit()
        return True

    def get_all_skill_presets(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM skill_presets ORDER BY is_default DESC, name').fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['skill_names'] = json.loads(d['skill_names']) if d['skill_names'] else []
            result.append(d)
        return result

    def get_default_skill_preset(self) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM skill_presets WHERE is_default=1').fetchone()
        if row:
            d = dict(row)
            d['skill_names'] = json.loads(d['skill_names']) if d['skill_names'] else []
            return d
        return None


# MCP/Skill 库实例
mcp_skill_library = MCPSkillLibrary(MCP_DB_FILE)


def register_builtin_mcp():
    """注册内置 MCP 服务器"""
    import sys
    # 获取内置 MCP 服务器路径
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent
    pathfixer_path = base_dir / 'mcp_servers' / 'pathfixer_server.py'
    if not pathfixer_path.exists():
        return
    # 获取 Python 解释器路径
    python_exe = sys.executable
    # 注册到数据库（如果不存在）
    existing = mcp_skill_library.get_mcp('pathfixer')
    if not existing:
        mcp_skill_library.add_mcp(
            name='pathfixer',
            command=python_exe,
            args=str(pathfixer_path),
            env='',
            category='常用',
            source='builtin',
            description='内置路径修正工具 + 代理搜索/抓取'
        )

# 启动时注册内置 MCP
register_builtin_mcp()


def sync_tool_usage_from_history():
    """从历史记录增量同步 MCP/Skill 到管理库

    首次启动：全量扫描所有历史文件
    后续启动：只扫描 mtime > last_sync_time 的文件
    """
    import time
    from core.history_parser import history_parser

    last_sync = tool_usage_db.get_last_sync_time()
    current_time = time.time()
    is_first_sync = last_sync == 0

    discovered_mcp = set()
    discovered_skills = set()
    scanned_files = 0

    for project_name in history_parser.list_projects():
        project_dir = history_parser.projects_dir / project_name
        if not project_dir.exists():
            continue

        for f in project_dir.glob('*.jsonl'):
            if not is_first_sync and f.stat().st_mtime <= last_sync:
                continue

            scanned_files += 1
            session = history_parser.parse_session_file(f)
            if session:
                for mcp_name in session.mcp_calls:
                    discovered_mcp.add(mcp_name)
                for skill_name in session.skill_calls:
                    discovered_skills.add(skill_name)

    # 从配置文件中读取 MCP 完整配置
    mcp_configs = _load_mcp_configs_from_files()

    # 添加到管理库（自动去重）
    added_mcp, added_skill = 0, 0
    for mcp_name in discovered_mcp:
        # mcp__pathfixer__xxx -> pathfixer
        parts = mcp_name.split('__')
        server_name = parts[1] if len(parts) >= 2 else mcp_name
        # 尝试从配置文件获取完整信息
        cfg = mcp_configs.get(server_name, {})
        if mcp_skill_library.add_mcp(
            server_name,
            command=cfg.get('command', 'npx'),
            args=cfg.get('args', ''),
            env=cfg.get('env', ''),
            source='discovered'
        ):
            added_mcp += 1

    for skill_name in discovered_skills:
        if mcp_skill_library.add_skill(skill_name, source='discovered'):
            added_skill += 1

    tool_usage_db.set_last_sync_time(current_time)

    if scanned_files > 0:
        print(f"[库同步] 扫描 {scanned_files} 文件, 新增 MCP:{added_mcp} Skill:{added_skill}")

    return added_mcp + added_skill


def _load_mcp_configs_from_files() -> dict:
    """从配置文件中加载 MCP 完整配置"""
    configs = {}
    home = Path.home()

    # 配置文件位置
    mcp_files = [
        home / '.claude.json',  # 全局 MCP 配置
        home / '.claude' / '.mcp.json',
        home / '.claude' / 'settings.json',
    ]

    for mcp_file in mcp_files:
        if not mcp_file.exists():
            continue
        try:
            data = json.loads(mcp_file.read_text(encoding='utf-8'))
            servers = data.get('mcpServers', {})
            for name, cfg in servers.items():
                if name in configs:
                    continue  # 不覆盖已有配置
                args = cfg.get('args', [])
                env = cfg.get('env', {})
                configs[name] = {
                    'command': cfg.get('command', 'npx'),
                    'args': ' '.join(args) if isinstance(args, list) else str(args),
                    'env': ' '.join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else '',
                }
        except (json.JSONDecodeError, OSError):
            continue

    return configs


# MCP JSON 文件路径（用于迁移）
MCP_JSON_FILE = Path(__file__).parent.parent / 'data' / 'mcp.json'


def load_mcp_from_json() -> list:
    """从旧 JSON 文件加载 MCP 列表（仅用于迁移）"""
    if MCP_JSON_FILE.exists():
        try:
            with open(MCP_JSON_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def migrate_mcp_list_to_library(mcp_list: list) -> int:
    """将 state.mcp_list 迁移到 mcp_library 数据库

    Args:
        mcp_list: 旧的 MCP 列表（来自 JSON 文件）

    Returns:
        迁移的 MCP 数量
    """
    migrated = 0
    for m in mcp_list:
        name = m.get('name', '')
        if not name:
            continue
        # 检查是否已存在
        existing = mcp_skill_library.get_mcp(name)
        if existing:
            # 更新 is_default 状态
            if m.get('is_default') and not existing.get('is_default'):
                mcp_skill_library.set_mcp_default(name, True)
            continue
        # 添加新 MCP
        if mcp_skill_library.add_mcp(
            name=name,
            command=m.get('command', 'npx'),
            args=m.get('args', ''),
            env=m.get('env', ''),
            category=m.get('category', '其他'),
            source='migrated',
            description=m.get('description', '')
        ):
            if m.get('is_default'):
                mcp_skill_library.set_mcp_default(name, True)
            migrated += 1
    return migrated


def generate_mcp_config(target_path: Path, mcp_names: list[str] = None) -> bool:
    """从数据库生成 .mcp.json 配置文件

    Args:
        target_path: 目标路径（如 ~/.claude/.mcp.json 或 {cwd}/.claude/.mcp.json）
        mcp_names: 要包含的 MCP 名称列表，None 表示所有默认的

    Returns:
        是否成功生成
    """
    if mcp_names is None:
        # 获取所有标记为默认的 MCP
        mcps = [m for m in mcp_skill_library.get_all_mcp() if m.get('is_default')]
    else:
        mcps = [mcp_skill_library.get_mcp(name) for name in mcp_names]
        mcps = [m for m in mcps if m]  # 过滤 None

    servers = {}
    for m in mcps:
        cfg = {'command': m.get('command', 'npx')}
        args = m.get('args', '')
        if args:
            cfg['args'] = args.split()
        env_str = m.get('env', '')
        if env_str:
            env_dict = {}
            for part in env_str.split():
                if '=' in part:
                    k, v = part.split('=', 1)
                    env_dict[k] = v
            if env_dict:
                cfg['env'] = env_dict
        servers[m['name']] = cfg

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps({'mcpServers': servers}, indent=2, ensure_ascii=False), encoding='utf-8')
        return True
    except OSError:
        return False
