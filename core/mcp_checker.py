"""MCP 服务器状态检测模块"""

import subprocess
import json
from typing import Tuple


def check_npm_version() -> Tuple[bool, str]:
    """检查 npm 版本"""
    try:
        result = subprocess.run(['npm', '-v'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "npm not found"
    except Exception as e:
        return False, str(e)


def check_npx_available() -> bool:
    """检查 npx 是否可用"""
    try:
        result = subprocess.run(['npx', '-v'], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def check_mcp_package(package_name: str) -> Tuple[bool, str]:
    """检查 MCP 包是否已安装及版本"""
    try:
        result = subprocess.run(
            ['npm', 'list', '-g', package_name, '--json'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            deps = data.get('dependencies', {})
            if package_name in deps:
                ver = deps[package_name].get('version', 'unknown')
                return True, ver
        return False, "not installed"
    except Exception as e:
        return False, str(e)


def get_mcp_status(mcp_config: dict) -> dict:
    """获取单个 MCP 服务器状态"""
    name = mcp_config.get('name', '')
    command = mcp_config.get('command', 'npx')
    args = mcp_config.get('args', '')

    status = {
        'name': name,
        'installed': False,
        'version': '',
        'error': '',
    }

    # 从 args 提取包名
    if args:
        parts = args.split()
        for p in parts:
            if p.startswith('@') or (not p.startswith('-') and '/' in p):
                pkg = p.split('@')[0] if '@' in p and not p.startswith('@') else p
                installed, ver = check_mcp_package(pkg)
                status['installed'] = installed
                status['version'] = ver if installed else ''
                if not installed:
                    status['error'] = ver
                break

    return status


def get_all_mcp_status(mcp_list: list) -> list:
    """获取所有 MCP 服务器状态"""
    return [get_mcp_status(m) for m in mcp_list]
