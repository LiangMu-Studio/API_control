# MCP Server Management

## Overview

MCP 服务器管理模块负责管理 Model Context Protocol 服务器配置，包括添加、编辑、删除、导入和同步到 CLI 工具。

## ADDED Requirements

### Requirement: MCP 配置管理

系统必须支持 CRUD 操作管理 MCP 服务器配置。

#### Scenario: 显示 MCP 列表

**Given** 用户进入 MCP 页面
**When** 系统加载 MCP 配置
**Then** 按分类分组显示 MCP 服务器
**And** 每个服务器显示：
  - 名称
  - 命令和参数
  - 是否为默认

#### Scenario: 添加 MCP 服务器

**Given** 用户点击"添加"按钮
**When** 用户填写配置（名称、分类、命令、参数、环境变量）
**And** 点击"保存"
**Then** 系统保存配置
**And** 刷新列表

#### Scenario: 编辑 MCP 服务器

**Given** 用户选中一个 MCP 服务器
**When** 用户点击"编辑"按钮
**And** 修改配置
**And** 点击"保存"
**Then** 系统更新配置
**And** 刷新列表

#### Scenario: 删除 MCP 服务器

**Given** 用户选中一个 MCP 服务器
**When** 用户点击"删除"按钮
**Then** 系统删除配置
**And** 刷新列表

---

### Requirement: 分类管理

系统必须支持按分类组织 MCP 服务器。

#### Scenario: 显示分类树

**Given** MCP 列表已加载
**When** 用户查看列表
**Then** 按分类分组显示：
  - 常用
  - 文件
  - 网络
  - 数据
  - 其他

#### Scenario: 展开/折叠分类

**Given** 分类树已显示
**When** 用户点击分类标题
**Then** 该分类展开或折叠

---

### Requirement: 默认 MCP 同步

系统必须支持将默认 MCP 同步到全局配置。

#### Scenario: 设置默认 MCP

**Given** 用户查看 MCP 列表
**When** 用户勾选某个 MCP 的"默认"复选框
**Then** 系统标记该 MCP 为默认
**And** 自动同步到 `~/.claude/.mcp.json`

#### Scenario: 取消默认 MCP

**Given** 某个 MCP 已设为默认
**When** 用户取消勾选"默认"复选框
**Then** 系统取消默认标记
**And** 从全局配置中移除

#### Scenario: 同步到全局配置

**Given** 存在默认 MCP 配置
**When** 用户修改默认 MCP 设置
**Then** 系统生成 MCP JSON 配置：
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@package/name"],
      "env": { "KEY": "value" }
    }
  }
}
```
**And** 写入 `~/.claude/.mcp.json`

---

### Requirement: MCP 导入

系统必须支持多种方式导入 MCP 配置。

#### Scenario: 从已安装 CLI 导入

**Given** 用户点击"导入" → "从已安装 CLI"
**When** 系统扫描已安装的 CLI 配置文件：
  - `~/.claude/settings.json`
  - `~/.codex/config.json`
  - VSCode Claude Code 插件配置
**Then** 显示找到的 MCP 服务器列表
**And** 用户可选择导入

#### Scenario: 从剪贴板导入

**Given** 用户复制了 MCP JSON 配置
**When** 用户点击"导入" → "从剪贴板"
**Then** 系统解析剪贴板内容
**And** 导入有效的 MCP 配置

#### Scenario: 从文件导入

**Given** 用户有 MCP JSON 文件
**When** 用户点击"导入" → "从文件"
**And** 选择文件
**Then** 系统解析文件内容
**And** 导入有效的 MCP 配置

#### Scenario: 从文本导入

**Given** 用户点击"导入" → "从文本"
**When** 用户粘贴 JSON 文本
**And** 点击"导入"
**Then** 系统解析文本
**And** 导入有效的 MCP 配置

---

### Requirement: MCP 仓库浏览

系统必须支持浏览和搜索 MCP 仓库。

#### Scenario: 同步 MCP 仓库

**Given** 用户点击"仓库"按钮
**And** 仓库为空或需要更新
**When** 系统从 npm registry 获取 MCP 包列表
**Then** 显示同步进度
**And** 保存到本地数据库

#### Scenario: 浏览仓库

**Given** MCP 仓库已同步
**When** 用户打开仓库浏览器
**Then** 显示 MCP 服务器列表
**And** 支持按分类筛选
**And** 支持关键词搜索

#### Scenario: 从仓库添加

**Given** 用户在仓库浏览器中
**When** 用户选中一个或多个 MCP
**And** 点击"添加选中"
**Then** 系统将选中的 MCP 添加到配置
**And** 关闭浏览器

#### Scenario: 自动更新仓库

**Given** 仓库超过 7 天未更新
**When** 应用启动
**Then** 系统在后台自动更新仓库

---

### Requirement: 官方 MCP 服务器

系统必须提供官方 MCP 服务器快速添加。

#### Scenario: 添加官方 MCP

**Given** 用户点击"官方"按钮
**When** 显示官方 MCP 列表：
  - Filesystem
  - Fetch
  - Memory
  - Sequential Thinking
  - Puppeteer
  - Brave Search
  - Google Maps
  - Slack
**And** 用户选择一个
**Then** 系统添加该 MCP 配置
**And** 预填充默认参数

---

### Requirement: 外部 MCP 市场

系统必须支持浏览外部 MCP 市场。

#### Scenario: 浏览 Smithery

**Given** 用户点击"市场" → "Smithery"
**When** 系统打开浏览器
**Then** 跳转到 https://smithery.ai/

#### Scenario: 浏览 MCP.so

**Given** 用户点击"市场" → "MCP.so"
**When** 系统打开浏览器
**Then** 跳转到 https://mcp.so/

#### Scenario: 浏览 Glama

**Given** 用户点击"市场" → "Glama"
**When** 系统打开浏览器
**Then** 跳转到 https://glama.ai/mcp/servers

---

### Requirement: MCP 状态检测

系统必须支持检测 MCP 服务器状态。

#### Scenario: 检测 npm 版本

**Given** 用户点击"检测状态"按钮
**When** 系统检测 npm
**Then** 显示 npm 版本或"未安装"

#### Scenario: 检测 MCP 包安装状态

**Given** 用户点击"检测状态"按钮
**When** 系统检测每个 MCP 的包
**Then** 显示每个 MCP 的状态：
  - ✓ 已安装（版本号）
  - ✗ 未安装

## Data Model

```typescript
interface MCPServer {
  id: number;
  name: string;
  category: string;
  command: string;
  args: string;
  env: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

interface MCPRegistryItem {
  id: string;
  name: string;
  description: string;
  package: string;
  command: string;
  args: string;
  category: string;
  source: string;
  updated_at: string;
}

interface MCPStatus {
  name: string;
  installed: boolean;
  version?: string;
}
```

## Tauri Commands

```rust
#[tauri::command]
async fn load_mcp_servers() -> Result<Vec<MCPServer>, String>;

#[tauri::command]
async fn save_mcp_server(server: MCPServer) -> Result<(), String>;

#[tauri::command]
async fn delete_mcp_server(id: i64) -> Result<(), String>;

#[tauri::command]
async fn set_mcp_default(id: i64, is_default: bool) -> Result<(), String>;

#[tauri::command]
async fn sync_mcp_to_global() -> Result<(), String>;

#[tauri::command]
async fn scan_installed_mcp() -> Result<Vec<MCPServer>, String>;

#[tauri::command]
async fn import_mcp_from_json(json: String) -> Result<Vec<MCPServer>, String>;

#[tauri::command]
async fn sync_mcp_registry() -> Result<SyncResult, String>;

#[tauri::command]
async fn search_mcp_registry(keyword: String, category: String, limit: u32) -> Result<Vec<MCPRegistryItem>, String>;

#[tauri::command]
async fn get_mcp_registry_stats() -> Result<RegistryStats, String>;

#[tauri::command]
async fn check_mcp_status(servers: Vec<MCPServer>) -> Result<Vec<MCPStatus>, String>;

#[tauri::command]
async fn open_mcp_market(market: String) -> Result<(), String>;
```
