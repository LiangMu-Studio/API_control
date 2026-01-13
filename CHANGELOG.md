# 更新日志

## [0.9] - 2025-11-29

### 新增功能
- **Python 环境管理**
  - 自动检测系统中的 Conda 环境
  - 支持在打开终端时选择和激活指定的 Python 环境
  - 环境列表会自动刷新

- **Claude 自动启动**
  - 当选择 Anthropic 提供商时，打开终端会自动进入 Claude
  - 其他提供商（OpenAI、Azure、Custom）只激活环境，不启动 Claude
  - 完全自动化工作流程

### 改进
- 优化终端启动逻辑，确保环境激活后终端保持打开
- 改进环境变量设置方式，支持 PowerShell 和 CMD 的不同语法
- 增强了配置检测机制，根据提供商类型智能决定是否启动 Claude

### 修复
- 修复了终端启动后立即关闭的问题
- 修复了 PowerShell 中的语法错误
- 修复了环境激活命令的格式问题

### 技术细节
- 添加了 `detect_python_envs()` 函数用于检测系统 Python 环境
- 添加了 `get_python_activation_command()` 方法用于生成环境激活命令
- 添加了 `refresh_python_envs()` 方法用于刷新环境列表
- 改进了 `open_terminal()` 方法以支持环境激活和 Claude 自动启动

## [0.8] - 初始版本

### 功能
- API 密钥管理（新增、编辑、删除）
- 多个 API 配置支持
- 快速复制密钥功能
- 集成终端（PowerShell 7、PowerShell 5、CMD）
- 环境变量自动注入
- 配置导出/导入
- 快捷键支持
- 单实例运行
