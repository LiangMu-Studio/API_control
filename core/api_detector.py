"""
API type detector - extensible system for auto-detecting different API providers
"""

from enum import Enum
from typing import Optional


class APIType(Enum):
    """Supported API types"""
    CLAUDE_CODE = "claude_code"
    STANDARD_ANTHROPIC = "standard_anthropic"
    GLM = "glm"
    GEMINI = "gemini"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    UNKNOWN = "unknown"


class APIDetector:
    """Auto-detect API type based on key and endpoint"""

    @staticmethod
    def detect(api_key: str, endpoint: Optional[str] = None, provider_type: Optional[str] = None) -> APIType:
        """
        Detect API type from key, endpoint, or provider type

        Args:
            api_key: API key string
            endpoint: API endpoint URL
            provider_type: Provider type from config (fallback)

        Returns:
            APIType enum
        """
        # Priority 1: Check endpoint (most reliable)
        if endpoint:
            if 'ai.itssx.com' in endpoint:
                return APIType.CLAUDE_CODE
            if 'bigmodel.cn' in endpoint:
                return APIType.GLM
            if 'generativelanguage.googleapis.com' in endpoint:
                return APIType.GEMINI
            if 'deepseek.com' in endpoint:
                return APIType.DEEPSEEK
            if 'api.anthropic.com' in endpoint:
                return APIType.STANDARD_ANTHROPIC

        # Priority 2: Check API key pattern
        if api_key.startswith('cr_'):
            return APIType.CLAUDE_CODE
        if api_key.startswith('sk-ant-'):
            return APIType.STANDARD_ANTHROPIC
        if api_key.startswith('sk-') and len(api_key) > 40:
            return APIType.CLAUDE_CODE
        if api_key.startswith('sk-'):
            return APIType.OPENAI
        if api_key.startswith('AIzaSy'):
            return APIType.GEMINI

        # Priority 3: Check provider_type from config (fallback)
        if provider_type:
            type_map = {
                "claude_code": APIType.CLAUDE_CODE,
                "anthropic": APIType.STANDARD_ANTHROPIC,
                "glm": APIType.GLM,
                "gemini": APIType.GEMINI,
                "openai": APIType.OPENAI,
                "deepseek": APIType.DEEPSEEK,
            }
            if provider_type in type_map:
                return type_map[provider_type]

        return APIType.UNKNOWN

    @staticmethod
    def get_auth_header(api_key: str, api_type: APIType) -> dict:
        """Get appropriate auth headers for API type"""
        if api_type == APIType.CLAUDE_CODE:
            return {"x-api-key": api_key}
        elif api_type == APIType.GEMINI:
            return {"x-goog-api-key": api_key}
        elif api_type in (APIType.OPENAI, APIType.DEEPSEEK):
            return {"Authorization": f"Bearer {api_key}"}
        else:
            return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def get_default_endpoint(api_type: APIType) -> str:
        """Get default endpoint for API type"""
        endpoints = {
            APIType.CLAUDE_CODE: "https://api.anthropic.com/v1/messages",
            APIType.STANDARD_ANTHROPIC: "https://api.anthropic.com/v1/messages",
            APIType.GLM: "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            APIType.GEMINI: "https://generativelanguage.googleapis.com/v1beta/models",
            APIType.OPENAI: "https://api.openai.com/v1/chat/completions",
            APIType.DEEPSEEK: "https://api.deepseek.com/v1/chat/completions",
        }
        return endpoints.get(api_type, "https://api.anthropic.com/v1/messages")
