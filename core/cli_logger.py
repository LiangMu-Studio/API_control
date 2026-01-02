"""CLI 启动日志模块"""

import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "data" / "cli_launch.log"
MAX_ENTRIES = 100


def log_cli_launch(config_name: str, cli_type: str, command: str, work_dir: str = None):
    """记录 CLI 启动"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(),
        "config": config_name,
        "cli": cli_type,
        "command": command,
        "workdir": work_dir or "",
    }
    entries = load_launch_log()
    entries.insert(0, entry)
    entries = entries[:MAX_ENTRIES]
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def load_launch_log() -> list:
    """加载启动日志"""
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def clear_launch_log():
    """清空日志"""
    if LOG_FILE.exists():
        LOG_FILE.unlink()
