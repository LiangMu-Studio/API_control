"""系统接口 - 让 AI_talk 可以执行系统命令和修改文件"""

import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, List
import threading
import queue


class SystemInterface:
    """系统接口 - 执行命令、修改文件、读取后台线程"""

    def __init__(self):
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.background_thread = None
        self.running = False

    def execute_command(self, cmd: str, shell: bool = True) -> Dict[str, Any]:
        """执行系统命令"""
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                'status': 'success' if result.returncode == 0 else 'error',
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'error': '命令执行超时'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """读取文件"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {'status': 'error', 'error': f'文件不存在: {file_path}'}

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            return {
                'status': 'success',
                'file': file_path,
                'size': len(content),
                'content': content
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def write_file(self, file_path: str, content: str, append: bool = False) -> Dict[str, Any]:
        """写入文件"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            mode = 'a' if append else 'w'
            with open(path, mode, encoding='utf-8') as f:
                f.write(content)

            return {
                'status': 'success',
                'file': file_path,
                'mode': 'append' if append else 'write'
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def modify_json(self, file_path: str, updates: Dict) -> Dict[str, Any]:
        """修改 JSON 文件"""
        try:
            path = Path(file_path)

            # 读取现有数据
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}

            # 更新数据
            data.update(updates)

            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return {
                'status': 'success',
                'file': file_path,
                'updated_keys': list(updates.keys())
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def list_files(self, directory: str, pattern: str = '*') -> Dict[str, Any]:
        """列出目录中的文件"""
        try:
            path = Path(directory)
            if not path.exists():
                return {'status': 'error', 'error': f'目录不存在: {directory}'}

            files = list(path.glob(pattern))
            return {
                'status': 'success',
                'directory': directory,
                'count': len(files),
                'files': [str(f.relative_to(path)) for f in files]
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def start_background_task(self, cmd: str) -> Dict[str, Any]:
        """启动后台任务"""
        try:
            self.process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return {
                'status': 'started',
                'pid': self.process.pid,
                'command': cmd
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def get_background_output(self) -> Dict[str, Any]:
        """获取后台任务输出"""
        try:
            if not hasattr(self, 'process') or self.process is None:
                return {'status': 'error', 'error': '没有运行的后台任务'}

            # 非阻塞读取
            stdout, stderr = self.process.communicate(timeout=0.1)
            return_code = self.process.returncode

            return {
                'status': 'success',
                'stdout': stdout,
                'stderr': stderr,
                'returncode': return_code,
                'finished': return_code is not None
            }
        except subprocess.TimeoutExpired:
            return {
                'status': 'running',
                'message': '后台任务仍在运行'
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            import platform
            return {
                'status': 'success',
                'system': platform.system(),
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cwd': os.getcwd()
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def change_directory(self, path: str) -> Dict[str, Any]:
        """改变工作目录"""
        try:
            os.chdir(path)
            return {
                'status': 'success',
                'cwd': os.getcwd()
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
