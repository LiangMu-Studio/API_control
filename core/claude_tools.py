"""Claude 工具集 - 让 Claude 可以直接操作文件"""

import json
from core.file_manager import FileManager
from core.history_compressor import HistoryCompressor
from core.code_analyzer import CodeAnalyzer
from core.command_executor import CommandExecutor


class ClaudeTools:
    """为 Claude 提供的工具集"""

    def __init__(self, root_path: str = "."):
        self.file_manager = FileManager(root_path)
        self.compressor = HistoryCompressor()
        self.analyzer = CodeAnalyzer(root_path)
        self.executor = CommandExecutor(root_path)

    def get_tools_definition(self) -> list:
        """获取工具定义（用于 Claude API）"""
        return [
            {
                "name": "read_file",
                "description": "读取本地文件内容",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "write_file",
                "description": "写入或创建文件",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径"
                        },
                        "content": {
                            "type": "string",
                            "description": "文件内容"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            },
            {
                "name": "delete_file",
                "description": "删除文件",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "list_directory",
                "description": "列出目录内容",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dir_path": {
                            "type": "string",
                            "description": "目录路径，默认为当前目录"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "edit_file",
                "description": "编辑文件（替换文本）",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径"
                        },
                        "old_text": {
                            "type": "string",
                            "description": "要替换的文本"
                        },
                        "new_text": {
                            "type": "string",
                            "description": "新文本"
                        }
                    },
                    "required": ["file_path", "old_text", "new_text"]
                }
            },
            {
                "name": "analyze_compression",
                "description": "分析消息文件的压缩效果",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "消息 JSON 文件路径"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "scan_project",
                "description": "扫描项目结构和代码依赖",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "search_code",
                "description": "搜索代码中的模式",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "搜索模式（正则表达式）"
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "find_related_files",
                "description": "找到与某个文件相关的所有文件",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "文件路径"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "find_function_usage",
                "description": "找函数在代码中的使用位置",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "function_name": {
                            "type": "string",
                            "description": "函数名"
                        }
                    },
                    "required": ["function_name"]
                }
            },
            {
                "name": "execute_command",
                "description": "执行系统命令（如 git, npm, python 等）",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "get_current_dir",
                "description": "获取当前工作目录",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "change_dir",
                "description": "改变工作目录",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "目标目录路径"
                        }
                    },
                    "required": ["path"]
                }
            }
        ]

    def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """执行工具"""
        if tool_name == "read_file":
            return self.file_manager.read(tool_input["file_path"])

        elif tool_name == "write_file":
            return self.file_manager.write(
                tool_input["file_path"],
                tool_input["content"]
            )

        elif tool_name == "delete_file":
            return self.file_manager.delete(tool_input["file_path"])

        elif tool_name == "list_directory":
            dir_path = tool_input.get("dir_path", ".")
            return self.file_manager.list_dir(dir_path)

        elif tool_name == "edit_file":
            return self.file_manager.edit(
                tool_input["file_path"],
                tool_input["old_text"],
                tool_input["new_text"]
            )

        elif tool_name == "analyze_compression":
            file_path = tool_input["file_path"]
            result = self.file_manager.read(file_path)
            if 'error' in result:
                return result
            try:
                messages = json.loads(result['content'])
                self.compressor.process_messages(messages)
                stats = self.compressor.get_compression_stats()
                return {
                    'status': 'success',
                    'file': file_path,
                    'stats': stats,
                    'cards': len(self.compressor.cards)
                }
            except Exception as e:
                return {'error': str(e)}

        elif tool_name == "scan_project":
            return self.analyzer.scan_project()

        elif tool_name == "search_code":
            pattern = tool_input["pattern"]
            results = self.analyzer.search_code(pattern)
            return {
                'status': 'success',
                'pattern': pattern,
                'results': results[:20],
                'total': len(results)
            }

        elif tool_name == "find_related_files":
            file_path = tool_input["file_path"]
            related = self.analyzer.find_related_files(file_path)
            return {
                'status': 'success',
                'file': file_path,
                'related_files': sorted(related),
                'count': len(related)
            }

        elif tool_name == "find_function_usage":
            func_name = tool_input["function_name"]
            usage = self.analyzer.find_function_usage(func_name)
            return {
                'status': 'success',
                'function': func_name,
                'usage': usage,
                'count': len(usage)
            }

        elif tool_name == "execute_command":
            command = tool_input["command"]
            return self.executor.execute(command)

        elif tool_name == "get_current_dir":
            return {
                'status': 'success',
                'current_dir': self.executor.get_current_dir()
            }

        elif tool_name == "change_dir":
            path = tool_input["path"]
            return self.executor.change_dir(path)

        return {'error': f'未知工具: {tool_name}'}
