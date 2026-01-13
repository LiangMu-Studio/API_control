"""会话导出模块 - 支持 HTML/Markdown 导出"""

from pathlib import Path
from datetime import datetime


def export_session_html(session_data: dict, output_path: str) -> bool:
    """导出单个会话为 HTML"""
    info = session_data.get('info', {})
    sid = session_data.get('session_id', 'unknown')
    messages = info.get('messages', [])

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Session {sid[:12]}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.header {{ background: #333; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
.msg {{ padding: 12px; margin: 8px 0; border-radius: 8px; }}
.user {{ background: #e3f2fd; border-left: 4px solid #2196f3; }}
.assistant {{ background: #f5f5f5; border-left: 4px solid #4caf50; }}
.role {{ font-weight: bold; font-size: 12px; color: #666; margin-bottom: 5px; }}
.content {{ white-space: pre-wrap; line-height: 1.6; }}
</style></head><body>
<div class="header">
<h2>Session: {sid[:20]}</h2>
<p>Path: {info.get('cwd', 'N/A')}</p>
<p>Messages: {info.get('message_count', len(messages))} | Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>
"""
    for msg in messages:
        role = msg.get('message', {}).get('role', msg.get('role', 'unknown'))
        content = msg.get('message', {}).get('content', msg.get('content', ''))
        if isinstance(content, list):
            content = ''.join(x.get('text', '') for x in content if isinstance(x, dict))
        content = str(content).replace('<', '&lt;').replace('>', '&gt;')
        css_class = 'user' if role == 'user' else 'assistant'
        html += f'<div class="msg {css_class}"><div class="role">{role.upper()}</div><div class="content">{content}</div></div>\n'

    html += "</body></html>"
    Path(output_path).write_text(html, encoding='utf-8')
    return True


def export_session_md(session_data: dict, output_path: str) -> bool:
    """导出单个会话为 Markdown"""
    info = session_data.get('info', {})
    sid = session_data.get('session_id', 'unknown')
    messages = info.get('messages', [])

    md = f"# Session: {sid[:20]}\n\n"
    md += f"- Path: {info.get('cwd', 'N/A')}\n"
    md += f"- Messages: {info.get('message_count', len(messages))}\n"
    md += f"- Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"

    for msg in messages:
        role = msg.get('message', {}).get('role', msg.get('role', 'unknown'))
        content = msg.get('message', {}).get('content', msg.get('content', ''))
        if isinstance(content, list):
            content = ''.join(x.get('text', '') for x in content if isinstance(x, dict))
        md += f"## {role.upper()}\n\n{content}\n\n---\n\n"

    Path(output_path).write_text(md, encoding='utf-8')
    return True


def export_sessions_batch(sessions: list, output_dir: str, fmt: str = 'html') -> int:
    """批量导出会话"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for s in sessions:
        sid = s.get('session_id', 'unknown')[:12]
        filename = f"session_{sid}.{fmt}"
        path = out / filename
        try:
            if fmt == 'html':
                export_session_html(s, str(path))
            else:
                export_session_md(s, str(path))
            count += 1
        except Exception:
            pass
    return count
