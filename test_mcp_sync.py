#!/usr/bin/env python
"""测试 MCP 仓库同步"""
import json
import sqlite3
import urllib.request
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path(__file__).parent / "mcp_data"
CONFIG_DIR.mkdir(exist_ok=True)
MCP_DB_FILE = CONFIG_DIR / "mcp_registry.db"

# npm registry - 深度分页获取更多 MCP
def generate_npm_urls():
    urls = []
    # 主要关键词 - 深度分页到 3000
    for kw in ['mcp-server', 'mcp']:
        for i in range(0, 3000, 250):
            urls.append(f'https://registry.npmjs.org/-/v1/search?text={kw}&size=250&from={i}')
    # 次要关键词 - 分页到 1000
    for kw in ['modelcontextprotocol', '@modelcontextprotocol', 'claude-mcp', 'mcp-tool',
               'mcp-client', 'mcp-plugin', 'mcp-connector', 'anthropic-mcp']:
        for i in range(0, 1000, 250):
            urls.append(f'https://registry.npmjs.org/-/v1/search?text={kw}&size=250&from={i}')
    return urls

NPM_SEARCH_URLS = generate_npm_urls()

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
    # 地图 - 地理位置服��
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

def init_db():
    with sqlite3.connect(MCP_DB_FILE) as conn:
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
        conn.execute('''CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)''')
        try:
            conn.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS servers_fts USING fts5(
                name, description, content='servers', content_rowid='rowid'
            )''')
        except:
            pass
        conn.commit()

def guess_category(name, desc):
    text = (name + ' ' + desc).lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in text:
            return cat
    return '其他'

def normalize_npm(obj):
    """从 npm 搜索结果中提取 MCP 服务器信息"""
    pkg = obj.get('package', {})
    name = pkg.get('name', '')
    desc = pkg.get('description', '') or ''

    # 严格过滤
    name_lower = name.lower()
    desc_lower = desc.lower()

    is_mcp = ('mcp' in name_lower or 'model context protocol' in desc_lower or
              'modelcontextprotocol' in name_lower)
    if not is_mcp:
        return None

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
        'category': guess_category(name, str(desc)),
        'source': 'npm',
    }

def fetch_all():
    init_db()
    errors, new_count = [], 0
    now = datetime.now().isoformat()

    for i, url in enumerate(NPM_SEARCH_URLS):
        print(f"获取 npm ({i+1}/{len(NPM_SEARCH_URLS)})...")
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode('utf-8'))
                items = raw.get('objects', [])
                batch_count = 0

                with sqlite3.connect(MCP_DB_FILE) as conn:
                    for item in items:
                        s = normalize_npm(item)
                        if not s:
                            continue
                        cur = conn.execute('SELECT 1 FROM servers WHERE id=?', (s['id'],))
                        if not cur.fetchone():
                            conn.execute('''INSERT INTO servers (id,name,description,package,command,args,category,source,updated_at)
                                VALUES (?,?,?,?,?,?,?,?,?)''',
                                (s['id'], s['name'], s['description'], s['package'], s['command'], s['args'], s['category'], s['source'], now))
                            new_count += 1
                            batch_count += 1
                    conn.commit()

                print(f"  获取 {len(items)} 个包, 新增 {batch_count} 个 MCP")
        except Exception as ex:
            errors.append(f"npm: {ex}")
            print(f"  错误 - {ex}")

    with sqlite3.connect(MCP_DB_FILE) as conn:
        conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('updated_at', now))
        conn.commit()

    return new_count, errors

def get_stats():
    with sqlite3.connect(MCP_DB_FILE) as conn:
        total = conn.execute('SELECT COUNT(*) FROM servers').fetchone()[0]
        updated = conn.execute('SELECT value FROM meta WHERE key="updated_at"').fetchone()
    return {'total': total, 'updated_at': updated[0] if updated else None}

def search(keyword='', category='全部', limit=10):
    with sqlite3.connect(MCP_DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        sql = 'SELECT * FROM servers'
        params = []
        conditions = []
        if keyword:
            conditions.append('(name LIKE ? OR description LIKE ?)')
            params.extend([f'%{keyword}%', f'%{keyword}%'])
        if category and category != '全部':
            conditions.append('category = ?')
            params.append(category)
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        sql += f' LIMIT {limit}'
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]

def get_categories():
    with sqlite3.connect(MCP_DB_FILE) as conn:
        rows = conn.execute('SELECT category, COUNT(*) FROM servers GROUP BY category ORDER BY COUNT(*) DESC').fetchall()
    return rows

if __name__ == '__main__':
    print('=' * 50)
    print('MCP 仓库同步测试')
    print('=' * 50)

    new_count, errors = fetch_all()

    print('=' * 50)
    stats = get_stats()
    print(f'同步完成!')
    print(f'  总数: {stats["total"]} 个')
    print(f'  新增: {new_count} 个')

    if errors:
        print(f'  错误: {len(errors)} 个')

    print()
    print('测试搜索 "file":')
    results = search('file', limit=5)
    for r in results:
        desc = (r.get('description') or '')[:40]
        print(f'  - {r["name"]}: {desc}...')

    print()
    print('分类统计:')
    for cat, count in get_categories():
        print(f'  {cat}: {count}')

    print()
    print(f'数据库文件: {MCP_DB_FILE}')
    print(f'文件大小: {MCP_DB_FILE.stat().st_size / 1024:.1f} KB')
