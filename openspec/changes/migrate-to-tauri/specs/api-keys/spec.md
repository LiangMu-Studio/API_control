# API Keys Management

## Overview

API Keys 管理模块负责管理多种 AI CLI 工具的配置，包括 API 密钥、端点、模型选择等。支持 6 种提供商类型。

## ADDED Requirements

### Requirement: 配置数据管理

系统必须支持 CRUD 操作管理 API 配置。

#### Scenario: 加载配置列表

**Given** 应用启动
**When** 用户进入 API Keys 页面
**Then** 系统从数据库加载所有配置
**And** 按 CLI 类型分组显示在树形视图中
**And** 恢复上次选中的配置项

#### Scenario: 创建新配置

**Given** 用户点击"添加"按钮
**When** 用户填写配置信息（名称、CLI类型、端点、API Key）
**And** 点击"保存"
**Then** 系统验证必填字段
**And** 保存配置到数据库
**And** 刷新配置列表

#### Scenario: 编辑配置

**Given** 用户选中一个配置
**When** 用户修改配置信息
**And** 点击"保存"
**Then** 系统更新数据库中的配置
**And** 刷新配置列表

#### Scenario: 删除配置

**Given** 用户选中一个配置
**When** 用户点击"删除"按钮
**And** 确认删除
**Then** 系统从数据库删除配置
**And** 刷新配置列表

---

### Requirement: 提供商默认配置

系统必须为每种提供商预设默认配置。

#### Provider: OpenAI

```json
{
  "endpoint": "https://api.openai.com/v1",
  "key_name": "OPENAI_API_KEY",
  "available_models": ["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "gpt-5", "gpt-5.1-codex-max"],
  "default_model": "gpt-4o"
}
```

#### Provider: Anthropic

```json
{
  "endpoint": "https://api.anthropic.com",
  "key_name": "ANTHROPIC_AUTH_TOKEN",
  "available_models": ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929", "claude-opus-4-5-20251101"],
  "default_model": "claude-haiku-4-5-20251001"
}
```

#### Provider: Gemini

```json
{
  "endpoint": "https://generativelanguage.googleapis.com/v1beta",
  "key_name": "x-goog-api-key",
  "available_models": [
    {"name": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
    {"name": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"name": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite"},
    {"name": "gemini-3-pro-preview", "label": "Gemini 3 Pro Preview"}
  ],
  "default_model": "gemini-2.5-pro"
}
```

#### Provider: DeepSeek

```json
{
  "endpoint": "https://api.deepseek.com/v1",
  "key_name": "DEEPSEEK_API_KEY",
  "available_models": ["DeepSeek-V3.2", "DeepSeek-V3", "DeepSeek-R1"],
  "default_model": "DeepSeek-V3.2"
}
```

#### Provider: GLM (智谱)

```json
{
  "endpoint": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
  "key_name": "ZHIPU_API_KEY",
  "available_models": [
    {"name": "glm-4.6", "label": "glm-4.6 (快速模式)", "mode": "fast"},
    {"name": "glm-4.6", "label": "glm-4.6 (均衡模式)", "mode": "balanced"},
    {"name": "glm-4.6", "label": "glm-4.6 (深度思考模式)", "mode": "deep"},
    {"name": "glm-4.6", "label": "glm-4.6 (创意模式)", "mode": "creative"},
    {"name": "glm-4.6", "label": "glm-4.6 (精确模式)", "mode": "precise"},
    {"name": "cogview-3", "label": "GLM 绘画 (CogView-3)", "mode": "image"}
  ],
  "default_model": "glm-4.6"
}
```

#### Provider: Custom

```json
{
  "endpoint": "",
  "key_name": "API_KEY",
  "available_models": [],
  "default_model": null
}
```

---

### Requirement: 三级树形配置视图

系统必须以三级树形结构展示配置：CLI 类型 → 端点 → 配置项。

#### Scenario: 展示配置树

**Given** 存在多个配置
**When** 用户查看配置列表
**Then** 配置按 CLI 类型（Claude/Codex/Gemini/Aider）分组
**And** 每个 CLI 类型下按端点分组
**And** 每个端点下显示具体配置项

#### Scenario: 展开/折叠分组

**Given** 配置树已显示
**When** 用户双击分组标题
**Then** 该分组展开或折叠
**And** 保持其他分组状态不变

#### Scenario: 选择配置项

**Given** 配置树已显示
**When** 用户单击配置项
**Then** 该配置项高亮显示
**And** 右侧显示配置详情

#### Scenario: 移动配置项

**Given** 用户选中一个配置项
**When** 用户点击上移/下移按钮
**Then** 配置项在同级内移动位置
**And** 保存新的排序

---

### Requirement: API Key 验证

系统必须支持验证 API Key 的有效性，不同提供商使用不同验证方式。

#### Scenario: 验证 Anthropic API Key

**Given** 用户选中一个 Anthropic 配置
**When** 用户点击"验证"按钮
**Then** 系统调用 `GET /v1/models` 验证密钥
**And** 显示验证结果（有效/无效）

#### Scenario: 验证 OpenAI API Key

**Given** 用户选中一个 OpenAI 配置
**When** 用户点击"验证"按钮
**Then** 系统调用 `GET /v1/models` 验证密钥
**And** 显示验证结果

#### Scenario: 验证 DeepSeek API Key

**Given** 用户选中一个 DeepSeek 配置
**When** 用户点击"验证"按钮
**Then** 系统调用 `GET /user/balance` 验证密钥
**And** 显示验证结果和账户余额

#### Scenario: 验证 Gemini API Key

**Given** 用户选中一个 Gemini 配置
**When** 用户点击"验证"按钮
**Then** 系统调用 `GET /models` 验证密钥
**And** 显示验证结果

#### Scenario: 验证 GLM API Key

**Given** 用户选中一个 GLM 配置
**When** 用户点击"验证"按钮
**Then** 系统使用 API Key 生成 JWT Token (HS256 签名)
**And** 调用 `POST /chat/completions` 验证
**And** 显示验证结果

#### GLM JWT Token 生成逻辑

```rust
fn generate_glm_jwt(api_key: &str) -> Result<String, Error> {
    // API Key 格式: {id}.{secret}
    let parts: Vec<&str> = api_key.split('.').collect();
    let (id, secret) = (parts[0], parts[1]);

    let header = json!({
        "alg": "HS256",
        "sign_type": "SIGN"
    });

    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis();
    let payload = json!({
        "api_key": id,
        "exp": now + 3600000,  // 1小时过期
        "timestamp": now
    });

    // HS256 签名
    let token = encode(&header, &payload, secret)?;
    Ok(token)
}
```

---

### Requirement: 模型选择

系统必须支持为每个配置选择模型。

#### Scenario: 获取可用模型列表

**Given** 用户选中一个配置
**When** 用户点击模型下拉框
**Then** 系统根据提供商类型显示可用模型列表

#### Scenario: 选择模型

**Given** 模型列表已显示
**When** 用户选择一个模型
**Then** 系统保存选择到配置
**And** 启动终端时使用该模型

#### Scenario: GLM 模式选择

**Given** 用户选中一个 GLM 配置
**When** 用户选择模型
**Then** 同时选择思考模式（fast/balanced/deep/creative/precise）

---

### Requirement: 终端启动

系统必须支持使用选中配置启动 CLI 终端。

#### Scenario: 启动 Claude Code

**Given** 用户选中一个 Claude 配置
**And** 用户选择了工作目录
**When** 用户点击"启动终端"按钮
**Then** 系统设置环境变量 ANTHROPIC_API_KEY
**And** 如果配置了自定义端点，设置 ANTHROPIC_BASE_URL
**And** 如果配置了自定义环境变量名 (base_url_env)，使用该名称
**And** 在选定终端中启动 `claude` 命令
**And** 如果配置了模型，添加 `--model` 参数
**And** 记录启动日志

#### Scenario: 命令注入防护

**Given** 环境变量值包含特殊字符
**When** 系统构建启动命令
**Then** 过滤危险字符 `&|<>^`
**And** 防止命令注入攻击

#### Scenario: 选择终端

**Given** 用户准备启动终端
**When** 用户点击终端下拉框
**Then** 系统显示已安装的终端列表（Windows Terminal、PowerShell、CMD 等）

#### Scenario: 选择工作目录

**Given** 用户准备启动终端
**When** 用户点击"选择目录"按钮
**Then** 系统打开目录选择对话框
**And** 用户选择目录后保存到历史记录（最多10个）

#### Scenario: 工作目录历史

**Given** 用户打开工作目录下拉菜单
**When** 系统显示历史记录
**Then** 显示最近 10 个工作目录
**And** 首次启动时从历史记录自动提取最近 5 个目录

#### Scenario: 清除工作目录历史

**Given** 用户选中一个工作目录
**When** 用户点击"清除"按钮
**Then** 系统删除该目录的历史记录
**And** 将该目录下的会话移到回收站

---

### Requirement: 会话下拉框

系统必须支持快速切换到历史会话。

#### Scenario: 加载会话列表

**Given** 用户选中一个配置
**When** 系统检测到配置的 cli_type
**Then** 异步加载对应 CLI 的历史会话
**And** 显示在会话下拉框中

#### Scenario: 切换会话

**Given** 会话下拉框已加载
**When** 用户选择一个会话
**Then** 系统切换到该会话的工作目录

---

### Requirement: 配置导入导出

系统必须支持配置的导入和导出。

#### Scenario: 导出配置

**Given** 存在配置数据
**When** 用户点击"导出"按钮
**Then** 系统将配置导出为 JSON 文件
**And** API Key 可选择是否包含

#### Scenario: 导入配置

**Given** 用户有配置 JSON 文件
**When** 用户点击"导入"按钮
**And** 选择文件
**Then** 系统解析文件并导入配置
**And** 处理重复配置（覆盖/跳过/重命名）

---

### Requirement: 配置标签

系统必须支持为配置添加标签。

#### Scenario: 添加标签

**Given** 用户编辑配置
**When** 用户输入标签（逗号分隔）
**Then** 系统保存标签到配置

#### Scenario: 按标签筛选

**Given** 配置列表已显示
**When** 用户选择标签筛选
**Then** 只显示包含该标签的配置

## Data Model

```typescript
interface Configuration {
  id: number;
  name: string;
  cli_type: 'claude' | 'codex' | 'gemini' | 'aider';
  provider_type: 'anthropic' | 'openai' | 'deepseek' | 'gemini' | 'glm' | 'custom';
  endpoint: string;
  api_key: string;
  selected_model?: string;
  thinking_mode?: 'fast' | 'balanced' | 'deep' | 'creative' | 'precise';
  token_limit?: number;
  base_url_env?: string;  // 自定义 API 地址环境变量名
  tags?: string[];
  sort_order: number;
  created_at: string;
  updated_at: string;
}

interface ProviderDefaults {
  endpoint: string;
  key_name: string;
  available_models: ModelOption[];
  default_model: string | null;
}

interface ModelOption {
  name: string;
  label?: string;
  mode?: string;  // GLM 专用
}

interface ValidationResult {
  valid: boolean;
  message: string;
  balance?: number;  // DeepSeek 返回余额
}

interface LaunchLog {
  time: string;
  config: string;
  cli: string;
  command: string;
  workdir: string;
}
```

## Tauri Commands

```rust
#[tauri::command]
async fn load_configs() -> Result<Vec<Configuration>, String>;

#[tauri::command]
async fn save_config(config: Configuration) -> Result<(), String>;

#[tauri::command]
async fn delete_config(id: i64) -> Result<(), String>;

#[tauri::command]
async fn reorder_configs(ids: Vec<i64>) -> Result<(), String>;

#[tauri::command]
async fn validate_api_key(
    provider_type: String,
    endpoint: String,
    api_key: String
) -> Result<ValidationResult, String>;

#[tauri::command]
async fn generate_glm_jwt(api_key: String) -> Result<String, String>;

#[tauri::command]
async fn launch_terminal(
    config: Configuration,
    workdir: String,
    terminal: String
) -> Result<(), String>;

#[tauri::command]
async fn detect_terminals() -> Result<HashMap<String, String>, String>;

#[tauri::command]
async fn detect_python_envs() -> Result<HashMap<String, String>, String>;

#[tauri::command]
async fn export_configs(include_keys: bool) -> Result<String, String>;

#[tauri::command]
async fn import_configs(json: String) -> Result<ImportResult, String>;

#[tauri::command]
async fn log_cli_launch(
    config: String,
    cli_type: String,
    command: String,
    workdir: String
) -> Result<(), String>;

#[tauri::command]
async fn load_launch_log() -> Result<Vec<LaunchLog>, String>;

#[tauri::command]
async fn get_work_dir_history() -> Result<Vec<String>, String>;

#[tauri::command]
async fn save_work_dir_history(dirs: Vec<String>) -> Result<(), String>;
```
