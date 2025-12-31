"""
Claude API service for AI_talk - auto-detects API type
"""

from typing import Optional, Generator, List, Dict
import requests
import json
from anthropic import Anthropic
from core.api_detector import APIDetector, APIType
from core.history_compressor import HistoryCompressor
from core.claude_tools import ClaudeTools


class ClaudeService:
    """Service for interacting with Claude API - auto-detects API type"""

    def __init__(self, api_key: str, base_url: str = None, model: str = 'claude-sonnet-4-5-20250929', provider_type: str = None, enable_compression: bool = True):
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.enable_compression = enable_compression
        self.compressor = HistoryCompressor() if enable_compression else None
        self.tools = ClaudeTools()

        # Auto-detect API type using detector module
        self.api_type = APIDetector.detect(api_key, base_url, provider_type)
        self.is_requests_based = self.api_type in (APIType.CLAUDE_CODE, APIType.GLM, APIType.GEMINI, APIType.OPENAI)

        if self.is_requests_based:
            # Use requests for Claude Code / GLM / Gemini / OpenAI
            if self.base_url:
                if self.api_type == APIType.GEMINI:
                    self.endpoint = self.base_url.rstrip('/')
                elif self.api_type == APIType.GLM and '/api/paas/v4/chat/completions' in self.base_url:
                    # GLM 原生 API - 不添加 /v1/messages
                    self.endpoint = self.base_url.rstrip('/')
                else:
                    self.endpoint = self.base_url.rstrip('/') + "/v1/messages"
            else:
                self.endpoint = APIDetector.get_default_endpoint(self.api_type)

            self.headers = {
                "Content-Type": "application/json",
            }
            self.headers.update(APIDetector.get_auth_header(api_key, self.api_type))

            if self.api_type in (APIType.CLAUDE_CODE, APIType.GLM):
                self.headers["anthropic-version"] = "2023-06-01"

            self.client = None
        else:
            # Standard Anthropic API - use SDK
            client_kwargs = {'api_key': api_key}
            if self.base_url:
                client_kwargs['base_url'] = self.base_url

            self.client = Anthropic(**client_kwargs)
            self.headers = None

    def chat(self, user_message: str, system_prompt: Optional[str] = None,
             temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None,
             thinking_mode: str = None) -> str:
        """Send a message and get response"""
        response_text = ""
        for chunk in self.chat_stream(user_message, system_prompt, temperature, max_tokens, attachments, thinking_mode):
            response_text += chunk
        return response_text

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                    temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None,
                    thinking_mode: str = None) -> Generator[str, None, None]:
        """Send a message with streaming response - 带重试机制"""
        # 在发送前更新卡片权重
        if self.enable_compression and self.compressor:
            self.compressor.update_card_weight(user_message)

        # 实现指数退避重试
        max_retries = 5
        for attempt in range(max_retries):
            try:
                if self.is_requests_based:
                    if self.api_type == APIType.GEMINI:
                        yield from self._chat_stream_gemini(user_message, system_prompt, temperature, max_tokens, attachments)
                    elif self.api_type == APIType.OPENAI:
                        yield from self._chat_stream_openai(user_message, system_prompt, temperature, max_tokens, attachments)
                    elif self.api_type == APIType.GLM and '/api/paas/v4/chat/completions' in self.endpoint:
                        # GLM 原生 API
                        yield from self._chat_stream_glm_native(user_message, system_prompt, temperature, max_tokens, attachments, thinking_mode)
                    else:
                        # Claude Code API 或 GLM anthropic 兼容模式
                        yield from self._chat_stream_requests(user_message, system_prompt, temperature, max_tokens, attachments, thinking_mode if self.api_type == APIType.GLM else None)
                else:
                    # Claude 官方 API 不支持 thinking_mode
                    yield from self._chat_stream_sdk(user_message, system_prompt, temperature, max_tokens, attachments)
                return  # 成功则退出
            except Exception as e:
                error_msg = str(e)
                # 检查是否是可重试的错误
                if attempt < max_retries - 1 and self._is_retryable_error(error_msg):
                    wait_time = (2 ** attempt) * 3  # 指数退避: 3s, 6s, 12s, 24s, 48s
                    yield f"\n[速率限制,{wait_time}秒后重试 {attempt+1}/{max_retries}]...\n"
                    import time
                    time.sleep(wait_time)
                else:
                    # 不可重试或已达最大重试次数
                    yield f"\n\n[错误] {error_msg}\n"
                    raise

    def _is_retryable_error(self, error_msg: str) -> bool:
        """检查是否是可重试的错误"""
        retryable_keywords = [
            'timeout',
            'connection',
            'network',
            '503',
            '502',
            '429',  # Too Many Requests
            'temporarily',
        ]
        return any(keyword.lower() in error_msg.lower() for keyword in retryable_keywords)

    def _chat_stream_glm_native(self, user_message: str, system_prompt: Optional[str] = None,
                               temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None,
                               thinking_mode: str = None) -> Generator[str, None, None]:
        """Stream using GLM native API (/api/paas/v4/chat/completions)"""
        messages = []

        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
            messages.append({"role": "assistant", "content": "OK, I understand."})

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
            "stream": True
        }

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

    def _chat_stream_gemini(self, user_message: str, system_prompt: Optional[str] = None,
                           temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None) -> Generator[str, None, None]:
        """Stream using Gemini API"""
        contents = []

        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "OK, I understand."}]})

        parts = []
        if attachments:
            for attachment in attachments:
                if attachment['type'] == 'image':
                    parts.append({
                        "inline_data": {
                            "mime_type": attachment['media_type'],
                            "data": attachment['data']
                        }
                    })

        parts.append({"text": user_message})
        contents.append({"role": "user", "parts": parts})

        try:
            model_name = self.model.split('/')[-1] if '/' in self.model else self.model
            url = f"{self.endpoint}/models/{model_name}:generateContent"

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                }
            }

            response = requests.post(url, json=payload, headers=self.headers, timeout=(10, 120), stream=False)
            response.raise_for_status()

            data = response.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "text" in part:
                            yield part["text"]
        except requests.exceptions.RequestException as e:
            yield f"\n\n[错误] {str(e)}\n"

    def _chat_stream_openai(self, user_message: str, system_prompt: Optional[str] = None,
                           temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None) -> Generator[str, None, None]:
        """Stream using OpenAI API"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        content = user_message
        if attachments:
            for attachment in attachments:
                if attachment['type'] == 'image':
                    content += f"\n[图片: {attachment.get('name', 'image')}]"

        messages.append({"role": "user", "content": content})

        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }

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

    def _chat_stream_requests(self, user_message: str, system_prompt: Optional[str] = None,
                              temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None,
                              thinking_mode: str = None) -> Generator[str, None, None]:
        """Stream using requests library (Claude Code API)"""
        messages = []

        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
            messages.append({"role": "assistant", "content": "OK, I understand."})

        # 构建用户消息内容
        content = []

        # 添加附件（图片/文件）
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

        # 添加文本消息
        content.append({"type": "text", "text": user_message})

        messages.append({"role": "user", "content": content})

        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                "tools": self.tools.get_tools_definition()
            }

            # 为GLM添加thinking_mode参数
            if thinking_mode and self.api_type == APIType.GLM:
                payload["thinking_mode"] = thinking_mode

            try:
                response = requests.post(
                    self.endpoint,
                    json=payload,
                    headers=self.headers,
                    timeout=(10, 120),
                    stream=True
                )
            except Exception as e:
                print(f"[STREAM] Request failed: {e}")
                yield f"\n\n[错误] 请求发送失败: {str(e)}\n"
                return

            response.raise_for_status()

            # 处理流式响应
            line_count = 0
            text_count = 0
            last_event_type = None
            print("[STREAM] Starting to read response lines...")
            try:
                for line in response.iter_lines():
                    line_count += 1
                    if not line:
                        print(f"[STREAM] Empty line #{line_count}")
                        continue
                    print(f"[STREAM] Line #{line_count}: {line[:100]}")

                    if line.startswith(b'event: '):
                        last_event_type = line[7:].decode('utf-8', errors='ignore')
                        print(f"[STREAM] Event type: {last_event_type}")
                    elif line.startswith(b'data: '):
                        try:
                            data = json.loads(line[6:])
                            print(f"[STREAM] Parsed JSON: type={data.get('type')}")
                            if data.get('type') == 'content_block_delta':
                                delta = data.get('delta', {})
                                if delta.get('type') == 'text_delta':
                                    text = delta.get('text', '')
                                    if text:
                                        text_count += 1
                                        print(f"[STREAM] Text #{text_count}: {len(text)} chars - {text[:50]}")
                                        yield text
                            elif data.get('type') == 'message_stop':
                                print("[STREAM] Received message_stop event")
                            elif data.get('type') == 'content_block_stop':
                                print("[STREAM] Received content_block_stop event")
                            last_event_type = None
                        except json.JSONDecodeError as e:
                            print(f"[STREAM] JSON decode error on line #{line_count}: {e}")
                            print(f"[STREAM] Raw line: {line}")
                            continue
                    else:
                        print(f"[STREAM] Non-data line #{line_count}: {line[:100]}")
            except Exception as e:
                print(f"[STREAM] Stream reading error: {e}")
                if last_event_type:
                    print(f"[STREAM] ERROR: Stream interrupted with incomplete event: {last_event_type}")
                raise

            if last_event_type:
                print(f"[STREAM] WARNING: Stream ended with incomplete event type: {last_event_type}")
            print(f"[STREAM] Response complete - total lines: {line_count}, text chunks: {text_count}")

        except requests.exceptions.Timeout:
            yield "\n\n[错误] 请求超时，请重试\n"
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "403" in error_msg or "forbidden" in error_msg.lower():
                yield "\n\n[错误] API 密钥无效或没有权限\n"
            else:
                yield f"\n\n[错误] {error_msg}\n"

    def _chat_stream_sdk(self, user_message: str, system_prompt: Optional[str] = None,
                         temperature: float = 0.7, max_tokens: int = 4000, attachments: Optional[list] = None) -> Generator[str, None, None]:
        """Stream using Anthropic SDK (Standard API)"""
        messages = []

        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
            messages.append({"role": "assistant", "content": "OK, I understand."})

        # 构建用户消息内容
        content = []

        # 添加附件（图片/文件）
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

        # 添加文本消息
        content.append({"type": "text", "text": user_message})

        messages.append({"role": "user", "content": content})

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                tools=self.tools.get_tools_definition() if self.tools else None
            )

            # 处理响应内容
            for block in response.content:
                if hasattr(block, 'text'):
                    yield block.text

        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "forbidden" in error_msg.lower():
                yield "\n\n[错误] API 密钥无效或没有权限\n"
            elif "timeout" in error_msg.lower():
                yield "\n\n[错误] 请求超时，请重试\n"
            else:
                yield f"\n\n[错误] {error_msg}\n"

    def update_credentials(self, api_key: str, base_url: str = None, provider_type: str = None):
        """Update API credentials"""
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.base_url = base_url

        # Re-detect API type using detector module
        self.api_type = APIDetector.detect(api_key, base_url, provider_type)
        self.is_requests_based = self.api_type in (APIType.CLAUDE_CODE, APIType.GLM, APIType.GEMINI, APIType.OPENAI)

        if self.is_requests_based:
            if self.base_url:
                self.endpoint = self.base_url.rstrip('/')
            else:
                self.endpoint = APIDetector.get_default_endpoint(self.api_type)

            self.headers = {
                "Content-Type": "application/json",
            }
            self.headers.update(APIDetector.get_auth_header(api_key, self.api_type))

            if self.api_type in (APIType.CLAUDE_CODE, APIType.GLM):
                self.headers["anthropic-version"] = "2023-06-01"

            self.client = None
        else:
            client_kwargs = {'api_key': api_key}
            if self.base_url:
                client_kwargs['base_url'] = self.base_url

            self.client = Anthropic(**client_kwargs)
            self.headers = None

    def set_model(self, model: str):
        """Change the model being used"""
        self.model = model

    def process_with_compression(self, messages: List[Dict], current_message: str = "") -> List[Dict]:
        """使用分层压缩处理消息，支持关键词关联"""
        if not self.compressor:
            return messages
        self.compressor.process_messages(messages)
        return self.compressor.get_api_context(current_message)

    def get_compression_cards(self) -> List[Dict]:
        """获取压缩后的卡片序列"""
        if not self.compressor:
            return []
        return self.compressor.export_cards()

    def get_cards_summary(self) -> str:
        """获取卡片摘要"""
        if not self.compressor:
            return ""
        return self.compressor.get_cards_summary()

    def get_context_tokens(self, current_message: str = "") -> Dict:
        """获取上下文的 token 消耗"""
        if not self.compressor:
            return {'total_tokens': 0}
        return self.compressor.get_context_tokens(current_message)

    def get_compression_stats(self) -> Dict:
        """获取压缩统计信息"""
        if not self.compressor:
            return {}
        return self.compressor.get_compression_stats()

    def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """执行工具"""
        return self.tools.execute_tool(tool_name, tool_input)
