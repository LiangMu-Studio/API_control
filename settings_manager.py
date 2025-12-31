"""
统一的设置管理器 - 与 AI_talk 保持一致
"""

import json
from pathlib import Path
from typing import Optional
from api_config_manager import ConfigManager


class SettingsManager:
    """设置管理器 - 与 AI_talk 保持一致"""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            # 使用当前目录的 data 文件夹
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.settings_file = self.data_dir / "settings.json"
        self.config_manager = ConfigManager(str(self.data_dir))
        self.settings = self._load()

    def _load(self) -> dict:
        """加载设置"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载设置失败: {e}")
        return self._default_settings()

    def _default_settings(self) -> dict:
        """默认设置"""
        return {
            'current_config_id': None,
            'theme': 'modern_dark'
        }

    def save(self) -> None:
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {e}")

    def get(self, key: str, default: any = None) -> any:
        """获取设置值"""
        return self.settings.get(key, default)

    def set(self, key: str, value: any) -> None:
        """设置值"""
        self.settings[key] = value
        self.save()

    def update(self, data: dict) -> None:
        """批量更新设置"""
        self.settings.update(data)
        self.save()

    def get_current_api_key(self) -> Optional[str]:
        """获取当前 API KEY"""
        config_id = self.get('current_config_id')
        config = self.config_manager.get_config_by_id(config_id)
        if config:
            return config.get('provider', {}).get('credentials', {}).get('api_key')
        return None

    def get_current_endpoint(self) -> Optional[str]:
        """获取当前端点"""
        config_id = self.get('current_config_id')
        config = self.config_manager.get_config_by_id(config_id)
        if config:
            return config.get('provider', {}).get('endpoint')
        return None

    def get_current_model(self) -> Optional[str]:
        """获取当前模型"""
        config_id = self.get('current_config_id')
        config = self.config_manager.get_config_by_id(config_id)
        if config:
            return config.get('provider', {}).get('model')
        return None

    def get_current_provider_type(self) -> Optional[str]:
        """获取当前提供商类型"""
        config_id = self.get('current_config_id')
        config = self.config_manager.get_config_by_id(config_id)
        if config:
            return config.get('provider', {}).get('type')
        return None

    def set_current_config(self, config_id: str) -> bool:
        """设置当前配置"""
        if self.config_manager.get_config_by_id(config_id):
            self.set('current_config_id', config_id)
            return True
        return False

    def get_all_configs(self):
        """获取所有配置"""
        return [(c.get('id'), c.get('label')) for c in self.config_manager.get_all_configs()]

    def get_config_info(self, config_id: Optional[str] = None):
        """获取配置信息"""
        if config_id is None:
            config_id = self.get('current_config_id')
        config = self.config_manager.get_config_by_id(config_id)
        if config:
            return {
                'id': config.get('id'),
                'label': config.get('label'),
                'api_key': config.get('provider', {}).get('credentials', {}).get('api_key'),
                'endpoint': config.get('provider', {}).get('endpoint'),
                'model': config.get('provider', {}).get('model'),
                'type': config.get('provider', {}).get('type'),
            }
        return None
