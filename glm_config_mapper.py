"""GLM模型配置映射器 - 将thinking_mode映射到对应的config配置"""

GLM_MODELS = {
    'fast': {
        'label': 'GLM_Fast',
        'thinking_mode': 'fast',
        'temperature': 0.7,
        'max_tokens': 2000
    },
    'balanced': {
        'label': 'GLM_Balanced',
        'thinking_mode': 'balanced',
        'temperature': 0.5,
        'max_tokens': 3000
    },
    'deep': {
        'label': 'GLM_Deep',
        'thinking_mode': 'deep',
        'temperature': 0.3,
        'max_tokens': 4000
    },
    'creative': {
        'label': 'GLM_Creative',
        'thinking_mode': 'creative',
        'temperature': 0.8,
        'max_tokens': 3000
    },
    'precise': {
        'label': 'GLM_Precise',
        'thinking_mode': 'precise',
        'temperature': 0.2,
        'max_tokens': 2500
    }
}

def get_glm_config(thinking_mode):
    """根据thinking_mode获取对应的GLM配置"""
    return GLM_MODELS.get(thinking_mode)

def get_glm_models():
    """获取所有GLM模型列表"""
    return list(GLM_MODELS.keys())
