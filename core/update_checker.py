"""GitHub 版本更新检查模块"""

import httpx
from typing import Tuple, Optional

GITHUB_REPO = "LiangMu-Studio/AI_CLI_Manager"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_update(current_version: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """检查是否有新版本

    Returns:
        (has_update, new_version, release_url)
    """
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(RELEASES_API)
            if resp.status_code == 200:
                data = resp.json()
                tag = data.get('tag_name', '').lstrip('v')
                url = data.get('html_url', '')
                if tag and _compare_versions(tag, current_version) > 0:
                    return True, tag, url
                return False, None, None
    except Exception:
        pass
    return False, None, None


def _compare_versions(v1: str, v2: str) -> int:
    """比较版本号，v1 > v2 返回 1，v1 < v2 返回 -1，相等返回 0"""
    def parse(v):
        return [int(x) for x in v.split('.') if x.isdigit()]
    p1, p2 = parse(v1), parse(v2)
    for a, b in zip(p1, p2):
        if a > b:
            return 1
        if a < b:
            return -1
    return len(p1) - len(p2)
