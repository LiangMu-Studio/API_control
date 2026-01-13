# History Management

## Overview

历史记录管理模块负责解析、展示和管理多种 AI CLI 工具的会话历史。这是性能优化的重点模块。

## ADDED Requirements

### Requirement: 多 CLI 历史记录支持

系统必须支持解析多种 CLI 工具的历史记录格式。

#### Scenario: 加载 Claude Code 历史

**Given** 用户选择 Claude CLI
**When** 系统扫描 `~/.claude/projects` 目录
**Then** 系统解析所有 `.jsonl` 文件
**And** 按项目文件夹分组显示
**And** 提取每个会话的 cwd、时间戳、消息数量

#### Claude 历史目录结构

```
~/.claude/projects/
├── {project_folder_hash}/
│   ├── {session_id}.jsonl
│   └── ...
└── ...
```

#### Scenario: 加载 Codex CLI 历史

**Given** 用户选择 Codex CLI
**When** 系统扫描 `~/.codex/sessions` 目录
**Then** 系统解析按日期分目录的 `.jsonl` 文件
**And** 按工作目录（cwd）分组显示
**And** 提取每个会话的元数据

#### Codex 历史目录结构

```
~/.codex/sessions/
├── 2025-01-01/
│   ├── {session_id}.jsonl
│   └── ...
├── 2025-01-02/
│   └── ...
└── ...
```

#### Scenario: 切换 CLI 类型

**Given** 用户正在查看 Claude 历史
**When** 用户从下拉框选择 Codex
**Then** 系统清空当前列表
**And** 加载 Codex 历史记录
**And** 显示加载进度

#### Scenario: 根据 KEY 配置自动选择 CLI

**Given** 用户在 API Keys 页面选中一个配置
**When** 系统检测到配置的 cli_type
**Then** 历史记录页面默认加载对应 CLI 的历史

---

### Requirement: 高性能历史扫描

系统必须能够快速扫描大量历史文件。

#### Scenario: 并行扫描

**Given** 存在 1000+ 会话文件
**When** 系统扫描历史目录
**Then** 使用 Rust rayon 并行扫描
**And** 扫描速度比 Python 版本快 10 倍以上

#### Rust 并行扫描实现

```rust
use rayon::prelude::*;
use walkdir::WalkDir;

fn scan_projects(base_dir: &Path) -> Vec<ProjectInfo> {
    WalkDir::new(base_dir)
        .min_depth(1)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_dir())
        .par_bridge()  // 并行处理
        .map(|entry| scan_single_project(entry.path()))
        .collect()
}
```

#### Scenario: 增量加载

**Given** 用户打开历史页面
**When** 系统开始加载
**Then** 首先快速显示项目列表（只读取目录结构和 cwd）
**And** 用户展开项目时再加载会话详情
**And** 显示加载进度条

#### Scenario: 快速获取项目 cwd

**Given** 用户打开历史页面
**When** 系统加载项目列表
**Then** 使用 `list_projects(with_cwd=True)` 快速获取前 10 个项目的真实路径
**And** 毫秒级显示项目路径

#### Scenario: LRU 缓存机制

**Given** 用户已加载过某个项目
**When** 用户再次展开该项目
**Then** 系统从缓存返回数据
**And** 缓存使用 LRU 策略，最多保留 50 个项目

#### Rust LRU 缓存实现

```rust
use lru::LruCache;
use std::sync::Mutex;

lazy_static! {
    static ref SESSION_CACHE: Mutex<LruCache<String, SessionDetail>> =
        Mutex::new(LruCache::new(NonZeroUsize::new(50).unwrap()));
}
```

---

### Requirement: 项目分组视图

系统必须以项目为单位分组显示会话。

#### Scenario: 显示项目列表

**Given** 历史记录已加载
**When** 用户查看项目列表
**Then** 每个项目显示：
  - 工作目录路径（缩短显示）
  - 会话数量
  - 最后活动时间
**And** 按最后活动时间倒序排列

#### Scenario: 展开项目

**Given** 项目列表已显示
**When** 用户点击项目标题
**Then** 展开显示该项目下的所有会话
**And** 每个会话显示：
  - 会话 ID（截断）
  - 对话轮次
  - 时间
  - 文件大小

#### Scenario: 打开项目目录

**Given** 项目列表已显示
**When** 用户点击文件夹图标
**Then** 系统在文件管理器中打开该目录

---

### Requirement: 会话详情查看

系统必须支持查看会话的详细内容。

#### Scenario: 显示会话详情

**Given** 用户选中一个会话
**When** 系统加载会话内容
**Then** 右侧面板显示：
  - 会话 ID
  - 工作目录
  - 对话轮次统计
  - 工具使用统计

#### Scenario: 显示对话时间线

**Given** 会话详情已加载
**When** 用户查看对话内容
**Then** 按轮次分组显示：
  - 用户消息（蓝色背景）
  - AI 回复文本
  - 工具调用时间线（带图标和颜色）

#### 工具调用图标映射

| 工具名 | 图标 | 颜色 |
|-------|------|------|
| Read | 📄 | 蓝色 |
| Write | ✏️ | 绿色 |
| Edit | 🔧 | 橙色 |
| Bash | 💻 | 紫色 |
| Glob | 🔍 | 青色 |
| Grep | 🔎 | 青色 |
| Task | 🤖 | 黄色 |
| WebFetch | 🌐 | 蓝色 |

#### Scenario: 展开工具调用详情

**Given** 对话时间线已显示
**When** 用户点击 Edit 工具调用
**Then** 展开显示 diff 内容：
  - 旧内容（红色背景）
  - 新内容（绿色背景）

#### Scenario: 分页加载对话

**Given** 会话有 100+ 轮对话
**When** 用户查看详情
**Then** 默认显示首尾各 1 轮
**And** 提供"向下 +3"和"向上 +3"按钮
**And** 点击按钮加载更多轮次

---

### Requirement: 搜索和过滤

系统必须支持搜索和过滤历史记录。

#### Scenario: 按项目路径搜索

**Given** 项目列表已显示
**When** 用户在搜索框输入关键词
**And** 按回车
**Then** 系统过滤显示路径包含关键词的项目

#### Scenario: 按日期过滤

**Given** 项目列表已显示
**When** 用户选择日期范围（开始日期、结束日期）
**Then** 系统只显示该时间范围内有活动的项目

#### Scenario: 日期筛选 UI

**Given** 用户打开历史页面
**When** 用户点击日期筛选控件
**Then** 显示日期选择器
**And** 支持快捷选项：今天、最近7天、最近30天、全部

---

### Requirement: 会话操作

系统必须支持对会话进行操作。

#### Scenario: 删除会话

**Given** 用户选中一个或多个会话
**When** 用户点击"删除"按钮
**And** 确认删除
**Then** 系统将会话移动到回收站
**And** 刷新会话列表

#### Scenario: 导出会话为 HTML

**Given** 用户选中一个会话
**When** 用户点击"导出 HTML"
**Then** 系统生成格式化的 HTML 文件
**And** 包含对话内容和工具调用
**And** 使用内置 CSS 样式

#### HTML 导出样式

```html
<style>
body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; }
.header { background: #333; color: white; padding: 15px; border-radius: 8px; }
.msg { padding: 12px; margin: 8px 0; border-radius: 8px; }
.user { background: #e3f2fd; border-left: 4px solid #2196f3; }
.assistant { background: #f5f5f5; border-left: 4px solid #4caf50; }
</style>
```

#### Scenario: 导出会话为 Markdown

**Given** 用户选中一个会话
**When** 用户点击"导出 MD"
**Then** 系统生成 Markdown 文件
**And** 包含对话内容

#### Scenario: 批量导出

**Given** 用户在项目列表
**When** 用户点击"批量导出"
**Then** 系统导出所有会话到指定目录
**And** 显示导出进度和结果
**And** 返回成功导出的数量

#### Scenario: 复制会话 ID

**Given** 用户选中一个会话
**When** 用户点击"复制 ID"
**Then** 系统将会话 ID 复制到剪贴板

#### Scenario: 复制恢复命令

**Given** 用户选中一个会话
**When** 用户点击"复制恢复命令"
**Then** 系统将 `claude --resume <session_id>` 复制到剪贴板

---

### Requirement: 回收站管理

系统必须支持回收站功能。

#### Scenario: 查看回收站

**Given** 用户点击"回收站"按钮
**When** 回收站对话框打开
**Then** 显示已删除的会话列表
**And** 每个项目显示：
  - 会话 ID
  - 项目名称
  - 删除时间
  - 剩余保留天数

#### Scenario: 恢复会话

**Given** 回收站中有会话
**When** 用户选中会话并点击"恢复"
**Then** 系统将会话恢复到原位置
**And** 刷新历史列表

#### Scenario: 永久删除

**Given** 回收站中有会话
**When** 用户选中会话并点击"永久删除"
**Then** 系统彻底删除会话文件
**And** 无法恢复

#### Scenario: 自动清理

**Given** 回收站中有过期会话（默认 7 天）
**When** 应用启动
**Then** 系统自动清理过期会话

#### Scenario: 配置保留周期

**Given** 用户打开回收站
**When** 用户修改保留天数
**And** 点击保存
**Then** 系统保存新的保留周期设置

---

### Requirement: 虚拟列表优化

系统必须使用虚拟列表优化大量数据的渲染。

#### Scenario: 虚拟滚动

**Given** 项目列表有 500+ 项
**When** 用户滚动列表
**Then** 只渲染可见区域的项目
**And** 滚动流畅无卡顿

#### React 虚拟列表实现

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

function ProjectList({ projects }) {
  const virtualizer = useVirtualizer({
    count: projects.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
  });
  // ...
}
```

## Data Model

```typescript
interface ProjectInfo {
  name: string;           // 项目文件夹名或 cwd
  cwd: string;            // 工作目录
  session_count: number;
  last_activity: string;
}

interface SessionInfo {
  id: string;
  project_name: string;
  cwd: string;
  file_path: string;
  message_count: number;
  first_timestamp: string;
  last_timestamp: string;
  size: number;
}

interface SessionDetail {
  id: string;
  cwd: string;
  messages: Message[];
  tool_stats: Record<string, number>;
  real_turns: number;
}

interface Message {
  type: 'user' | 'assistant';
  timestamp: string;
  content: string;
  tool_calls?: ToolCall[];
}

interface ToolCall {
  name: string;
  input: Record<string, any>;
  output?: string;
}

interface TrashItem {
  session_id: string;
  project_name: string;
  deleted_at: number;
  dir_name: string;
}

interface DateFilter {
  start_date?: string;  // YYYY-MM-DD
  end_date?: string;
}
```

## Tauri Commands

```rust
#[tauri::command]
async fn list_projects(
    cli_type: String,
    limit: Option<u32>,
    with_cwd: Option<bool>
) -> Result<Vec<ProjectInfo>, String>;

#[tauri::command]
async fn get_project_cwd(cli_type: String, project_name: String) -> Result<String, String>;

#[tauri::command]
async fn load_project_sessions(
    cli_type: String,
    project_name: String
) -> Result<Vec<SessionInfo>, String>;

#[tauri::command]
async fn load_session_detail(
    cli_type: String,
    session_id: String,
    file_path: String
) -> Result<SessionDetail, String>;

#[tauri::command]
async fn search_projects(
    cli_type: String,
    keyword: String,
    date_filter: Option<DateFilter>
) -> Result<Vec<ProjectInfo>, String>;

#[tauri::command]
async fn delete_sessions(
    cli_type: String,
    sessions: Vec<SessionInfo>
) -> Result<u32, String>;

#[tauri::command]
async fn delete_sessions_by_cwd(
    cli_type: String,
    cwd: String
) -> Result<u32, String>;

#[tauri::command]
async fn export_session_html(session: SessionDetail, path: String) -> Result<(), String>;

#[tauri::command]
async fn export_session_md(session: SessionDetail, path: String) -> Result<(), String>;

#[tauri::command]
async fn export_sessions_batch(
    sessions: Vec<SessionInfo>,
    dir: String,
    format: String
) -> Result<u32, String>;

#[tauri::command]
async fn get_trash_items(cli_type: String) -> Result<Vec<TrashItem>, String>;

#[tauri::command]
async fn restore_from_trash(cli_type: String, item: TrashItem) -> Result<(), String>;

#[tauri::command]
async fn permanently_delete(cli_type: String, item: TrashItem) -> Result<(), String>;

#[tauri::command]
async fn cleanup_expired_trash(cli_type: String, retention_days: u32) -> Result<u32, String>;

#[tauri::command]
async fn clear_session_cache() -> Result<(), String>;
```

## Performance Requirements

| 操作 | 目标时间 | 当前 Python 时间 |
|------|---------|-----------------|
| 扫描 1000 个项目 | < 500ms | ~5s |
| 加载单个项目会话 | < 100ms | ~500ms |
| 解析单个会话详情 | < 50ms | ~200ms |
| 快速获取 10 个项目 cwd | < 50ms | ~300ms |
