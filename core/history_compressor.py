"""智能分层压缩系统 - 本地语义分析 + 分段卡片"""

from typing import List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
import re
from collections import defaultdict, Counter
from core.token_counter import TokenCounter
from core.weight_manager import WeightManager


@dataclass
class CompressedMessage:
    """压缩后的消息"""
    original_content: str
    compressed_content: str
    keywords: List[str]
    is_user: bool
    timestamp: str
    importance_score: float
    original_tokens: int = 0
    compressed_tokens: int = 0

    def __post_init__(self):
        """初始化后计算 token 数"""
        if self.original_tokens == 0:
            self.original_tokens = TokenCounter.count_tokens(self.original_content)
        if self.compressed_tokens == 0:
            self.compressed_tokens = TokenCounter.count_tokens(self.compressed_content)


@dataclass
class ConversationCard:
    """对话卡片 - 代表一个话题段，支持多层版本"""
    card_id: str
    topic: str
    keywords: List[str]
    messages: List[CompressedMessage]
    start_time: str
    end_time: str
    importance_level: int  # 1-5，越近的话题级别越高
    dynamic_weight: float = 0.0  # 动态权重，用户提及时增加

    def to_dict(self):
        return {
            'card_id': self.card_id,
            'topic': self.topic,
            'keywords': self.keywords,
            'messages': [asdict(m) for m in self.messages],
            'start_time': self.start_time,
            'end_time': self.end_time,
            'importance_level': self.importance_level,
            'versions': self.get_versions()
        }

    def get_versions(self) -> Dict[str, str]:
        """获取卡片的多个版本"""
        keywords_str = '、'.join(self.keywords) if self.keywords else self.topic
        msg_count = len(self.messages)

        return {
            'minimal': f"[{self.topic}] {keywords_str}",
            'compact': f"[{self.topic}] {keywords_str} ({msg_count}条)",
            'summary': self._generate_summary(),
            'full': self._generate_full()
        }

    def get_tokens_stats(self) -> Dict[str, int]:
        """获取卡片的 token 统计"""
        original_total = sum(m.original_tokens for m in self.messages)
        compressed_total = sum(m.compressed_tokens for m in self.messages)

        return {
            'original_tokens': original_total,
            'compressed_tokens': compressed_total,
            'saved_tokens': original_total - compressed_total
        }

    def _generate_summary(self) -> str:
        """生成摘要版本"""
        summaries = []
        for msg in self.messages[:3]:  # 只取前3条
            summaries.append(msg.compressed_content)
        return '|'.join(summaries)

    def _generate_full(self) -> str:
        """生成完整版本"""
        full_parts = []
        for msg in self.messages:
            role = "用户" if msg.is_user else "助手"
            full_parts.append(f"[{role}] {msg.original_content}")
        return '\n'.join(full_parts)


class LocalCompressor:
    """本地压缩器 - 使用关键词和语义分析"""

    def __init__(self):
        self.stop_words = {
            '的', '了', '和', '是', '在', '我', '你', '他', '这', '那',
            '有', '没', '不', '很', '就', '也', '都', '要', '会', '可以',
            '吗', '呢', '啊', '哦', '嗯', '好', '对', '是的', '不是'
        }

    def compress_message(self, content: str, is_user: bool) -> CompressedMessage:
        """压缩单条消息"""
        keywords = self._extract_keywords(content)
        compressed = self._compress_text(content)
        importance = self._calculate_importance(content, keywords)

        return CompressedMessage(
            original_content=content,
            compressed_content=compressed,
            keywords=keywords,
            is_user=is_user,
            timestamp=datetime.now().isoformat(),
            importance_score=importance
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词 - 支持 jieba 分词"""
        try:
            import jieba
            words = jieba.cut(text)
        except ImportError:
            # 如果没有 jieba，使用正则表达式
            words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)

        keywords = [w for w in words if w not in self.stop_words and len(w) > 1]
        freq = Counter(keywords)
        return [w for w, _ in freq.most_common(5)]

    def _compress_text(self, text: str) -> str:
        """压缩文本 - 保留关键信息"""
        if len(text) <= 50:
            return text

        # 提取第一句和最后一句
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) == 1:
            return text[:50] + '...' if len(text) > 50 else text

        # 第一句 + 最后一句
        first = sentences[0][:30]
        last = sentences[-1][:30]
        return f"{first}...{last}"

    def _calculate_importance(self, text: str, keywords: List[str]) -> float:
        """计算重要性分数 (0-1)"""
        score = 0.0

        # 长度因素
        score += min(len(text) / 200, 0.3)

        # 关键词因素
        score += min(len(keywords) / 5, 0.3)

        # 特殊标记因素
        if any(mark in text for mark in ['重要', '关键', '必须', '一定', '重点']):
            score += 0.2

        # 问号因素（问题通常重要）
        if '？' in text or '?' in text:
            score += 0.2

        return min(score, 1.0)


class CardBuilder:
    """卡片构建器 - 将消息分组成话题卡片"""

    def __init__(self, compressor: LocalCompressor):
        self.compressor = compressor
        self.topic_keywords = defaultdict(list)

    def build_cards(self, messages: List[Dict]) -> List[ConversationCard]:
        """从消息列表构建卡片序列"""
        compressed_msgs = [
            self.compressor.compress_message(msg['content'], msg['role'] == 'user')
            for msg in messages
        ]

        # 分段：检测话题转换点
        segments = self._segment_messages(compressed_msgs)

        # 构建卡片
        cards = []
        for i, segment in enumerate(segments):
            card = self._create_card(segment, i, len(segments))
            cards.append(card)

        return cards

    def _segment_messages(
        self, messages: List[CompressedMessage]
    ) -> List[List[CompressedMessage]]:
        """根据语义相似度分段"""
        if not messages:
            return []

        segments = [[messages[0]]]
        current_keywords = set(messages[0].keywords)

        for msg in messages[1:]:
            msg_keywords = set(msg.keywords)

            if msg_keywords:
                union = current_keywords | msg_keywords
                similarity = len(current_keywords & msg_keywords) / len(union)
            else:
                similarity = 0

            if similarity < 0.3 and len(segments[-1]) > 2:
                segments.append([msg])
                current_keywords = msg_keywords
            else:
                segments[-1].append(msg)
                current_keywords.update(msg_keywords)

        return segments

    def _create_card(
        self, messages: List[CompressedMessage], index: int, total: int
    ) -> ConversationCard:
        """创建单个卡片"""
        importance_level = max(1, min(5, (index + 1) * 5 // total))

        all_keywords = []
        for msg in messages:
            all_keywords.extend(msg.keywords)

        top_keywords = [w for w, _ in Counter(all_keywords).most_common(3)]
        topic = '、'.join(top_keywords) if top_keywords else '对话'

        return ConversationCard(
            card_id=f"card_{index}",
            topic=topic,
            keywords=top_keywords,
            messages=messages,
            start_time=messages[0].timestamp,
            end_time=messages[-1].timestamp,
            importance_level=importance_level
        )


class HistoryCompressor:
    """完整的分层压缩系统"""

    def __init__(self):
        self.local_compressor = LocalCompressor()
        self.card_builder = CardBuilder(self.local_compressor)
        self.cards: List[ConversationCard] = []
        self.keyword_to_cards: Dict[str, List[int]] = {}  # 关键词到卡片索引的映射
        self.weight_manager = WeightManager()  # 权重管理器

    def process_messages(self, messages: List[Dict]) -> List[ConversationCard]:
        """处理消息，返回卡片序列"""
        self.cards = self.card_builder.build_cards(messages)
        self._build_keyword_index()
        self._load_weights()
        return self.cards

    def _load_weights(self):
        """从权重管理器加载权重"""
        for card in self.cards:
            card.dynamic_weight = self.weight_manager.get_weight(card.card_id)

    def _build_keyword_index(self):
        """构建关键词到卡片的索引"""
        self.keyword_to_cards.clear()
        for i, card in enumerate(self.cards):
            for keyword in card.keywords:
                if keyword not in self.keyword_to_cards:
                    self.keyword_to_cards[keyword] = []
                self.keyword_to_cards[keyword].append(i)

    def find_related_cards(self, text: str) -> List[int]:
        """查找与文本相关的卡片索引"""
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        related_indices = set()

        for word in words:
            if word in self.keyword_to_cards:
                related_indices.update(self.keyword_to_cards[word])

        return sorted(related_indices)

    def update_card_weight(self, current_message: str):
        """根据当前消息更新卡片权重"""
        related_indices = self.find_related_cards(current_message)
        for i in related_indices:
            card = self.cards[i]
            card.dynamic_weight += 0.5
            self.weight_manager.update_weight(card.card_id, 0.5)

    def get_api_context(self, current_message: str = "") -> List[Dict]:
        """获取用于 API 调用的上下文，支持关键词关联和动态权重"""
        context = []
        related_card_indices = self.find_related_cards(current_message) if current_message else []

        for i, card in enumerate(self.cards):
            is_current_topic = (i == len(self.cards) - 1)
            is_related = i in related_card_indices
            has_high_weight = card.dynamic_weight > 0

            if is_current_topic:
                # 当前话题：包含完整消息
                for msg in card.messages:
                    context.append({
                        'role': 'user' if msg.is_user else 'assistant',
                        'content': msg.original_content
                    })
            elif is_related or has_high_weight:
                # 相关话题或高权重：包含摘要版本
                versions = card.get_versions()
                context.append({
                    'role': 'user',
                    'content': f"[相关背景] {versions['summary']}"
                })
            else:
                # 无关话题：极简版本
                versions = card.get_versions()
                context.append({
                    'role': 'user',
                    'content': versions['minimal']
                })

        return context

    def get_cards_summary(self) -> str:
        """获取卡片序列的文本摘要"""
        summary_parts = []
        for card in self.cards:
            versions = card.get_versions()
            summary_parts.append(f"【{card.topic}】{versions['summary']}")
        return '\n'.join(summary_parts)

    def export_cards(self) -> List[Dict]:
        """导出卡片数据"""
        return [card.to_dict() for card in self.cards]

    def get_context_tokens(self, current_message: str = "") -> Dict[str, int]:
        """计算整个上下文的 token 消耗"""
        context = self.get_api_context(current_message)

        total_tokens = 0
        for msg in context:
            total_tokens += TokenCounter.count_tokens(msg['content'])

        # 加上当前消息
        current_msg_tokens = TokenCounter.count_tokens(current_message)

        return {
            'context_tokens': total_tokens,
            'current_message_tokens': current_msg_tokens,
            'total_tokens': total_tokens + current_msg_tokens
        }

    def get_compression_stats(self) -> Dict:
        """获取压缩统计信息"""
        original_total = 0
        compressed_total = 0

        for card in self.cards:
            stats = card.get_tokens_stats()
            original_total += stats['original_tokens']
            compressed_total += stats['compressed_tokens']

        saved = original_total - compressed_total
        ratio = (saved / original_total * 100) if original_total > 0 else 0

        return {
            'original_tokens': original_total,
            'compressed_tokens': compressed_total,
            'saved_tokens': saved,
            'compression_ratio': f"{ratio:.1f}%"
        }
