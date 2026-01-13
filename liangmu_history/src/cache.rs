//! 历史记录缓存模块
//!
//! 使用 SQLite 缓存历史记录元数据，避免每次都扫描文件系统。
//! 完全复刻 DEV 版 (Tauri) 的缓存机制。

use rusqlite::{Connection, params};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use lru::LruCache;
use std::num::NonZeroUsize;

use crate::types::{SessionInfo, Project};

lazy_static::lazy_static! {
    /// 按 CLI 类型分开的数据库连接
    static ref DB_CONNECTIONS: Mutex<HashMap<String, Connection>> = Mutex::new(HashMap::new());
    /// LRU 内存缓存（会话详情）- 增大到 200
    static ref SESSION_CACHE: Mutex<LruCache<String, CachedSessionDetail>> =
        Mutex::new(LruCache::new(NonZeroUsize::new(200).unwrap()));
}

/// 缓存的会话详情
#[derive(Clone)]
pub struct CachedSessionDetail {
    pub messages_json: String,
    pub tool_stats_json: String,
}

/// 获取数据目录
fn get_data_dir() -> PathBuf {
    // 优先使用 exe 同级目录的 data
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let data_dir = exe_dir.join("data");
            if data_dir.exists() || std::fs::create_dir_all(&data_dir).is_ok() {
                return data_dir;
            }
        }
    }
    // 回退到用户数据目录
    dirs::data_dir()
        .map(|d| d.join("liangmu_history"))
        .unwrap_or_else(|| PathBuf::from("."))
}

/// 初始化数据库连接
fn init_db(cli_type: &str) -> rusqlite::Result<Connection> {
    let data_dir = get_data_dir();
    std::fs::create_dir_all(&data_dir).ok();

    let db_path = data_dir.join(format!("{}_history.db", cli_type));
    let conn = Connection::open(&db_path)?;

    // 优化设置
    conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")?;

    // 创建表结构（与 DEV 版完全一致）
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS history_cache (
            file_path TEXT PRIMARY KEY,
            cli_type TEXT NOT NULL,
            project_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            message_count INTEGER NOT NULL,
            user_turn_count INTEGER NOT NULL DEFAULT 0,
            first_timestamp TEXT,
            last_timestamp TEXT,
            file_mtime INTEGER NOT NULL,
            project_cwd TEXT,
            messages_json TEXT,
            tool_stats_json TEXT,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS trash (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            session_path TEXT NOT NULL,
            deleted_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS kv_store (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_history_project ON history_cache(project_id);
        CREATE INDEX IF NOT EXISTS idx_history_mtime ON history_cache(file_mtime);
        CREATE INDEX IF NOT EXISTS idx_history_cwd ON history_cache(project_cwd);
        "
    )?;

    // 添加 user_turn_count 列（如果不存在）- 兼容旧数据库
    conn.execute(
        "ALTER TABLE history_cache ADD COLUMN user_turn_count INTEGER NOT NULL DEFAULT 0",
        [],
    ).ok();

    Ok(conn)
}

/// 获取或创建数据库连接
pub fn get_db(cli_type: &str) -> rusqlite::Result<()> {
    let mut conns = DB_CONNECTIONS.lock().unwrap();
    if !conns.contains_key(cli_type) {
        let conn = init_db(cli_type)?;
        conns.insert(cli_type.to_string(), conn);
    }
    Ok(())
}

/// 从缓存查找匹配 cwd 的项目
pub fn find_project_by_cwd_cached(cli_type: &str, cwd: &str) -> Option<Project> {
    get_db(cli_type).ok()?;
    let conns = DB_CONNECTIONS.lock().ok()?;
    let conn = conns.get(cli_type)?;

    // 标准化路径
    let cwd_normalized = cwd.to_lowercase().replace('\\', "/");

    let mut stmt = conn.prepare(
        "SELECT project_id, project_cwd, COUNT(*) as session_count, MAX(last_timestamp) as last_activity
         FROM history_cache
         WHERE project_cwd IS NOT NULL
         GROUP BY project_id"
    ).ok()?;

    let projects: Vec<(String, Option<String>, usize, Option<String>)> = stmt
        .query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })
        .ok()?
        .filter_map(|r| r.ok())
        .collect();

    for (project_id, project_cwd, session_count, last_activity) in projects {
        if let Some(ref pcwd) = project_cwd {
            let pcwd_normalized = pcwd.to_lowercase().replace('\\', "/");
            if pcwd_normalized == cwd_normalized {
                return Some(Project {
                    id: project_id.clone(),
                    cwd: project_cwd,
                    last_modified: 0.0,
                    session_count,
                    last_activity,
                });
            }
        }
    }

    None
}

/// 从缓存加载项目会话列表
/// 复刻 DEV 版的完整过滤规则
pub fn load_project_from_cache(cli_type: &str, project_id: &str) -> Vec<SessionInfo> {
    if get_db(cli_type).is_err() {
        return Vec::new();
    }

    let conns = match DB_CONNECTIONS.lock() {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    let conn = match conns.get(cli_type) {
        Some(c) => c,
        None => return Vec::new(),
    };

    // 复刻 DEV 版过滤规则：
    // 1. message_count > 1 (过滤空会话)
    // 2. user_turn_count > 0 (过滤无用户消息的会话)
    // 3. 有有效时间戳
    let mut stmt = match conn.prepare(
        "SELECT session_id, file_path, message_count, first_timestamp, last_timestamp, project_cwd, user_turn_count
         FROM history_cache
         WHERE project_id = ?
           AND message_count > 1
           AND user_turn_count > 0
           AND (first_timestamp IS NOT NULL OR last_timestamp IS NOT NULL)
         ORDER BY last_timestamp DESC"
    ) {
        Ok(s) => s,
        Err(_) => return Vec::new(),
    };

    stmt.query_map([project_id], |row| {
        Ok(SessionInfo {
            id: row.get(0)?,
            file_path: row.get(1)?,
            message_count: row.get(2)?,
            first_timestamp: row.get(3)?,
            last_timestamp: row.get(4)?,
            cwd: row.get(5)?,
            user_turn_count: row.get(6)?,
            file_size: 0,
        })
    })
    .map(|iter| iter.filter_map(|r| r.ok()).collect())
    .unwrap_or_default()
}

/// 更新缓存条目
pub fn update_cache_entry(
    cli_type: &str,
    file_path: &str,
    project_id: &str,
    session_id: &str,
    message_count: usize,
    user_turn_count: usize,
    first_timestamp: Option<&str>,
    last_timestamp: Option<&str>,
    file_mtime: i64,
    project_cwd: Option<&str>,
) -> rusqlite::Result<()> {
    get_db(cli_type)?;
    let conns = DB_CONNECTIONS.lock().unwrap();
    let conn = conns.get(cli_type).ok_or(rusqlite::Error::InvalidQuery)?;

    conn.execute(
        "INSERT OR REPLACE INTO history_cache
         (file_path, cli_type, project_id, session_id, message_count, user_turn_count, first_timestamp, last_timestamp, file_mtime, project_cwd)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        params![file_path, cli_type, project_id, session_id, message_count, user_turn_count, first_timestamp, last_timestamp, file_mtime, project_cwd],
    )?;

    Ok(())
}

/// 检查缓存是否有效（文件未修改）
pub fn is_cache_valid(cli_type: &str, file_path: &str, file_mtime: i64) -> bool {
    if get_db(cli_type).is_err() {
        return false;
    }

    let conns = match DB_CONNECTIONS.lock() {
        Ok(c) => c,
        Err(_) => return false,
    };

    let conn = match conns.get(cli_type) {
        Some(c) => c,
        None => return false,
    };

    let cached_mtime: Option<i64> = conn
        .query_row(
            "SELECT file_mtime FROM history_cache WHERE file_path = ?",
            [file_path],
            |row| row.get(0),
        )
        .ok();

    cached_mtime.map_or(false, |m| m >= file_mtime)
}

/// 获取上次启动时间
pub fn get_last_startup_time(cli_type: &str) -> i64 {
    if get_db(cli_type).is_err() {
        return 0;
    }

    let conns = match DB_CONNECTIONS.lock() {
        Ok(c) => c,
        Err(_) => return 0,
    };

    let conn = match conns.get(cli_type) {
        Some(c) => c,
        None => return 0,
    };

    conn.query_row(
        "SELECT value FROM kv_store WHERE key = 'last_startup_time'",
        [],
        |row| row.get::<_, String>(0).map(|s| s.parse().unwrap_or(0)),
    )
    .unwrap_or(0)
}

/// 更新启动时间
pub fn update_startup_time(cli_type: &str) -> rusqlite::Result<()> {
    get_db(cli_type)?;
    let conns = DB_CONNECTIONS.lock().unwrap();
    let conn = conns.get(cli_type).ok_or(rusqlite::Error::InvalidQuery)?;

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    conn.execute(
        "INSERT OR REPLACE INTO kv_store (key, value) VALUES ('last_startup_time', ?)",
        [now.to_string()],
    )?;

    Ok(())
}

/// 删除缓存条目
pub fn delete_cache_entry(cli_type: &str, file_path: &str) -> rusqlite::Result<()> {
    get_db(cli_type)?;
    let conns = DB_CONNECTIONS.lock().unwrap();
    let conn = conns.get(cli_type).ok_or(rusqlite::Error::InvalidQuery)?;

    conn.execute("DELETE FROM history_cache WHERE file_path = ?", [file_path])?;
    Ok(())
}

/// 清空缓存
pub fn clear_cache(cli_type: &str) -> rusqlite::Result<usize> {
    get_db(cli_type)?;
    let conns = DB_CONNECTIONS.lock().unwrap();
    let conn = conns.get(cli_type).ok_or(rusqlite::Error::InvalidQuery)?;

    conn.execute("DELETE FROM history_cache", [])
}

/// LRU 内存缓存操作
pub fn get_session_from_memory(key: &str) -> Option<CachedSessionDetail> {
    SESSION_CACHE.lock().ok()?.get(key).cloned()
}

pub fn set_session_to_memory(key: String, detail: CachedSessionDetail) {
    if let Ok(mut cache) = SESSION_CACHE.lock() {
        cache.put(key, detail);
    }
}

pub fn clear_memory_cache() {
    if let Ok(mut cache) = SESSION_CACHE.lock() {
        cache.clear();
    }
}

/// 获取文件修改时间
pub fn get_file_mtime(path: &str) -> i64 {
    std::fs::metadata(path)
        .ok()
        .and_then(|m| m.modified().ok())
        .map(|t| t.duration_since(UNIX_EPOCH).unwrap_or_default().as_secs() as i64)
        .unwrap_or(0)
}
