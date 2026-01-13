# LiangMu Dev

## Purpose

LiangMu Dev 是一个跨平台桌面应用，用于统一管理多种 AI CLI 工具（Claude Code、Codex CLI、Gemini CLI、Aider）的 API 密钥、提示词、MCP 服务器配置和历史记录。

**核心目标：**
- 统一管理多个 AI CLI 工具的配置
- 提供高性能的历史记录管理
- 简化 MCP 服务器配置
- 提供便捷的终端启动功能

## Tech Stack

### 当前技术栈（待迁移）
- Python 3.11+
- Flet (Flutter for Python)
- SQLite
- PyInstaller

### 目标技术栈
- Rust (Tauri 后端)
- React + TypeScript (前端)
- SQLite (rusqlite)
- Tauri 内置打包

## Project Conventions

### Code Style

**Rust:**
- 使用 rustfmt 格式化
- 遵循 Rust API Guidelines
- 错误处理使用 Result/Option
- 异步使用 tokio

**TypeScript/React:**
- 使用 ESLint + Prettier
- 函数组件 + Hooks
- 状态管理使用 Zustand
- 样式使用 Tailwind CSS

### Architecture Patterns

**前后端分离:**
- Tauri Commands 作为 API 层
- React 负责 UI 渲染
- Rust 负责文件系统、数据库、系统调用

**状态管理:**
- 前端：Zustand stores
- 后端：Rust 结构体 + Mutex

### Testing Strategy

- Rust: 单元测试 + 集成测试
- React: Vitest + React Testing Library
- E2E: Playwright (可选)

### Git Workflow

- main: 稳定版本
- feature/*: 功能分支
- Conventional Commits 规范

## Domain Context

### 支持的 CLI 工具

| CLI | 配置目录 | 历史目录 | 提示词文件 |
|-----|---------|---------|-----------|
| Claude Code | ~/.claude | ~/.claude/projects | CLAUDE.md |
| Codex CLI | ~/.codex | ~/.codex/sessions | AGENTS.md |
| Gemini CLI | ~/.gemini | - | GEMINI.md |
| Aider | - | - | .aider.conf.yml |

### MCP (Model Context Protocol)

MCP 是 Anthropic 定义的协议，允许 AI 工具调用外部服务。配置格式：
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

### 历史记录格式

**Claude Code:** JSONL 格式，每行一条消息
```json
{"type": "user", "timestamp": "...", "cwd": "...", "message": {...}}
{"type": "assistant", "timestamp": "...", "message": {...}}
```

**Codex CLI:** JSONL 格式，按日期分目录
```
~/.codex/sessions/2025/01/06/rollout-xxx.jsonl
```

## Important Constraints

1. **跨平台支持**: Windows、macOS、Linux
2. **性能要求**: 历史记录扫描需支持 10000+ 会话
3. **安全性**: API Key 不能明文存储在日志中
4. **兼容性**: 需兼容现有 Flet 版本的配置文件格式

## External Dependencies

### 系统依赖
- Node.js (MCP 服务器运行)
- 终端模拟器 (Windows Terminal / PowerShell / CMD)

### 网络服务
- npm registry (MCP 仓库同步)
- GitHub API (更新检查、Gist 同步)
- 各 AI 提供商 API (密钥验证)

## 核心功能模块

### 1. API Keys 管理
- 多 CLI 工具支持
- 三级树形配置：CLI → 端点 → 配置项
- API Key 验证和余额查询
- 模型选择和参数配置

### 2. 提示词管理
- 全局系统提示词
- 用户自定义提示词
- 模板变量支持
- 自动写入 CLI 配置文件

### 3. MCP 服务器管理
- 配置管理（command, args, env）
- 分类管理
- npm 仓库同步
- 状态检测

### 4. 历史记录管理
- 多 CLI 历史解析
- 项目分组
- 会话详情（消息、工具调用）
- 搜索、过滤、导出
- 回收站

### 5. 系统功能
- 多语言（中/英）
- 主题切换
- 系统托盘
- 全局快捷键
- 单实例运行
