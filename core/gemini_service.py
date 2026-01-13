"""Gemini API 服务 (generativelanguage.googleapis.com)"""

import requests
import json
from typing import Optional, Generator
from .base_service import BaseAPIService


class GeminiService(BaseAPIService):
    """Gemini API 服务 - generativelanguage.googleapis.com (不支持流式)"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = 'gemini-pro'):
        super().__init__(api_key, base_url, model)
        self.endpoint = base_url.rstrip('/') if base_url else "https://generativelanguage.googleapis.com/v1beta/models"
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

    def chat_stream(self, user_message: str, system_prompt: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 4000,
                   attachments: Optional[list] = None, **kwargs) -> Generator[str, None, None]:
        """流式聊天 - Gemini API (一次性响应)"""

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
            url = f"{self.endpoint}/{model_name}:generateContent"

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
                for part in data["candidates"][0]["content"]["parts"]:
                    if "text" in part:
                        yield part["text"]
        except requests.exceptions.RequestException as e:
            yield f"\n\n[错误] {str(e)}\n"
