# AI CLI Manager

<p align="center">
  <img src="icon.jpg" width="128" height="128" alt="AI CLI Manager">
</p>

<p align="center">
  <strong>A powerful management tool for AI CLI tools</strong><br>
  <strong>强大的 AI CLI 工具管理器</strong>
</p>

<p align="center">
  <a href="#english">English</a> | <a href="#中文">中文</a>
</p>

---

<a name="english"></a>
## English

AI CLI Manager is a comprehensive desktop application for managing AI command-line tools. It provides unified management for API keys, MCP servers, prompt templates, and conversation history across multiple AI CLI tools.

### Supported AI CLI Tools

| CLI Tool | Command | Provider | Description |
|----------|---------|----------|-------------|
| Claude Code | `claude` | Anthropic | Anthropic's official CLI for Claude |
| Codex CLI | `codex` | OpenAI | OpenAI's coding assistant CLI |
| Gemini CLI | `gemini` | Google | Google's Gemini AI CLI |
| Aider | `aider` | Multiple | AI pair programming tool |

### Key Features

#### 1. API Key Management
- **Multi-Provider Support**: OpenAI, Anthropic, Google Gemini, DeepSeek, GLM (Zhipu), Custom endpoints
- **Model Selection**: Configure specific models for each API key (GPT-5, Claude Opus 4.5, Gemini 3 Pro, etc.)
- **Auto Model Injection**: Terminal launches with `--model` parameter automatically
- **Tree View Organization**: CLI Tool → API Endpoint → Configuration hierarchy
- **Import/Export**: Backup and restore all configurations as JSON
- **API Validation**: Test API keys before saving

#### 2. MCP Server Management
- **Online Registry**: Browse 1000+ MCP servers from npm registry
- **Category Filter**: File, Network, Database, Knowledge Base, Development, Search, etc.
- **Full-Text Search**: Search by name or description
- **Default MCP Set**: Mark MCPs as default for all projects
- **Per-Project Config**: Generate `.mcp.json` for specific working directories
- **One-Click Install**: Automatic npm package installation
- **Usage Statistics**: Track MCP usage across projects

#### 3. Skill Management
- **Skill Library**: Manage custom skills (slash commands)
- **Skill Presets**: Create preset combinations for different workflows
- **Usage Tracking**: Monitor skill usage statistics

#### 4. Prompt Management
- **System Prompt**: Global system prompt applied to all conversations
- **User Prompts**: Category-based templates (Coding, Writing, Analysis, Drawing)
- **Built-in Templates**: Pre-configured prompts for common tasks
- **CLI Integration**: Auto-write to CLAUDE.md, AGENTS.md, GEMINI.md
- **SQLite Storage**: Fast and reliable prompt database

#### 5. Conversation History
- **Multi-CLI Support**: View history from Claude Code and Codex CLI
- **Rust-Powered Parser**: High-performance history parsing with `liangmu_history` library
- **Session Browser**: Browse conversations organized by project/date
- **Full-Text Search**: Search across all conversations
- **Batch Operations**: Select and delete multiple sessions
- **Date Filtering**: Today, this week, this month, or custom range
- **Export to Markdown**: Export conversations for documentation
- **Trash & Recovery**: Deleted sessions go to trash with 30-day retention

#### 6. Screenshot Tool
- **WeChat-Style Interface**: Familiar region selection UI
- **Annotation Tools**: Rectangle, Ellipse, Arrow, Line, Text, Pen, Mosaic
- **Color Picker**: Choose annotation colors
- **Global Hotkey**: Customizable shortcut (default: Alt+S)
- **Auto Cleanup**: Screenshots auto-delete after 7 days
- **Clipboard Integration**: Auto-copy to clipboard after capture

#### 7. Integrated Terminal
- **Multi-Terminal Support**: PowerShell 7, PowerShell 5, CMD, Git Bash
- **Environment Injection**: Auto-set API keys, endpoints, and base URLs
- **Python Environment**: Auto-detect and activate Conda environments
- **Working Directory**: Quick directory picker with history
- **CLI Auto-Start**: Automatically launch selected CLI with configured model
- **Copy Path Tool**: Alt+C to copy current path from any window

#### 8. System Features
- **System Tray**: Minimize to tray, quick access menu
- **Theme Support**: Light/Dark mode with custom themes
- **Multi-Language**: English and Chinese interface
- **High DPI Support**: Proper scaling on high-resolution displays
- **Auto Update Check**: Notify when new versions are available

### Installation

#### Option 1: pip install (All Platforms)
```bash
# Install from GitHub
pip install git+https://github.com/LiangMu-Studio/AI_CLI_Manager.git

# Run
ai-cli-manager
```

#### Option 2: Run from Source
```bash
# Clone the repository
git clone https://github.com/LiangMu-Studio/AI_CLI_Manager.git
cd AI_CLI_Manager

# Install dependencies
pip install -e .

# Run
python main.py
```

#### Option 3: Download Release (Windows)
Download `AI-CLI-Manager-Windows.zip` from [Releases](https://github.com/LiangMu-Studio/AI_CLI_Manager/releases)

### Usage

1. **Launch**: Run `main.py` or `AI-CLI-Manager.exe`
2. **Add API Key**: Click "Add" → Select provider → Enter API key and select model
3. **Configure MCP**: Go to MCP tab → Browse registry → Add to library → Set as default
4. **Set Prompts**: Go to Prompts tab → Edit system prompt or add user prompts
5. **Open Terminal**: Select configuration → Set working directory → Click "Open Terminal"

### Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `Alt+S` | Screenshot (customizable) |
| `Alt+C` | Copy current path |
| `Ctrl+T` | Open Terminal |
| `Ctrl+C` | Copy API Key |
| `Delete` | Delete selected item |
| `Double-click` | Edit configuration |

### Requirements

- Windows 10/11
- Python 3.10+ (for source)
- Node.js (for MCP servers)

---

<a name="中文"></a>
## 中文

AI CLI Manager 是一个全面的桌面应用程序，用于管理 AI 命令行工具。它为多个 AI CLI 工具提供统一的 API 密钥、MCP 服务器、提示词模板和对话历史管理。

### 支持的 AI CLI 工具

| CLI 工具 | 命令 | 提供商 | 描述 |
|----------|------|--------|------|
| Claude Code | `claude` | Anthropic | Anthropic 官方 Claude CLI |
| Codex CLI | `codex` | OpenAI | OpenAI 编程助手 CLI |
| Gemini CLI | `gemini` | Google | Google Gemini AI CLI |
| Aider | `aider` | 多家 | AI 结对编程工具 |

### 核心功能

#### 1. API 密钥管理
- **多提供商支持**：OpenAI、Anthropic、Google Gemini、DeepSeek、GLM（智谱）、自定义端点
- **模型选择**：为每个 API 密钥配置特定模型（GPT-5、Claude Opus 4.5、Gemini 3 Pro 等）
- **自动模型注入**：终端启动时自动带上 `--model` 参数
- **树形视图组织**：CLI 工具 → API 端点 → 配置项 层级结构
- **导入/导出**：JSON 格式备份和恢复所有配置
- **API 验证**：保存前测试 API 密钥有效性

#### 2. MCP 服务器管理
- **在线注册表**：浏览 npm 上 1000+ 个 MCP 服务器
- **分类筛选**：文件、网络、数据库、知识库、开发、搜索等
- **全文搜索**：按名称或描述搜索
- **默认 MCP 集**：标记 MCP 为所有项目的默认配置
- **项目配置**：为特定工作目录生成 `.mcp.json`
- **一键安装**：自动安装 npm 包
- **使用统计**：跟踪各项目的 MCP 使用情况

#### 3. Skill 管理
- **Skill 库**：管理自定义 Skill（斜杠命令）
- **Skill 预设**：为不同工作流创建预设组合
- **使用追踪**：监控 Skill 使用统计

#### 4. 提示词管理
- **系统提示词**：应用于所有对话的全局系统提示词
- **用户提示词**：按分类组织的模板（编程、写作、分析、绘画）
- **内置模板**：预配置的常用任务提示词
- **CLI 集成**：自动写入 CLAUDE.md、AGENTS.md、GEMINI.md
- **SQLite 存储**：快速可靠的提示词数据库

#### 5. 对话历史
- **多 CLI 支持**：查看 Claude Code 和 Codex CLI 的历史
- **Rust 加速解析**：使用 `liangmu_history` 库高性能解析历史
- **会话浏览**：按项目/日期组织浏览对话
- **全文搜索**：跨所有对话搜索
- **批量操作**：选择并删除多个会话
- **日期过滤**：今天、本周、本月或自定义范围
- **导出 Markdown**：导出对话用于文档
- **回收站与恢复**：删除的会话进入回收站，保留 30 天

#### 6. 截图工具
- **微信风格界面**：熟悉的区域选择 UI
- **标注工具**：矩形、椭圆、箭头、直线、文字、画笔、马赛克
- **颜色选择器**：选择标注颜色
- **全局快捷键**：可自定义快捷键（默认：Alt+S）
- **自动清理**：截图 7 天后自动删除
- **剪贴板集成**：截图后自动复制到剪贴板

#### 7. 集成终端
- **多终端支持**：PowerShell 7、PowerShell 5、CMD、Git Bash
- **环境注入**：自动设置 API 密钥、端点和 Base URL
- **Python 环境**：自动检测和激活 Conda 环境
- **工作目录**：带历史记录的快速目录选择器
- **CLI 自动启动**：自动启动选定的 CLI 并使用配置的模型
- **复制路径工具**：Alt+C 从任意窗口复制当前路径

#### 8. 系统功能
- **系统托盘**：最小化到托盘，快速访问菜单
- **主题支持**：明/暗模式及自定义主题
- **多语言**：中英文界面
- **高 DPI 支持**：高分辨率显示器正确缩放
- **自动更新检查**：新版本可用时通知

### 安装

#### 方式一：pip 安装（全平台）
```bash
# 从 GitHub 安装
pip install git+https://github.com/LiangMu-Studio/AI_CLI_Manager.git

# 运行
ai-cli-manager
```

#### 方式二：从源码运行
```bash
# 克隆仓库
git clone https://github.com/LiangMu-Studio/AI_CLI_Manager.git
cd AI_CLI_Manager

# 安装依赖
pip install -e .

# 运行
python main.py
```

#### 方式三：下载发布版（Windows）
从 [Releases](https://github.com/LiangMu-Studio/AI_CLI_Manager/releases) 下载 `AI-CLI-Manager-Windows.zip`

### 使用方法

1. **启动**：运行 `main.py` 或 `AI-CLI-Manager.exe`
2. **添加密钥**：点击"新增" → 选择提供商 → 输入 API 密钥并选择模型
3. **配置 MCP**：进入 MCP 标签 → 浏览注册表 → 添加到库 → 设为默认
4. **设置提示词**：进入提示词标签 → 编辑系统提示词或添加用户提示词
5. **打开终端**：选择配置 → 设置工作目录 → 点击"打开终端"

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt+S` | 截图（可自定义）|
| `Alt+C` | 复制当前路径 |
| `Ctrl+T` | 打开终端 |
| `Ctrl+C` | 复制 API 密钥 |
| `Delete` | 删除选中项 |
| `双击` | 编辑配置 |

### 系统要求

- Windows 10/11
- Python 3.10+（源码运行）
- Node.js（MCP 服务器需要）

---

## Project Structure / 项目结构

```
AI_CLI_Manager/
├── main.py                  # Main entry / 主入口
├── AI-CLI-Manager.spec      # PyInstaller config / 打包配置
├── icon.ico                 # App icon / 应用图标
│
├── ui/                      # User Interface / 用户界面
│   ├── common.py            # Common configs, themes / 公共配置、主题
│   ├── state.py             # App state management / 应用状态管理
│   ├── lang.py              # i18n support / 多语言支持
│   ├── database.py          # Database operations / 数据库操作
│   ├── hotkey.py            # Global hotkeys / 全局快捷键
│   ├── tray.py              # System tray / 系统托盘
│   ├── theme_manager.py     # Theme manager / 主题管理器
│   ├── pages/               # Page modules / 页面模块
│   │   ├── api_keys.py      # API keys page / API 密钥页面
│   │   ├── mcp.py           # MCP server page / MCP 服务器页面
│   │   ├── skills.py        # Skills page / Skill 页面
│   │   ├── prompts.py       # Prompts page / 提示词页面
│   │   └── history.py       # History page / 历史记录页面
│   └── tools/               # Tool modules / 工具模块
│       ├── screenshot_tool.py  # Screenshot tool / 截图工具
│       ├── path_picker.py      # Path picker / 路径选择器
│       └── copypath_tool.py    # Copy path tool / 复制路径工具
│
├── core/                    # Core logic / 核心逻辑
│   ├── key_manager.py       # Key management / 密钥管理
│   ├── api_validator.py     # API validation / API 验证
│   ├── history_parser.py    # History parsing / 历史解析
│   ├── token_counter.py     # Token counting / Token 计数
│   ├── service_factory.py   # API service factory / API 服务工厂
│   ├── anthropic_service.py # Anthropic API
│   ├── openai_service.py    # OpenAI API
│   ├── gemini_service.py    # Gemini API
│   ├── glm_service.py       # GLM API
│   └── deepseek_service.py  # DeepSeek API
│
├── liangmu_history/         # Rust history parser / Rust 历史解析库
│   ├── Cargo.toml           # Rust config / Rust 配置
│   └── src/                 # Rust source / Rust 源码
│
├── services/                # API service wrappers / API 服务封装
│   └── api_services/        # Provider services / 各提供商服务
│
├── data/                    # User data (not in repo) / 用户数据（不在仓库中）
│   ├── config.json          # API configs / API 配置
│   ├── settings.json        # App settings / 应用设置
│   └── prompts.db           # Prompts database / 提示词数据库
│
└── mcp_data/                # MCP registry / MCP 注册表
    ├── mcp_registry.db      # MCP server database / MCP 服务器数据库
    └── tool_usage.db        # Usage statistics / 使用统计
```

---

## Version History / 版本历史

### v1.0 (2026-01-12)
- Initial public release / 首个公开发布版本
- Multi-provider API key management / 多提供商 API 密钥管理
- MCP server management with online registry / MCP 服务器管理及在线注册表
- Skill management and presets / Skill 管理和预设
- Prompt management with SQLite storage / 提示词管理及 SQLite 存储
- Conversation history viewer with Rust acceleration / Rust 加速的对话历史查看
- WeChat-style screenshot tool / 微信风格截图工具
- Integrated terminal with environment injection / 集成终端及环境注入
- System tray support / 系统托盘支持
- Supported models / 支持的模型:
  - OpenAI: GPT-4o, GPT-5, GPT-5.1-codex-max, GPT-5.2-codex-high
  - Anthropic: Claude Haiku 4.5, Claude Sonnet 4.5, Claude Opus 4.5
  - Google: Gemini 2.5 Pro/Flash, Gemini 3 Pro Preview/High/Image
  - GLM: GLM-4.7 (5 thinking modes)
  - DeepSeek: DeepSeek Chat/Coder

---

## License / 许可证

GPL v3

## Developer / 开发者

LiangMu-Studio

## Feedback / 反馈

[GitHub Issues](https://github.com/LiangMu-Studio/AI_CLI_Manager/issues)
