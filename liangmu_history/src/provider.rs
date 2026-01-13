//! CLI Provider trait 定义 - 可扩展架构

use crate::types::*;
use std::path::Path;

/// CLI 历史记录提供者 trait
/// 实现此 trait 可支持新的 CLI 工具
pub trait CliHistoryProvider: Send + Sync {
    /// 获取 CLI 类型名称
    fn cli_type(&self) -> &'static str;

    /// 获取基础目录
    fn base_dir(&self) -> &Path;

    /// 列出所有项目（按最后修改时间倒序）
    fn list_projects(&self, limit: usize) -> Vec<Project>;

    /// 根据工作目录查找项目
    fn find_project_by_cwd(&self, cwd: &str) -> Option<Project>;

    /// 加载项目的所有会话
    fn load_project(&self, project_id: &str) -> Vec<SessionInfo>;

    /// 加载单个会话的完整消息
    fn load_session(&self, file_path: &str) -> Option<Session>;

    /// 分页加载会话消息
    fn load_session_paginated(
        &self,
        file_path: &str,
        first_turns: usize,
        last_turns: usize,
    ) -> Option<PaginatedMessages>;

    /// 搜索包含关键词的会话
    fn search(&self, keyword: &str, limit: usize) -> Vec<SessionInfo>;

    /// 删除会话（移动到回收站）
    fn delete_session(&self, file_path: &str) -> Result<(), String>;

    /// 获取回收站目录
    fn trash_dir(&self) -> std::path::PathBuf {
        self.base_dir().join("trash")
    }
}

/// Provider 注册表 - 管理所有 CLI 提供者
pub struct ProviderRegistry {
    providers: Vec<Box<dyn CliHistoryProvider>>,
}

impl ProviderRegistry {
    pub fn new() -> Self {
        Self { providers: Vec::new() }
    }

    pub fn register(&mut self, provider: Box<dyn CliHistoryProvider>) {
        self.providers.push(provider);
    }

    pub fn get(&self, cli_type: &str) -> Option<&dyn CliHistoryProvider> {
        self.providers
            .iter()
            .find(|p| p.cli_type() == cli_type)
            .map(|p| p.as_ref())
    }

    pub fn list_types(&self) -> Vec<&'static str> {
        self.providers.iter().map(|p| p.cli_type()).collect()
    }
}

impl Default for ProviderRegistry {
    fn default() -> Self {
        Self::new()
    }
}
