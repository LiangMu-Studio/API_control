"""
统一服务入口 - 兼容旧代码，使用新架构
"""

from typing import Optional, Generator
from services.api_services.service_factory import ServiceFactory
from services.api_services.base_service import BaseAPIService


class ClaudeService:
    """
    兼容层 - 保持与旧代码的兼容性
    实际使用新的 ServiceFactory 创建对应的服务
    """

    def __init__(self, api_key: str, base_url: str = None, model: str = 'claude-sonnet-4-5-20250929',
                 provider_type: str = None, enable_compression: bool = True):
        """初始化服务"""
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.provider_type = provider_type
        self.enable_compression = enable_compression

        # 使用工厂创建实际的服务
        self._service: BaseAPIService = ServiceFactory.create_service(
            api_key=api_key,
            base_url=base_url,
            model=model,
            provider_type=provider_type
        )

    def chat(self, user_message: str, system_prompt: Optional[str] = None,
            temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None,
            thinking_mode: str = None) -> str:
        """非流式聊天"""
        return self._service.chat(
            user_message=user_message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            attachments=attachments,
            thinking_mode=thinking_mode
        )

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None,
                   thinking_mode: str = None) -> Generator[str, None, None]:
        """流式聊天"""
        yield from self._service.chat_stream(
            user_message=user_message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            attachments=attachments,
            thinking_mode=thinking_mode
        )
