# AI CLI Manager v1.0

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

A comprehensive management tool for AI CLI tools. Supports multi-provider API key management, MCP server configuration, prompt templates, and conversation history viewing.

### Features

#### API Key Management
- **Multi-Provider Support**: OpenAI, Anthropic, Google Gemini, DeepSeek, GLM (Zhipu), Custom
- **Model Selection**: Configure specific models for each API key
- **Auto Model Injection**: Terminal launches with `--model` parameter based on configuration
- **Tree View**: Organized by CLI Tool → API Endpoint → Configuration
- **Import/Export**: Backup and restore configurations as JSON

#### Supported CLI Tools
| CLI Tool | Command | Default Key Name |
|----------|---------|------------------|
| Claude Code | `claude` | ANTHROPIC_API_KEY |
| Codex CLI | `codex` | OPENAI_API_KEY |
| Gemini CLI | `gemini` | GEMINI_API_KEY |
| Aider | `aider` | OPENAI_API_KEY |

#### MCP Server Management
- **MCP Registry**: Browse and install MCP servers from online registry
- **Category Organization**: File, Network, Data, Common, Other
- **Global Default**: Set default MCP servers for all projects
- **Per-Project Config**: Sync MCP configuration to working directory
- **One-Click Install**: Automatic npm package installation

#### Prompt Management
- **Global System Prompt**: Applied to all conversations
- **User Prompts**: Category-based prompt templates (Coding, Writing, Analysis, Drawing)
- **Built-in Templates**: Pre-configured prompts for common tasks
- **CLI Integration**: Write prompts to CLAUDE.md, AGENTS.md, GEMINI.md

#### Conversation History
- **Multi-CLI Support**: View history from Claude Code and Codex CLI
- **Session Browser**: Browse conversations by date
- **Search**: Filter sessions by keyword
- **Batch Operations**: Select and delete multiple sessions
- **Date Filtering**: Filter by today, week, month, or custom range

#### Screenshot Tool
- **WeChat-Style Screenshot**: Region selection with annotation tools
- **Annotation Tools**: Rectangle, Ellipse, Arrow, Line, Text, Pen
- **Global Hotkey**: Customizable shortcut (default: Alt+S)
- **Auto Cleanup**: Screenshots auto-delete after 7 days

#### Integrated Terminal
- **Multi-Terminal Support**: PowerShell 7, PowerShell 5, CMD, Git Bash
- **Environment Injection**: Auto-set API keys and endpoints
- **Python Environment**: Auto-detect and activate Conda environments
- **Working Directory**: Specify terminal startup directory
- **CLI Auto-Start**: Automatically launches selected CLI tool with configured model

### Usage

1. **Launch**: Run `app_flet.py` or `LiangMu-API-Key.exe`
2. **Add API Key**: Click "Add" → Select provider → Fill in details
3. **Select Configuration**: Click a key in the tree view
4. **Open Terminal**: Set working directory → Click "Open Terminal"

### Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `Alt+S` | Screenshot (customizable) |
| `Ctrl+T` | Open Terminal |
| `Ctrl+C` | Copy Key |
| `Delete` | Delete Configuration |
| `Double-click` | Edit Configuration |

---

<a name="中文"></a>
## 中文

一个全面的 AI CLI 工具管理器。支持多提供商 API 密钥管理、MCP 服务器配置、提示词模板和对话历史查看。

### 功能特性

#### API 密钥管理
- **多提供商支持**：OpenAI、Anthropic、Google Gemini、DeepSeek、GLM（智谱）、自定义
- **模型选择**：为每个 API 密钥配置特定模型
- **自动模型注入**：终端启动时自动带上 `--model` 参数
- **树形视图**：按 CLI 工具 → API 端点 → 配置项 组织
- **导入/导出**：JSON 格式备份和恢复配置

#### 支持的 CLI 工具
| CLI 工具 | 命令 | 默认 KEY 名称 |
|----------|------|---------------|
| Claude Code | `claude` | ANTHROPIC_API_KEY |
| Codex CLI | `codex` | OPENAI_API_KEY |
| Gemini CLI | `gemini` | GEMINI_API_KEY |
| Aider | `aider` | OPENAI_API_KEY |

#### MCP 服务器管理
- **MCP 注册表**：浏览和安装在线 MCP 服务器
- **分类组织**：文件、网络、数据、常用、其他
- **全局默认**：设置所有项目的默认 MCP 服务器
- **项目配置**：同步 MCP 配置到工作目录
- **一键安装**：自动安装 npm 包

#### 提示词管理
- **全局系统提示词**：应用于所有对话
- **用户提示词**：按分类组织的提示词模板（编程、写作、分析、绘画）
- **内置模板**：预配置的常用任务提示词
- **CLI 集成**：写入 CLAUDE.md、AGENTS.md、GEMINI.md

#### 对话历史
- **多 CLI 支持**：查看 Claude Code 和 Codex CLI 的历史
- **会话浏览**：按日期浏览对话
- **搜索**：按关键词过滤会话
- **批量操作**：选择并删除多个会话
- **日期过滤**：按今天、本周、本月或自定义范围过滤

#### 截图工具
- **微信风格截图**：区域选择和标注工具
- **标注工具**：矩形、椭圆、箭头、直线、文字、画笔
- **全局快捷键**：可自定义快捷键（默认：Alt+S）
- **自动清理**：截图 7 天后自动删除

#### 集成终端
- **多终端支持**：PowerShell 7、PowerShell 5、CMD、Git Bash
- **环境注入**：自动设置 API 密钥和端点
- **Python 环境**：自动检测和激活 Conda 环境
- **工作目录**：指定终端启动目录
- **CLI 自动启动**：自动启动选定的 CLI 工具并使用配置的模型

### 使用方法

1. **启动**：运行 `app_flet.py` 或 `LiangMu-API-Key.exe`
2. **添加密钥**：点击"新增" → 选择提供商 → 填写信息
3. **选择配置**：在树形视图中点击密钥
4. **打开终端**：设置工作目录 → 点击"打开终端"

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt+S` | 截图（可自定义）|
| `Ctrl+T` | 打开终端 |
| `Ctrl+C` | 复制密钥 |
| `Delete` | 删除配置 |
| `双击` | 编辑配置 |

---

## Project Structure / 项目结构

```
AI_CLI_Manager/
├── app_flet.py              # 主入口 / Main entry
├── LiangMu-API-Key.spec     # PyInstaller 打包配置 / Build config
├── icon.ico                 # 应用图标 / App icon
│
├── ui/                      # 用户界面 / User Interface
│   ├── common.py            # 公共配置、主题、CLI定义 / Common configs
│   ├── state.py             # 应用状态管理 / App state
│   ├── lang.py              # 多语言支持 / i18n
│   ├── database.py          # 数据库操作 / Database ops
│   ├── hotkey.py            # 全局快捷键 / Global hotkeys
│   ├── theme_manager.py     # 主题管理器 / Theme manager
│   ├── pages/               # 页面模块 / Page modules
│   │   ├── api_keys.py      # API 密钥页面 / API keys page
│   │   ├── mcp.py           # MCP 服务器页面 / MCP page
│   │   ├── prompts.py       # 提示词页面 / Prompts page
│   │   └── history.py       # 历史记录页面 / History page
│   └── tools/               # 工具模块 / Tool modules
│       └── screenshot_tool.py # 截图工具 / Screenshot tool
│
├── core/                    # 核心逻辑 / Core logic
│   ├── key_manager.py       # 密钥管理 / Key management
│   ├── token_counter.py     # Token 计数 / Token counting
│   ├── file_manager.py      # 文件操作 / File operations
│   ├── service_factory.py   # API 服务工厂 / Service factory
│   ├── anthropic_service.py # Anthropic API
│   ├── openai_service.py    # OpenAI API
│   ├── gemini_service.py    # Gemini API
│   └── glm_service.py       # GLM API
│
├── services/                # API 服务封装 / API services
│   └── api_services/        # 各提供商服务 / Provider services
│
├── data/                    # 用户数据（不打包）/ User data
│   ├── config.json          # API 配置 / API configs
│   ├── settings.json        # 应用设置 / App settings
│   ├── mcp.json             # MCP 配置 / MCP configs
│   └── prompts.db           # 提示词数据库 / Prompts DB
│
└── mcp_data/                # MCP 注册表（打包）/ MCP registry
    └── mcp_registry.db      # MCP 服务器数据库 / MCP DB
```

---

## Version History / 版本历史

### v1.1 (2026-01-02)
- Screenshot tool with WeChat-style annotation / 微信风格截图标注工具
- Global hotkey support (Alt+S) / 全局快捷键支持
- Auto cleanup screenshots after 7 days / 截图 7 天自动清理
- Theme manager optimization / 主题管理器优化

### v1.0 (2026-01-01)
- Initial release with full feature set / 首个完整功能版本
- Multi-provider API key management / 多提供商 API 密钥管理
- MCP server management / MCP 服务器管理
- Prompt management with categories / 分类提示词管理
- Conversation history viewer / 对话历史查看
- Model selection per API key / 每个密钥的模型选择
- Auto `--model` parameter on terminal launch / 终端启动自动带模型参数

---

## License / 许可证

GPL v3

## Developer / 开发者

LiangMu-Studio

## Feedback / 反馈

[Issues](https://github.com/LiangMu-Studio/AI_CLI_Manager/issues)
