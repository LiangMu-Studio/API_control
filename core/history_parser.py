# AI CLI Manager - 历史记录解析器
# 支持 Claude Code 完整的 JSONL 消息格式
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ContentBlock:
    """内容块基类"""
    type: str
    raw: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        """提取文本内容"""
        if self.type == 'text':
            return self.raw.get('text', '')
        elif self.type == 'tool_use':
            name = self.raw.get('name', '')
            inp = self.raw.get('input', {})
            if name == 'Read':
                return f"[读取文件: {inp.get('file_path', '')}]"
            elif name == 'Write':
                return f"[写入文件: {inp.get('file_path', '')}]"
            elif name == 'Edit':
                return f"[编辑文件: {inp.get('file_path', '')}]"
            elif name == 'Bash':
                cmd = inp.get('command', '')[:50]
                return f"[执行命令: {cmd}...]"
            elif name == 'Glob':
                return f"[搜索文件: {inp.get('pattern', '')}]"
            elif name == 'Grep':
                return f"[搜索内容: {inp.get('pattern', '')}]"
            elif name == 'Task':
                return f"[启动任务: {inp.get('description', '')}]"
            elif name == 'TodoWrite':
                return f"[更新待办]"
            else:
                return f"[工具调用: {name}]"
        elif self.type == 'tool_result':
            content = self.raw.get('content', '')
            is_error = self.raw.get('is_error', False)
            if is_error:
                return f"[错误: {str(content)[:100]}]"
            if isinstance(content, str):
                if '[Old tool result content cleared]' in content:
                    return '[结果已清理]'
                return content[:200] + '...' if len(content) > 200 else content
            return '[工具结果]'
        elif self.type == 'thinking':
            return f"[思考中...]"
        elif self.type == 'redacted_thinking':
            return '[思考内容已隐藏]'
        elif self.type == 'image':
            return '[图片]'
        return f'[{self.type}]'

    @property
    def full_text(self) -> str:
        """获取完整文本（不截断）"""
        if self.type == 'text':
            return self.raw.get('text', '')
        elif self.type == 'tool_result':
            content = self.raw.get('content', '')
            return str(content) if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        return self.text


@dataclass
class Message:
    """消息对象"""
    uuid: str
    timestamp: str
    msg_type: str  # user, assistant, summary, attachment 等
    role: str  # user, assistant
    content_blocks: list[ContentBlock] = field(default_factory=list)
    parent_uuid: Optional[str] = None
    session_id: str = ''
    cwd: str = ''
    version: str = ''
    git_branch: str = ''
    is_sidechain: bool = False
    agent_id: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        """获取消息的纯文本内容"""
        parts = []
        for block in self.content_blocks:
            t = block.text
            if t:
                parts.append(t)
        return '\n'.join(parts)

    @property
    def text_only(self) -> str:
        """只获取 text 类型的内容"""
        return '\n'.join(b.raw.get('text', '') for b in self.content_blocks if b.type == 'text')

    @property
    def tool_calls(self) -> list[ContentBlock]:
        """获取所有工具调用"""
        return [b for b in self.content_blocks if b.type == 'tool_use']

    @property
    def tool_results(self) -> list[ContentBlock]:
        """获取所有工具结果"""
        return [b for b in self.content_blocks if b.type == 'tool_result']

    @property
    def datetime(self) -> Optional[datetime]:
        """解析时间戳"""
        try:
            return datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except:
            return None

    @property
    def time_str(self) -> str:
        """格式化时间"""
        dt = self.datetime
        return dt.strftime('%m-%d %H:%M') if dt else self.timestamp[:16]


@dataclass
class Session:
    """会话对象"""
    session_id: str
    file_path: Path
    messages: list[Message] = field(default_factory=list)
    cwd: str = ''
    git_branch: str = ''
    version: str = ''
    summary: str = ''
    custom_title: str = ''
    mcp_calls: list[str] = field(default_factory=list)    # MCP 调用列表
    skill_calls: list[str] = field(default_factory=list)  # Skill 调用列表

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_messages(self) -> list[Message]:
        return [m for m in self.messages if m.role == 'user' and m.msg_type == 'user']

    @property
    def assistant_messages(self) -> list[Message]:
        return [m for m in self.messages if m.role == 'assistant' and m.msg_type == 'assistant']

    @property
    def first_timestamp(self) -> str:
        return self.messages[0].timestamp if self.messages else ''

    @property
    def last_timestamp(self) -> str:
        return self.messages[-1].timestamp if self.messages else ''

    @property
    def first_prompt(self) -> str:
        """获取首个用户提示"""
        for m in self.messages:
            if m.role == 'user' and m.msg_type == 'user':
                return m.text_only[:100]
        return ''

    @property
    def last_exchange(self) -> tuple[str, str]:
        """获取最后一轮对话"""
        user_msg, ai_msg = '', ''
        for m in reversed(self.messages):
            if m.msg_type == 'user' and not user_msg:
                user_msg = m.text_only[:50]
            elif m.msg_type == 'assistant' and not ai_msg:
                ai_msg = m.text_only[:50]
            if user_msg and ai_msg:
                break
        return user_msg, ai_msg

    @property
    def tool_usage(self) -> dict[str, int]:
        """统计工具使用情况"""
        usage = {}
        for m in self.messages:
            for tc in m.tool_calls:
                name = tc.raw.get('name', 'unknown')
                usage[name] = usage.get(name, 0) + 1
        return usage

    @property
    def file_size(self) -> int:
        try:
            return self.file_path.stat().st_size
        except:
            return 0

    @property
    def duration_minutes(self) -> float:
        """会话持续时间（分钟）"""
        if len(self.messages) < 2:
            return 0
        first = self.messages[0].datetime
        last = self.messages[-1].datetime
        if first and last:
            return (last - first).total_seconds() / 60
        return 0


class HistoryParser:
    """历史记录解析器"""

    def __init__(self, claude_dir: Path = None):
        self.claude_dir = claude_dir or Path.home() / '.claude'
        self.projects_dir = self.claude_dir / 'projects'

    def parse_content_block(self, block: Any) -> ContentBlock:
        """解析内容块"""
        if isinstance(block, str):
            return ContentBlock(type='text', raw={'text': block})
        if isinstance(block, dict):
            return ContentBlock(type=block.get('type', 'unknown'), raw=block)
        return ContentBlock(type='unknown', raw={})

    def parse_message(self, data: dict) -> Optional[Message]:
        """解析单条消息"""
        msg_type = data.get('type', '')

        # 跳过非消息类型
        if msg_type not in ('user', 'assistant'):
            return None

        # 解析 message 字段
        message_data = data.get('message', {})
        role = message_data.get('role', msg_type)
        content = message_data.get('content', [])

        # 解析内容块
        if isinstance(content, str):
            blocks = [ContentBlock(type='text', raw={'text': content})]
        elif isinstance(content, list):
            blocks = [self.parse_content_block(b) for b in content]
        else:
            blocks = []

        return Message(
            uuid=data.get('uuid', ''),
            timestamp=data.get('timestamp', ''),
            msg_type=msg_type,
            role=role,
            content_blocks=blocks,
            parent_uuid=data.get('parentUuid'),
            session_id=data.get('sessionId', ''),
            cwd=data.get('cwd', ''),
            version=data.get('version', ''),
            git_branch=data.get('gitBranch', ''),
            is_sidechain=data.get('isSidechain', False),
            agent_id=data.get('agentId'),
            raw=data
        )

    def parse_session_file(self, file_path: Path) -> Optional[Session]:
        """解析会话文件"""
        if not file_path.exists():
            return None

        messages = []
        summary = ''
        custom_title = ''
        cwd = ''
        git_branch = ''
        version = ''
        mcp_calls = []
        skill_calls = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        msg_type = data.get('type', '')

                        # 提取元数据
                        if not cwd:
                            cwd = data.get('cwd', '')
                        if not git_branch:
                            git_branch = data.get('gitBranch', '')
                        if not version:
                            version = data.get('version', '')

                        # 处理特殊消息类型
                        if msg_type == 'summary':
                            summary = data.get('summary', '')
                        elif msg_type == 'custom-title':
                            custom_title = data.get('customTitle', '')
                        elif msg_type in ('user', 'assistant'):
                            msg = self.parse_message(data)
                            if msg:
                                messages.append(msg)
                            # 提取 MCP 和 Skill 调用
                            if msg_type == 'assistant':
                                content = data.get('message', {}).get('content', [])
                                if isinstance(content, list):
                                    for block in content:
                                        if block.get('type') == 'tool_use':
                                            name = block.get('name', '')
                                            if name.startswith('mcp__'):
                                                mcp_calls.append(name)
                                            elif name == 'Skill':
                                                inp = block.get('input')
                                                if inp and isinstance(inp, dict):
                                                    skill_name = inp.get('skill', '')
                                                    if skill_name:
                                                        skill_calls.append(skill_name)
                    except json.JSONDecodeError:
                        continue
        except (OSError, IOError):
            return None

        if not messages:
            return None

        return Session(
            session_id=file_path.stem,
            file_path=file_path,
            messages=messages,
            cwd=cwd,
            git_branch=git_branch,
            version=version,
            summary=summary,
            custom_title=custom_title,
            mcp_calls=mcp_calls,
            skill_calls=skill_calls
        )

    def list_projects(self) -> list[str]:
        """列出所有项目"""
        if not self.projects_dir.exists():
            return []
        dirs = [d.name for d in self.projects_dir.iterdir() if d.is_dir()]
        # 按修改时间排序
        dirs.sort(key=lambda n: (self.projects_dir / n).stat().st_mtime, reverse=True)
        return dirs

    def load_project(self, project_name: str) -> list[Session]:
        """加载项目的所有会话"""
        project_dir = self.projects_dir / project_name
        if not project_dir.exists():
            return []

        sessions = []
        for f in project_dir.glob('*.jsonl'):
            session = self.parse_session_file(f)
            if session:
                sessions.append(session)

        # 按最后时间戳排序
        sessions.sort(key=lambda s: s.last_timestamp, reverse=True)
        return sessions

    def get_project_cwd(self, project_name: str) -> str:
        """快速获取项目的工作目录"""
        project_dir = self.projects_dir / project_name
        if not project_dir.exists():
            return ''

        for f in project_dir.glob('*.jsonl'):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    for line in fp:
                        if '"cwd"' in line:
                            data = json.loads(line)
                            cwd = data.get('cwd', '')
                            if cwd:
                                return cwd
            except:
                pass
        return ''

    def search_sessions(self, keyword: str, limit: int = 50) -> list[Session]:
        """搜索包含关键词的会话"""
        results = []
        keyword_lower = keyword.lower()

        for project_name in self.list_projects():
            if len(results) >= limit:
                break
            for session in self.load_project(project_name):
                if len(results) >= limit:
                    break
                # 搜索消息内容
                for msg in session.messages:
                    if keyword_lower in msg.text.lower():
                        results.append(session)
                        break

        return results


# 全局解析器实例
history_parser = HistoryParser()
