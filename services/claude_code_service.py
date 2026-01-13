"""
Claude Code API 服务 (ai.itssx.com)
- 端点: ai.itssx.com
- 认证: x-api-key
- 协议: Anthropic Messages API v1
- 流式: ✅ 支持
- 工具调用: ✅ 支持
- thinking_mode: ❌ 不支持
"""

import requests
import json
from typing import Optional, Generator
from services.base_service import BaseAPIService
from core.claude_tools import ClaudeTools


class ClaudeCodeService(BaseAPIService):
    """Claude Code API 服务"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = 'claude-sonnet-4-5-20250929'):
        super().__init__(api_key, base_url, model)
        self.tools = ClaudeTools()

        # 设置端点
        if base_url:
            self.endpoint = base_url.rstrip('/') + "/v1/messages"
        else:
            self.endpoint = "https://ai.itssx.com/v1/messages"

        # 设置请求头
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000,
                   attachments: Optional[list] = None) -> Generator[str, None, None]:
        """流式聊天 - Claude Code API"""

        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
            messages.append({"role": "assistant", "content": "OK, I understand."})

        # 构建用户消息内容
        content = []
        if attachments:
            for attachment in attachments:
                if attachment['type'] == 'image':
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": attachment['media_type'],
                            "data": attachment['data']
                        }
                    })
                elif attachment['type'] == 'document':
                    content.append({
                        "type": "text",
                        "text": f"[文件: {attachment['name']}]\n{attachment['data']}"
                    })

        content.append({"type": "text", "text": user_message})
        messages.append({"role": "user", "content": content})

        # 构建请求
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "tools": self.tools.get_tools_definition()
        }

        # 发送请求并处理流
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=self.headers,
                timeout=(10, 120),
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                if line.startswith(b'event: '):
                    continue
                elif line.startswith(b'data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('type') == 'content_block_delta':
                            delta = data.get('delta', {})
                            if delta.get('type') == 'text_delta':
                                text = delta.get('text', '')
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue
        except requests.exceptions.RequestException as e:
            yield f"\n\n[错误] {str(e)}\n"
