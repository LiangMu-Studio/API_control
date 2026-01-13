"""Token 计数模块 - 估算消息的 token 消耗"""

import re


class TokenCounter:
    """Token 计数器 - 基于字符和词汇估算"""

    # 平均每个 token 的字符数（Claude 3.5 Sonnet 优化）
    # 中文：1 个汉字 ≈ 0.8 tokens (Claude 3.5 对中文压缩率很高)
    # 英文：1 个单词 ≈ 1.0 tokens
    # 标点符号：1 个 ≈ 0.5 tokens

    @staticmethod
    def count_tokens(text: str) -> int:
        """估算文本的 token 数"""
        if not text:
            return 0

        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        punctuation = len(re.findall(r'[^\w\s\u4e00-\u9fff]', text))
        spaces = len(re.findall(r'\s+', text))

        # 估算 token 数 (Claude 3.5 Sonnet 优化)
        tokens = (
            int(chinese_chars * 0.8) +  # Claude 3.5 中文优化
            int(english_words * 1.0) +  # 英文
            int(punctuation * 0.5) +    # 标点符号
            int(spaces * 0.1)           # 空格
        )

        return max(1, tokens)

    @staticmethod
    def format_tokens(tokens: int) -> str:
        """格式化 token 数显示"""
        if tokens < 1000:
            return f"{tokens}T"
        return f"{tokens / 1000:.1f}K"

    @staticmethod
    def compare_compression(original_text: str, compressed_text: str) -> dict:
        """比较压缩前后的 token 消耗"""
        original_tokens = TokenCounter.count_tokens(original_text)
        compressed_tokens = TokenCounter.count_tokens(compressed_text)
        ratio = (1 - compressed_tokens / original_tokens) * 100 if original_tokens > 0 else 0

        return {
            'original_tokens': original_tokens,
            'compressed_tokens': compressed_tokens,
            'saved_tokens': original_tokens - compressed_tokens,
            'compression_ratio': ratio
        }


class ConversationTokenCounter:
    """对话级别的 token 计数"""

    def __init__(self):
        self.message_tokens = {}  # 消息 ID -> token 数
        self.total_tokens = 0

    def add_message(self, message_id: str, content: str) -> int:
        """添加消息并计数"""
        tokens = TokenCounter.count_tokens(content)
        self.message_tokens[message_id] = tokens
        self.total_tokens += tokens
        return tokens

    def get_message_tokens(self, message_id: str) -> int:
        """获取消息的 token 数"""
        return self.message_tokens.get(message_id, 0)

    def get_total_tokens(self) -> int:
        """获取总 token 数"""
        return self.total_tokens

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self.message_tokens:
            return {
                'total_messages': 0,
                'total_tokens': 0,
                'avg_tokens_per_message': 0
            }

        return {
            'total_messages': len(self.message_tokens),
            'total_tokens': self.total_tokens,
            'avg_tokens_per_message': self.total_tokens // len(self.message_tokens),
            'max_tokens': max(self.message_tokens.values()),
            'min_tokens': min(self.message_tokens.values())
        }
