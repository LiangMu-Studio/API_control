"""Markdown渲染缓存 - LRU缓存加速"""

from collections import OrderedDict
from typing import Optional
import hashlib


class MarkdownCache:
    """Markdown渲染缓存 - LRU缓存"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _hash_content(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, content: str) -> Optional[str]:
        """获取缓存的HTML"""
        key = self._hash_content(content)
        if key in self.cache:
            self.hits += 1
            # 移到末尾（最近使用）
            self.cache.move_to_end(key)
            return self.cache[key]
        self.misses += 1
        return None

    def put(self, content: str, html: str):
        """存储HTML到缓存"""
        key = self._hash_content(content)
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = html

        # 超过大小限制时删除最旧的
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0

    def get_stats(self) -> dict:
        """获取缓存统计"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.get_hit_rate()
        }
