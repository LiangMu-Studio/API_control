# cython: language_level=3
# fast_scan.pyx - 高性能文件遍历模块
import os
import json
from pathlib import Path

def get_cwd_fast(str filepath):
    """快速读取 jsonl 文件中的 cwd"""
    cdef str line
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if '"cwd"' in line:
                    data = json.loads(line)
                    return data.get('payload', {}).get('cwd', '') or data.get('cwd', '')
    except:
        pass
    return ''

def scan_codex_sessions(str sessions_dir, int limit=0):
    """扫描 Codex 会话目录，返回 {cwd: mtime} 字典"""
    cdef dict cwd_map = {}
    cdef str year_name, month_name, day_name, fname
    cdef str year_path, month_path, day_path, fpath
    cdef str cwd
    cdef float mtime
    cdef int count = 0

    if not os.path.isdir(sessions_dir):
        return cwd_map

    years = sorted(os.listdir(sessions_dir), reverse=True)
    for year_name in years:
        year_path = os.path.join(sessions_dir, year_name)
        if not os.path.isdir(year_path):
            continue
        months = sorted(os.listdir(year_path), reverse=True)
        for month_name in months:
            month_path = os.path.join(year_path, month_name)
            if not os.path.isdir(month_path):
                continue
            days = sorted(os.listdir(month_path), reverse=True)
            for day_name in days:
                day_path = os.path.join(month_path, day_name)
                if not os.path.isdir(day_path):
                    continue
                for fname in os.listdir(day_path):
                    if not fname.endswith('.jsonl'):
                        continue
                    fpath = os.path.join(day_path, fname)
                    cwd = get_cwd_fast(fpath) or "未知目录"
                    mtime = os.path.getmtime(fpath)
                    if cwd not in cwd_map:
                        cwd_map[cwd] = mtime
                        count += 1
                        if limit > 0 and count >= limit:
                            return cwd_map
                    elif mtime > cwd_map[cwd]:
                        cwd_map[cwd] = mtime
    return cwd_map

def load_project_fast(str sessions_dir, str target_cwd):
    """快速加载指定 cwd 的会话，返回 {session_id: {file, last_timestamp}} 字典
    优化：使用 os.walk 一次遍历，减少系统调用
    """
    cdef dict result = {}
    cdef str root, fname, fpath
    cdef str cwd, session_id, last_ts
    cdef list dirs, files

    if not os.path.isdir(sessions_dir):
        return result

    for root, dirs, files in os.walk(sessions_dir):
        for fname in files:
            if not fname.endswith('.jsonl'):
                continue
            fpath = os.path.join(root, fname)
            cwd = get_cwd_fast(fpath)
            if cwd != target_cwd and (not cwd and target_cwd != "未知目录"):
                continue
            session_id = fname.replace("rollout-", "").replace(".jsonl", "")
            last_ts = get_last_timestamp_fast(fpath)
            result[session_id] = {'file': fpath, 'last_timestamp': last_ts}
    return result

def get_last_timestamp_fast(str filepath):
    """快速获取最后一条消息的时间戳"""
    cdef str line, last_ts = ''
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if '"timestamp"' in line:
                    try:
                        data = json.loads(line)
                        ts = data.get('timestamp')
                        if ts:
                            last_ts = ts
                    except:
                        pass
    except:
        pass
    return last_ts
