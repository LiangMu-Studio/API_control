"""提示词管理系统"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class PromptTemplate:
    """提示词模板"""

    def __init__(self, id: str, name: str, content: str, description: str = "",
                 tags: List[str] = None, is_builtin: bool = False, category: str = "", default_id: str = ""):
        self.id = id
        self.name = name
        self.content = content
        self.description = description
        self.tags = tags or []
        self.is_builtin = is_builtin
        self.category = category
        self.default_id = default_id  # 用于标识默认提示词
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'description': self.description,
            'tags': self.tags,
            'is_builtin': self.is_builtin,
            'category': self.category,
            'default_id': self.default_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PromptTemplate':
        prompt = cls(
            data['id'],
            data['name'],
            data['content'],
            data.get('description', ''),
            data.get('tags', []),
            data.get('is_builtin', False),
            data.get('category', ''),
            data.get('default_id', '')
        )
        prompt.created_at = data.get('created_at', prompt.created_at)
        prompt.updated_at = data.get('updated_at', prompt.updated_at)
        return prompt


class PromptManager:
    """提示词管理器"""

    SYSTEM_PROMPTS = {
        'system_1': {
            'name': '优先直接回答用户的问题',
            'content': '1. 优先直接回答用户的问题。只有当用户明确要求你执行某个操作（如创建文件、修改系统等）时，才使用可用的工具。',
            'description': '系统指令',
            'category': '强制执行',
            'tags': ['系统'],
            'is_system': True
        },
        'system_2': {
            'name': '语言匹配原则',
            'content': '2. 除非用户明确指定回复语言，否则用户用什么语言提问，就用什么语言回复。',
            'description': '系统指令',
            'category': '强制执行',
            'tags': ['系统'],
            'is_system': True
        },
        'system_3': {
            'name': '遵循用户明确指示',
            'content': '3. 遵循用户的明确指示，不去修改、变更用户未提及需要更改的地方。',
            'description': '系统指令',
            'category': '强制执行',
            'tags': ['系统'],
            'is_system': True
        }
    }

    BUILTIN_PROMPTS = {
        'blank': {
            'name': '空白',
            'content': '',
            'description': '无提示词',
            'category': '默认',
            'tags': ['默认']
        },
        'coding_general': {
            'name': '通用编程',
            'content': '你是一个专业的编程助手。提供高质量的代码示例和解释。遵循最佳实践和设计模式。考虑性能、安全性和可维护性。提供完整的、可运行的代码。',
            'description': '编程',
            'category': '编程',
            'tags': ['编程']
        },
        'coding_debug': {
            'name': '代码调试',
            'content': '你是一个代码调试专家。帮助用户找出代码中的问题。提供清晰的错误分析和解决方案。逐步解释问题的原因和修复方法。',
            'description': '编程',
            'category': '编程',
            'tags': ['编程']
        },
        'coding_review': {
            'name': '代码审查',
            'content': '你是一个资深的代码审查员。分析代码质量、可读性和性能。提供具体的改进建议。指出潜在的问题和优化机会。',
            'description': '编程',
            'category': '编程',
            'tags': ['编程']
        },
        'writing_article': {
            'name': '文章写作',
            'content': '你是一个专业的文章写手。帮助用户撰写高质量的文章。确保逻辑清晰、表达准确。提供结构建议和内容优化。',
            'description': '写作',
            'category': '写作',
            'tags': ['写作']
        },
        'writing_creative': {
            'name': '创意写作',
            'content': '你是一个创意写作专家。帮助用户创作故事、诗歌或其他创意内容。提供灵感和创意建议。确保内容生动有趣。',
            'description': '写作',
            'category': '写作',
            'tags': ['写作']
        },
        'writing_edit': {
            'name': '文本编辑',
            'content': '你是一个专业的编辑。帮助用户改进文本质量。检查语法、拼写和标点。优化表达方式和逻辑结构。',
            'description': '写作',
            'category': '写作',
            'tags': ['写作']
        },
        'analysis_data': {
            'name': '数据分析',
            'content': '你是一个数据分析专家。深入分析数据和趋势。提供数据支持的观点和结论。用清晰的方式解释复杂的数据。',
            'description': '分析',
            'category': '分析',
            'tags': ['分析']
        },
        'analysis_research': {
            'name': '研究分析',
            'content': '你是一个研究分析员。帮助用户进行深入的研究和分析。总结关键要点和发现。提供基于证据的建议。',
            'description': '分析',
            'category': '分析',
            'tags': ['分析']
        },
        'analysis_summary': {
            'name': '内容总结',
            'content': '你是一个内容总结专家。快速提取关键信息。用简洁的方式总结复杂内容。突出重点和核心观点。',
            'description': '分析',
            'category': '分析',
            'tags': ['分析']
        }
    }

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path.home() / ".ai_talk")
        self.prompt_dir = self.data_dir / "prompts"
        self.prompt_dir.mkdir(parents=True, exist_ok=True)
        self.prompts: Dict[str, PromptTemplate] = {}
        self.default_prompt_id = "blank"
        self._load_all()

    def _load_all(self) -> None:
        """加载所有提示词"""
        # 加载系统提示词
        for idx, (prompt_id, data) in enumerate(self.SYSTEM_PROMPTS.items(), 1):
            prompt = PromptTemplate(
                prompt_id,
                data['name'],
                data['content'],
                data['description'],
                data['tags'],
                is_builtin=True,
                category=data.get('category', ''),
                default_id=f"system_{idx}"
            )
            self.prompts[prompt_id] = prompt

        # 加载内置提示词
        for idx, (prompt_id, data) in enumerate(self.BUILTIN_PROMPTS.items(), 1):
            prompt = PromptTemplate(
                prompt_id,
                data['name'],
                data['content'],
                data['description'],
                data['tags'],
                is_builtin=True,
                category=data.get('category', ''),
                default_id=f"builtin_{idx}"
            )
            self.prompts[prompt_id] = prompt

        # 加载自定义提示词
        for file in self.prompt_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    prompt = PromptTemplate.from_dict(data)
                    self.prompts[prompt.id] = prompt
            except Exception as e:
                print(f"加载提示词失败 {file}: {e}")

    def get_prompt(self, prompt_id: str) -> Optional[PromptTemplate]:
        """获取提示词"""
        return self.prompts.get(prompt_id)

    def get_default_prompt(self) -> PromptTemplate:
        """获取默认提示词"""
        return self.prompts.get(self.default_prompt_id) or self.prompts.get('blank')

    def list_prompts(self) -> List[PromptTemplate]:
        """列出所有提示词"""
        return list(self.prompts.values())

    def list_by_category(self) -> Dict[str, List[PromptTemplate]]:
        """按分类列出提示词"""
        result = {}
        for prompt in self.prompts.values():
            category = prompt.category or '其他'
            if category not in result:
                result[category] = []
            result[category].append(prompt)

        # 确保"默认"分类中"空白"提示词排在最前面
        if '默认' in result:
            blank_prompts = [p for p in result['默认'] if p.id == 'blank']
            other_prompts = [p for p in result['默认'] if p.id != 'blank']
            result['默认'] = blank_prompts + other_prompts

        # 按顺序排列分类：强制执行 -> 默认 -> 其他 -> 新分类
        ordered_result = {}
        if '强制执行' in result:
            ordered_result['强制执行'] = result['强制执行']
        if '默认' in result:
            ordered_result['默认'] = result['默认']

        # 内置分类
        builtin_categories = {'强制执行', '默认', '编程', '写作', '分析', '其他'}
        for category in sorted(result.keys()):
            if category not in ordered_result and category in builtin_categories:
                ordered_result[category] = result[category]

        # 新分类排在最后
        for category in sorted(result.keys()):
            if category not in ordered_result:
                ordered_result[category] = result[category]

        return ordered_result

    def create_prompt(self, name: str, content: str, description: str = "",
                     tags: List[str] = None, category: str = "") -> PromptTemplate:
        """创建新提示词"""
        prompt_id = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        prompt = PromptTemplate(prompt_id, name, content, description, tags or [], category=category)
        self.prompts[prompt_id] = prompt
        self._save_prompt(prompt)
        return prompt

    def update_prompt(self, prompt_id: str, name: str = None, content: str = None,
                     description: str = None, tags: List[str] = None, category: str = None) -> bool:
        """更新提示词"""
        if prompt_id not in self.prompts:
            return False

        prompt = self.prompts[prompt_id]

        if name:
            prompt.name = name
        if content is not None:
            prompt.content = content
        if description is not None:
            prompt.description = description
        if tags is not None:
            prompt.tags = tags
        if category is not None:
            prompt.category = category

        prompt.updated_at = datetime.now().isoformat()
        self._save_prompt(prompt)
        return True

    def delete_prompt(self, prompt_id: str) -> bool:
        """删除提示词"""
        if prompt_id not in self.prompts:
            return False

        del self.prompts[prompt_id]
        file = self.prompt_dir / f"{prompt_id}.json"
        if file.exists():
            file.unlink()
        return True

    def reset_builtin_prompts(self) -> None:
        """恢复所有默认提示词到原始状态"""
        # 原始提示词的ID集合
        builtin_ids = set(self.SYSTEM_PROMPTS.keys()) | set(self.BUILTIN_PROMPTS.keys())

        # 删除原始提示词文件和内存中的提示词
        for prompt_id in builtin_ids:
            if prompt_id in self.prompts:
                del self.prompts[prompt_id]
            file = self.prompt_dir / f"{prompt_id}.json"
            if file.exists():
                file.unlink()

        # 重新加载所有默认提示词
        self._load_all()

    def _save_prompt(self, prompt: PromptTemplate) -> None:
        """保存提示词到文件"""
        file = self.prompt_dir / f"{prompt.id}.json"
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(prompt.to_dict(), f, ensure_ascii=False, indent=2)

    def export_prompt(self, prompt_id: str, export_path: Path) -> bool:
        """导出提示词"""
        prompt = self.prompts.get(prompt_id)
        if not prompt:
            return False

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(prompt.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"导出提示词失败: {e}")
            return False

    def import_prompt(self, import_path: Path) -> Optional[PromptTemplate]:
        """导入提示词"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                prompt = PromptTemplate.from_dict(data)
                self.prompts[prompt.id] = prompt
                self._save_prompt(prompt)
                return prompt
        except Exception as e:
            print(f"导入提示词失败: {e}")
            return None
