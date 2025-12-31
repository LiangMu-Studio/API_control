# LiangMu-Studio API Key Manager v1.0 - 多CLI集成终端

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

A simple and easy-to-use API key management tool that supports multiple CLI tools (Claude Code, Codex CLI, Gemini CLI, Aider), multiple API configurations, quick switching, and integrated terminal.

### Features

#### Multi-CLI Tool Support
- **Claude Code** - Anthropic's Claude CLI tool
- **Codex CLI** - OpenAI's Codex CLI tool
- **Gemini CLI** - Google's Gemini CLI tool
- **Aider** - AI pair programming tool

#### Key Management
- **Add Configuration** - Add new API key configurations with CLI tool selection
- **Edit Configuration** - Modify existing configuration information
- **Delete Configuration** - Remove unwanted configurations
- **Copy Key** - One-click copy key to clipboard

#### Quick Operations
- **Keyboard Shortcuts**
  - `Ctrl+T` - Quick open terminal
  - `Ctrl+C` - Quick copy key
  - `Delete` - Quick delete configuration

#### Configuration Management
- **Export Configuration** - Save all configurations as JSON file (for backup)
- **Import Configuration** - Import configurations from JSON file (supports merging)
- **Sort Management** - Move up/down to adjust configuration order
- **3-Level Tree View** - Organized by CLI Tool → API Endpoint → Configuration

#### Integrated Terminal
- **Multi-terminal Support** - PowerShell 7, PowerShell 5, CMD, Git Bash
- **Windows Terminal Auto-detection** - Automatically uses Windows Terminal when available
- **Environment Variable Injection** - Automatically sets API keys and addresses
- **Working Directory Selection** - Specify the directory where terminal opens
- **Python Environment Management** - Auto-detect and activate Conda environments
- **CLI Auto-start** - Automatically starts the selected CLI tool

### Usage Guide

#### First Time Use

1. **Launch Software** - Run `main.py` or `LiangMu-API-Key.exe`
2. **Add Configuration** - Click "Add" button
3. **Fill Information**
   - CLI Tool: Select CLI tool type (Claude Code, Codex CLI, Gemini CLI, Aider)
   - Name: Configuration name (e.g., "My Claude API")
   - API Address: API endpoint address
   - KEY Name: Environment variable name (auto-filled based on CLI tool)
   - API Key: The actual API key

#### Open Terminal

1. **Select Configuration** - Click the configuration you want to use in the tree view
2. **Select Terminal** - Choose terminal type from dropdown menu
3. **Select Python Environment** (optional) - Choose Python environment to activate
4. **Select Directory** (optional) - Click "Browse" to select working directory
5. **Open Terminal** - Click "Open Terminal" or press `Ctrl+T`

The terminal will automatically:
- Activate the selected Python environment
- Inject the selected configuration's API key and address
- Start the selected CLI tool

### Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `Ctrl+T` | Open Terminal |
| `Ctrl+C` | Copy Key |
| `Delete` | Delete Configuration |
| `Double-click` | Edit Configuration |

### Supported CLI Tools

| CLI Tool | Default Key Name | Default Endpoint |
|----------|------------------|------------------|
| Claude Code | ANTHROPIC_API_KEY | https://api.anthropic.com |
| Codex CLI | OPENAI_API_KEY | https://api.openai.com/v1 |
| Gemini CLI | GEMINI_API_KEY | https://generativelanguage.googleapis.com |
| Aider | OPENAI_API_KEY | https://api.openai.com/v1 |

### Configuration File Locations

- **Configuration Data** - `data/config.json`
- **Terminal Settings** - `data/settings.json`
- **Last Opened Directory** - `data/last_folder.txt`

---

<a name="中文"></a>
## 中文

一个简单易用的 API 密钥管理工具，支持多种 CLI 工具（Claude Code、Codex CLI、Gemini CLI、Aider）、多个 API 配置、快速切换和集成终端。

### 功能特性

#### 多 CLI 工具支持
- **Claude Code** - Anthropic 的 Claude CLI 工具
- **Codex CLI** - OpenAI 的 Codex CLI 工具
- **Gemini CLI** - Google 的 Gemini CLI 工具
- **Aider** - AI 结对编程工具

#### 密钥管理
- **新增配置** - 添加新的 API 密钥配置，可选择 CLI 工具
- **编辑配置** - 修改已有的配置信息
- **删除配置** - 移除不需要的配置
- **复制密钥** - 一键复制密钥到剪贴板

#### 快速操作
- **快捷键支持**
  - `Ctrl+T` - 快速打开终端
  - `Ctrl+C` - 快速复制密钥
  - `Delete` - 快速删除配置

#### 配置管理
- **导出配置** - 将所有配置保存为 JSON 文件（备份用）
- **导入配置** - 从 JSON 文件导入配置（支持合并）
- **排序管理** - 上移/下移调整配置顺序
- **三级树形视图** - 按 CLI 工具 → API 端点 → 配置项 组织

#### 集成终端
- **多终端支持** - PowerShell 7、PowerShell 5、CMD、Git Bash
- **Windows Terminal 自动检测** - 安装后自动使用 Windows Terminal 打开终端
- **环境变量注入** - 自动设置 API 密钥和地址
- **工作目录选择** - 指定终端打开的目录
- **Python 环境管理** - 自动检测和激活 Conda 环境
- **CLI 自动启动** - 自动启动选定的 CLI 工具

### 使用指南

#### 第一次使用

1. **启动软件** - 运行 `main.py` 或 `LiangMu-API-Key.exe`
2. **添加配置** - 点击"新增"按钮
3. **填写信息**
   - CLI工具：选择 CLI 工具类型（Claude Code、Codex CLI、Gemini CLI、Aider）
   - 名称：配置的名称（如 "我的 Claude API"）
   - API地址：API 的端点地址
   - KEY名称：环境变量名称（根据 CLI 工具自动填充）
   - API密钥：实际的 API 密钥

#### 打开终端

1. **选择配置** - 在树形视图中点击要使用的配置
2. **选择终端** - 从下拉菜单选择终端类型
3. **选择 Python 环境**（可选）- 从下拉菜单选择要激活的 Python 环境
4. **选择目录**（可选）- 点击"浏览"选择工作目录
5. **打开终端** - 点击"打开终端"或按 `Ctrl+T`

终端会自动：
- 激活选定的 Python 环境
- 注入选中配置的 API 密钥和地址
- 启动选定的 CLI 工具

### 快捷键速查

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+T` | 打开终端 |
| `Ctrl+C` | 复制密钥 |
| `Delete` | 删除配置 |
| `双击` | 编辑配置 |

### 支持的 CLI 工具

| CLI 工具 | 默认 KEY 名称 | 默认端点 |
|----------|---------------|----------|
| Claude Code | ANTHROPIC_API_KEY | https://api.anthropic.com |
| Codex CLI | OPENAI_API_KEY | https://api.openai.com/v1 |
| Gemini CLI | GEMINI_API_KEY | https://generativelanguage.googleapis.com |
| Aider | OPENAI_API_KEY | https://api.openai.com/v1 |

### 配置文件位置

- **配置数据** - `data/config.json`
- **终端设置** - `data/settings.json`
- **最后打开目录** - `data/last_folder.txt`

### 常见问题

**Q: 密钥会被保存吗？**
A: 是的，密钥保存在本地 `data/config.json` 文件中。请妥善保管此文件。

**Q: 可以同时打开多个终端吗？**
A: 可以。每次点击"打开终端"都会创建一个新的终端窗口。

**Q: 如何迁移到其他电脑？**
A: 使用"导出"功能备份配置，然后在新电脑上使用"导入"功能恢复。

---

## Version History / 版本历史

### v1.0 (2025-12-31)
- Added multi-CLI tool support (Claude Code, Codex CLI, Gemini CLI, Aider) / 新增多 CLI 工具支持
- Added 3-level tree view (CLI Tool → Endpoint → Config) / 新增三级树形视图
- Added Windows Terminal auto-detection and integration / 新增 Windows Terminal 自动检测和集成
- Added UTF-8 encoding support for conda / 新增 conda UTF-8 编码支持
- Optimized terminal startup logic / 优化终端启动逻辑

### v0.9 (2025-11-29)
- Added Python environment auto-detection and activation / 新增 Python 环境自动检测和激活功能
- Added Claude auto-start feature / 新增 Claude 自动启动功能

### v0.8
- Initial version / 初始版本
- Multi API configuration management / 支持多个 API 配置管理
- Integrated terminal functionality / 集成终端功能

---

## License / 许可证

GPL v3

## Developer / 开发者

LiangMu-Studio

## Feedback / 反馈

[Issues](https://github.com/LiangMu-Studio/API_control/issues)
