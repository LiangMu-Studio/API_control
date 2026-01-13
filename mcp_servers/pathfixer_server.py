#!/usr/bin/env python3
"""PathFixer MCP Server - 自动修正路径的文件操作工具 + 代理搜索/抓取"""
import sys
import os
import json
import re
from pathlib import Path
from html.parser import HTMLParser
from html import unescape
from typing import List, Optional
from urllib.parse import urljoin
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stdin.reconfigure(encoding='utf-8', errors='replace')

# 当前工作目录，由 Claude Code 传入
WORKING_DIR = os.environ.get('CLAUDE_WORKING_DIR', os.getcwd())

# 代理配置（可通过环境变量覆盖）
PROXY_HOST = os.environ.get('PATHFIXER_PROXY', '127.0.0.1:38080')

# ============== HTML to Markdown 转换器 ==============

DEFAULT_ALLOWED_INLINE = {"a", "strong", "b", "em", "i", "code", "span", "img", "sup", "sub", "del"}
DEFAULT_ALLOWED_BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "pre", "code", "table", "thead", "tbody", "tr", "th", "td", "hr"}

def is_allowed(tag, allow_inline=DEFAULT_ALLOWED_INLINE, allow_block=DEFAULT_ALLOWED_BLOCK):
    return tag.lower() in allow_inline or tag.lower() in allow_block

class HTMLToMarkdownParser(HTMLParser):
    def __init__(self, base_url=None, drop_unknown_tags=False):
        super().__init__()
        self.text: List[str] = []
        self.list_stack: List[str] = []
        self.link_stack: List[str] = []
        self.in_code = False
        self.in_pre = False
        self.in_li = False
        self.after_checkbox = False
        self.in_table = False
        self.current_row = None
        self.current_row_is_header = False
        self.current_cell = None
        self.current_cell_align = None
        self.table_rows = []
        self.base_url = base_url
        self.drop_unknown_tags = drop_unknown_tags

    def handle_starttag(self, tag, attrs):
        if self.drop_unknown_tags and not is_allowed(tag):
            return
        attrs_dict = dict(attrs)
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.text.append('\n' + '#' * int(tag[1]) + ' ')
        elif tag == 'br':
            self.text.append('\n')
        elif tag in ['strong', 'b']:
            self.text.append('**')
        elif tag in ['em', 'i']:
            self.text.append('*')
        elif tag == 'code':
            self.text.append('`')
            self.in_code = True
        elif tag == 'pre':
            self.in_pre = True
            self.text.append('\n```\n')
        elif tag in ['ul', 'ol']:
            self.list_stack.append(tag)
        elif tag == 'li':
            indent = '  ' * (len(self.list_stack) - 1)
            marker = '1. ' if self.list_stack and self.list_stack[-1] == 'ol' else '- '
            self.text.append(f'\n{indent}{marker}')
            self.in_li = True
        elif tag == 'a':
            self.text.append('[')
            href = attrs_dict.get('href', '')
            if self.base_url and href and not href.startswith(('http', 'data:', '#')):
                href = urljoin(self.base_url, href)
            self.link_stack.append(href)
        elif tag == 'blockquote':
            self.text.append('\n> ')
        elif tag == 'img':
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', '')
            if self.base_url and src and not src.startswith(('http', 'data:')):
                src = urljoin(self.base_url, src)
            self.text.append(f'![{alt}]({src})')
        elif tag == 'table':
            self.in_table = True
            self.table_rows = []
        elif tag == 'tr':
            if self.in_table:
                self.current_row = []
                self.current_row_is_header = False
        elif tag in ['th', 'td']:
            if self.in_table:
                self.current_cell = []
                self.current_cell_align = attrs_dict.get('align')
                if tag == 'th':
                    self.current_row_is_header = True

    def handle_endtag(self, tag):
        if self.drop_unknown_tags and not is_allowed(tag):
            return
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']:
            self.text.append('\n')
        elif tag in ['strong', 'b']:
            self.text.append('**')
        elif tag in ['em', 'i']:
            self.text.append('*')
        elif tag == 'code':
            self.text.append('`')
            self.in_code = False
        elif tag == 'pre':
            self.text.append('\n```\n')
            self.in_pre = False
        elif tag == 'a':
            href = self.link_stack.pop() if self.link_stack else ''
            self.text.append(f']({href})' if href else ']')
        elif tag in ['ul', 'ol']:
            if self.list_stack:
                self.list_stack.pop()
            self.text.append('\n')
        elif tag == 'li':
            self.in_li = False
        elif tag in ['th', 'td']:
            if self.in_table and self.current_cell is not None:
                self.current_row.append((''.join(self.current_cell).strip(), self.current_cell_align))
                self.current_cell = None
        elif tag == 'tr':
            if self.in_table and self.current_row is not None:
                self.table_rows.append({"header": self.current_row_is_header, "cells": self.current_row})
                self.current_row = None
        elif tag == 'table':
            if self.in_table:
                self._flush_table()
                self.in_table = False

    def handle_data(self, data):
        if self.in_table and self.current_cell is not None:
            self.current_cell.append(data)
            return
        if data.strip() or self.in_code or self.in_pre:
            self.text.append(data)

    def get_markdown(self):
        md = ''.join(self.text)
        md = re.sub(r'\n{3,}', '\n\n', md)
        md = re.sub(r'\[\]\(url\)', '', md)
        md = re.sub(r'(?<!!)\\[\\]', '', md)
        return md.strip()

    def _flush_table(self):
        if not self.table_rows:
            return
        header_cells = []
        body_rows = []
        for idx, row in enumerate(self.table_rows):
            if not header_cells and (row.get("header") or idx == 0):
                header_cells = row["cells"]
                continue
            body_rows.append(row["cells"])
        if not header_cells:
            return
        col_count = max(len(header_cells), *(len(r) for r in body_rows) if body_rows else [0])
        def pad(cells):
            return list(cells) + [('', None)] * (col_count - len(cells))
        header_cells = pad(header_cells)
        body_rows = [pad(r) for r in body_rows]
        lines = ['| ' + ' | '.join(c.strip() for c, _ in header_cells) + ' |']
        lines.append('| ' + ' | '.join(':---:' if a == 'center' else '---:' if a == 'right' else '---' for _, a in header_cells) + ' |')
        for row in body_rows:
            lines.append('| ' + ' | '.join(c.strip() for c, _ in row) + ' |')
        self.text.append('\n' + '\n'.join(lines) + '\n')

def html_to_markdown(html_content, base_url=None):
    """Convert HTML to Markdown"""
    html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html_content, flags=re.IGNORECASE)
    html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<div[^>]*>', '', html)
    html = re.sub(r'(</div>)+', '\n', html)
    html = re.sub(r'\s*style="[^"]*"', '', html)
    html = re.sub(r'<span[^>]*>', '', html)
    html = re.sub(r'</span>', '', html)
    html = unescape(html)
    parser = HTMLToMarkdownParser(base_url=base_url)
    try:
        parser.feed(html)
        return parser.get_markdown()
    except Exception:
        return html_content

def _simple_extract(html):
    """简单提取正文"""
    html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<!--[\s\S]*?-->', '', html)
    for tag in ['nav', 'header', 'footer', 'aside', 'iframe', 'noscript']:
        html = re.sub(rf'<{tag}[^>]*>[\s\S]*?</{tag}>', '', html, flags=re.IGNORECASE)
    noise_kw = r'nav|menu|sidebar|footer|header|comment|recommend|related|ad|share|social|logo|copyright|qrcode'
    html = re.sub(rf'<div[^>]*(?:class|id)="[^"]*(?:{noise_kw})[^"]*"[^>]*>[\s\S]*?</div>', '', html, flags=re.IGNORECASE)
    for pattern in [r'<article[^>]*>([\s\S]*?)</article>', r'<main[^>]*>([\s\S]*?)</main>']:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(0)
    return html

# ============== 代理功能 ==============

def proxy_fetch(url, prompt=""):
    """通过代理访问网页，自动提取正文并转为 Markdown"""
    try:
        proxy = urllib.request.ProxyHandler({'http': f'http://{PROXY_HOST}', 'https': f'http://{PROXY_HOST}'})
        opener = urllib.request.build_opener(proxy)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with opener.open(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        html = _simple_extract(html)
        content = html_to_markdown(html, base_url=url)
        if len(content) > 15000:
            content = content[:15000] + "\n...(truncated)"
        return content
    except Exception as e:
        return {"error": f"请求失败: {e}", "url": url}

def _extract_real_url(ddg_url):
    if 'uddg=' in ddg_url:
        match = re.search(r'uddg=([^&]+)', ddg_url)
        if match:
            return urllib.parse.unquote(match.group(1))
    return ddg_url

def _search_duckduckgo(query, opener):
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with opener.open(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        for match in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>', html):
            results.append((match.group(2), _extract_real_url(match.group(1))))
            if len(results) >= 10:
                break
    except Exception:
        pass
    return results

def _search_bing(query, opener):
    results = []
    try:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=20"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'zh-CN,zh;q=0.9'})
        with opener.open(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        for match in re.finditer(r'<li class="b_algo"[^>]*>.*?<h2><a[^>]*href="(https?://[^"]+)"[^>]*>([^<]+)', html, re.DOTALL):
            if 'bing.com' not in match.group(1) and 'microsoft.com' not in match.group(1):
                results.append((match.group(2).strip(), match.group(1)))
                if len(results) >= 10:
                    break
    except Exception:
        pass
    return results

def proxy_search(query):
    """通过代理搜索（DuckDuckGo + Bing）"""
    try:
        proxy = urllib.request.ProxyHandler({'http': f'http://{PROXY_HOST}', 'https': f'http://{PROXY_HOST}'})
        opener = urllib.request.build_opener(proxy)
        ddg_results = _search_duckduckgo(query, opener)
        bing_results = _search_bing(query, opener)
        lines = [f"## 搜索: {query}", ""]
        if ddg_results:
            lines.append("### DuckDuckGo")
            for i, (title, url) in enumerate(ddg_results, 1):
                lines.extend([f"{i}. {title}", f"   {url}", ""])
        if bing_results:
            lines.append("### Bing")
            for i, (title, url) in enumerate(bing_results, 1):
                lines.extend([f"{i}. {title}", f"   {url}", ""])
        if not ddg_results and not bing_results:
            return f'未找到关于 "{query}" 的结果'
        return "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"

# ============== 文件操作 ==============

def fix_path(file_path):
    """自动修正路径"""
    if not file_path:
        return file_path
    file_path = file_path.replace('\\', '/')
    match = re.match(r'^/([a-zA-Z])/(.*)', file_path)
    if match:
        file_path = f"{match.group(1).upper()}:/{match.group(2)}"
    match = re.match(r'^([a-zA-Z])/(.*)', file_path)
    if match and len(match.group(1)) == 1:
        file_path = f"{match.group(1).upper()}:/{match.group(2)}"
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(WORKING_DIR) / p
    return str(p.resolve())

def read_file(file_path, offset=0, limit=2000):
    file_path = fix_path(file_path)
    path = Path(file_path)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    if not path.is_file():
        return {"error": f"不是文件: {file_path}"}
    for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
        try:
            with open(path, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        return {"error": f"无法解码文件: {file_path}"}
    total = len(lines)
    lines = lines[offset:offset + limit] if limit else lines[offset:]
    numbered = [f"{offset + i + 1:6d}│{line.rstrip()}" for i, line in enumerate(lines)]
    return {"content": '\n'.join(numbered), "total_lines": total, "file_path": file_path}

def write_file(file_path, content):
    file_path = fix_path(file_path)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    try:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
        return {"success": True, "file_path": file_path}
    except PermissionError:
        return {"error": f"文件被占用: {file_path}"}

def edit_file(file_path, old_string, new_string, replace_all=False):
    file_path = fix_path(file_path)
    path = Path(file_path)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    for enc in ['utf-8', 'gbk', 'latin-1']:
        try:
            with open(path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    else:
        return {"error": "无法解码文件"}
    content = content.replace('\r\n', '\n')
    old_string = old_string.replace('\r\n', '\n')
    new_string = new_string.replace('\r\n', '\n')
    if old_string not in content:
        return {"error": f"未找到匹配内容，file_path: {file_path}"}
    count = content.count(old_string)
    if count > 1 and not replace_all:
        return {"error": f"找到 {count} 处匹配，请设置 replace_all=true 或提供更精确的内容"}
    new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    return {"success": True, "file_path": file_path, "replacements": count if replace_all else 1}

# ============== MCP 协议 ==============

TOOLS = [
    {"name": "pathfixer_read", "description": "读取文件(自动修正相对路径)",
     "inputSchema": {"type": "object", "properties": {
         "file_path": {"type": "string", "description": "文件路径(支持相对路径)"},
         "offset": {"type": "integer", "description": "起始行号(0开始)"},
         "limit": {"type": "integer", "description": "读取行数"}
     }, "required": ["file_path"]}},
    {"name": "pathfixer_write", "description": "写入文件(自动修正相对路径,自动创建目录)",
     "inputSchema": {"type": "object", "properties": {
         "file_path": {"type": "string", "description": "文件路径(支持相对路径)"},
         "content": {"type": "string", "description": "文件内容"}
     }, "required": ["file_path", "content"]}},
    {"name": "pathfixer_edit", "description": "编辑文件(查找替换,自动修正相对路径)",
     "inputSchema": {"type": "object", "properties": {
         "file_path": {"type": "string", "description": "文件路径(支持相对路径)"},
         "old_string": {"type": "string", "description": "要替换的内容"},
         "new_string": {"type": "string", "description": "替换后的内容"},
         "replace_all": {"type": "boolean", "description": "是否替换所有匹配"}
     }, "required": ["file_path", "old_string", "new_string"]}},
    {"name": "proxy_search", "description": "通过代理搜索网页(用于需要翻墙的搜索)",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "搜索关键词"}
     }, "required": ["query"]}},
    {"name": "proxy_fetch", "description": "通过代理访问网页(用于需要翻墙的网站)",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string", "description": "网页URL"},
         "prompt": {"type": "string", "description": "提示词(可选)"}
     }, "required": ["url"]}}
]

FUNCS = {
    "pathfixer_read": read_file,
    "pathfixer_write": write_file,
    "pathfixer_edit": edit_file,
    "proxy_search": proxy_search,
    "proxy_fetch": proxy_fetch
}

def respond(req_id, result=None, error=None):
    if error:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": str(error)}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}

def handle(req):
    method, params, req_id = req.get("method"), req.get("params", {}), req.get("id")
    if method == "initialize":
        return respond(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "pathfixer", "version": "1.0"}
        })
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return respond(req_id, {"tools": TOOLS})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments", {})
        if name in FUNCS:
            try:
                result = FUNCS[name](**args)
                text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                return respond(req_id, {"content": [{"type": "text", "text": text}]})
            except Exception as e:
                return respond(req_id, error=str(e))
        return respond(req_id, error=f"Unknown tool: {name}")
    return respond(req_id, {})

if __name__ == "__main__":
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            result = handle(json.loads(line))
            if result:
                print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"jsonrpc": "2.0", "error": {"code": -1, "message": str(e)}}, ensure_ascii=False), flush=True)
