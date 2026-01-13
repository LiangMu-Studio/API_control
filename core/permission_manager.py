"""权限管理模块 - 控制 AI 对文件的访问权限"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum


class OperationType(Enum):
    """操作类型"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"


class PermissionManager:
    """权限管理器"""

    def __init__(self, config_path: str = None, root_path: str = "."):
        """
        初始化权限管理器

        Args:
            config_path: 配置文件路径
            root_path: 项目根路径
        """
        self.root_path = Path(root_path)

        if config_path is None:
            config_path = self.root_path / "core" / "permission_config.json"

        self.config_path = Path(config_path)
        self.approved_path = self.root_path / "core" / "approved_paths.json"

        self.config = self._load_config()
        self.approved_paths = self._load_approved_paths()
        self.ask_callback: Optional[Callable] = None

    def _load_config(self) -> dict:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[警告] 加载配置文件失败: {e}")

        return self._get_default_config()

    def _load_approved_paths(self) -> List[str]:
        """加载已批准的路径"""
        try:
            if self.approved_path.exists():
                with open(self.approved_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("approved", [])
        except Exception as e:
            print(f"[警告] 加载已批准路径失败: {e}")

        return []

    def _save_approved_paths(self) -> None:
        """保存已批准的路径"""
        try:
            data = {
                "approved": self.approved_paths,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.approved_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[错误] 保存已批准路径失败: {e}")

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "workspace": {
                "description": "工作区范围（工作区外的路径一律不允许操作）",
                "paths": ["d:/Dropbox/AI_tools/"]
            },
            "whitelist": {
                "description": "工作区内的高权限文件夹（无需询问）",
                "paths": []
            }
        }

    def _normalize_path(self, file_path: str) -> str:
        """规范化路径"""
        path = Path(file_path)
        try:
            path = path.resolve()
        except:
            pass
        return str(path).replace("\\", "/").lower()

    def _is_in_workspace(self, file_path: str) -> bool:
        """检查文件是否在工作区内"""
        normalized = self._normalize_path(file_path)
        workspace_paths = self.config.get("workspace", {}).get("paths", [])

        for ws_path in workspace_paths:
            ws_normalized = self._normalize_path(ws_path)
            if normalized.startswith(ws_normalized):
                return True

        return False

    def _is_in_whitelist(self, file_path: str) -> bool:
        """检查文件是否在白名单中（高权限）"""
        normalized = self._normalize_path(file_path)
        whitelist = self.config.get("whitelist", {}).get("paths", [])

        for wl_path in whitelist:
            wl_normalized = self._normalize_path(wl_path)
            if normalized.startswith(wl_normalized):
                return True

        return False

    def _is_approved(self, file_path: str) -> bool:
        """检查文件是否已被用户批准"""
        normalized = self._normalize_path(file_path)

        for approved in self.approved_paths:
            approved_normalized = self._normalize_path(approved)
            if normalized.startswith(approved_normalized):
                return True

        return False

    def _ask_user(self, file_path: str, operation: str) -> bool:
        """询问用户是否允许操作"""
        if self.ask_callback:
            return self.ask_callback(file_path, operation)

        # 如果没有设置回调，默认拒绝
        return False

    def set_ask_callback(self, callback: Callable[[str, str], bool]) -> None:
        """
        设置询问用户的回调函数

        Args:
            callback: 函数签名 (file_path: str, operation: str) -> bool
        """
        self.ask_callback = callback

    def check_permission(self, file_path: str, operation: str = "write") -> bool:
        """
        检查是否有权限执行操作

        Args:
            file_path: 文件路径
            operation: 操作类型 ("read", "write", "delete", "execute")

        Returns:
            True 表示允许，False 表示拒绝
        """
        # 1. 检查是否在工作区内（工作区外一律拒绝）
        if not self._is_in_workspace(file_path):
            return False

        # 2. 检查白名单（高权限，无需询问）
        if self._is_in_whitelist(file_path):
            return True

        # 3. 工作区内但不在白名单：每次都询问
        return self._ask_user(file_path, operation)

    def remember_approval(self, file_path: str) -> None:
        """记住用户的批准"""
        normalized = self._normalize_path(file_path)

        if normalized not in self.approved_paths:
            self.approved_paths.append(normalized)
            self._save_approved_paths()

    def revoke_approval(self, file_path: str) -> None:
        """撤销用户的批准"""
        normalized = self._normalize_path(file_path)

        if normalized in self.approved_paths:
            self.approved_paths.remove(normalized)
            self._save_approved_paths()

    def get_approved_paths(self) -> List[str]:
        """获取所有已批准的路径"""
        return self.approved_paths.copy()

    def get_workspace_paths(self) -> List[str]:
        """获取工作区路径"""
        return self.config.get("workspace", {}).get("paths", []).copy()

    def add_to_whitelist(self, file_path: str) -> bool:
        """添加路径到白名单"""
        try:
            whitelist = self.config.get("whitelist", {}).get("paths", [])
            normalized = self._normalize_path(file_path)

            if normalized not in whitelist:
                whitelist.append(normalized)
                self.config["whitelist"]["paths"] = whitelist
                self._save_config()
                return True

            return False
        except Exception as e:
            print(f"[错误] 添加白名单失败: {e}")
            return False

    def remove_from_whitelist(self, file_path: str) -> bool:
        """从白名单移除路径"""
        try:
            whitelist = self.config.get("whitelist", {}).get("paths", [])
            normalized = self._normalize_path(file_path)

            if normalized in whitelist:
                whitelist.remove(normalized)
                self.config["whitelist"]["paths"] = whitelist
                self._save_config()
                return True

            return False
        except Exception as e:
            print(f"[错误] 移除白名单失败: {e}")
            return False

    def get_whitelist(self) -> List[str]:
        """获取白名单"""
        return self.config.get("whitelist", {}).get("paths", []).copy()

    def _save_config(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[错误] 保存配置文件失败: {e}")

    def reload_config(self) -> None:
        """重新加载配置"""
        self.config = self._load_config()
        self.approved_paths = self._load_approved_paths()

    def get_config(self) -> dict:
        """获取完整配置"""
        return self.config.copy()

    def add_workspace_path(self, path: str) -> bool:
        """添加工作区路径"""
        try:
            workspace_paths = self.config.get("workspace", {}).get("paths", [])
            normalized = self._normalize_path(path)
            if normalized not in workspace_paths:
                workspace_paths.append(normalized)
                self.config["workspace"]["paths"] = workspace_paths
                self._save_config()
                return True
            return False
        except Exception as e:
            print(f"[错误] 添加工作区路径失败: {e}")
            return False

    def remove_workspace_path(self, path: str) -> bool:
        """移除工作区路径"""
        try:
            workspace_paths = self.config.get("workspace", {}).get("paths", [])
            normalized = self._normalize_path(path)
            if normalized in workspace_paths:
                workspace_paths.remove(normalized)
                self.config["workspace"]["paths"] = workspace_paths
                self._save_config()
                return True
            return False
        except Exception as e:
            print(f"[错误] 移除工作区路径失败: {e}")
            return False
