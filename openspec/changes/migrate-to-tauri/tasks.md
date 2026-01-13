# Implementation Tasks

## Phase 1: 项目初始化

### 1.1 创建 Tauri + React 项目
- [ ] 使用 `pnpm create tauri-app` 创建项目
- [ ] 选择 React + TypeScript 模板
- [ ] 配置 Vite 构建
- [ ] 安装依赖：
  - `@tauri-apps/api`
  - `zustand` (状态管理)
  - `tailwindcss` (样式)
  - `@radix-ui/react-*` (UI 组件)
  - `lucide-react` (图标)
  - `i18next` (国际化)
  - `@tanstack/react-virtual` (虚拟列表)

### 1.2 配置 Rust 后端
- [ ] 配置 `Cargo.toml` 依赖：
  - `rusqlite` (数据库)
  - `serde` + `serde_json` (序列化)
  - `walkdir` (文件遍历)
  - `rayon` (并行处理)
  - `tokio` (异步运行时)
  - `lru` (LRU 缓存)
  - `chrono` (日期时间)
  - `jsonwebtoken` (GLM JWT)
  - `reqwest` (HTTP 请求)
  - `tauri-plugin-shell` (终端启动)
  - `tauri-plugin-dialog` (文件对话框)
  - `tauri-plugin-clipboard-manager` (剪贴板)
  - `tauri-plugin-global-shortcut` (全局快捷键)
  - `tauri-plugin-single-instance` (单实例)
- [ ] 配置 `tauri.conf.json`

### 1.3 项目结构搭建
- [ ] 创建前端目录结构 (`src/components`, `src/pages`, `src/stores`, `src/hooks`, `src/lib`)
- [ ] 创建后端目录结构 (`src-tauri/src/commands`, `src-tauri/src/db`, `src-tauri/src/history`, `src-tauri/src/services`)
- [ ] 配置 ESLint + Prettier
- [ ] 配置 Tailwind CSS

---

## Phase 2: 核心基础设施

### 2.1 数据库模块 (Rust)
- [ ] 实现数据库初始化和迁移
- [ ] 创建表结构：
  - `configurations`
  - `prompts`
  - `mcp_servers`
  - `mcp_registry`
  - `settings`
  - `trash` (回收站)
  - `launch_log` (启动日志)
- [ ] 实现基础 CRUD 操作

### 2.2 状态管理 (React)
- [ ] 创建 `configStore` (配置管理)
- [ ] 创建 `historyStore` (历史记录)
- [ ] 创建 `mcpStore` (MCP 管理)
- [ ] 创建 `settingsStore` (设置)
- [ ] 实现 Tauri IPC 封装 (`lib/tauri.ts`)

### 2.3 国际化
- [ ] 配置 i18next
- [ ] 创建中文语言包
- [ ] 创建英文语言包
- [ ] 实现语言切换

### 2.4 主题系统
- [ ] 配置 Tailwind 主题变量
- [ ] 实现亮色/暗色主题
- [ ] 实现跟随系统主题

---

## Phase 3: API Keys 管理模块

### 3.1 后端 Commands
- [ ] `load_configs` - 加载配置列表
- [ ] `save_config` - 保存配置
- [ ] `delete_config` - 删除配置
- [ ] `validate_api_key` - 验证 API Key (支持 6 种 provider)
- [ ] `generate_glm_token` - 生成智谱 JWT Token
- [ ] `detect_terminals` - 检测终端
- [ ] `detect_python_envs` - 检测 Python 环境
- [ ] `launch_terminal` - 启动终端 (含命令注入防护)
- [ ] `log_cli_launch` - 记录 CLI 启动日志
- [ ] `get_launch_logs` - 获取启动日志

### 3.2 前端页面
- [ ] 创建 `ApiKeysPage` 组件
- [ ] 实现三级树形视图组件
- [ ] 实现配置编辑表单
- [ ] 实现终端选择下拉框
- [ ] 实现工作目录选择
- [ ] 实现 API Key 验证 UI

### 3.3 功能完善
- [ ] 配置导入/导出
- [ ] 模型选择 (PROVIDER_DEFAULTS 预设)
- [ ] 工作目录历史记录 (最近 20 个)
- [ ] 会话下拉框 (根据 cli_type 加载)
- [ ] API 余额显示 (DeepSeek)

---

## Phase 4: 历史记录管理模块 (重点)

### 4.1 后端 - 历史扫描器
- [ ] 实现 Claude 历史解析器 (`history/claude.rs`)
- [ ] 实现 Codex 历史解析器 (`history/codex.rs`)
- [ ] 实现并行扫描器 (`history/scanner.rs`)
  - 使用 `walkdir` + `rayon`
  - 实现增量加载
  - 实现 LRU 缓存

### 4.2 后端 Commands
- [ ] `list_projects` - 列出项目 (with_cwd 参数)
- [ ] `load_project_sessions` - 加载项目会话
- [ ] `load_session_detail` - 加载会话详情 (LRU 缓存)
- [ ] `delete_sessions` - 删除会话
- [ ] `export_session_html` - 导出 HTML
- [ ] `export_session_md` - 导出 Markdown
- [ ] `export_sessions_batch` - 批量导出

### 4.3 后端 - 回收站
- [ ] 实现 `TrashManager`
- [ ] `get_trash_items` - 获取回收站列表
- [ ] `restore_from_trash` - 恢复会话
- [ ] `permanently_delete` - 永久删除
- [ ] `cleanup_expired_trash` - 清理过期

### 4.4 前端页面
- [ ] 创建 `HistoryPage` 组件
- [ ] 实现项目列表（懒加载）
- [ ] 实现会话列表
- [ ] 实现会话详情面板
- [ ] 实现对话时间线组件
- [ ] 实现工具调用展示 (图标映射)
- [ ] 实现搜索和过滤
- [ ] 实现日期范围筛选
- [ ] 实现回收站对话框

### 4.5 性能优化
- [ ] 实现虚拟列表 (@tanstack/react-virtual)
- [ ] 优化大文件解析
- [ ] 添加加载进度指示
- [ ] 实现 LRU 缓存 (50 项)

---

## Phase 5: MCP 服务器管理模块

### 5.1 后端 Commands
- [ ] `load_mcp_servers` - 加载 MCP 列表
- [ ] `save_mcp_server` - 保存 MCP
- [ ] `delete_mcp_server` - 删除 MCP
- [ ] `set_mcp_default` - 设置默认
- [ ] `sync_mcp_to_global` - 同步到全局配置
- [ ] `scan_installed_mcp` - 扫描已安装 MCP
- [ ] `import_mcp_from_json` - 从 JSON 导入
- [ ] `sync_mcp_registry` - 同步仓库
- [ ] `search_mcp_registry` - 搜索仓库 (FTS5 全文搜索)
- [ ] `check_mcp_status` - 检测 MCP 安装状态
- [ ] `open_mcp_market` - 打开外部市场

### 5.2 前端页面
- [ ] 创建 `McpPage` 组件
- [ ] 实现分类树形视图
- [ ] 实现 MCP 编辑表单
- [ ] 实现导入对话框 (CLI/剪贴板/文件/文本)
- [ ] 实现仓库浏览器
- [ ] 实现状态检测
- [ ] 实现外部市场链接 (Smithery/MCP.so/Glama)

---

## Phase 6: 提示词管理模块

### 6.1 后端 Commands
- [ ] `load_prompts` - 加载提示词
- [ ] `get_system_prompt` - 获取系统提示词
- [ ] `save_prompt` - 保存提示词
- [ ] `delete_prompt` - 删除提示词
- [ ] `get_builtin_prompts` - 获取内置提示词 (多语言)
- [ ] `write_prompt_to_cli` - 写入 CLI 配置
- [ ] `detect_prompt_from_file` - 检测已有提示词
- [ ] `expand_template_vars` - 展开模板变量 (8 种)
- [ ] `get_available_template_vars` - 获取可用变量列表

### 6.2 前端页面
- [ ] 创建 `PromptsPage` 组件
- [ ] 实现全局提示词编辑区
- [ ] 实现提示词分类列表
- [ ] 实现提示词编辑表单
- [ ] 实现内置提示词展示
- [ ] 实现模板变量帮助弹窗

---

## Phase 7: 系统功能模块

### 7.1 系统托盘
- [ ] 实现托盘图标
- [ ] 实现托盘菜单
- [ ] 实现快速启动子菜单 (列出配置)
- [ ] 实现点击激活窗口
- [ ] 实现最小化到托盘

### 7.2 全局快捷键
- [ ] 实现快捷键注册
- [ ] 实现截图快捷键
- [ ] 实现复制路径快捷键
- [ ] 实现快捷键自定义

### 7.3 截图工具
- [ ] 实现全屏截图
- [ ] 实现区域选择
- [ ] 实现标注工具 (矩形/椭圆/箭头/直线/文字/画笔)
- [ ] 实现颜色选择 (8 种预设色)
- [ ] 实现线条粗细调节
- [ ] 实现撤销/重做
- [ ] 实现保存和复制
- [ ] 实现设置持久化

### 7.4 单实例运行
- [ ] 实现实例检测
- [ ] 实现窗口激活

### 7.5 其他功能
- [ ] Gist 同步 (备份/恢复)
- [ ] 自动更新检查 (GitHub Release)
- [ ] CLI 启动日志记录
- [ ] DPI 感知 (高分屏适配)
- [ ] Win+V 剪贴板历史支持
- [ ] 设置页面

---

## Phase 8: 测试和优化

### 8.1 测试
- [ ] Rust 单元测试
- [ ] React 组件测试
- [ ] 集成测试

### 8.2 性能优化
- [ ] 历史扫描性能测试
- [ ] 内存占用优化
- [ ] 启动速度优化

### 8.3 打包发布
- [ ] Windows 打包 (.msi)
- [ ] macOS 打包 (.dmg)
- [ ] Linux 打包 (.AppImage)
- [ ] 自动更新配置

---

## 依赖关系

```
Phase 1 (项目初始化)
    │
    ▼
Phase 2 (核心基础设施)
    │
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
Phase 3        Phase 4        Phase 5        Phase 6
(API Keys)     (History)      (MCP)          (Prompts)
    │              │              │              │
    └──────────────┴──────────────┴──────────────┘
                   │
                   ▼
              Phase 7 (系统功能)
                   │
                   ▼
              Phase 8 (测试和优化)
```

## 可并行任务

- Phase 3, 4, 5, 6 可以并行开发
- 后端 Commands 和前端页面可以并行开发
- 测试可以在每个 Phase 完成后进行

## 关键里程碑

1. **M1**: 项目骨架完成，能够编译运行
2. **M2**: API Keys 管理功能可用，能启动终端
3. **M3**: 历史记录管理功能可用，性能达标
4. **M4**: 所有功能完成，进入测试阶段
5. **M5**: 发布 v2.0
