//! Codex CLI 历史记录提供者

use crate::provider::CliHistoryProvider;
use crate::types::*;
use rayon::prelude::*;
use serde_json::Value;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::time::SystemTime;
use walkdir::WalkDir;

pub struct CodexProvider {
    base_dir: PathBuf,
}

impl CodexProvider {
    pub fn new(base_dir: PathBuf) -> Self {
        Self { base_dir }
    }

    pub fn default() -> Option<Self> {
        let home = dirs::home_dir()?;
        let codex_dir = home.join(".codex");
        if codex_dir.exists() {
            Some(Self::new(codex_dir))
        } else {
            None
        }
    }

    fn sessions_dir(&self) -> PathBuf {
        self.base_dir.join("sessions")
    }

    /// 从文件快速提取 cwd
    fn get_cwd_fast(file_path: &Path) -> Option<String> {
        let file = File::open(file_path).ok()?;
        let reader = BufReader::new(file);
        for line in reader.lines() {
            let line = line.ok()?;
            if line.contains("\"cwd\"") {
                let data: Value = serde_json::from_str(&line).ok()?;
                // Codex 格式：payload.cwd 或直接 cwd
                if let Some(cwd) = data
                    .get("payload")
                    .and_then(|p| p.get("cwd"))
                    .and_then(|v| v.as_str())
                {
                    return Some(cwd.to_string());
                }
                if let Some(cwd) = data.get("cwd").and_then(|v| v.as_str()) {
                    return Some(cwd.to_string());
                }
            }
        }
        None
    }

    /// 规范化路径：统一使用反斜杠，盘符大写
    fn normalize_path(path: &str) -> String {
        let normalized = path.replace('/', "\\");
        // 盘符大写
        if normalized.len() >= 2 && normalized.chars().nth(1) == Some(':') {
            let mut chars: Vec<char> = normalized.chars().collect();
            chars[0] = chars[0].to_ascii_uppercase();
            chars.into_iter().collect()
        } else {
            normalized
        }
    }

    /// 解析 Codex 消息
    fn parse_codex_message(data: &Value) -> Option<Message> {
        let msg_type = data.get("type")?.as_str()?;

        match msg_type {
            "response_item" => {
                let payload = data.get("payload")?;
                if payload.get("type")?.as_str()? != "message" {
                    return None;
                }
                let role = payload
                    .get("role")
                    .and_then(|v| v.as_str())
                    .unwrap_or("assistant");
                let content = payload.get("content");

                let mut blocks = Vec::new();
                if let Some(Value::Array(arr)) = content {
                    for item in arr {
                        if let Some(text) = item.get("text").and_then(|v| v.as_str()) {
                            blocks.push(ContentBlock {
                                block_type: "text".to_string(),
                                text: Some(text.to_string()),
                                tool_name: None,
                                tool_input: None,
                            });
                        }
                    }
                }

                Some(Message {
                    uuid: None,
                    timestamp: data
                        .get("timestamp")
                        .and_then(|v| v.as_str())
                        .map(String::from),
                    msg_type: "response_item".to_string(),
                    role: role.to_string(),
                    content_blocks: blocks,
                    is_real_user: false,
                })
            }
            "event_msg" => {
                let payload = data.get("payload")?;
                let event_type = payload.get("type")?.as_str()?;

                let (role, is_real_user) = match event_type {
                    "user_message" => ("user", true),
                    "agent_message" => ("assistant", false),
                    _ => return None,
                };

                let message_text = payload
                    .get("message")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let blocks = vec![ContentBlock {
                    block_type: "text".to_string(),
                    text: Some(message_text.to_string()),
                    tool_name: None,
                    tool_input: None,
                }];

                Some(Message {
                    uuid: None,
                    timestamp: data
                        .get("timestamp")
                        .and_then(|v| v.as_str())
                        .map(String::from),
                    msg_type: event_type.to_string(),
                    role: role.to_string(),
                    content_blocks: blocks,
                    is_real_user,
                })
            }
            _ => None,
        }
    }

    /// 解析会话文件
    fn parse_session_file(&self, file_path: &Path) -> Option<Session> {
        let file = File::open(file_path).ok()?;
        let reader = BufReader::new(file);

        let mut messages = Vec::new();
        let mut first_ts: Option<String> = None;
        let mut last_ts: Option<String> = None;
        let mut cwd: Option<String> = None;

        for line in reader.lines() {
            let line = match line {
                Ok(l) if !l.trim().is_empty() => l,
                _ => continue,
            };

            let data: Value = match serde_json::from_str(&line) {
                Ok(v) => v,
                Err(_) => continue,
            };

            // 提取 cwd
            if cwd.is_none() {
                if let Some(c) = data
                    .get("payload")
                    .and_then(|p| p.get("cwd"))
                    .and_then(|v| v.as_str())
                {
                    cwd = Some(c.to_string());
                }
            }

            let ts = data
                .get("timestamp")
                .and_then(|v| v.as_str())
                .map(String::from);
            if let Some(ref t) = ts {
                if first_ts.is_none() {
                    first_ts = Some(t.clone());
                }
                last_ts = Some(t.clone());
            }

            if let Some(msg) = Self::parse_codex_message(&data) {
                messages.push(msg);
            }
        }

        if messages.is_empty() {
            return None;
        }

        let user_turn_count = messages.iter().filter(|m| m.is_real_user).count();
        let file_size = fs::metadata(file_path).map(|m| m.len()).unwrap_or(0);

        let session_id = file_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .replace("rollout-", "");

        Some(Session {
            info: SessionInfo {
                id: session_id,
                file_path: file_path.to_string_lossy().to_string(),
                cwd,
                first_timestamp: first_ts,
                last_timestamp: last_ts,
                message_count: messages.len(),
                user_turn_count,
                file_size,
            },
            messages,
        })
    }

    /// 快速解析会话信息
    /// 复刻 DEV 版的完整过滤规则
    fn parse_session_info(&self, file_path: &Path) -> Option<SessionInfo> {
        // [过滤1] 空文件过滤
        let file_size = fs::metadata(file_path).map(|m| m.len()).unwrap_or(0);
        if file_size == 0 {
            return None;
        }

        let file = File::open(file_path).ok()?;
        let reader = BufReader::new(file);

        let mut msg_count = 0;
        let mut user_turn_count = 0;
        let mut first_ts: Option<String> = None;
        let mut last_ts: Option<String> = None;
        let mut cwd: Option<String> = None;

        for line in reader.lines() {
            let line = match line {
                Ok(l) if !l.trim().is_empty() => l,
                _ => continue,
            };

            let data: Value = match serde_json::from_str(&line) {
                Ok(v) => v,
                Err(_) => continue,
            };

            if cwd.is_none() {
                if let Some(c) = data
                    .get("payload")
                    .and_then(|p| p.get("cwd"))
                    .and_then(|v| v.as_str())
                {
                    cwd = Some(c.to_string());
                }
            }

            let ts = data
                .get("timestamp")
                .and_then(|v| v.as_str())
                .map(String::from);
            if let Some(ref t) = ts {
                if first_ts.is_none() {
                    first_ts = Some(t.clone());
                }
                last_ts = Some(t.clone());
            }

            let msg_type = data.get("type").and_then(|v| v.as_str());
            match msg_type {
                Some("response_item") => {
                    if data
                        .get("payload")
                        .and_then(|p| p.get("type"))
                        .and_then(|v| v.as_str())
                        == Some("message")
                    {
                        msg_count += 1;
                    }
                }
                Some("event_msg") => {
                    let event_type = data
                        .get("payload")
                        .and_then(|p| p.get("type"))
                        .and_then(|v| v.as_str());
                    if event_type == Some("user_message") {
                        msg_count += 1;
                        user_turn_count += 1;
                    } else if event_type == Some("agent_message") {
                        msg_count += 1;
                    }
                }
                _ => {}
            }
        }

        // [过滤2] 无消息过滤
        if msg_count == 0 {
            return None;
        }

        // [过滤3] 无有效时间戳过滤
        if first_ts.is_none() && last_ts.is_none() {
            return None;
        }

        // [过滤4] 用户消息为0过滤
        if user_turn_count == 0 {
            return None;
        }

        let session_id = file_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .replace("rollout-", "");

        Some(SessionInfo {
            id: session_id,
            file_path: file_path.to_string_lossy().to_string(),
            cwd,
            first_timestamp: first_ts,
            last_timestamp: last_ts,
            message_count: msg_count,
            user_turn_count,
            file_size,
        })
    }

    /// 扫描所有会话文件，按 cwd 分组
    fn scan_sessions_by_cwd(&self, limit: usize) -> HashMap<String, f64> {
        let sessions_dir = self.sessions_dir();
        if !sessions_dir.exists() {
            return HashMap::new();
        }

        let files: Vec<PathBuf> = WalkDir::new(&sessions_dir)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.file_type().is_file()
                    && e.path()
                        .extension()
                        .map(|ext| ext == "jsonl")
                        .unwrap_or(false)
            })
            .map(|e| e.path().to_path_buf())
            .collect();

        // 并行扫描
        let cwd_map: HashMap<String, f64> = files
            .par_iter()
            .filter_map(|file_path| {
                let cwd = Self::get_cwd_fast(file_path).unwrap_or_else(|| "未知目录".to_string());
                // 规范化路径：统一使用反斜杠，首字母大写
                let cwd_normalized = Self::normalize_path(&cwd);
                let mtime = fs::metadata(file_path)
                    .and_then(|m| m.modified())
                    .ok()
                    .and_then(|t| t.duration_since(SystemTime::UNIX_EPOCH).ok())
                    .map(|d| d.as_secs_f64())
                    .unwrap_or(0.0);
                Some((cwd_normalized, mtime))
            })
            .fold(HashMap::new, |mut acc, (cwd, mtime)| {
                let entry = acc.entry(cwd).or_insert(0.0);
                if mtime > *entry {
                    *entry = mtime;
                }
                acc
            })
            .reduce(HashMap::new, |mut a, b| {
                for (k, v) in b {
                    let entry = a.entry(k).or_insert(0.0);
                    if v > *entry {
                        *entry = v;
                    }
                }
                a
            });

        if limit > 0 {
            let mut sorted: Vec<_> = cwd_map.into_iter().collect();
            sorted.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            sorted.truncate(limit);
            sorted.into_iter().collect()
        } else {
            cwd_map
        }
    }
}

impl CliHistoryProvider for CodexProvider {
    fn cli_type(&self) -> &'static str {
        "codex"
    }

    fn base_dir(&self) -> &Path {
        &self.base_dir
    }

    fn list_projects(&self, limit: usize) -> Vec<Project> {
        let cwd_map = self.scan_sessions_by_cwd(limit);

        let mut projects: Vec<_> = cwd_map
            .into_iter()
            .map(|(cwd, mtime)| Project {
                id: cwd.clone(),
                cwd: Some(cwd),
                last_modified: mtime,
                session_count: 0, // 会在 load_project 时填充
                last_activity: None,
            })
            .collect();

        projects.sort_by(|a, b| {
            b.last_modified
                .partial_cmp(&a.last_modified)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        projects
    }

    fn find_project_by_cwd(&self, cwd: &str) -> Option<Project> {
        let cwd_normalized = cwd.replace('\\', "/").to_lowercase();
        self.list_projects(0).into_iter().find(|p| {
            p.cwd
                .as_ref()
                .map(|c| c.replace('\\', "/").to_lowercase() == cwd_normalized)
                .unwrap_or(false)
        })
    }

    fn load_project(&self, cwd_path: &str) -> Vec<SessionInfo> {
        let sessions_dir = self.sessions_dir();
        if !sessions_dir.exists() {
            return Vec::new();
        }

        // 使用规范化路径进行比较
        let cwd_normalized = Self::normalize_path(cwd_path);

        let files: Vec<PathBuf> = WalkDir::new(&sessions_dir)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.file_type().is_file()
                    && e.path()
                        .extension()
                        .map(|ext| ext == "jsonl")
                        .unwrap_or(false)
            })
            .map(|e| e.path().to_path_buf())
            .collect();

        // 并行过滤和解析，过滤掉 <=1 轮的无效会话
        let mut sessions: Vec<SessionInfo> = files
            .par_iter()
            .filter_map(|file_path| {
                let cwd = Self::get_cwd_fast(file_path)?;
                if Self::normalize_path(&cwd) != cwd_normalized {
                    return None;
                }
                self.parse_session_info(file_path)
            })
            .filter(|s| s.user_turn_count >= 1) // 保留至少 1 轮对话的会话
            .collect();

        sessions.sort_by(|a, b| b.last_timestamp.as_ref().cmp(&a.last_timestamp.as_ref()));
        sessions
    }

    fn load_session(&self, file_path: &str) -> Option<Session> {
        self.parse_session_file(Path::new(file_path))
    }

    fn load_session_paginated(
        &self,
        file_path: &str,
        first_turns: usize,
        last_turns: usize,
    ) -> Option<PaginatedMessages> {
        let session = self.load_session(file_path)?;
        let messages = session.messages;

        // 按轮次分组
        let mut rounds: Vec<Vec<Message>> = Vec::new();
        let mut current_round: Vec<Message> = Vec::new();

        for msg in messages {
            if msg.is_real_user {
                if !current_round.is_empty() {
                    rounds.push(current_round);
                }
                current_round = vec![msg];
            } else {
                current_round.push(msg);
            }
        }
        if !current_round.is_empty() {
            rounds.push(current_round);
        }

        let total_turns = rounds.len();
        let total_messages: usize = rounds.iter().map(|r| r.len()).sum();

        if first_turns + last_turns >= total_turns {
            let all: Vec<Message> = rounds.into_iter().flatten().collect();
            return Some(PaginatedMessages {
                first: all,
                last: Vec::new(),
                has_middle: false,
                total_turns,
                total_messages,
            });
        }

        let first: Vec<Message> = rounds[..first_turns].iter().flatten().cloned().collect();
        let last: Vec<Message> = rounds[total_turns - last_turns..]
            .iter()
            .flatten()
            .cloned()
            .collect();

        Some(PaginatedMessages {
            first,
            last,
            has_middle: true,
            total_turns,
            total_messages,
        })
    }

    fn search(&self, keyword: &str, limit: usize) -> Vec<SessionInfo> {
        let keyword_lower = keyword.to_lowercase();
        let sessions_dir = self.sessions_dir();

        if !sessions_dir.exists() {
            return Vec::new();
        }

        let files: Vec<PathBuf> = WalkDir::new(&sessions_dir)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.file_type().is_file()
                    && e.path()
                        .extension()
                        .map(|ext| ext == "jsonl")
                        .unwrap_or(false)
            })
            .map(|e| e.path().to_path_buf())
            .collect();

        files
            .par_iter()
            .filter_map(|file_path| {
                let file = File::open(file_path).ok()?;
                let reader = BufReader::new(file);
                for line in reader.lines() {
                    let line = match line {
                        Ok(l) => l,
                        Err(_) => continue,
                    };
                    if line.to_lowercase().contains(&keyword_lower) {
                        return self.parse_session_info(file_path);
                    }
                }
                None
            })
            .take_any(limit)
            .collect()
    }

    fn delete_session(&self, file_path: &str) -> Result<(), String> {
        use std::time::{SystemTime, UNIX_EPOCH};

        let path = Path::new(file_path);
        if !path.exists() {
            return Err("文件不存在".to_string());
        }

        let session_id = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .replace("rollout-", "");

        // 获取 cwd 作为项目名
        let project_name = Self::get_cwd_fast(path).unwrap_or_else(|| "未知目录".to_string());

        // 创建回收站目录
        let trash_dir = self.trash_dir();
        fs::create_dir_all(&trash_dir).map_err(|e| e.to_string())?;

        // 创建带时间戳的子目录
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let item_dir = trash_dir.join(format!("{}_{}", session_id, timestamp));
        fs::create_dir_all(&item_dir).map_err(|e| e.to_string())?;

        // 移动会话文件
        let dest_file = item_dir.join(path.file_name().unwrap());
        fs::rename(path, &dest_file).map_err(|e| e.to_string())?;

        // 更新 manifest
        let manifest_path = trash_dir.join("manifest.json");
        let mut manifest: crate::types::TrashManifest = if manifest_path.exists() {
            let content = fs::read_to_string(&manifest_path).unwrap_or_default();
            serde_json::from_str(&content)
                .unwrap_or(crate::types::TrashManifest { items: Vec::new() })
        } else {
            crate::types::TrashManifest { items: Vec::new() }
        };

        manifest.items.push(crate::types::TrashItem {
            session_id,
            project_name,
            deleted_at: timestamp as i64,
            dir_name: item_dir.file_name().unwrap().to_string_lossy().to_string(),
            original_file: file_path.to_string(),
            original_file_history: None,
        });

        let manifest_json = serde_json::to_string_pretty(&manifest).map_err(|e| e.to_string())?;
        fs::write(&manifest_path, manifest_json).map_err(|e| e.to_string())?;

        Ok(())
    }
}
