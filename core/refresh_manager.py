"""
自动刷新管理器 - 监控配置文件变化并自动刷新UI
"""

import os
import time
from pathlib import Path
from typing import Optional, Callable
from PySide6.QtCore import QObject, QTimer, QFileSystemWatcher, Signal


class ConfigRefreshManager(QObject):
    """配置文件自动刷新管理器"""

    # 信号定义
    config_changed = Signal()  # 配置文件变化信号
    refresh_triggered = Signal()  # 刷新触发信号

    def __init__(self, config_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.config_path = config_path or self._get_default_config_path()
        self.watcher = QFileSystemWatcher()
        self.refresh_timer = QTimer()
        self.refresh_delay = 1000  # 1秒延迟
        self.is_initialized = False
        self.last_modified_time = 0

        # 防抖设置
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._perform_refresh)

        # 状态跟踪
        self._is_running = False

        self.init()

    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        current_dir = Path(__file__).parent.parent
        return str(current_dir / "data" / "config.json")

    def init(self):
        """初始化监控器"""
        if not os.path.exists(self.config_path):
            print(f"警告: 配置文件不存在: {self.config_path}")
            return

        # 获取文件最后修改时间
        self.last_modified_time = os.path.getmtime(self.config_path)

        # 添加文件监控
        self.watcher.addPath(self.config_path)

        # 连接信号
        self.watcher.fileChanged.connect(self._on_file_changed)

        self.is_initialized = True
        self._is_running = True

        print(f"配置文件监控已启动: {self.config_path}")

    def _on_file_changed(self, path: str):
        """文件变化回调"""
        try:
            # 确保文件存在
            if not os.path.exists(path):
                return

            # 获取新的修改时间
            current_mtime = os.path.getmtime(path)

            # 防止重复触发（快速多次修改）
            if current_mtime <= self.last_modified_time:
                return

            # 更新最后修改时间
            self.last_modified_time = current_mtime

            print(f"检测到配置文件变化: {path}")

            # 延迟触发刷新，避免频繁刷新
            self.refresh_timer.start(self.refresh_delay)

        except Exception as e:
            print(f"处理文件变化时出错: {e}")

    def _perform_refresh(self):
        """执行刷新操作"""
        try:
            print("触发配置刷新...")
            self.config_changed.emit()
            self.refresh_triggered.emit()

        except Exception as e:
            print(f"执行刷新时出错: {e}")

    def stop(self):
        """停止监控"""
        if self._is_running:
            self.watcher.removePath(self.config_path)
            self.refresh_timer.stop()
            self._is_running = False
            print("配置文件监控已停止")

    def restart(self):
        """重新启动监控"""
        self.stop()
        self.init()

    def force_refresh(self):
        """强制刷新"""
        self._perform_refresh()

    def set_refresh_delay(self, delay: int):
        """设置刷新延迟（毫秒）"""
        self.refresh_delay = delay
        self.refresh_timer.setInterval(delay)

    def get_config_path(self) -> str:
        """获取配置文件路径"""
        return self.config_path

    def is_monitoring(self) -> bool:
        """是否正在监控"""
        return self._is_running and self.is_initialized


class GlobalRefreshManager:
    """全局刷新管理器 - 单例模式"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not GlobalRefreshManager._initialized:
            self.config_manager: Optional[ConfigRefreshManager] = None
            self.refresh_callbacks: list[Callable] = []
            GlobalRefreshManager._initialized = True

    def init_manager(self, config_path: Optional[str] = None):
        """初始化管理器"""
        if self.config_manager is None:
            self.config_manager = ConfigRefreshManager(config_path)
            self.config_manager.config_changed.connect(self._on_config_changed)

    def register_refresh_callback(self, callback: Callable):
        """注册刷新回调函数"""
        if callback not in self.refresh_callbacks:
            self.refresh_callbacks.append(callback)

    def unregister_refresh_callback(self, callback: Callable):
        """取消注册刷新回调函数"""
        if callback in self.refresh_callbacks:
            self.refresh_callbacks.remove(callback)

    def _on_config_changed(self):
        """配置变化回调"""
        # 执行所有注册的回调函数
        for callback in self.refresh_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"执行刷新回调时出错: {e}")

    def force_refresh(self):
        """强制刷新"""
        if self.config_manager:
            self.config_manager.force_refresh()

    def stop(self):
        """停止监控"""
        if self.config_manager:
            self.config_manager.stop()

    def restart(self):
        """重新启动监控"""
        if self.config_manager:
            self.config_manager.restart()


def get_global_refresh_manager() -> GlobalRefreshManager:
    """获取全局刷新管理器实例"""
    return GlobalRefreshManager()