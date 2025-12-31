"""代码分析引擎 - 理解项目结构和代码依赖"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class CodeAnalyzer:
    """分析代码项目结构和依赖关系"""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.files: Dict[str, str] = {}  # 文件路径 -> 内容
        self.imports: Dict[str, Set[str]] = defaultdict(set)  # 文件 -> 导入的文件
        self.functions: Dict[str, List[str]] = defaultdict(list)  # 文件 -> 函数列表
        self.classes: Dict[str, List[str]] = defaultdict(list)  # 文件 -> 类列表

    def scan_project(self, extensions: List[str] = None) -> Dict[str, any]:
        """扫描项目"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go']

        file_count = 0
        for ext in extensions:
            for file_path in self.root_path.rglob(f'*{ext}'):
                if self._should_skip(file_path):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    rel_path = str(file_path.relative_to(self.root_path))
                    self.files[rel_path] = content
                    self._analyze_file(rel_path, content)
                    file_count += 1
                except Exception:
                    pass

        return {
            'status': 'success',
            'files_scanned': file_count,
            'total_lines': sum(len(c.split('\n')) for c in self.files.values())
        }

    def _should_skip(self, file_path: Path) -> bool:
        """检查是否应该跳过文件"""
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build'}
        return any(skip_dir in file_path.parts for skip_dir in skip_dirs)

    def _analyze_file(self, file_path: str, content: str):
        """分析单个文件"""
        # 提取导入
        self._extract_imports(file_path, content)
        # 提取函数
        self._extract_functions(file_path, content)
        # 提取类
        self._extract_classes(file_path, content)

    def _extract_imports(self, file_path: str, content: str):
        """提取导入语句"""
        # Python imports
        for match in re.finditer(r'from\s+([\w.]+)\s+import|import\s+([\w.]+)', content):
            module = match.group(1) or match.group(2)
            # 转换为文件路径
            module_path = module.replace('.', '/') + '.py'
            self.imports[file_path].add(module_path)

    def _extract_functions(self, file_path: str, content: str):
        """提取函数定义"""
        # Python functions
        for match in re.finditer(r'def\s+(\w+)\s*\(', content):
            self.functions[file_path].append(match.group(1))

    def _extract_classes(self, file_path: str, content: str):
        """提取类定义"""
        # Python classes
        for match in re.finditer(r'class\s+(\w+)', content):
            self.classes[file_path].append(match.group(1))

    def find_related_files(self, file_path: str, depth: int = 2) -> Set[str]:
        """找到相关文件"""
        related = {file_path}
        to_check = {file_path}
        checked = set()

        for _ in range(depth):
            new_to_check = set()
            for current_file in to_check:
                if current_file in checked:
                    continue
                checked.add(current_file)

                # 找导入这个文件的文件
                for other_file, imports in self.imports.items():
                    if current_file in imports or any(current_file.endswith(imp) for imp in imports):
                        related.add(other_file)
                        new_to_check.add(other_file)

                # 找这个文件导入的文件
                for imported in self.imports.get(current_file, set()):
                    for file_name in self.files.keys():
                        if file_name.endswith(imported):
                            related.add(file_name)
                            new_to_check.add(file_name)

            to_check = new_to_check

        return related

    def search_code(self, pattern: str, file_type: str = None) -> List[Tuple[str, int, str]]:
        """搜索代码"""
        results = []
        regex = re.compile(pattern, re.IGNORECASE)

        for file_path, content in self.files.items():
            if file_type and not file_path.endswith(file_type):
                continue

            for line_num, line in enumerate(content.split('\n'), 1):
                if regex.search(line):
                    results.append((file_path, line_num, line.strip()))

        return results

    def find_function_usage(self, function_name: str) -> List[Tuple[str, int]]:
        """找函数使用位置"""
        results = []
        pattern = re.compile(rf'\b{function_name}\s*\(')

        for file_path, content in self.files.items():
            for line_num, line in enumerate(content.split('\n'), 1):
                if pattern.search(line):
                    results.append((file_path, line_num))

        return results

    def find_class_usage(self, class_name: str) -> List[Tuple[str, int]]:
        """找类使用位置"""
        results = []
        pattern = re.compile(rf'\b{class_name}\b')

        for file_path, content in self.files.items():
            for line_num, line in enumerate(content.split('\n'), 1):
                if pattern.search(line):
                    results.append((file_path, line_num))

        return results

    def get_project_structure(self) -> Dict:
        """获取项目结构"""
        structure = {
            'files': len(self.files),
            'functions': sum(len(f) for f in self.functions.values()),
            'classes': sum(len(c) for c in self.classes.values()),
            'file_list': sorted(self.files.keys()),
            'dependencies': dict(self.imports)
        }
        return structure

    def get_file_context(self, file_path: str) -> Dict:
        """获取文件的完整上下文"""
        if file_path not in self.files:
            return {'error': f'文件不存在: {file_path}'}

        related_files = self.find_related_files(file_path)

        return {
            'file': file_path,
            'content': self.files[file_path],
            'functions': self.functions.get(file_path, []),
            'classes': self.classes.get(file_path, []),
            'imports': list(self.imports.get(file_path, [])),
            'related_files': sorted(related_files),
            'lines': len(self.files[file_path].split('\n'))
        }
