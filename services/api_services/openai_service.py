"""OpenAI API 服务"""

import requests
import json
from typing import Optional, Generator
from .base_service import BaseAPIService


class OpenAIService(BaseAPIService):
    """OpenAI API 服务"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = 'gpt-4'):
        super().__init__(api_key, base_url, model)
        self.endpoint = (base_url.rstrip('/') + "/v1/chat/completions") if base_url else "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000,
                   attachments: Optional[list] = None, **kwargs) -> Generator[str, None, None]:
        """流式聊天 - OpenAI API"""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        content = user_message
        if attachments:
            for attachment in attachments:
                if attachment['type'] == 'image':
                    content += f"\n[图片: {attachment.get('name', 'image')}]"

        messages.append({"role": "user", "content": content})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            response = requests.post(self.endpoint, json=payload, headers=self.headers, timeout=(10, 120), stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or not line.startswith(b'data: '):
                    continue
                try:
                    data = json.loads(line[6:])
                    if data.get('choices') and len(data['choices']) > 0:
                        delta = data['choices'][0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                except json.JSONDecodeError:
                    continue
        except requests.exceptions.RequestException as e:
            yield f"\n\n[错误] {str(e)}\n"
