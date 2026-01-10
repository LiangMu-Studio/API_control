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


# ========== Claude 历史记录管理器 ==========
class HistoryManager:
    def __init__(self, claude_dir: Path):
        self.claude_dir = claude_dir
        self.trash_manager = TrashManager(claude_dir)

    def list_projects(self, with_cwd: bool = False, limit: int = 0) -> list:
        """列出项目文件夹，按最后修改时间倒序
        with_cwd: 是否同时获取每个项目的cwd（从第一个session读取）
        limit: 限制返回数量，0表示不限制
        """
        projects_dir = self.claude_dir / "projects"
        if not projects_dir.exists():
            return []
        dirs = [d for d in projects_dir.iterdir() if d.is_dir()]
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        if limit > 0:
            dirs = dirs[:limit]
        if not with_cwd:
            return [d.name for d in dirs]
        # 返回 [(folder_name, cwd), ...]
        result = []
        for d in dirs:
            cwd = ''
            for f in d.glob("*.jsonl"):
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        for line in fp:
                            if '"cwd"' in line:
                                import json
                                data = json.loads(line)
                                cwd = data.get('cwd', '')
                                break
                    if cwd:
                        break
                except (OSError, json.JSONDecodeError):
                    pass
            result.append((d.name, cwd))
        return result

    def get_project_cwd(self, project_name: str) -> str:
        """获取项目的工作目录"""
        project_dir = self.claude_dir / "projects" / project_name
        if not project_dir.exists():
            return ''
        for f in project_dir.glob("*.jsonl"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    for line in fp:
                        if '"cwd"' in line:
                            data = json.loads(line)
                            return data.get('cwd', '')
            except (OSError, json.JSONDecodeError):
                pass
        return ''

    def load_project(self, project_name: str) -> dict:
        """加载单个项目的会话"""
        project_dir = self.claude_dir / "projects" / project_name
        result = {}
        if not project_dir.exists():
            return result
        for session_file in project_dir.glob("*.jsonl"):
            info = self._parse_session(session_file)
            if info:
                result[session_file.stem] = info
        return result

    def load_sessions(self, callback=None) -> dict:
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
                    except json.JSONDecodeError:
                        continue  # 跳过损坏的行
            if not messages:
                return None
            return {
                'file': session_file, 'messages': messages, 'message_count': len(messages),
                'first_timestamp': first_ts, 'last_timestamp': last_ts, 'cwd': cwd,
                'size': session_file.stat().st_size
            }
        except (OSError, json.JSONDecodeError):
            return None

    def _extract_text(self, content) -> str:
        """从消息内容提取文本"""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            text = ""
            for c in content.get('content', []):
                if isinstance(c, dict) and c.get('type') == 'text':
                    text += c.get('text', '')
            return text
        return str(content)

    def delete_session(self, project_name: str, session_id: str, info: dict) -> bool:
        file_history_dir = info['file'].parent / "file-history" / session_id
        return self.trash_manager.move_to_trash(session_id, project_name, info['file'], file_history_dir if file_history_dir.exists() else None)

    def delete_sessions_by_cwd(self, cwd: str) -> int:
        """删除指定工作目录下的所有会话（移到回收站）"""
        cwd_norm = Path(cwd).resolve().as_posix().lower().rstrip('/')
        cnt = 0
        for project_name in self.list_projects():
            sessions = self.load_project(project_name)
            for sid, info in sessions.items():
                session_cwd = info.get('cwd', '')
                if session_cwd and Path(session_cwd).resolve().as_posix().lower().rstrip('/') == cwd_norm:
                    if self.delete_session(project_name, sid, info):
                        cnt += 1
        return cnt

    def export_to_markdown(self, session_id: str, info: dict) -> str:
        lines = [f"# Claude 会话: {session_id}\n", f"路径: {info.get('cwd', '未知')}\n\n---\n\n"]
        for msg in info['messages']:
            role = msg.get('type', '未知')
            content = msg.get('message', {})
            if isinstance(content, dict):
                text = ""
                for c in content.get('content', []):
                    if isinstance(c, dict) and c.get('type') == 'text':
                        text += c.get('text', '')
            else:
                text = str(content)
            lines.append(f"## {role.upper()}\n\n{text}\n\n---\n\n")
        return ''.join(lines)



# ========== Codex 历史记录管理器 ==========
# 尝试导入 Cython 加速模块
try:
    from core.fast_scan import scan_codex_sessions, get_cwd_fast, load_project_fast
    _USE_CYTHON = True
except ImportError:
    _USE_CYTHON = False
    load_project_fast = None

class CodexHistoryManager:
    def __init__(self, codex_dir: Path):
        self.codex_dir = codex_dir
        self.trash_manager = TrashManager(codex_dir)
        self._cwd_cache = {}  # cwd -> mtime 缓存

    def _get_cwd(self, f: Path) -> str:
        if _USE_CYTHON:
            return get_cwd_fast(str(f))
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                for line in fp:
                    if '"cwd"' in line:
                        data = json.loads(line)
                        return data.get('payload', {}).get('cwd', '') or data.get('cwd', '')
        except (OSError, json.JSONDecodeError):
            pass
        return ''

    def list_projects(self, with_cwd: bool = False, limit: int = 0, on_update=None) -> list:
        """列出工作目录分组，使用 Cython 加速"""
        sessions_dir = str(self.codex_dir / "sessions")
        if _USE_CYTHON:
            self._cwd_cache = scan_codex_sessions(sessions_dir, limit)
        else:
            # 纯 Python 回退
            self._cwd_cache = self._scan_sessions_py(sessions_dir, limit)
        sorted_cwds = sorted(self._cwd_cache.keys(), key=lambda x: self._cwd_cache[x], reverse=True)
        if limit > 0:
            sorted_cwds = sorted_cwds[:limit]
        if not with_cwd:
            return sorted_cwds
        return [(cwd, cwd) for cwd in sorted_cwds]

    def _scan_sessions_py(self, sessions_dir: str, limit: int) -> dict:
        """纯 Python 回退扫描"""
        import os
        cwd_map = {}
        if not os.path.isdir(sessions_dir):
            return cwd_map
        count = 0
        for year in sorted(os.listdir(sessions_dir), reverse=True):
            yp = os.path.join(sessions_dir, year)
            if not os.path.isdir(yp): continue
            for month in sorted(os.listdir(yp), reverse=True):
                mp = os.path.join(yp, month)
                if not os.path.isdir(mp): continue
                for day in sorted(os.listdir(mp), reverse=True):
                    dp = os.path.join(mp, day)
                    if not os.path.isdir(dp): continue
                    for f in os.listdir(dp):
                        if not f.endswith('.jsonl'): continue
                        fp = os.path.join(dp, f)
                        cwd = self._get_cwd(Path(fp)) or "未知目录"
                        mtime = os.path.getmtime(fp)
                        if cwd not in cwd_map:
                            cwd_map[cwd] = mtime
                            count += 1
                            if limit > 0 and count >= limit:
                                return cwd_map
                        elif mtime > cwd_map[cwd]:
                            cwd_map[cwd] = mtime
        return cwd_map

    def load_project(self, cwd_path: str) -> dict:
        """加载指定工作目录的会话"""
        sessions_dir = self.codex_dir / "sessions"
        if not sessions_dir.exists():
            return {}
        # 使用 Cython 加速
        if _USE_CYTHON and load_project_fast:
            raw = load_project_fast(str(sessions_dir), cwd_path)
            result = {}
            for sid, info in raw.items():
                result[sid] = {'file': Path(info['file']), 'last_timestamp': info['last_timestamp']}
            return result
        # 纯 Python 回退
        result = {}
        for session_file in sessions_dir.rglob("*.jsonl"):
            cwd = self._get_cwd(session_file)
            if cwd != cwd_path and (not cwd and cwd_path != "未知目录"):
                continue
            session_id = session_file.stem.replace("rollout-", "")
            info = self._parse_session(session_file)
            if info:
                result[session_id] = info
        return result

    def load_sessions(self, callback=None) -> dict:
        sessions_dir = self.codex_dir / "sessions"
        result = {}
        if not sessions_dir.exists():
            return result
        for session_file in sessions_dir.rglob("*.jsonl"):
            if callback:
                callback(f"扫描: {session_file.name[:30]}...")
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
                        if data.get('type') == 'session_meta':
                            cwd = data.get('payload', {}).get('cwd')
                        if data.get('type') == 'response_item':
                            payload = data.get('payload', {})
                            if payload.get('type') == 'message':
                                messages.append(payload)
                        elif data.get('type') == 'event_msg':
                            payload = data.get('payload', {})
                            if payload.get('type') in ('user_message', 'agent_message'):
                                messages.append({'role': 'user' if 'user' in payload.get('type') else 'assistant',
                                                'content': payload.get('message', '')})
                    except json.JSONDecodeError:
                        continue  # 跳过损坏的行
            if not messages:
                return None
            return {
                'file': session_file, 'messages': messages, 'message_count': len(messages),
                'first_timestamp': first_ts, 'last_timestamp': last_ts, 'cwd': cwd,
                'size': session_file.stat().st_size
            }
        except (OSError, json.JSONDecodeError):
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


# ========== 全局实例 ==========
mcp_registry = MCPRegistry(MCP_DB_FILE)
history_manager = HistoryManager(CLAUDE_DIR) if CLAUDE_DIR.exists() else None
codex_history_manager = CodexHistoryManager(CODEX_DIR) if CODEX_DIR.exists() else None
history_cache = {"claude": None, "codex": None}
