//! Claude Code 历史记录提供者

use crate::provider::CliHistoryProvider;
use crate::types::*;
use rayon::prelude::*;
use serde_json::Value;
use std::fs::{self, File};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::time::SystemTime;

pub struct ClaudeProvider {
    base_dir: PathBuf,
}

impl ClaudeProvider {
    pub fn new(base_dir: PathBuf) -> Self {
        Self { base_dir }
    }

    pub fn default() -> Option<Self> {
        let home = dirs::home_dir()?;
        let claude_dir = home.join(".claude");
        if claude_dir.exists() {
            Some(Self::new(claude_dir))
        } else {
            None
        }
    }

    fn projects_dir(&self) -> PathBuf {
        self.base_dir.join("projects")
    }

    /// 解析消息内容块
    fn parse_content_blocks(content: &Value) -> Vec<ContentBlock> {
        let mut blocks = Vec::new();
        match content {
            Value::String(s) => {
                blocks.push(ContentBlock {
                    block_type: "text".to_string(),
                    text: Some(s.clone()),
                    tool_name: None,
                    tool_input: None,
                });
            }
            Value::Array(arr) => {
                for item in arr {
                    if let Value::Object(obj) = item {
                        let block_type = obj
                            .get("type")
                            .and_then(|v| v.as_str())
                            .unwrap_or("unknown")
                            .to_string();

                        let text = obj.get("text").and_then(|v| v.as_str()).map(String::from);
                        let tool_name = obj.get("name").and_then(|v| v.as_str()).map(String::from);
                        let tool_input = obj.get("input").map(|v| v.to_string());

                        blocks.push(ContentBlock {
                            block_type,
                            text,
                            tool_name,
                            tool_input,
                        });
                    }
                }
            }
            _ => {}
        }
        blocks
    }

    /// 解析单条消息
    fn parse_message(data: &Value) -> Option<Message> {
        let msg_type = data.get("type")?.as_str()?;
        if msg_type != "user" && msg_type != "assistant" {
            return None;
        }

        let message_data = data.get("message")?;
        let role = message_data
            .get("role")
            .and_then(|v| v.as_str())
            .unwrap_or(msg_type);
        let content = message_data.get("content").unwrap_or(&Value::Null);
        let content_blocks = Self::parse_content_blocks(content);

        // 判断是否为真实用户输入（没有 tool_result）
        let has_tool_result = content_blocks.iter().any(|b| b.block_type == "tool_result");
        let is_real_user = msg_type == "user" && !has_tool_result;

        Some(Message {
            uuid: data.get("uuid").and_then(|v| v.as_str()).map(String::from),
            timestamp: data
                .get("timestamp")
                .and_then(|v| v.as_str())
                .map(String::from),
            msg_type: msg_type.to_string(),
            role: role.to_string(),
            content_blocks,
            is_real_user,
        })
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

            // 提取元数据
            if cwd.is_none() {
                cwd = data.get("cwd").and_then(|v| v.as_str()).map(String::from);
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

            if let Some(msg) = Self::parse_message(&data) {
                messages.push(msg);
            }
        }

        if messages.is_empty() {
            return None;
        }

        let user_turn_count = messages.iter().filter(|m| m.is_real_user).count();
        let file_size = fs::metadata(file_path).map(|m| m.len()).unwrap_or(0);

        Some(Session {
            info: SessionInfo {
                id: file_path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("unknown")
                    .to_string(),
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

    /// 快速解析会话信息（不加载全部消息）
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

            // [过滤2] 系统中断消息过滤
            if line.contains("[Request interrupted by user") {
                continue;
            }

            let data: Value = match serde_json::from_str(&line) {
                Ok(v) => v,
                Err(_) => continue,
            };

            if cwd.is_none() {
                cwd = data.get("cwd").and_then(|v| v.as_str()).map(String::from);
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
            if msg_type == Some("user") || msg_type == Some("assistant") {
                msg_count += 1;
                if msg_type == Some("user") {
                    // 检查是否为真实用户输入（伪用户消息过滤）
                    let content = data.get("message").and_then(|m| m.get("content"));
                    let has_tool_result = content
                        .and_then(|c| c.as_array())
                        .map(|arr| {
                            arr.iter().any(|b| {
                                b.get("type").and_then(|t| t.as_str()) == Some("tool_result")
                            })
                        })
                        .unwrap_or(false);
                    if !has_tool_result {
                        user_turn_count += 1;
                    }
                }
            }
        }

        // [过滤3] 无消息过滤
        if msg_count == 0 {
            return None;
        }

        // [过滤4] 无有效时间戳过滤
        if first_ts.is_none() && last_ts.is_none() {
            return None;
        }

        // [过滤5] 用户消息为0过滤
        if user_turn_count == 0 {
            return None;
        }

        Some(SessionInfo {
            id: file_path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("unknown")
                .to_string(),
            file_path: file_path.to_string_lossy().to_string(),
            cwd,
            first_timestamp: first_ts,
            last_timestamp: last_ts,
            message_count: msg_count,
            user_turn_count,
            file_size,
        })
    }
}

impl CliHistoryProvider for ClaudeProvider {
    fn cli_type(&self) -> &'static str {
        "claude"
    }

    fn base_dir(&self) -> &Path {
        &self.base_dir
    }

    fn list_projects(&self, limit: usize) -> Vec<Project> {
        let projects_dir = self.projects_dir();
        if !projects_dir.exists() {
            return Vec::new();
        }

        let mut dirs: Vec<_> = fs::read_dir(&projects_dir)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
            .collect();

        // 按修改时间排序
        dirs.sort_by(|a, b| {
            let a_time = a
                .metadata()
                .and_then(|m| m.modified())
                .unwrap_or(SystemTime::UNIX_EPOCH);
            let b_time = b
                .metadata()
                .and_then(|m| m.modified())
                .unwrap_or(SystemTime::UNIX_EPOCH);
            b_time.cmp(&a_time)
        });

        if limit > 0 && dirs.len() > limit {
            dirs.truncate(limit);
        }

        // 并行获取每个项目的 cwd
        dirs.par_iter()
            .filter_map(|entry| {
                let path = entry.path();
                let id = path.file_name()?.to_str()?.to_string();
                let mtime = entry
                    .metadata()
                    .and_then(|m| m.modified())
                    .ok()
                    .and_then(|t| t.duration_since(SystemTime::UNIX_EPOCH).ok())
                    .map(|d| d.as_secs_f64())
                    .unwrap_or(0.0);

                // 获取 cwd
                let cwd = self.get_project_cwd(&path);
                let session_count = fs::read_dir(&path)
                    .ok()
                    .map(|rd| {
                        rd.filter(|e| {
                            e.as_ref()
                                .map(|e| {
                                    e.path()
                                        .extension()
                                        .map(|ext| ext == "jsonl")
                                        .unwrap_or(false)
                                })
                                .unwrap_or(false)
                        })
                        .count()
                    })
                    .unwrap_or(0);

                Some(Project {
                    id,
                    cwd,
                    last_modified: mtime,
                    session_count,
                    last_activity: None,
                })
            })
            .collect()
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

    fn load_project(&self, project_id: &str) -> Vec<SessionInfo> {
        let project_dir = self.projects_dir().join(project_id);
        if !project_dir.exists() {
            return Vec::new();
        }

        let files: Vec<_> = fs::read_dir(&project_dir)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.path()
                    .extension()
                    .map(|ext| ext == "jsonl")
                    .unwrap_or(false)
            })
            .filter(|e| {
                // 复刻 DEV 版：过滤 agent- 开头的子任务文件
                !e.file_name().to_string_lossy().starts_with("agent-")
            })
            .map(|e| e.path())
            .collect();

        // 并行解析，过滤掉 <=1 轮的无效会话
        let mut sessions: Vec<SessionInfo> = files
            .par_iter()
            .filter_map(|f| self.parse_session_info(f))
            .filter(|s| s.user_turn_count > 1) // 复刻 DEV 版：过滤 <=1 轮会话
            .collect();

        // 按最后时间戳排序
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
            // 全部显示
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
        let projects_dir = self.projects_dir();

        if !projects_dir.exists() {
            return Vec::new();
        }

        // 收集所有 jsonl 文件
        let files: Vec<PathBuf> = fs::read_dir(&projects_dir)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false))
            .flat_map(|dir| {
                fs::read_dir(dir.path())
                    .ok()
                    .into_iter()
                    .flatten()
                    .filter_map(|e| e.ok())
                    .filter(|e| {
                        e.path()
                            .extension()
                            .map(|ext| ext == "jsonl")
                            .unwrap_or(false)
                    })
                    .map(|e| e.path())
            })
            .collect();

        // 并行搜索
        let results: Vec<SessionInfo> = files
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
            .collect();

        results
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
            .to_string();

        let project_name = path
            .parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str())
            .unwrap_or("unknown")
            .to_string();

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

        // 移动 file-history 目录（如果存在）
        let file_history_dir = path
            .parent()
            .unwrap()
            .join("file-history")
            .join(&session_id);
        let original_file_history = if file_history_dir.exists() {
            let dest_fh = item_dir.join("file-history");
            fs::rename(&file_history_dir, &dest_fh).ok();
            Some(file_history_dir.to_string_lossy().to_string())
        } else {
            None
        };

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
            original_file_history,
        });

        let manifest_json = serde_json::to_string_pretty(&manifest).map_err(|e| e.to_string())?;
        fs::write(&manifest_path, manifest_json).map_err(|e| e.to_string())?;

        Ok(())
    }
}

impl ClaudeProvider {
    /// 快速获取项目的 cwd
    fn get_project_cwd(&self, project_dir: &Path) -> Option<String> {
        for entry in fs::read_dir(project_dir).ok()? {
            let entry = entry.ok()?;
            if entry
                .path()
                .extension()
                .map(|e| e == "jsonl")
                .unwrap_or(false)
            {
                let file = File::open(entry.path()).ok()?;
                let reader = BufReader::new(file);
                for line in reader.lines() {
                    let line = line.ok()?;
                    if line.contains("\"cwd\"") {
                        let data: Value = serde_json::from_str(&line).ok()?;
                        return data.get("cwd").and_then(|v| v.as_str()).map(String::from);
                    }
                }
            }
        }
        None
    }
}
