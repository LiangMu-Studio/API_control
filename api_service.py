# -*- coding: utf-8 -*-
"""
统一 API 服务包装器 - 支持多提供商
使用新的 DLL 模块进行 KEY 管理和 API 通讯
"""

from core.key_manager import KeyManager
from services.api_services.glm_api_service import GLMAPIService
from services.chat_worker import ChatWorker


class UnifiedAPIService:
    """统一的 API 服务接口"""

    def __init__(self, config_dir='./data'):
        """初始化服务"""
        self.key_manager = KeyManager(config_dir)
        self.chat_worker = None

    def get_all_configs(self):
        """获取所有配置"""
        return self.key_manager.get_all_configs()

    def get_current_config(self):
        """获取当前配置"""
        return self.key_manager.get_current_config()

    def set_current_config(self, config_id):
        """设置当前配置"""
        return self.key_manager.set_current_config(config_id)

    def query(self, question: str, config_id=None, **kwargs) -> str:
        """
        查询 API

        Args:
            question: 提问内容
            config_id: 配置 ID（可选，使用当前配置）
            **kwargs: 其他参数（temperature, max_tokens 等）

        Returns:
            API 的回复
        """
        if config_id:
            self.set_current_config(config_id)

        config = self.get_current_config()
        if not config:
            return "错误：未设置配置"

        provider_type = config.get('provider', {}).get('type')

        if provider_type == 'glm':
            return self._query_glm(config, question, **kwargs)
        elif provider_type == 'gemini':
            return self._query_gemini(config, question, **kwargs)
        elif provider_type == 'claude_code':
            return self._query_claude_code(config, question, **kwargs)
        else:
            return f"错误：不支持的提供商类型 {provider_type}"

    def _query_glm(self, config, question, **kwargs):
        """查询 GLM API"""
        try:
            api_key = config.get('provider', {}).get('credentials', {}).get('api_key')
            endpoint = config.get('provider', {}).get('endpoint')
            model = config.get('provider', {}).get('model', 'glm-4.7')
            thinking_mode = config.get('provider', {}).get('thinking_mode', 'fast')
            temperature = kwargs.get('temperature', config.get('provider', {}).get('temperature', 0.7))
            max_tokens = kwargs.get('max_tokens', config.get('provider', {}).get('max_tokens', 2000))

            service = GLMAPIService(
                api_key=api_key,
                base_url=endpoint,
                model=model
            )

            response = service.chat_stream(
                user_message=question,
                thinking_mode=thinking_mode,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response
        except Exception as e:
            return f"GLM API 错误: {str(e)}"

    def _query_gemini(self, config, question, **kwargs):
        """查询 Gemini API"""
        try:
            import requests
            import os

            api_key = config.get('provider', {}).get('credentials', {}).get('api_key')
            model = config.get('provider', {}).get('model', 'gemini-2.5-flash')
            temperature = kwargs.get('temperature', 0.7)
            max_tokens = kwargs.get('max_tokens', 2048)

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }

            payload = {
                "contents": [{
                    "parts": [{
                        "text": question
                    }]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        return candidate['content']['parts'][0]['text']
                return "无回复内容"
            else:
                error_data = response.json()
                if 'error' in error_data:
                    return f"API 错误: {error_data['error'].get('message', '未知错误')}"
                return f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return f"Gemini API 错误: {str(e)}"

    def _query_claude_code(self, config, question, **kwargs):
        """查询 Claude Code API"""
        try:
            import requests

            api_key = config.get('provider', {}).get('credentials', {}).get('api_key')
            endpoint = config.get('provider', {}).get('endpoint')
            model = config.get('provider', {}).get('model', 'claude-haiku-4-5-20251001')
            temperature = kwargs.get('temperature', 0.7)
            max_tokens = kwargs.get('max_tokens', 2048)

            url = f"{endpoint}/messages"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "anthropic-version": "2023-06-01"
            }

            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": question}
                ]
            }

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if 'content' in result and len(result['content']) > 0:
                    return result['content'][0].get('text', '无回复内容')
                return "无回复内容"
            else:
                return f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return f"Claude Code API 错误: {str(e)}"

    def get_token_limit_per_request(self):
        """获取单次请求 TOKEN 限制"""
        return self.key_manager.get_token_limit_per_request()

    def get_token_limit_total(self):
        """获取总 TOKEN 限制"""
        return self.key_manager.get_token_limit_total()


if __name__ == "__main__":
    service = UnifiedAPIService()

    print("=" * 60)
    print("统一 API 服务测试")
    print("=" * 60)
    print()

    configs = service.get_all_configs()
    print(f"可用配置: {len(configs)}")
    for config in configs:
        print(f"  - {config['label']} ({config['provider']['type']})")
    print()

    current = service.get_current_config()
    print(f"当前配置: {current['label']}")
    print(f"TOKEN 限制: {service.get_token_limit_per_request()} / {service.get_token_limit_total()}")
    print()

    test_question = "你好，请简要介绍自己"
    print(f"提问: {test_question}")
    print()

    reply = service.query(test_question)
    print(f"回复: {reply}")
