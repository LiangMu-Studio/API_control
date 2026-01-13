"""设置管理模块"""

import json
from pathlib import Path
from typing import Optional
from core.key_manager import KeyManager


class SettingsManager:
    """设置管理器"""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            # 使用项目目录下的 data 文件夹
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data"
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self.settings_file = self.data_dir / "settings.json"
        self.key_manager = KeyManager()
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
        return self.key_manager.get_api_key(config_id)

    def get_current_base_url(self) -> Optional[str]:
        """获取当前 Base URL"""
        config_id = self.get('current_config_id')
        return self.key_manager.get_base_url(config_id)

    def get_current_model(self) -> Optional[str]:
        """获取当前模型"""
        config_id = self.get('current_config_id')
        return self.key_manager.get_model(config_id)

    def set_current_config(self, config_id: str) -> bool:
        """设置当前配置"""
        if self.key_manager.set_current_config(config_id):
            self.set('current_config_id', config_id)
            return True
        return False

    def get_all_configs(self):
        """获取所有配置"""
        return self.key_manager.get_config_list()
