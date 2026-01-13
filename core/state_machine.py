"""状态机管理 - 清晰的状态转换规则"""

from enum import Enum
from typing import Callable, Optional


class AppState(Enum):
    """应用状态枚举"""
    IDLE = "idle"  # 空闲
    PROCESSING_FILES = "processing_files"  # 处理文件中
    SENDING = "sending"  # 发送消息中
    STREAMING = "streaming"  # 流式接收中
    ERROR = "error"  # 错误状态


class StateMachine:
    """状态机 - 管理应用状态转换"""

    def __init__(self):
        self.current_state = AppState.IDLE
        self.state_callbacks = {}  # 状态变化回调

    def register_callback(self, state: AppState, callback: Callable):
        """注册状态变化回调"""
        if state not in self.state_callbacks:
            self.state_callbacks[state] = []
        self.state_callbacks[state].append(callback)

    def transition(self, new_state: AppState, reason: str = "") -> bool:
        """状态转换"""
        if not self._is_valid_transition(self.current_state, new_state):
            print(f"[STATE] 非法转换: {self.current_state.value} -> {new_state.value}")
            return False

        old_state = self.current_state
        self.current_state = new_state
        print(f"[STATE] 转换: {old_state.value} -> {new_state.value} ({reason})")

        # 触发回调
        if new_state in self.state_callbacks:
            for callback in self.state_callbacks[new_state]:
                try:
                    callback()
                except Exception as e:
                    print(f"[STATE] 回调错误: {e}")

        return True

    def _is_valid_transition(self, from_state: AppState, to_state: AppState) -> bool:
        """检查转换是否合法"""
        valid_transitions = {
            AppState.IDLE: [AppState.PROCESSING_FILES, AppState.SENDING, AppState.ERROR],
            AppState.PROCESSING_FILES: [AppState.SENDING, AppState.ERROR, AppState.IDLE],
            AppState.SENDING: [AppState.STREAMING, AppState.ERROR, AppState.IDLE],
            AppState.STREAMING: [AppState.IDLE, AppState.ERROR],
            AppState.ERROR: [AppState.IDLE],
        }
        return to_state in valid_transitions.get(from_state, [])

    def is_idle(self) -> bool:
        """是否空闲"""
        return self.current_state == AppState.IDLE

    def is_processing(self) -> bool:
        """是否正在处理"""
        return self.current_state in (AppState.PROCESSING_FILES, AppState.SENDING, AppState.STREAMING)

    def reset(self):
        """重置为空闲状态"""
        self.transition(AppState.IDLE, "reset")
