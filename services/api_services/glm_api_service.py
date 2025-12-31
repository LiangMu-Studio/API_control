"""GLM API 服务 (bigmodel.cn) - 支持 thinking_mode"""

import requests
import json
from typing import Optional, Generator
from .base_service import BaseAPIService
from core.claude_tools import ClaudeTools


class GLMAPIService(BaseAPIService):
    """GLM API 服务 - bigmodel.cn (支持 thinking_mode)"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = 'glm-4-plus'):
        super().__init__(api_key, base_url, model)
        self.tools = ClaudeTools()
        self.base_url = base_url or "https://open.bigmodel.cn/api/anthropic"
        self.endpoint = self.base_url.rstrip('/') + "/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01"
        }

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000,
                   attachments: Optional[list] = None, thinking_mode: Optional[str] = None, **kwargs) -> Generator[str, None, None]:
        """流式聊天 - GLM API (支持 thinking_mode)"""

        messages = []
        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
            messages.append({"role": "assistant", "content": "OK, I understand."})

        content = user_message
        if attachments:
            for attachment in attachments:
                if attachment['type'] == 'image':
                    content += f"\n[图片: {attachment.get('name', 'image')}]"
                elif attachment['type'] == 'document':
                    content += f"\n[文件: {attachment['name']}]\n{attachment['data']}"

        messages.append({"role": "user", "content": content})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }

        # GLM 支持 thinking_mode 参数
        if thinking_mode:
            payload["thinking_mode"] = thinking_mode

        try:
            response = requests.post(self.endpoint, json=payload, headers=self.headers, timeout=(10, 120), stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or line.startswith(b'event: '):
                    continue
                if line.startswith(b'data: '):
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
