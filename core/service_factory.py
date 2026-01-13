"""API 服务工厂 - 统一创建和管理不同 API 类型的服务"""

from typing import Optional
from core.api_detector import APIDetector, APIType
from .base_service import BaseAPIService
from .claude_code_service import ClaudeCodeService
from .glm_api_service import GLMAPIService
from .gemini_service import GeminiService
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService
from .deepseek_service import DeepSeekService


class ServiceFactory:
    """API 服务工厂"""

    @staticmethod
    def create_service(api_key: str, base_url: Optional[str] = None, model: str = None,
                      provider_type: Optional[str] = None) -> BaseAPIService:
        """
        根据 API 类型创建对应的服务实例

        Args:
            api_key: API 密钥
            base_url: 自定义端点 (可选)
            model: 模型名称 (可选)
            provider_type: 提供商类型 (可选，用于手动指定)

        Returns:
            BaseAPIService 的子类实例
        """

        # 检测 API 类型
        api_type = APIDetector.detect(api_key, base_url, provider_type)

        # 根据类型创建对应的服务
        if api_type == APIType.CLAUDE_CODE:
            return ClaudeCodeService(
                api_key,
                base_url,
                model or 'claude-sonnet-4-5-20250929'
            )

        elif api_type == APIType.GLM:
            return GLMAPIService(
                api_key,
                base_url,
                model or 'glm-4-plus'
            )

        elif api_type == APIType.GEMINI:
            return GeminiService(
                api_key,
                base_url,
                model or 'gemini-pro'
            )

        elif api_type == APIType.OPENAI:
            return OpenAIService(
                api_key,
                base_url,
                model or 'gpt-4'
            )

        elif api_type == APIType.DEEPSEEK:
            return DeepSeekService(
                api_key,
                base_url,
                model or 'DeepSeek-V3.2'
            )

        elif api_type == APIType.STANDARD_ANTHROPIC:
            return AnthropicService(
                api_key,
                base_url,
                model or 'claude-sonnet-4-5-20250929'
            )

        else:
            # 默认使用 Anthropic 官方 API
            return AnthropicService(
                api_key,
                base_url,
                model or 'claude-sonnet-4-5-20250929'
            )

    @staticmethod
    def get_service_info(api_type: APIType) -> dict:
        """获取 API 类型的信息"""
        info_map = {
            APIType.CLAUDE_CODE: {
                "name": "Claude Code API",
                "endpoint": "ai.itssx.com",
                "auth": "x-api-key",
                "stream": True,
                "tools": True,
                "thinking_mode": False,
            },
            APIType.GLM: {
                "name": "GLM (智谱清言)",
                "endpoint": "bigmodel.cn",
                "auth": "Bearer",
                "stream": True,
                "tools": True,
                "thinking_mode": True,
            },
            APIType.GEMINI: {
                "name": "Google Gemini",
                "endpoint": "generativelanguage.googleapis.com",
                "auth": "x-goog-api-key",
                "stream": False,
                "tools": False,
                "thinking_mode": False,
            },
            APIType.OPENAI: {
                "name": "OpenAI",
                "endpoint": "api.openai.com",
                "auth": "Bearer",
                "stream": True,
                "tools": False,
                "thinking_mode": False,
            },
            APIType.DEEPSEEK: {
                "name": "DeepSeek",
                "endpoint": "api.deepseek.com",
                "auth": "Bearer",
                "stream": True,
                "tools": False,
                "thinking_mode": False,
            },
            APIType.STANDARD_ANTHROPIC: {
                "name": "Claude (官方 API)",
                "endpoint": "api.anthropic.com",
                "auth": "x-api-key",
                "stream": True,
                "tools": True,
                "thinking_mode": False,
            },
        }
        return info_map.get(api_type, {})
