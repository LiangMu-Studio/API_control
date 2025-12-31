"""系统提示词管理"""

import json
from pathlib import Path


def get_system_prompt():
    """获取系统提示词"""
    default_prompt = """1. 优先直接回答用户的问题。只有当用户明确要求你执行某个操作（如创建文件、修改系统等）时，才使用可用的工具。
2. 除非用户明确指定回复语言，否则用户用什么语言提问，就用什么语言回复。
3. 只在用户明确要求时才调用工具。"""

    config_path = Path.home() / ".ai_talk" / "system_prompt.json"

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('system_prompt', default_prompt)
        except Exception:
            pass

    return default_prompt
