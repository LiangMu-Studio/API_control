"""权重管理系统 - 持久化存储卡片权重"""

import json
from pathlib import Path
from typing import Dict


class WeightManager:
    """管理卡片的动态权重，支持持久化"""

    def __init__(self, weight_file: str = "data/card_weights.json"):
        self.weight_file = Path(weight_file)
        self.weights: Dict[str, float] = {}
        self.load()

    def load(self):
        """从文件加载权重"""
        if self.weight_file.exists():
            try:
                with open(self.weight_file, 'r', encoding='utf-8') as f:
                    self.weights = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.weights = {}
        else:
            self.weights = {}

    def save(self):
        """保存权重到文件"""
        self.weight_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.weight_file, 'w', encoding='utf-8') as f:
            json.dump(self.weights, f, ensure_ascii=False, indent=2)

    def update_weight(self, card_id: str, delta: float = 0.5):
        """更新卡片权重"""
        if card_id not in self.weights:
            self.weights[card_id] = 0.0
        self.weights[card_id] += delta
        self.save()

    def get_weight(self, card_id: str) -> float:
        """获取卡片权重"""
        return self.weights.get(card_id, 0.0)

    def reset_weight(self, card_id: str):
        """重置卡片权重"""
        if card_id in self.weights:
            self.weights[card_id] = 0.0
            self.save()

    def reset_all(self):
        """重置所有权重"""
        self.weights = {}
        self.save()

    def decay_weights(self, factor: float = 0.9):
        """衰减所有权重（模拟时间流逝）"""
        for card_id in self.weights:
            self.weights[card_id] *= factor
        self.save()
