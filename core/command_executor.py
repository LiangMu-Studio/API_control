"""命令执行器 - 执行系统命令"""

import subprocess
import os
from typing import Dict


class CommandExecutor:
    """执行系统命令"""

    def __init__(self, cwd: str = "."):
        self.cwd = cwd

    def execute(self, command: str, timeout: int = 90) -> Dict:
        """执行命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                'status': 'success',
                'command': command,
                'stdout': result.stdout[:5000],
                'stderr': result.stderr[:5000],
                'return_code': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'command': command,
                'error': f'对话延迟生成失败：命令执行超时（{timeout}秒）'
            }
        except Exception as e:
            return {
                'status': 'error',
                'command': command,
                'error': str(e)
            }

    def get_current_dir(self) -> str:
        """获取当前目录"""
        return os.getcwd()

    def change_dir(self, path: str) -> Dict:
        """改变目录"""
        try:
            os.chdir(path)
            self.cwd = path
            return {
                'status': 'success',
                'current_dir': os.getcwd()
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
