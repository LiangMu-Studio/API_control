"""对话管理模块 - 重构版本"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class Message:
    """消息类"""

    def __init__(self, content: str, is_user: bool, timestamp: Optional[str] = None):
        self.content = content
        self.is_user = is_user
        self.timestamp = timestamp or datetime.now().strftime("%H:%M:%S")

    def to_dict(self) -> dict:
        return {
            'content': self.content,
            'is_user': self.is_user,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        return cls(data['content'], data['is_user'], data.get('timestamp'))


class Conversation:
    """对话类"""

    def __init__(self, conv_id: str, title: str = "新对话", config_id: str = "", prompt_id: str = "default"):
        self.id = conv_id
        self.title = title
        self.messages: List[Message] = []
        self.created_at = datetime.now().isoformat()
        self.config_id = config_id
        self.prompt_id = prompt_id

    def add_message(self, content: str, is_user: bool) -> Message:
        msg = Message(content, is_user)
        self.messages.append(msg)
        return msg

    def delete_message(self, index: int) -> bool:
        """删除指定索引的消息"""
        if 0 <= index < len(self.messages):
            self.messages.pop(index)
            return True
        return False

    def delete_messages_after(self, index: int) -> None:
        """删除指定索引之后的所有消息"""
        if 0 <= index < len(self.messages):
            self.messages = self.messages[:index + 1]

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'messages': [msg.to_dict() for msg in self.messages],
            'created_at': self.created_at,
            'config_id': self.config_id,
            'prompt_id': self.prompt_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Conversation':
        conv = cls(data['id'], data.get('title', '新对话'), data.get('config_id', ''), data.get('prompt_id', 'default'))
        conv.created_at = data.get('created_at', datetime.now().isoformat())
        for msg_data in data.get('messages', []):
            msg = Message.from_dict(msg_data)
            conv.messages.append(msg)
        return conv


class ConversationManager:
    """对话管理器"""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path.home() / ".ai_talk")
        self.conv_dir = self.data_dir / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.conversations: Dict[str, Conversation] = {}
        self._load_all()

    def _load_all(self) -> None:
        """加载所有对话"""
        for file in self.conv_dir.glob("*.json"):
            if file.name == "order.json":
                continue
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    conv = Conversation.from_dict(data)
                    self.conversations[conv.id] = conv
            except Exception as e:
                print(f"加载对话失败 {file}: {e}")

    def create(self, conv_id: str, title: str = "新对话", config_id: str = "") -> Conversation:
        conv = Conversation(conv_id, title, config_id)
        self.conversations[conv_id] = conv
        return conv

    def get(self, conv_id: str) -> Optional[Conversation]:
        return self.conversations.get(conv_id)

    def save(self, conv_id: str) -> None:
        conv = self.conversations.get(conv_id)
        if not conv:
            return
        try:
            file = self.conv_dir / f"{conv_id}.json"
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(conv.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存对话失败: {e}")

    def list_all(self) -> List[Conversation]:
        return list(self.conversations.values())

    def delete(self, conv_id: str) -> None:
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            file = self.conv_dir / f"{conv_id}.json"
            if file.exists():
                file.unlink()

        # 删除对应的截图文件夹
        import shutil
        app_dir = self.conv_dir.parent.parent
        screenshot_dir = app_dir / "screenshots" / conv_id
        if screenshot_dir.exists():
            shutil.rmtree(screenshot_dir)
