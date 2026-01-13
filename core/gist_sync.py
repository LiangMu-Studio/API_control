"""GitHub Gist 配置同步模块"""

import json
import httpx
from typing import Tuple, Optional, Dict
from pathlib import Path

GIST_API = "https://api.github.com/gists"
GIST_FILENAME = "ai_cli_manager_config.json"


class GistSync:
    """GitHub Gist 同步管理器"""

    def __init__(self, token: str, gist_id: str = None):
        self.token = token
        self.gist_id = gist_id
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def upload(self, configs: list, prompts: dict = None, mcp_list: list = None) -> Tuple[bool, str]:
        """上传配置到 Gist"""
        data = {
            "configs": configs,
            "prompts": prompts or {},
            "mcp_list": mcp_list or [],
            "version": "1.0"
        }
        content = json.dumps(data, ensure_ascii=False, indent=2)

        payload = {
            "description": "AI CLI Manager Config Backup",
            "public": False,
            "files": {GIST_FILENAME: {"content": content}}
        }

        try:
            with httpx.Client(timeout=30) as client:
                if self.gist_id:
                    # 更新现有 Gist
                    resp = client.patch(f"{GIST_API}/{self.gist_id}", headers=self.headers, json=payload)
                else:
                    # 创建新 Gist
                    resp = client.post(GIST_API, headers=self.headers, json=payload)

                if resp.status_code in (200, 201):
                    result = resp.json()
                    self.gist_id = result.get("id")
                    return True, self.gist_id
                else:
                    return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, str(e)

    def download(self) -> Tuple[bool, Dict]:
        """从 Gist 下载配置"""
        if not self.gist_id:
            return False, {"error": "未设置 Gist ID"}

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(f"{GIST_API}/{self.gist_id}", headers=self.headers)

                if resp.status_code == 200:
                    result = resp.json()
                    files = result.get("files", {})
                    if GIST_FILENAME in files:
                        content = files[GIST_FILENAME].get("content", "{}")
                        data = json.loads(content)
                        return True, data
                    return False, {"error": "配置文件不存在"}
                elif resp.status_code == 404:
                    return False, {"error": "Gist 不存在"}
                else:
                    return False, {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return False, {"error": str(e)}

    def list_gists(self) -> list:
        """列出用户的所有 Gist，查找配置文件"""
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(GIST_API, headers=self.headers)
                if resp.status_code == 200:
                    gists = resp.json()
                    # 查找包含配置文件的 Gist
                    for gist in gists:
                        if GIST_FILENAME in gist.get("files", {}):
                            return [{"id": gist["id"], "description": gist.get("description", ""), "updated": gist.get("updated_at", "")}]
                    return []
        except Exception:
            pass
        return []


def load_sync_settings() -> dict:
    """加载同步设置"""
    path = Path(__file__).parent.parent / "data" / "sync.json"
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_sync_settings(settings: dict):
    """保存同步设置"""
    path = Path(__file__).parent.parent / "data" / "sync.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
