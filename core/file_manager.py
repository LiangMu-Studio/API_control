"""文件管理系统 - 像 Claude Code 一样直接操作文件"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List


class FileManager:
    """文件管理器 - 读取、修改、删除本地文件"""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)

    def read(self, file_path: str) -> Dict[str, Any]:
        """读取文件"""
        try:
            path = self.root_path / file_path
            if not path.exists():
                return {'error': f'文件不存在: {file_path}'}

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            return {
                'status': 'success',
                'file': file_path,
                'content': content,
                'size': len(content)
            }
        except Exception as e:
            return {'error': str(e)}

    def write(self, file_path: str, content: str) -> Dict[str, Any]:
        """写入文件"""
        try:
            path = self.root_path / file_path
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            return {
                'status': 'success',
                'file': file_path,
                'message': '文件已写入'
            }
        except Exception as e:
            return {'error': str(e)}

    def delete(self, file_path: str) -> Dict[str, Any]:
        """删除文件"""
        try:
            path = self.root_path / file_path
            if not path.exists():
                return {'error': f'文件不存在: {file_path}'}

            if path.is_file():
                path.unlink()
                return {
                    'status': 'success',
                    'file': file_path,
                    'message': '文件已删除'
                }
            else:
                return {'error': f'{file_path} 是目录，不是文件'}
        except Exception as e:
            return {'error': str(e)}

    def list_dir(self, dir_path: str = ".") -> Dict[str, Any]:
        """列出目录"""
        try:
            path = self.root_path / dir_path
            if not path.exists():
                return {'error': f'目录不存在: {dir_path}'}

            items = []
            for item in sorted(path.iterdir()):
                items.append({
                    'name': item.name,
                    'type': 'dir' if item.is_dir() else 'file',
                    'size': item.stat().st_size if item.is_file() else 0
                })

            return {
                'status': 'success',
                'directory': dir_path,
                'items': items,
                'count': len(items)
            }
        except Exception as e:
            return {'error': str(e)}

    def edit(self, file_path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """编辑文件（替换文本）"""
        try:
            path = self.root_path / file_path
            if not path.exists():
                return {'error': f'文件不存在: {file_path}'}

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            if old_text not in content:
                return {'error': f'找不到要替换的文本'}

            new_content = content.replace(old_text, new_text, 1)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return {
                'status': 'success',
                'file': file_path,
                'message': '文件已修改'
            }
        except Exception as e:
            return {'error': str(e)}

    def append(self, file_path: str, content: str) -> Dict[str, Any]:
        """追加内容到文件"""
        try:
            path = self.root_path / file_path
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'a', encoding='utf-8') as f:
                f.write(content)

            return {
                'status': 'success',
                'file': file_path,
                'message': '内容已追加'
            }
        except Exception as e:
            return {'error': str(e)}

    def exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        return (self.root_path / file_path).exists()

    def get_tree(self, dir_path: str = ".", max_depth: int = 3) -> Dict[str, Any]:
        """获取目录树"""
        def build_tree(path: Path, depth: int) -> Dict:
            if depth > max_depth:
                return {}

            items = {}
            try:
                for item in sorted(path.iterdir()):
                    if item.is_dir():
                        items[item.name] = build_tree(item, depth + 1)
                    else:
                        items[item.name] = 'file'
            except PermissionError:
                pass

            return items

        try:
            path = self.root_path / dir_path
            tree = build_tree(path, 0)
            return {
                'status': 'success',
                'directory': dir_path,
                'tree': tree
            }
        except Exception as e:
            return {'error': str(e)}
