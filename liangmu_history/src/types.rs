//! 共享数据类型定义

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// 项目信息
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    #[pyo3(get)]
    pub id: String,
    #[pyo3(get)]
    pub cwd: Option<String>,
    #[pyo3(get)]
    pub last_modified: f64,
    #[pyo3(get)]
    pub session_count: usize,
    #[pyo3(get)]
    pub last_activity: Option<String>,
}

#[pymethods]
impl Project {
    fn __repr__(&self) -> String {
        format!("Project(id={}, cwd={:?})", self.id, self.cwd)
    }
}

/// 会话信息
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionInfo {
    #[pyo3(get)]
    pub id: String,
    #[pyo3(get)]
    pub file_path: String,
    #[pyo3(get)]
    pub cwd: Option<String>,
    #[pyo3(get)]
    pub first_timestamp: Option<String>,
    #[pyo3(get)]
    pub last_timestamp: Option<String>,
    #[pyo3(get)]
    pub message_count: usize,
    #[pyo3(get)]
    pub user_turn_count: usize,
    #[pyo3(get)]
    pub file_size: u64,
}

#[pymethods]
impl SessionInfo {
    fn __repr__(&self) -> String {
        format!("SessionInfo(id={}, turns={})", self.id, self.user_turn_count)
    }
}

/// 消息内容块
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContentBlock {
    #[pyo3(get)]
    pub block_type: String,
    #[pyo3(get)]
    pub text: Option<String>,
    #[pyo3(get)]
    pub tool_name: Option<String>,
    #[pyo3(get)]
    pub tool_input: Option<String>,
}

#[pymethods]
impl ContentBlock {
    fn __repr__(&self) -> String {
        format!("ContentBlock(type={})", self.block_type)
    }
}

/// 消息
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    #[pyo3(get)]
    pub uuid: Option<String>,
    #[pyo3(get)]
    pub timestamp: Option<String>,
    #[pyo3(get)]
    pub msg_type: String,
    #[pyo3(get)]
    pub role: String,
    #[pyo3(get)]
    pub content_blocks: Vec<ContentBlock>,
    #[pyo3(get)]
    pub is_real_user: bool,
}

#[pymethods]
impl Message {
    /// 获取纯文本内容
    pub fn get_text(&self) -> String {
        self.content_blocks
            .iter()
            .filter_map(|b| b.text.as_ref())
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// 获取工具调用摘要
    pub fn get_tool_summary(&self) -> Vec<String> {
        self.content_blocks
            .iter()
            .filter(|b| b.block_type == "tool_use")
            .filter_map(|b| b.tool_name.as_ref().map(|n| n.clone()))
            .collect()
    }

    fn __repr__(&self) -> String {
        format!("Message(role={}, type={})", self.role, self.msg_type)
    }
}

/// 完整会话数据
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    #[pyo3(get)]
    pub info: SessionInfo,
    #[pyo3(get)]
    pub messages: Vec<Message>,
}

#[pymethods]
impl Session {
    /// 获取真实用户轮次数
    fn real_turn_count(&self) -> usize {
        self.messages.iter().filter(|m| m.is_real_user).count()
    }

    /// 获取工具使用统计
    fn tool_usage(&self) -> HashMap<String, usize> {
        let mut usage = HashMap::new();
        for msg in &self.messages {
            for block in &msg.content_blocks {
                if block.block_type == "tool_use" {
                    if let Some(name) = &block.tool_name {
                        *usage.entry(name.clone()).or_insert(0) += 1;
                    }
                }
            }
        }
        usage
    }

    fn __repr__(&self) -> String {
        format!("Session(id={}, messages={})", self.info.id, self.messages.len())
    }
}

/// 分页消息结果
#[pyclass]
#[derive(Debug, Clone)]
pub struct PaginatedMessages {
    #[pyo3(get)]
    pub first: Vec<Message>,
    #[pyo3(get)]
    pub last: Vec<Message>,
    #[pyo3(get)]
    pub has_middle: bool,
    #[pyo3(get)]
    pub total_turns: usize,
    #[pyo3(get)]
    pub total_messages: usize,
}

#[pymethods]
impl PaginatedMessages {
    fn __repr__(&self) -> String {
        format!(
            "PaginatedMessages(first={}, last={}, has_middle={})",
            self.first.len(),
            self.last.len(),
            self.has_middle
        )
    }
}

/// 回收站项目
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrashItem {
    #[pyo3(get)]
    pub session_id: String,
    #[pyo3(get)]
    pub project_name: String,
    #[pyo3(get)]
    pub deleted_at: i64,
    #[pyo3(get)]
    pub dir_name: String,
    #[pyo3(get)]
    pub original_file: String,
    #[pyo3(get)]
    pub original_file_history: Option<String>,
}

#[pymethods]
impl TrashItem {
    fn __repr__(&self) -> String {
        format!("TrashItem(session={}, deleted_at={})", self.session_id, self.deleted_at)
    }
}

/// 回收站清单
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrashManifest {
    pub items: Vec<TrashItem>,
}
