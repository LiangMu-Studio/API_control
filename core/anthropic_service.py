"""Anthropic 官方 API 服务"""

from typing import Optional, Generator
from anthropic import Anthropic
from .base_service import BaseAPIService


class AnthropicService(BaseAPIService):
    """Anthropic 官方 API 服务 - 使用 SDK"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = 'claude-sonnet-4-5-20250929'):
        super().__init__(api_key, base_url, model)
        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url
        self.client = Anthropic(**client_kwargs)

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000,
                   attachments: Optional[list] = None, **kwargs) -> Generator[str, None, None]:
        """流式聊天 - Anthropic 官方 API"""

        messages = []
        if attachments:
            for attachment in attachments:
                if attachment['type'] == 'image':
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": attachment['media_type'],
                                    "data": attachment['data']
                                }
                            }
                        ]
                    })

        messages.append({"role": "user", "content": user_message})

        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=temperature,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            yield f"\n\n[错误] {str(e)}\n"
