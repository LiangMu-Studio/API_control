# Architecture Design

## Overview

LiangMu Dev 采用 Tauri 架构，前后端分离：
- **后端 (Rust)**: 文件系统操作、数据库、系统调用、性能敏感操作
- **前端 (React)**: UI 渲染、用户交互、状态管理

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │API Keys │  │ History │  │   MCP   │  │ Prompts │        │
│  │  Page   │  │  Page   │  │  Page   │  │  Page   │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│  ┌────┴────────────┴────────────┴────────────┴────┐        │
│  │              Zustand State Store                │        │
│  └────────────────────┬────────────────────────────┘        │
│                       │                                      │
│  ┌────────────────────┴────────────────────────────┐        │
│  │              Tauri IPC (invoke)                  │        │
│  └────────────────────┬────────────────────────────┘        │
└───────────────────────┼─────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────────┐
│                       │         Rust Backend                 │
│  ┌────────────────────┴────────────────────────────┐        │
│  │              Tauri Commands                      │        │
│  └────┬────────────┬────────────┬────────────┬─────┘        │
│       │            │            │            │              │
│  ┌────┴────┐  ┌────┴────┐  ┌────┴────┐  ┌────┴────┐        │
│  │ Config  │  │ History │  │   MCP   │  │ Prompts │        │
│  │ Manager │  │ Scanner │  │ Manager │  │ Manager │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│  ┌────┴────────────┴────────────┴────────────┴────┐        │
│  │              SQLite Database                    │        │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │              System Services                     │        │
│  │  • Terminal Launcher  • Tray  • Hotkeys         │        │
│  └─────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
liangmu-dev/
├── src/                          # React 前端
│   ├── components/               # 通用组件
│   │   ├── ui/                   # 基础 UI 组件 (shadcn/ui)
│   │   ├── TreeView.tsx          # 树形视图
│   │   ├── ConfigEditor.tsx      # 配置编辑器
│   │   ├── Timeline.tsx          # 时间线组件
│   │   └── VirtualList.tsx       # 虚拟列表
│   ├── pages/                    # 页面组件
│   │   ├── ApiKeysPage.tsx
│   │   ├── HistoryPage.tsx
│   │   ├── McpPage.tsx
│   │   ├── PromptsPage.tsx
│   │   └── SettingsPage.tsx
│   ├── stores/                   # Zustand stores
│   │   ├── configStore.ts
│   │   ├── historyStore.ts
│   │   ├── mcpStore.ts
│   │   ├── promptStore.ts
│   │   └── settingsStore.ts
│   ├── hooks/                    # 自定义 Hooks
│   │   ├── useTauriCommand.ts
│   │   ├── useHotkey.ts
│   │   └── useVirtualizer.ts
│   ├── lib/                      # 工具函数
│   │   ├── tauri.ts              # Tauri IPC 封装
│   │   ├── i18n.ts               # 国际化
│   │   └── providers.ts          # 提供商配置
│   ├── locales/                  # 语言文件
│   │   ├── zh.json
│   │   └── en.json
│   ├── App.tsx
│   └── main.tsx
├── src-tauri/                    # Rust 后端
│   ├── src/
│   │   ├── main.rs               # 入口
│   │   ├── commands/             # Tauri Commands
│   │   │   ├── mod.rs
│   │   │   ├── config.rs         # 配置管理
│   │   │   ├── history.rs        # 历史记录
│   │   │   ├── mcp.rs            # MCP 管理
│   │   │   ├── prompts.rs        # 提示词管理
│   │   │   ├── terminal.rs       # 终端启动
│   │   │   ├── system.rs         # 系统功能
│   │   │   └── validation.rs     # API 验证
│   │   ├── db/                   # 数据库
│   │   │   ├── mod.rs
│   │   │   ├── schema.rs
│   │   │   └── migrations.rs
│   │   ├── history/              # 历史记录解析
│   │   │   ├── mod.rs
│   │   │   ├── claude.rs
│   │   │   ├── codex.rs
│   │   │   ├── scanner.rs        # 并行扫描器
│   │   │   └── cache.rs          # LRU 缓存
│   │   ├── services/             # 系统服务
│   │   │   ├── mod.rs
│   │   │   ├── tray.rs
│   │   │   ├── hotkey.rs
│   │   │   ├── screenshot.rs
│   │   │   ├── clipboard.rs
│   │   │   └── single_instance.rs
│   │   ├── providers/            # API 提供商
│   │   │   ├── mod.rs
│   │   │   ├── anthropic.rs
│   │   │   ├── openai.rs
│   │   │   ├── deepseek.rs
│   │   │   ├── gemini.rs
│   │   │   └── glm.rs            # 含 JWT 生成
│   │   └── utils/
│   │       ├── mod.rs
│   │       ├── path.rs
│   │       └── template.rs       # 模板变量
│   ├── Cargo.toml
│   └── tauri.conf.json
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── vite.config.ts
```

## Key Design Decisions

### 1. 状态管理

**前端 (Zustand)**:
```typescript
// stores/configStore.ts
interface ConfigStore {
  configs: Configuration[];
  selectedConfig: Configuration | null;
  selectedCli: string | null;
  selectedEndpoint: string | null;
  loading: boolean;
  terminals: Record<string, string>;
  pythonEnvs: Record<string, string>;
  workDirHistory: string[];

  loadConfigs: () => Promise<void>;
  saveConfig: (config: Configuration) => Promise<void>;
  deleteConfig: (id: number) => Promise<void>;
  selectConfig: (config: Configuration) => void;
  reorderConfigs: (ids: number[]) => Promise<void>;
  validateApiKey: (config: Configuration) => Promise<ValidationResult>;
  launchTerminal: (config: Configuration, workdir: string, terminal: string) => Promise<void>;
}

// stores/historyStore.ts
interface HistoryStore {
  cliType: string;
  projects: ProjectInfo[];
  selectedProject: ProjectInfo | null;
  sessions: SessionInfo[];
  selectedSession: SessionDetail | null;
  loading: boolean;
  dateFilter: DateFilter | null;

  setCliType: (type: string) => void;
  loadProjects: (limit?: number) => Promise<void>;
  loadProjectSessions: (projectName: string) => Promise<void>;
  loadSessionDetail: (session: SessionInfo) => Promise<void>;
  deleteSession: (session: SessionInfo) => Promise<void>;
  exportSession: (session: SessionDetail, format: 'html' | 'md') => Promise<void>;
}
```

**后端 (Rust)**:
```rust
// 使用 Mutex 保护共享状态
pub struct AppState {
    pub db: Mutex<Connection>,
    pub settings: RwLock<Settings>,
    pub session_cache: Mutex<LruCache<String, SessionDetail>>,
}
```

### 2. 提供商配置

```typescript
// lib/providers.ts
export const PROVIDER_DEFAULTS: Record<string, ProviderDefaults> = {
  anthropic: {
    endpoint: 'https://api.anthropic.com',
    key_name: 'ANTHROPIC_AUTH_TOKEN',
    available_models: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101'],
    default_model: 'claude-haiku-4-5-20251001',
  },
  openai: {
    endpoint: 'https://api.openai.com/v1',
    key_name: 'OPENAI_API_KEY',
    available_models: ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
    default_model: 'gpt-4o',
  },
  deepseek: {
    endpoint: 'https://api.deepseek.com/v1',
    key_name: 'DEEPSEEK_API_KEY',
    available_models: ['DeepSeek-V3.2', 'DeepSeek-V3', 'DeepSeek-R1'],
    default_model: 'DeepSeek-V3.2',
  },
  gemini: {
    endpoint: 'https://generativelanguage.googleapis.com/v1beta',
    key_name: 'x-goog-api-key',
    available_models: [
      { name: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
      { name: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    ],
    default_model: 'gemini-2.5-pro',
  },
  glm: {
    endpoint: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    key_name: 'ZHIPU_API_KEY',
    available_models: [
      { name: 'glm-4.6', label: 'glm-4.6 (快速模式)', mode: 'fast' },
      { name: 'glm-4.6', label: 'glm-4.6 (均衡模式)', mode: 'balanced' },
      { name: 'glm-4.6', label: 'glm-4.6 (深度思考模式)', mode: 'deep' },
    ],
    default_model: 'glm-4.6',
  },
};
```

### 3. 历史记录扫描

使用 Rust 的 `rayon` 进行并行扫描：

```rust
use rayon::prelude::*;
use walkdir::WalkDir;
use lru::LruCache;

pub fn scan_projects(dir: &Path, with_cwd: bool) -> Vec<ProjectInfo> {
    WalkDir::new(dir)
        .min_depth(1)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_dir())
        .par_bridge()  // 并行迭代
        .map(|entry| {
            let path = entry.path();
            let cwd = if with_cwd {
                get_project_cwd(path).ok()
            } else {
                None
            };
            ProjectInfo {
                name: path.file_name().unwrap().to_string_lossy().to_string(),
                cwd: cwd.unwrap_or_default(),
                session_count: count_sessions(path),
                last_activity: get_last_modified(path),
            }
        })
        .collect()
}

// LRU 缓存
lazy_static! {
    static ref SESSION_CACHE: Mutex<LruCache<String, SessionDetail>> =
        Mutex::new(LruCache::new(NonZeroUsize::new(50).unwrap()));
}
```

### 4. API 验证

```rust
// providers/mod.rs
pub async fn validate_api_key(
    provider_type: &str,
    endpoint: &str,
    api_key: &str,
) -> Result<ValidationResult, Error> {
    match provider_type {
        "anthropic" => anthropic::validate(endpoint, api_key).await,
        "openai" => openai::validate(endpoint, api_key).await,
        "deepseek" => deepseek::validate(endpoint, api_key).await,
        "gemini" => gemini::validate(endpoint, api_key).await,
        "glm" => glm::validate(endpoint, api_key).await,
        _ => Err(Error::UnsupportedProvider),
    }
}

// providers/glm.rs - JWT Token 生成
pub fn generate_jwt(api_key: &str) -> Result<String, Error> {
    let parts: Vec<&str> = api_key.split('.').collect();
    if parts.len() != 2 {
        return Err(Error::InvalidApiKey);
    }
    let (id, secret) = (parts[0], parts[1]);

    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;
    let header = json!({ "alg": "HS256", "sign_type": "SIGN" });
    let payload = json!({
        "api_key": id,
        "exp": now + 3600000,
        "timestamp": now
    });

    encode(&Header::new(Algorithm::HS256), &payload, &EncodingKey::from_secret(secret.as_bytes()))
}

// providers/deepseek.rs - 返回余额
pub async fn validate(endpoint: &str, api_key: &str) -> Result<ValidationResult, Error> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/user/balance", endpoint))
        .header("Authorization", format!("Bearer {}", api_key))
        .send()
        .await?;

    if resp.status().is_success() {
        let data: serde_json::Value = resp.json().await?;
        let balance = data["balance_infos"][0]["total_balance"]
            .as_str()
            .and_then(|s| s.parse::<f64>().ok());
        Ok(ValidationResult {
            valid: true,
            message: "API Key 有效".to_string(),
            balance,
        })
    } else {
        Ok(ValidationResult {
            valid: false,
            message: "API Key 无效".to_string(),
            balance: None,
        })
    }
}
```

### 5. 数据库 Schema

```sql
-- 配置表
CREATE TABLE configurations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cli_type TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    api_key TEXT NOT NULL,
    selected_model TEXT,
    thinking_mode TEXT,
    token_limit INTEGER,
    base_url_env TEXT,
    tags TEXT,  -- JSON array
    sort_order INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

-- 提示词表
CREATE TABLE prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT,
    category TEXT DEFAULT 'user',
    prompt_type TEXT DEFAULT 'user',
    is_builtin INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

-- MCP 服务器表
CREATE TABLE mcp_servers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'other',
    command TEXT NOT NULL,
    args TEXT,
    env TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

-- MCP 仓库缓存表
CREATE TABLE mcp_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    package TEXT,
    command TEXT DEFAULT 'npx',
    args TEXT,
    category TEXT DEFAULT 'other',
    source TEXT,
    updated_at TEXT
);

-- 设置表
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 回收站表
CREATE TABLE trash (
    id INTEGER PRIMARY KEY,
    cli_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    project_name TEXT,
    dir_name TEXT NOT NULL,
    deleted_at INTEGER NOT NULL
);

-- CLI 启动日志表
CREATE TABLE launch_log (
    id INTEGER PRIMARY KEY,
    time TEXT NOT NULL,
    config TEXT NOT NULL,
    cli TEXT NOT NULL,
    command TEXT NOT NULL,
    workdir TEXT
);
```

### 6. 终端启动

```rust
#[tauri::command]
async fn launch_terminal(
    config: Configuration,
    workdir: String,
    terminal: String,
) -> Result<(), String> {
    let cli_tool = get_cli_tool(&config.cli_type);

    // 设置环境变量 (过滤危险字符)
    let mut env = std::env::vars().collect::<HashMap<_, _>>();
    let safe_key = sanitize_env_value(&config.api_key);
    env.insert(cli_tool.default_key_name.to_string(), safe_key);

    if !config.endpoint.is_empty() {
        let env_name = config.base_url_env.as_deref()
            .unwrap_or(&cli_tool.default_base_url_env);
        env.insert(env_name.to_string(), config.endpoint.clone());
    }

    // 构建命令
    let mut args = vec![cli_tool.command.to_string()];
    if let Some(model) = &config.selected_model {
        args.extend(["--model".to_string(), model.clone()]);
    }

    let cmd = match terminal.as_str() {
        "Windows Terminal" => {
            Command::new("wt")
                .args(["-d", &workdir])
                .args(&args)
                .envs(&env)
        }
        "PowerShell" => {
            Command::new("powershell")
                .args(["-NoExit", "-Command", &format!("cd '{}'; {}", workdir, args.join(" "))])
                .envs(&env)
        }
        _ => return Err("Unsupported terminal".to_string()),
    };

    cmd.spawn().map_err(|e| e.to_string())?;

    // 记录启动日志
    log_cli_launch(&config.name, &config.cli_type, &args.join(" "), &workdir)?;

    Ok(())
}

fn sanitize_env_value(value: &str) -> String {
    value.chars().filter(|c| !matches!(c, '&' | '|' | '<' | '>' | '^')).collect()
}
```

### 7. 系统托盘

```rust
use tauri::{
    menu::{Menu, MenuItem, Submenu},
    tray::{TrayIcon, TrayIconBuilder},
};

pub fn setup_tray(app: &App, configs: &[Configuration]) -> Result<TrayIcon, tauri::Error> {
    // 快速启动子菜单
    let quick_launch_items: Vec<MenuItem> = configs.iter()
        .map(|c| MenuItem::with_id(app, &format!("launch_{}", c.id), &c.name, true, None::<&str>).unwrap())
        .collect();
    let quick_launch = Submenu::with_items(app, "快速启动", true, &quick_launch_items)?;

    let menu = Menu::with_items(app, &[
        &MenuItem::with_id(app, "show", "显示窗口", true, None::<&str>)?,
        &quick_launch,
        &MenuItem::with_id(app, "screenshot", "截图", true, Some("Alt+S"))?,
        &MenuItem::with_id(app, "copypath", "复制路径", true, Some("Alt+C"))?,
        &MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?,
    ])?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(|app, event| {
            let id = event.id.as_ref();
            if id == "show" {
                if let Some(window) = app.get_webview_window("main") {
                    window.show().unwrap();
                    window.set_focus().unwrap();
                }
            } else if id == "quit" {
                app.exit(0);
            } else if id == "screenshot" {
                app.emit("take-screenshot", ()).unwrap();
            } else if id == "copypath" {
                app.emit("copy-path", ()).unwrap();
            } else if id.starts_with("launch_") {
                let config_id: i64 = id.strip_prefix("launch_").unwrap().parse().unwrap();
                app.emit("quick-launch", config_id).unwrap();
            }
        })
        .build(app)
}
```

## Performance Considerations

### 历史记录扫描优化

1. **并行扫描**: 使用 rayon 并行遍历文件系统
2. **增量加载**: 首次只加载项目列表，展开时再加载会话
3. **LRU 缓存**: 缓存已解析的会话信息，最多 50 个
4. **流式解析**: 使用 serde_json 的流式 API 解析大文件

### 内存优化

1. **懒加载**: 会话详情按需加载
2. **虚拟列表**: 长列表使用 @tanstack/react-virtual
3. **缓存清理**: 定期清理过期缓存

### 启动优化

1. **异步初始化**: 非关键模块异步加载
2. **预编译**: 使用 Release 构建
3. **资源压缩**: 压缩前端资源

## Security Considerations

1. **API Key 存储**: 使用系统 keychain 或加密存储
2. **IPC 安全**: 验证所有 Tauri Command 参数
3. **文件访问**: 限制文件系统访问范围
4. **命令注入防护**: 过滤环境变量中的危险字符
