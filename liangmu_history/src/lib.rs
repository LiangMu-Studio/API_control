//! liangmu_history - 高性能历史记录解析器
//!
//! 为 AI CLI 工具（Claude、Codex 等）提供高性能的历史记录解析功能。
//! 通过 PyO3 暴露给 Python 使用。

mod cache;
mod provider;
mod providers;
mod types;

use pyo3::prelude::*;
use std::fs;
use std::path::Path;
use std::sync::OnceLock;

pub use provider::{CliHistoryProvider, ProviderRegistry};
pub use providers::{ClaudeProvider, CodexProvider};
pub use types::*;

// 全局 Provider 实例（懒加载）
static CLAUDE_PROVIDER: OnceLock<Option<ClaudeProvider>> = OnceLock::new();
static CODEX_PROVIDER: OnceLock<Option<CodexProvider>> = OnceLock::new();

fn get_claude_provider() -> Option<&'static ClaudeProvider> {
    CLAUDE_PROVIDER
        .get_or_init(|| ClaudeProvider::default())
        .as_ref()
}

fn get_codex_provider() -> Option<&'static CodexProvider> {
    CODEX_PROVIDER
        .get_or_init(|| CodexProvider::default())
        .as_ref()
}

// ==================== Python 绑定函数 ====================

/// 列出支持的 CLI 类型
#[pyfunction]
fn list_cli_types() -> Vec<&'static str> {
    let mut types = Vec::new();
    if get_claude_provider().is_some() {
        types.push("claude");
    }
    if get_codex_provider().is_some() {
        types.push("codex");
    }
    types
}

/// 列出项目
#[pyfunction]
#[pyo3(signature = (cli_type, limit=50))]
fn list_projects(cli_type: &str, limit: usize) -> PyResult<Vec<Project>> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            Ok(provider.list_projects(limit))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            Ok(provider.list_projects(limit))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 根据工作目录查找项目
#[pyfunction]
fn find_project_by_cwd(cli_type: &str, cwd: &str) -> PyResult<Option<Project>> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            Ok(provider.find_project_by_cwd(cwd))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            Ok(provider.find_project_by_cwd(cwd))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 加载项目的会话列表
#[pyfunction]
fn load_project(cli_type: &str, project_id: &str) -> PyResult<Vec<SessionInfo>> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            Ok(provider.load_project(project_id))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            Ok(provider.load_project(project_id))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 加载完整会话
#[pyfunction]
fn load_session(cli_type: &str, file_path: &str) -> PyResult<Option<Session>> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            Ok(provider.load_session(file_path))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            Ok(provider.load_session(file_path))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 分页加载会话
#[pyfunction]
#[pyo3(signature = (cli_type, file_path, first_turns=3, last_turns=3))]
fn load_session_paginated(
    cli_type: &str,
    file_path: &str,
    first_turns: usize,
    last_turns: usize,
) -> PyResult<Option<PaginatedMessages>> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            Ok(provider.load_session_paginated(file_path, first_turns, last_turns))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            Ok(provider.load_session_paginated(file_path, first_turns, last_turns))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 搜索会话
#[pyfunction]
#[pyo3(signature = (cli_type, keyword, limit=1000))]
fn search(cli_type: &str, keyword: &str, limit: usize) -> PyResult<Vec<SessionInfo>> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            Ok(provider.search(keyword, limit))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            Ok(provider.search(keyword, limit))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 删除会话（移动到回收站）
#[pyfunction]
fn delete_session(cli_type: &str, file_path: &str) -> PyResult<()> {
    match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.delete_session(file_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e))
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.delete_session(file_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e))
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    }
}

/// 获取回收站项目列表
#[pyfunction]
fn get_trash_items(cli_type: &str) -> PyResult<Vec<TrashItem>> {
    let trash_dir = match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.trash_dir()
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.trash_dir()
        }
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    };

    let manifest_path = trash_dir.join("manifest.json");
    if !manifest_path.exists() {
        return Ok(Vec::new());
    }

    let content = fs::read_to_string(&manifest_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    let manifest: TrashManifest = serde_json::from_str(&content)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

    Ok(manifest.items)
}

/// 从回收站恢复会话
#[pyfunction]
fn restore_from_trash(cli_type: &str, dir_name: &str) -> PyResult<()> {
    let trash_dir = match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.trash_dir()
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.trash_dir()
        }
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    };

    let manifest_path = trash_dir.join("manifest.json");
    if !manifest_path.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyIOError, _>("回收站清单不存在"));
    }

    let content = fs::read_to_string(&manifest_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    let mut manifest: TrashManifest = serde_json::from_str(&content)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

    let item = manifest.items.iter().find(|i| i.dir_name == dir_name)
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("回收站项不存在"))?
        .clone();

    let item_dir = trash_dir.join(&item.dir_name);
    if !item_dir.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyIOError, _>("回收站目录不存在"));
    }

    // 恢复会话文件
    let original_path = Path::new(&item.original_file);
    if let Some(parent) = original_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    }

    for entry in fs::read_dir(&item_dir)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?
    {
        let entry = entry.map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        let path = entry.path();
        if path.extension().map(|e| e == "jsonl").unwrap_or(false) {
            fs::rename(&path, original_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
            break;
        }
    }

    // 恢复 file-history（如果存在）
    if let Some(ref fh_path) = item.original_file_history {
        let fh_src = item_dir.join("file-history");
        if fh_src.exists() {
            fs::rename(&fh_src, fh_path).ok();
        }
    }

    // 删除回收站目录
    fs::remove_dir_all(&item_dir).ok();

    // 更新 manifest
    manifest.items.retain(|i| i.dir_name != dir_name);
    let manifest_json = serde_json::to_string_pretty(&manifest)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
    fs::write(&manifest_path, manifest_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

    Ok(())
}

/// 永久删除回收站项
#[pyfunction]
fn permanently_delete(cli_type: &str, dir_name: &str) -> PyResult<()> {
    let trash_dir = match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.trash_dir()
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.trash_dir()
        }
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    };

    let item_dir = trash_dir.join(dir_name);
    if item_dir.exists() {
        fs::remove_dir_all(&item_dir)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    }

    // 更新 manifest
    let manifest_path = trash_dir.join("manifest.json");
    if manifest_path.exists() {
        let content = fs::read_to_string(&manifest_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        let mut manifest: TrashManifest = serde_json::from_str(&content)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

        manifest.items.retain(|i| i.dir_name != dir_name);
        let manifest_json = serde_json::to_string_pretty(&manifest)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        fs::write(&manifest_path, manifest_json)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    }

    Ok(())
}

/// 清理过期回收站项
#[pyfunction]
#[pyo3(signature = (cli_type, retention_days=30))]
fn cleanup_expired_trash(cli_type: &str, retention_days: i64) -> PyResult<usize> {
    let trash_dir = match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.trash_dir()
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.trash_dir()
        }
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    };

    let manifest_path = trash_dir.join("manifest.json");
    if !manifest_path.exists() {
        return Ok(0);
    }

    let content = fs::read_to_string(&manifest_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    let mut manifest: TrashManifest = serde_json::from_str(&content)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let cutoff = now - (retention_days * 24 * 3600);

    let mut removed = 0;
    manifest.items.retain(|item| {
        if item.deleted_at < cutoff {
            let item_dir = trash_dir.join(&item.dir_name);
            fs::remove_dir_all(&item_dir).ok();
            removed += 1;
            false
        } else {
            true
        }
    });

    let manifest_json = serde_json::to_string_pretty(&manifest)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
    fs::write(&manifest_path, manifest_json)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

    Ok(removed)
}

/// 导出会话为 Markdown
#[pyfunction]
fn export_to_markdown(cli_type: &str, file_path: &str) -> PyResult<String> {
    let session = match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.load_session(file_path)
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.load_session(file_path)
        }
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("不支持的 CLI 类型: {}", cli_type),
        )),
    };

    let session = session.ok_or_else(||
        PyErr::new::<pyo3::exceptions::PyValueError, _>("会话不存在"))?;

    let cli_name = match cli_type {
        "claude" => "Claude",
        "codex" => "Codex",
        _ => "Unknown",
    };

    let mut lines = Vec::new();
    lines.push(format!("# {} 会话: {}\n", cli_name, session.info.id));
    lines.push(format!("路径: {}\n", session.info.cwd.as_deref().unwrap_or("未知")));
    lines.push("\n---\n\n".to_string());

    for msg in &session.messages {
        let role = msg.role.to_uppercase();
        let text = msg.get_text();
        if !text.is_empty() {
            lines.push(format!("## {}\n\n{}\n\n---\n\n", role, text));
        }
    }

    Ok(lines.join(""))
}

// ==================== 缓存相关 Python 绑定 ====================

/// 从缓存查找匹配 cwd 的项目
#[pyfunction]
fn find_project_by_cwd_cached(cli_type: &str, cwd: &str) -> PyResult<Option<Project>> {
    Ok(cache::find_project_by_cwd_cached(cli_type, cwd))
}

/// 从缓存加载项目会话列表
#[pyfunction]
fn load_project_from_cache(cli_type: &str, project_id: &str) -> PyResult<Vec<SessionInfo>> {
    Ok(cache::load_project_from_cache(cli_type, project_id))
}

/// 刷新缓存并加载会话（DEV 版核心功能）
#[pyfunction]
fn refresh_and_load_sessions(cli_type: &str, cwd: &str) -> PyResult<Vec<SessionInfo>> {
    // 1. 先从文件系统找到匹配的项目
    let project = match cli_type {
        "claude" => {
            let provider = get_claude_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Claude 目录不存在"))?;
            provider.find_project_by_cwd(cwd)
        }
        "codex" => {
            let provider = get_codex_provider()
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Codex 目录不存在"))?;
            provider.find_project_by_cwd(cwd)
        }
        _ => return Ok(Vec::new()),
    };

    let project = match project {
        Some(p) => p,
        None => return Ok(Vec::new()),
    };

    // 2. 刷新该项目的缓存（只刷新有变化的文件）
    if cli_type == "claude" {
        if let Some(provider) = get_claude_provider() {
            let sessions = provider.load_project(&project.id);
            for session in &sessions {
                let file_mtime = cache::get_file_mtime(&session.file_path);
                if !cache::is_cache_valid(cli_type, &session.file_path, file_mtime) {
                    cache::update_cache_entry(
                        cli_type,
                        &session.file_path,
                        &project.id,
                        &session.id,
                        session.message_count,
                        session.user_turn_count,
                        session.first_timestamp.as_deref(),
                        session.last_timestamp.as_deref(),
                        file_mtime,
                        session.cwd.as_deref(),
                    ).ok();
                }
            }
            return Ok(sessions);
        }
    } else if cli_type == "codex" {
        if let Some(provider) = get_codex_provider() {
            let sessions = provider.load_project(&project.id);
            for session in &sessions {
                let file_mtime = cache::get_file_mtime(&session.file_path);
                if !cache::is_cache_valid(cli_type, &session.file_path, file_mtime) {
                    cache::update_cache_entry(
                        cli_type,
                        &session.file_path,
                        &project.id,
                        &session.id,
                        session.message_count,
                        session.user_turn_count,
                        session.first_timestamp.as_deref(),
                        session.last_timestamp.as_deref(),
                        file_mtime,
                        session.cwd.as_deref(),
                    ).ok();
                }
            }
            return Ok(sessions);
        }
    }

    Ok(Vec::new())
}

/// 启动时增量刷新历史缓存
#[pyfunction]
fn refresh_history_on_startup(cli_type: &str) -> PyResult<usize> {
    let last_startup = cache::get_last_startup_time(cli_type);
    cache::update_startup_time(cli_type).ok();

    let mut updated_count = 0;

    if cli_type == "claude" {
        if let Some(provider) = get_claude_provider() {
            for project in provider.list_projects(0) {
                let sessions = provider.load_project(&project.id);
                for session in sessions {
                    let file_mtime = cache::get_file_mtime(&session.file_path);
                    if file_mtime > last_startup && !cache::is_cache_valid(cli_type, &session.file_path, file_mtime) {
                        cache::update_cache_entry(
                            cli_type,
                            &session.file_path,
                            &project.id,
                            &session.id,
                            session.message_count,
                            session.user_turn_count,
                            session.first_timestamp.as_deref(),
                            session.last_timestamp.as_deref(),
                            file_mtime,
                            session.cwd.as_deref(),
                        ).ok();
                        updated_count += 1;
                    }
                }
            }
        }
    }

    Ok(updated_count)
}

/// 清空缓存
#[pyfunction]
fn clear_cache(cli_type: &str) -> PyResult<usize> {
    cache::clear_cache(cli_type)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

/// 清空内存缓存
#[pyfunction]
fn clear_memory_cache() -> PyResult<()> {
    cache::clear_memory_cache();
    Ok(())
}

/// Python 模块定义
#[pymodule]
fn liangmu_history(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 注册数据类型
    m.add_class::<Project>()?;
    m.add_class::<SessionInfo>()?;
    m.add_class::<ContentBlock>()?;
    m.add_class::<Message>()?;
    m.add_class::<Session>()?;
    m.add_class::<PaginatedMessages>()?;
    m.add_class::<TrashItem>()?;

    // 注册函数 - 基础功能
    m.add_function(wrap_pyfunction!(list_cli_types, m)?)?;
    m.add_function(wrap_pyfunction!(list_projects, m)?)?;
    m.add_function(wrap_pyfunction!(find_project_by_cwd, m)?)?;
    m.add_function(wrap_pyfunction!(load_project, m)?)?;
    m.add_function(wrap_pyfunction!(load_session, m)?)?;
    m.add_function(wrap_pyfunction!(load_session_paginated, m)?)?;
    m.add_function(wrap_pyfunction!(search, m)?)?;
    m.add_function(wrap_pyfunction!(delete_session, m)?)?;
    m.add_function(wrap_pyfunction!(get_trash_items, m)?)?;
    m.add_function(wrap_pyfunction!(restore_from_trash, m)?)?;
    m.add_function(wrap_pyfunction!(permanently_delete, m)?)?;
    m.add_function(wrap_pyfunction!(cleanup_expired_trash, m)?)?;
    m.add_function(wrap_pyfunction!(export_to_markdown, m)?)?;

    // 注册函数 - 缓存功能（DEV 版核心）
    m.add_function(wrap_pyfunction!(find_project_by_cwd_cached, m)?)?;
    m.add_function(wrap_pyfunction!(load_project_from_cache, m)?)?;
    m.add_function(wrap_pyfunction!(refresh_and_load_sessions, m)?)?;
    m.add_function(wrap_pyfunction!(refresh_history_on_startup, m)?)?;
    m.add_function(wrap_pyfunction!(clear_cache, m)?)?;
    m.add_function(wrap_pyfunction!(clear_memory_cache, m)?)?;

    Ok(())
}
