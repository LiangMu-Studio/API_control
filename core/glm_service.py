"""
GLM 模型服务 - 统一使用 GLM 4.6，支持不同思考模式的智能配置
"""

import json
from typing import Dict, List, Optional, Any
from enum import Enum


class GLMThinkingMode(Enum):
    """GLM 思考模式枚举"""

    FAST = "fast"  # 快速模式 - 快速响应
    BALANCED = "balanced"  # 均衡模式 - 性能与质量平衡
    DEEP = "deep"  # 深度思考模式 - 深度推理
    CREATIVE = "creative"  # 创意模式 - 创意内容生成
    PRECISE = "precise"  # 精确模式 - 高精度输出


class GLMModelConfig:
    """GLM 4.6 模型配置类 - 统一使用 GLM 4.6 模型名"""

    # 统一使用 GLM 4.6，但支持不同思考模式的配置
    MODEL_MODES = {
        "fast": {
            "name": "GLM 4.6 快速模式",
            "description": "快速响应模式，适合简单对话和快速问答",
            "temperature": 0.7,
            "max_tokens": 12000,
            "top_p": 0.9,
            "thinking_mode": "fast",
            "recommended_use": ["快速问答", "日常对话", "简单文本处理"],
            "system_prompt": "你是GLM 4.6，请快速准确地回答用户问题，保持简洁高效。",
        },
        "balanced": {
            "name": "GLM 4.6 均衡模式",
            "description": "性能与质量平衡的模式，适合大多数场景",
            "temperature": 0.5,
            "max_tokens": 12000,
            "top_p": 0.8,
            "thinking_mode": "balanced",
            "recommended_use": ["通用对话", "内容创作", "文档处理"],
            "system_prompt": "你是GLM 4.6，请平衡回答的质量和速度，提供准确且有深度的回答。",
        },
        "deep": {
            "name": "GLM 4.6 深度思考模式",
            "description": "深度推理和分析模式，适合复杂问题解决",
            "temperature": 0.3,
            "max_tokens": 32000,
            "top_p": 0.7,
            "thinking_mode": "deep",
            "recommended_use": ["复杂推理", "代码编写", "数据分析", "学术论文"],
            "system_prompt": "你是GLM 4.6，请进行深度思考和分析，从多个角度思考问题，提供详细的推理过程和全面的答案。",
        },
        "creative": {
            "name": "GLM 4.6 创意模式",
            "description": "创意激发模式，适合创作和头脑风暴",
            "temperature": 0.8,
            "max_tokens": 12000,
            "top_p": 0.9,
            "thinking_mode": "creative",
            "recommended_use": ["创意写作", "头脑风暴", "内容创作", "艺术创作"],
            "system_prompt": "你是GLM 4.6，发挥你的创造力，提供富有创意和想象力的回答。",
        },
        "precise": {
            "name": "GLM 4.6 精确模式",
            "description": "高精度输出模式，确保准确性和专业性",
            "temperature": 0.2,
            "max_tokens": 12000,
            "top_p": 0.6,
            "thinking_mode": "precise",
            "recommended_use": ["技术文档", "专业分析", "数据报告", "精确翻译"],
            "system_prompt": "你是GLM 4.6，请提供精确、准确、高可信度的回答，确保每个细节都准确无误。",
        },
    }

    @classmethod
    def get_mode_info(cls, mode: str) -> Optional[Dict[str, Any]]:
        """获取思考模式信息"""
        return cls.MODEL_MODES.get(mode)

    @classmethod
    def get_all_modes(cls) -> List[Dict[str, Any]]:
        """获取所有思考模式信息"""
        modes = []
        for mode_key, config in cls.MODEL_MODES.items():
            modes.append(
                {
                    "id": mode_key,
                    "name": config["name"],
                    "description": config["description"],
                    "temperature": config["temperature"],
                    "max_tokens": config["max_tokens"],
                    "top_p": config["top_p"],
                    "thinking_mode": config["thinking_mode"],
                    "recommended_use": config["recommended_use"],
                }
            )
        return modes

    @classmethod
    def get_system_prompt_for_mode(cls, thinking_mode: str) -> str:
        """根据思考模式获取系统提示"""
        mode_info = cls.get_mode_info(thinking_mode)
        return mode_info.get("system_prompt", "") if mode_info else ""


class GLMRequestBuilder:
    """GLM 请求构建器 - 基于 glm-4.7 模型"""

    def __init__(self, model_name: str = "glm-4.7"):
        self.model_name = model_name

    def build_request(
        self,
        messages: List[Dict[str, str]],
        thinking_mode: str = "balanced",
        temperature: float = None,
        max_tokens: int = None,
        top_p: float = None,
    ) -> Dict[str, Any]:
        """构建GLM 4.6 API请求"""

        # 获取模式配置
        mode_info = GLMModelConfig.get_mode_info(thinking_mode)
        if not mode_info:
            mode_info = GLMModelConfig.get_mode_info("balanced")

        # 使用模式默认参数或覆盖参数
        if temperature is None:
            temperature = mode_info["temperature"]
        if max_tokens is None:
            max_tokens = mode_info["max_tokens"]
        if top_p is None:
            top_p = mode_info["top_p"]

        # 构建基础请求
        request = {
            "model": self.model_name,  # 统一使用 glm-4.7
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }

        # 根据思考模式添加特殊参数
        thinking_mode_value = mode_info["thinking_mode"]

        if thinking_mode_value == "deep":
            # 深度思考模式配置
            request.update(
                {
                    "thinking_mode": "deep",
                    "temperature": max(0.1, temperature - 0.1),  # 进一步降低温度
                    "max_tokens": int(max_tokens * 1.5),  # 增加输出长度
                }
            )
        elif thinking_mode_value == "fast":
            # 快速模式配置
            request.update(
                {
                    "thinking_mode": "fast",
                    "temperature": min(0.9, temperature + 0.1),  # 提高温度
                    "max_tokens": int(max_tokens * 0.7),  # 减少输出长度
                }
            )
        elif thinking_mode_value == "creative":
            # 创意模式配置
            request.update(
                {
                    "temperature": min(1.0, temperature + 0.1),  # 提高温度
                    "top_p": min(1.0, top_p + 0.1),  # 提高top_p
                    "presence_penalty": 0.3,  # 增加重复惩罚，鼓励创新
                }
            )
        elif thinking_mode_value == "precise":
            # 精确模式配置
            request.update(
                {
                    "temperature": max(0.1, temperature - 0.1),  # 降低温度
                    "top_p": max(0.1, top_p - 0.1),  # 降低top_p
                    "frequency_penalty": 0.2,  # 减少重复，提高精确性
                }
            )

        return request

    def get_system_prompt_for_mode(self, thinking_mode: str) -> str:
        """根据思考模式获取系统提示"""
        return GLMModelConfig.get_system_prompt_for_mode(thinking_mode)


class GLMModelManager:
    """GLM 4.6 模型管理器 - 统一管理不同思考模式"""

    def __init__(self):
        self.request_builder = GLMRequestBuilder()

    def get_request_builder(self, model_name: str = "glm-4.7") -> GLMRequestBuilder:
        """获取请求构建器"""
        return GLMRequestBuilder(model_name)

    def get_all_models(self) -> List[Dict[str, Any]]:
        """获取所有GLM模型信息（统一使用 glm-4.7，显示不同模式）"""
        modes = GLMModelConfig.get_all_modes()
        models = []
        for mode in modes:
            models.append(
                {
                    "id": f"glm-4.7-{mode['id']}",
                    "name": mode["name"],
                    "description": mode["description"],
                    "model_name": "glm-4.7",  # 统一使用 glm-4.7
                    "mode": mode["id"],  # 思考模式
                    "temperature": mode["temperature"],
                    "max_tokens": mode["max_tokens"],
                    "top_p": mode["top_p"],
                    "thinking_mode": mode["thinking_mode"],
                    "recommended_use": mode["recommended_use"],
                }
            )
        return models

    def recommend_mode_for_task(
        self, task_type: str, complexity: str = "medium"
    ) -> str:
        """根据任务类型推荐思考模式"""
        recommendations = {
            "simple": {"fast": "fast", "medium": "balanced", "complex": "balanced"},
            "content_creation": {
                "fast": "balanced",
                "medium": "creative",
                "complex": "creative",
            },
            "code": {"fast": "balanced", "medium": "deep", "complex": "deep"},
            "analysis": {"fast": "balanced", "medium": "deep", "complex": "deep"},
            "writing": {
                "fast": "balanced",
                "medium": "creative",
                "complex": "creative",
            },
            "research": {"fast": "balanced", "medium": "deep", "complex": "deep"},
        }

        return recommendations.get(task_type, {}).get(complexity, "balanced")


# 全局实例
glm_model_manager = GLMModelManager()
