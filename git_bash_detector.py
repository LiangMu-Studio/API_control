"""Git Bash 检测和配置模块"""
import os
import shutil
from pathlib import Path


def find_git_bash():
    """查找 Git Bash 的安装位置"""
    # 常见的 Git Bash 安装路径
    common_paths = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        os.path.expandvars(r"%PROGRAMFILES%\Git\bin\bash.exe"),
        os.path.expandvars(r"%PROGRAMFILES(x86)%\Git\bin\bash.exe"),
    ]

    # 检查常见路径
    for path in common_paths:
        if os.path.exists(path):
            return path

    # 尝试从 PATH 中查找
    bash_path = shutil.which('bash')
    if bash_path:
        return bash_path

    return None


def get_git_bash_command():
    """获取 Git Bash 命令"""
    bash_path = find_git_bash()
    if bash_path:
        return bash_path
    return None


def is_git_bash_available():
    """检查 Git Bash 是否可用"""
    return find_git_bash() is not None
