"""压缩可视化工具 - 显示每条消息的多层压缩效果"""

from typing import List, Dict
from core.token_counter import TokenCounter


class CompressionVisualizer:
    """压缩可视化器 - 用于 DEBUG 查看压缩效果"""

    @staticmethod
    def visualize_message_compression(message: object) -> str:
        """可视化单条消息的压缩效果"""
        output = []
        output.append(f"\n{'='*80}")
        output.append(f"消息压缩详情")
        output.append(f"{'='*80}")

        # 原始消息
        original_tokens = message.original_tokens
        output.append(f"\n[原始] ({original_tokens}T)")
        output.append(f"  {message.original_content[:100]}...")

        # 压缩消息
        compressed_tokens = message.compressed_tokens
        saved = original_tokens - compressed_tokens
        ratio = (saved / original_tokens * 100) if original_tokens > 0 else 0
        output.append(f"\n[压缩] ({compressed_tokens}T, 节省 {saved}T, {ratio:.1f}%)")
        output.append(f"  {message.compressed_content[:100]}...")

        # 关键词
        output.append(f"\n[关键词] ({len(message.keywords)}个)")
        output.append(f"  {', '.join(message.keywords)}")

        # 重要性
        output.append(f"\n[重要性分数] {message.importance_score:.2f}")

        return '\n'.join(output)

    @staticmethod
    def visualize_card_versions(card: object) -> str:
        """可视化卡片的多个版本"""
        output = []
        output.append(f"\n{'='*80}")
        output.append(f"卡片: {card.topic}")
        output.append(f"{'='*80}")

        versions = card.get_versions()
        stats = card.get_tokens_stats()

        # 卡片统计
        output.append(f"\n[卡片统计]")
        output.append(f"  消息数: {len(card.messages)}")
        output.append(f"  原始 Token: {stats['original_tokens']}")
        output.append(f"  压缩后 Token: {stats['compressed_tokens']}")
        output.append(f"  节省 Token: {stats['saved_tokens']}")

        # 关键词
        output.append(f"\n[关键词]")
        output.append(f"  {', '.join(card.keywords)}")

        # 重要性
        output.append(f"\n[重要性级别] {card.importance_level}/5")

        # 多个版本
        output.append(f"\n[版本对比]")

        for version_name, version_content in versions.items():
            tokens = TokenCounter.count_tokens(version_content)
            output.append(f"\n  {version_name.upper()} ({tokens}T):")

            if len(version_content) > 150:
                output.append(f"    {version_content[:150]}...")
            else:
                output.append(f"    {version_content}")

        return '\n'.join(output)

    @staticmethod
    def visualize_all_cards(cards: List) -> str:
        """可视化所有卡片"""
        output = []
        output.append(f"\n{'='*80}")
        output.append(f"所有卡片压缩效果总览")
        output.append(f"{'='*80}\n")

        for i, card in enumerate(cards, 1):
            versions = card.get_versions()
            stats = card.get_tokens_stats()

            output.append(f"【卡片 {i}】{card.topic}")
            output.append(f"  消息数: {len(card.messages)} | 重要性: {'*' * card.importance_level}")
            output.append(f"  原始: {stats['original_tokens']}T → 压缩: {stats['compressed_tokens']}T (节省 {stats['saved_tokens']}T)")

            output.append(f"  版本:")
            output.append(f"    - minimal: {TokenCounter.count_tokens(versions['minimal'])}T")
            output.append(f"    - compact: {TokenCounter.count_tokens(versions['compact'])}T")
            output.append(f"    - summary: {TokenCounter.count_tokens(versions['summary'])}T")
            output.append(f"    - full: {TokenCounter.count_tokens(versions['full'])}T")
            output.append("")

        return '\n'.join(output)

    @staticmethod
    def visualize_context_generation(context: List[Dict], current_message: str) -> str:
        """可视化上下文生成过程"""
        output = []
        output.append(f"\n{'='*80}")
        output.append(f"上下文生成详情")
        output.append(f"{'='*80}\n")

        output.append(f"当前消息 ({TokenCounter.count_tokens(current_message)}T):")
        output.append(f"  {current_message}\n")

        output.append(f"上下文消息 ({len(context)}条):")

        total_context_tokens = 0
        for i, msg in enumerate(context, 1):
            tokens = TokenCounter.count_tokens(msg['content'])
            total_context_tokens += tokens
            role = "用户" if msg['role'] == 'user' else "助手"

            output.append(f"\n  [{i}] {role} ({tokens}T):")
            content = msg['content']
            if len(content) > 100:
                output.append(f"      {content[:100]}...")
            else:
                output.append(f"      {content}")

        total = total_context_tokens + TokenCounter.count_tokens(current_message)
        output.append(f"\n总计: {total_context_tokens}T (上下文) + {TokenCounter.count_tokens(current_message)}T (当前) = {total}T")

        return '\n'.join(output)


def print_compression_debug(compressor: object, current_message: str = ""):
    """打印完整的压缩调试信息"""
    visualizer = CompressionVisualizer()

    # 显示所有卡片
    print(visualizer.visualize_all_cards(compressor.cards))

    # 显示每个卡片的详细版本
    for card in compressor.cards:
        print(visualizer.visualize_card_versions(card))

    # 显示上下文生成
    if current_message:
        context = compressor.get_api_context(current_message)
        print(visualizer.visualize_context_generation(context, current_message))
