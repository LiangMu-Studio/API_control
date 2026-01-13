"""
统一的 KEY 管理 + 模型连接接口
兼容所有模型：Claude Code、Anthropic、GLM、Gemini、OpenAI
"""

from typing import Optional, Dict, Any
from .key_manager import KeyManager
from .service_factory import ServiceFactory


class KeyModelManager:
    """KEY 管理 + 模型连接统一接口"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化管理器"""
        self.key_manager = KeyManager(config_path)
        self.service_factory = ServiceFactory()
        self._service_cache: Dict[str, Any] = {}

    def get_service(self, config_id: Optional[str] = None):
        """根据 KEY ID 获取对应模型的服务"""
        if config_id is None:
            config_id = self.key_manager.current_config_id

        if config_id in self._service_cache:
            return self._service_cache[config_id]

        config = self.key_manager.get_config_by_id(config_id)
        if not config:
            raise ValueError(f"Config not found: {config_id}")

        provider = config.get("provider", {})
        api_key = provider.get("credentials", {}).get("api_key")
        base_url = provider.get("endpoint")
        model = self.key_manager.get_model(config_id)
        provider_type = provider.get("type")

        service = self.service_factory.create_service(
            api_key=api_key,
            base_url=base_url,
            model=model,
            provider_type=provider_type
        )
        self._service_cache[config_id] = service
        return service

    def add_key(self, label: str, api_key: str, endpoint: str = None,
                model: str = None) -> str:
        """添加 KEY 并自动检测模型类型"""
        provider_type = self.key_manager._detect_provider_type(endpoint or "", api_key)

        config_id = self.key_manager.add_config(
            label=label,
            provider_type=provider_type,
            endpoint=endpoint or self._get_default_endpoint(provider_type),
            key_name="ANTHROPIC_AUTH_TOKEN",
            api_key=api_key,
            model=model
        )
        return config_id

    def delete_key(self, config_id: str) -> bool:
        """删除 KEY"""
        if config_id in self._service_cache:
            del self._service_cache[config_id]
        return self.key_manager.delete_config(config_id)

    def list_keys(self) -> list:
        """列出所有 KEY"""
        return self.key_manager.get_config_list()

    def get_key_info(self, config_id: Optional[str] = None) -> Dict[str, str]:
        """获取 KEY 信息"""
        label, api_key, base_url = self.key_manager.get_config_info(config_id)
        provider_type = self.key_manager.get_provider_type(config_id)
        model = self.key_manager.get_model(config_id)

        return {
            "label": label,
            "api_key": api_key,
            "endpoint": base_url,
            "type": provider_type,
            "model": model
        }

    def set_current_key(self, config_id: str) -> bool:
        """设置当前 KEY"""
        return self.key_manager.set_current_config(config_id)

    def get_current_key(self) -> Optional[str]:
        """获取当前 KEY ID"""
        return self.key_manager.current_config_id

    def chat(self, message: str, config_id: Optional[str] = None,
             system_prompt: Optional[str] = None, **kwargs) -> str:
        """发送消息（非流式）"""
        service = self.get_service(config_id)
        return service.chat(message, system_prompt=system_prompt, **kwargs)

    def chat_stream(self, message: str, config_id: Optional[str] = None,
                    system_prompt: Optional[str] = None, **kwargs):
        """发送消息（流式）"""
        service = self.get_service(config_id)
        return service.chat_stream(message, system_prompt=system_prompt, **kwargs)

    def export_keys(self, export_path: str) -> bool:
        """导出所有 KEY"""
        return self.key_manager.export_configs(export_path)

    def import_keys(self, import_path: str, merge: bool = True) -> bool:
        """导入 KEY"""
        result = self.key_manager.import_configs(import_path, merge)
        self._service_cache.clear()
        return result

    def _get_default_endpoint(self, provider_type: str) -> str:
        """获取默认 endpoint"""
        endpoints = {
            "claude_code": "https://ai.itssx.com/api",
            "anthropic": "https://api.anthropic.com",
            "glm": "https://open.bigmodel.cn/api/anthropic",
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        return endpoints.get(provider_type, "")

    def clear_cache(self):
        """清除服务缓存"""
        self._service_cache.clear()
