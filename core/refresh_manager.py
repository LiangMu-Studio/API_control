"""
自动刷新管理器 - 监控配置文件变化并自动刷新UI
"""

import os
import threading
from pathlib import Path
from typing import Optional, Callable, List


class ConfigRefreshManager:
    """配置文件自动刷新管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.refresh_delay = 1.0  # 1秒延迟
        self.is_initialized = False
        self.last_modified_time = 0
        self._is_running = False
        self._timer: Optional[threading.Timer] = None
        self._watch_thread: Optional[threading.Thread] = None
        # 回调函数
        self.on_config_changed: Callable[[], None] = None
        self.on_refresh_triggered: Callable[[], None] = None

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

        self.last_modified_time = os.path.getmtime(self.config_path)
        self.is_initialized = True
        self._is_running = True

        # 启动文件监控线程
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

        print(f"配置文件监控已启动: {self.config_path}")

    def _watch_loop(self):
        """文件监控循环"""
        while self._is_running:
            try:
                if os.path.exists(self.config_path):
                    current_mtime = os.path.getmtime(self.config_path)
                    if current_mtime > self.last_modified_time:
                        self.last_modified_time = current_mtime
                        print(f"检测到配置文件变化: {self.config_path}")
                        self._schedule_refresh()
            except Exception as e:
                print(f"监控文件时出错: {e}")
            threading.Event().wait(0.5)  # 每0.5秒检查一次

    def _schedule_refresh(self):
        """延迟触发刷新"""
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.refresh_delay, self._perform_refresh)
        self._timer.start()

    def _perform_refresh(self):
        """执行刷新操作"""
        try:
            print("触发配置刷新...")
            if self.on_config_changed:
                self.on_config_changed()
            if self.on_refresh_triggered:
                self.on_refresh_triggered()
        except Exception as e:
            print(f"执行刷新时出错: {e}")

    def stop(self):
        """停止监控"""
        if self._is_running:
            self._is_running = False
            if self._timer:
                self._timer.cancel()
            print("配置文件监控已停止")

    def restart(self):
        """重新启动监控"""
        self.stop()
        self.init()

    def force_refresh(self):
        """强制刷新"""
        self._perform_refresh()

    def set_refresh_delay(self, delay: float):
        """设置刷新延迟（秒）"""
        self.refresh_delay = delay

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
            self.refresh_callbacks: List[Callable] = []
            GlobalRefreshManager._initialized = True

    def init_manager(self, config_path: Optional[str] = None):
        """初始化管理器"""
        if self.config_manager is None:
            self.config_manager = ConfigRefreshManager(config_path)
            self.config_manager.on_config_changed = self._on_config_changed

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
