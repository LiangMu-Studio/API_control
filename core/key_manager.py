"""
API Key 管理模块 - 兼容 API_control 系统
支持多 API、多 key、按对话切换
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class KeyManager:
    """API Key 管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化 Key 管理器"""
        if config_path:
            p = Path(config_path)
            if p.is_dir() or (not p.exists() and not p.suffix):
                self.config_path = p / "config.json"
            else:
                self.config_path = p
        else:
            project_root = Path(__file__).parent.parent
            self.config_path = project_root / "data" / "config.json"

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        self.configs: List[Dict] = []
        self.current_config_id: Optional[str] = None
        self.load_configs()

    def load_configs(self) -> bool:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.configs = data.get("configurations", [])
                    self.current_config_id = data.get("defaultConfiguration")

                    # 确保所有配置都有order字段
                    self._ensure_order_field()
                    return True
        except Exception:
            pass
        return False

    def get_all_configs(self) -> List[Dict]:
        """获取所有配置"""
        return self.configs

    def get_config_by_id(self, config_id: str) -> Optional[Dict]:
        """根据 ID 获取配置"""
        for config in self.configs:
            if config.get("id") == config_id:
                return config
        return None

    def get_current_config(self) -> Optional[Dict]:
        """获取当前配置"""
        if self.current_config_id:
            return self.get_config_by_id(self.current_config_id)
        return self.configs[0] if self.configs else None

    def set_current_config(self, config_id: str) -> bool:
        """设置当前配置"""
        if self.get_config_by_id(config_id):
            self.current_config_id = config_id
            # 保存到文件
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["defaultConfiguration"] = config_id
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return True
        return False

    def get_api_key(self, config_id: Optional[str] = None) -> Optional[str]:
        """获取 API Key"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("credentials", {}).get("api_key")
        return None

    def get_base_url(self, config_id: Optional[str] = None) -> Optional[str]:
        """获取 Base URL"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("endpoint")
        return None

    def get_config_info(self, config_id: Optional[str] = None) -> Tuple[str, str, str]:
        """获取配置信息 (label, api_key, base_url)"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            label = config.get("label", "Unknown")
            api_key = config.get("provider", {}).get("credentials", {}).get("api_key", "")
            base_url = config.get("provider", {}).get("endpoint", "")
            return label, api_key, base_url
        return "", "", ""

    def get_config_list(self) -> List[Tuple[str, str]]:
        """获取配置列表 [(id, label), ...] - 严格按照保存顺序"""
        # 确保按照添加顺序返回配置
        ordered_configs = sorted(self.configs, key=lambda x: x.get("order", 0))
        return [(config.get("id"), config.get("label")) for config in ordered_configs]

    def export_configs(self, export_path: str) -> bool:
        """导出配置到文件"""
        try:
            data = {
                "version": "1.0",
                "configurations": self.configs,
                "defaultConfiguration": self.current_config_id
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def import_configs(self, import_path: str, merge: bool = True) -> bool:
        """导入配置从文件"""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                imported = data.get("configurations", [])

                if merge:
                    # 合并模式：添加新配置，避免重复
                    existing_ids = {c.get("id") for c in self.configs}
                    for config in imported:
                        if config.get("id") not in existing_ids:
                            self.configs.append(config)
                else:
                    # 覆盖模式
                    self.configs = imported

                self.current_config_id = data.get("defaultConfiguration")
                result = self.save_configs()
                if result:
                    # 重新加载以确保数据一致
                    self.load_configs()
                return result
        except Exception as e:
            print(f"导入配置失败: {e}")
            return False

    def save_configs(self) -> bool:
        """保存配置到文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # 自动检测和修复 provider type
            self._auto_fix_provider_types()

            data = {
                "version": "1.0",
                "configurations": self.configs,
                "defaultConfiguration": self.current_config_id
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def _auto_fix_provider_types(self):
        """自动检测和修复 provider type"""
        for cfg in self.configs:
            provider = cfg.get("provider", {})
            endpoint = provider.get("endpoint", "")
            api_key = provider.get("credentials", {}).get("api_key", "")
            old_type = provider.get("type", "")

            # 根据 endpoint 和 api_key 检测正确的 type
            correct_type = self._detect_provider_type(endpoint, api_key)

            if old_type != correct_type:
                provider["type"] = correct_type

    def add_config(
        self,
        label: str,
        provider_type: str,
        endpoint: str,
        key_name: str,
        api_key: str,
        model: str = None,
        max_tokens: int = 32000,
        token_limit_per_request: int = 200000,
        thinking_mode: str = None,
    ) -> Optional[str]:
        """添加新配置"""
        import time
        config_id = f"{label}-{int(time.time())}"
        config = {
            "id": config_id,
            "label": label,
            "provider": {
                "name": label,
                "type": provider_type,
                "endpoint": endpoint,
                "key_name": key_name,
                "credentials": {"api_key": api_key},
                "max_tokens": max_tokens,
                "token_limit_per_request": token_limit_per_request,
                "selected_model": model,
                "available_models": [model] if model else []
            },
            "createdAt": __import__("datetime").datetime.now().isoformat(),
            "updatedAt": __import__("datetime").datetime.now().isoformat(),
            "order": len(self.configs)
        }
        if thinking_mode:
            config["provider"]["thinking_mode"] = thinking_mode

        self.configs.append(config)
        self.save_configs()
        return config_id

    def _ensure_order_field(self):
        """确保所有配置都有order字段，并修复重复的order值"""
        # 为没有order字段的配置分配新值
        for i, config in enumerate(self.configs):
            if "order" not in config:
                config["order"] = i

        # 修复重复的order值
        seen_orders = set()
        max_order = -1
        for config in self.configs:
            order = config["order"]
            max_order = max(max_order, order)

        # 重新分配唯一的order值
        unique_order = 0
        temp_configs = sorted(self.configs, key=lambda x: x.get("order", 0))

        for config in temp_configs:
            config["order"] = unique_order
            unique_order += 1

    def delete_config(self, config_id: str) -> bool:
        """删除配置"""
        self.configs = [c for c in self.configs if c.get("id") != config_id]
        if self.current_config_id == config_id:
            self.current_config_id = None
        self.save_configs()
        return True

    def get_provider_type(self, config_id: Optional[str] = None) -> Optional[str]:
        """获取提供商类型"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("type")
        return None

    def get_model(self, config_id: Optional[str] = None) -> Optional[str]:
        """获取当前选中的模型名称"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("selected_model")
        return None

    def get_max_tokens(self, config_id: Optional[str] = None) -> int:
        """获取单次响应最大tokens限制（输出token上限）"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("max_tokens", 32000)
        return 32000

    def get_models(self, config_id: Optional[str] = None) -> list:
        """获取所有可用模型列表"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("available_models", [])
        return []

    def get_thinking_mode(self, config_id: Optional[str] = None) -> Optional[str]:
        """获取GLM思考模式"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("thinking_mode")
        return None

    def get_token_limit_per_request(self, config_id: Optional[str] = None) -> int:
        """获取单句最大tokens限制"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("token_limit_per_request", 4000)
        return 4000

    def get_token_limit_total(self, config_id: Optional[str] = None) -> int:
        """获取总额度上限"""
        config = (
            self.get_config_by_id(config_id)
            if config_id
            else self.get_current_config()
        )
        if config:
            return config.get("provider", {}).get("token_limit_total", 50000)
        return 50000

    def _detect_provider_type(self, endpoint: str, api_key: str) -> str:
        """根据 endpoint 和 api_key 自动检测 provider type"""
        # 优先级 1: 根据 endpoint
        if endpoint:
            if 'ai.itssx.com' in endpoint:
                return 'claude_code'
            if 'bigmodel.cn' in endpoint or 'open.bigmodel.cn' in endpoint:
                return 'glm'
            if 'generativelanguage.googleapis.com' in endpoint:
                return 'gemini'
            if 'deepseek.com' in endpoint:
                return 'deepseek'
            if 'api.anthropic.com' in endpoint:
                return 'anthropic'
            if 'openai.com' in endpoint:
                return 'openai'

        # 优先级 2: 根据 api_key
        if api_key.startswith('cr_'):
            return 'claude_code'
        if api_key.startswith('sk-ant-'):
            return 'anthropic'
        if api_key.startswith('AIza'):
            return 'gemini'
        if api_key.startswith('sk-'):
            return 'openai'

        return 'anthropic'  # 默认
