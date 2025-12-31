"""
基础服务类 - 所有 API 服务的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Generator


class BaseAPIService(ABC):
    """所有 API 服务的基类"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = 'default'):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000,
                   attachments: Optional[list] = None) -> Generator[str, None, None]:
        """流式聊天接口 - 所有子类必须实现"""
        pass

    def chat(self, user_message: str, system_prompt: Optional[str] = None,
            temperature: float = 0.7, max_tokens: int = 4000,
            attachments: Optional[list] = None) -> str:
        """非流式聊天 - 基于 chat_stream 实现"""
        response_text = ""
        for chunk in self.chat_stream(user_message, system_prompt, temperature, max_tokens, attachments):
            response_text += chunk
        return response_text

    @staticmethod
    def _is_retryable_error(error_msg: str) -> bool:
        """检查是否是可重试的错误"""
        retryable_keywords = ['timeout', 'connection', 'network', '503', '502', '429', 'temporarily']
        return any(keyword.lower() in error_msg.lower() for keyword in retryable_keywords)
