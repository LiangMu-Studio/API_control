"""消息懒加载 - 按需加载消息"""

from typing import List, Callable, Optional


class LazyMessageLoader:
    """消息懒加载器 - 支持分页加载"""

    def __init__(self, total_messages: int, page_size: int = 50):
        self.total_messages = total_messages
        self.page_size = page_size
        self.loaded_messages = set()  # 已加载的消息索引
        self.current_page = 0

    def get_initial_messages(self) -> List[int]:
        """获取初始消息索引（最后50条）"""
        start = max(0, self.total_messages - self.page_size)
        indices = list(range(start, self.total_messages))
        self.loaded_messages.update(indices)
        return indices

    def load_more_messages(self) -> List[int]:
        """加载更多消息（向上翻页）"""
        start = max(0, self.current_page * self.page_size - self.page_size)
        end = self.current_page * self.page_size
        indices = list(range(start, end))
        self.loaded_messages.update(indices)
        self.current_page += 1
        return indices

    def is_loaded(self, index: int) -> bool:
        """检查消息是否已加载"""
        return index in self.loaded_messages

    def get_loaded_range(self) -> tuple:
        """获取已加载的范围"""
        if not self.loaded_messages:
            return (0, 0)
        return (min(self.loaded_messages), max(self.loaded_messages))

    def clear(self):
        """清空加载状态"""
        self.loaded_messages.clear()
        self.current_page = 0
