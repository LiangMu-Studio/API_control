# System Features

## Overview

系统功能模块包括多语言支持、主题切换、系统托盘、全局快捷键、单实例运行、截图工具、路径复制等。

## ADDED Requirements

### Requirement: 多语言支持

系统必须支持中英文切换。

#### Scenario: 默认语言

**Given** 应用首次启动
**When** 系统检测系统语言
**Then** 如果系统语言为中文，使用中文
**Otherwise** 使用英文

#### Scenario: 切换语言

**Given** 用户在设置中
**When** 用户选择语言（中文/英文）
**Then** 系统立即切换界面语言
**And** 保存语言设置

#### Scenario: 语言持久化

**Given** 用户已设置语言
**When** 应用重启
**Then** 系统使用上次设置的语言

#### 语言键数量

系统支持约 240 个语言键，覆盖所有 UI 文本。

---

### Requirement: 主题切换

系统必须支持亮色/暗色主题切换。

#### Scenario: 默认主题

**Given** 应用首次启动
**When** 系统检测系统主题
**Then** 跟随系统主题设置

#### Scenario: 切换主题

**Given** 用户在设置中
**When** 用户选择主题（亮色/暗色/跟随系统）
**Then** 系统立即切换主题
**And** 保存主题设置

#### Scenario: 主题样式

**Given** 用户选择亮色主题
**Then** 使用浅色背景、深色文字
**Given** 用户选择暗色主题
**Then** 使用深色背景、浅色文字

---

### Requirement: 系统托盘

系统必须支持系统托盘功能。

#### Scenario: 显示托盘图标

**Given** 应用启动
**When** 系统初始化完成
**Then** 在系统托盘显示应用图标

#### Scenario: 托盘菜单

**Given** 用户右键点击托盘图标
**When** 显示菜单
**Then** 菜单包含：
  - 显示窗口
  - 快速启动（子菜单，列出配置）
  - 截图
  - 复制路径
  - 退出

#### Scenario: 点击托盘图标

**Given** 用户左键点击托盘图标
**When** 窗口已隐藏
**Then** 显示并激活窗口
**When** 窗口已显示
**Then** 隐藏窗口

#### Scenario: 最小化到托盘

**Given** 用户点击窗口关闭按钮
**When** 设置为最小化到托盘
**Then** 窗口隐藏而非退出
**And** 托盘图标保持显示

#### Tauri 托盘实现

```rust
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::menu::{Menu, MenuItem};

fn setup_tray(app: &App) -> Result<(), Error> {
    let menu = Menu::with_items(app, &[
        &MenuItem::new(app, "显示窗口", true, None)?,
        &MenuItem::new(app, "截图", true, Some("Alt+S"))?,
        &MenuItem::new(app, "复制路径", true, Some("Alt+C"))?,
        &MenuItem::new(app, "退出", true, None)?,
    ])?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { .. } = event {
                // 切换窗口显示状态
            }
        })
        .build(app)?;
    Ok(())
}
```

---

### Requirement: 全局快捷键

系统必须支持全局快捷键。

#### Scenario: 截图快捷键

**Given** 应用在后台运行
**When** 用户按下 Alt+S（可自定义）
**Then** 系统启动截图工具
**And** 截图完成后自动复制到剪贴板

#### Scenario: 复制路径快捷键

**Given** 应用在后台运行
**And** 用户在文件管理器中选中文件
**When** 用户按下 Alt+C（可自定义）
**Then** 系统获取选中文件的路径
**And** 复制到剪贴板

#### Scenario: 自定义快捷键

**Given** 用户在设置中
**When** 用户修改快捷键绑定
**Then** 系统保存新的快捷键
**And** 立即生效

#### Tauri 全局快捷键实现

```rust
use tauri_plugin_global_shortcut::GlobalShortcutExt;

fn register_hotkeys(app: &App) -> Result<(), Error> {
    app.global_shortcut().register("Alt+S", |app, shortcut| {
        app.emit("take-screenshot", ()).unwrap();
    })?;

    app.global_shortcut().register("Alt+C", |app, shortcut| {
        app.emit("copy-path", ()).unwrap();
    })?;
    Ok(())
}
```

---

### Requirement: 单实例运行

系统必须确保只有一个实例运行。

#### Scenario: 首次启动

**Given** 没有运行中的实例
**When** 用户启动应用
**Then** 应用正常启动

#### Scenario: 重复启动

**Given** 已有运行中的实例
**When** 用户再次启动应用
**Then** 新实例检测到已有实例
**And** 激活已有实例的窗口
**And** 新实例退出

#### Tauri 单实例实现

```rust
use tauri_plugin_single_instance::init;

fn main() {
    tauri::Builder::default()
        .plugin(init(|app, argv, cwd| {
            if let Some(window) = app.get_webview_window("main") {
                window.show().unwrap();
                window.set_focus().unwrap();
            }
        }))
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

---

### Requirement: 截图工具

系统必须提供截图功能。

#### Scenario: 启动截图

**Given** 用户触发截图（快捷键或菜单）
**When** 截图工具启动
**Then** 全屏显示半透明遮罩
**And** 用户可以框选区域

#### Scenario: 框选区域

**Given** 截图工具已启动
**When** 用户拖动鼠标框选
**Then** 显示选区边框
**And** 显示选区尺寸

#### Scenario: 标注工具

**Given** 用户已框选区域
**When** 用户选择标注工具
**Then** 支持以下标注：
  - 矩形
  - 椭圆
  - 箭头
  - 直线
  - 文字
  - 画笔

#### 标注工具数据结构

```typescript
enum ToolType {
  NONE = 'none',
  RECT = 'rect',
  ELLIPSE = 'ellipse',
  ARROW = 'arrow',
  LINE = 'line',
  TEXT = 'text',
  PEN = 'pen',
}

interface Annotation {
  tool: ToolType;
  color: string;
  width: number;
  start: { x: number; y: number };
  end: { x: number; y: number };
  text?: string;
  points?: { x: number; y: number }[];
}
```

#### Scenario: 预设颜色

**Given** 用户选择颜色
**When** 显示颜色选择器
**Then** 提供 8 种预设颜色：红、橙、黄、绿、青、蓝、紫、白
**And** 支持自定义颜色选择

#### 预设颜色值

```typescript
const PRESET_COLORS = [
  '#ff0000',  // 红
  '#ff8000',  // 橙
  '#ffff00',  // 黄
  '#00ff00',  // 绿
  '#00ffff',  // 青
  '#0000ff',  // 蓝
  '#8000ff',  // 紫
  '#ffffff',  // 白
];
```

#### Scenario: 撤销/重做

**Given** 用户已添加标注
**When** 用户按 Ctrl+Z
**Then** 撤销最后一个标注
**When** 用户按 Ctrl+Y
**Then** 重做撤销的标注

#### Scenario: 保存截图

**Given** 用户完成截图
**When** 用户点击确认
**Then** 截图保存到临时目录
**And** 复制到剪贴板
**And** 返回截图路径

#### Scenario: 截图设置持久化

**Given** 用户修改了颜色或线条粗细
**When** 下次截图
**Then** 使用上次的设置

#### 截图配置文件

```json
{
  "color": "#ff0000",
  "width": 3
}
```

#### Scenario: 截图自动清理

**Given** 截图保存到临时目录
**When** 截图超过 7 天
**Then** 系统自动清理过期截图

---

### Requirement: 路径复制工具

系统必须支持复制文件路径。

#### Scenario: 复制选中文件路径

**Given** 用户在文件管理器中选中文件
**When** 用户触发复制路径（快捷键或菜单）
**Then** 系统获取选中文件的绝对路径
**And** 复制到剪贴板
**And** 显示通知

#### Windows 获取选中文件路径

```rust
use windows::Win32::UI::Shell::*;
use windows::Win32::System::Com::*;

fn get_selected_files() -> Result<Vec<String>, Error> {
    unsafe {
        CoInitialize(None)?;
        let shell: IShellWindows = CoCreateInstance(&ShellWindows, None, CLSCTX_ALL)?;
        // 遍历资源管理器窗口获取选中文件
    }
}
```

#### Scenario: 路径选择器

**Given** 用户点击"抓取路径"按钮
**When** 系统打开文件选择对话框
**And** 用户选择文件
**Then** 系统复制文件路径到剪贴板

---

### Requirement: GitHub Gist 同步

系统必须支持配置同步到 GitHub Gist。

#### Scenario: 配置 Gist Token

**Given** 用户在设置中
**When** 用户输入 GitHub Personal Access Token
**Then** 系统保存 Token（加密存储）

#### Scenario: 上传配置

**Given** 用户已配置 Gist Token
**When** 用户点击"上传到 Gist"
**Then** 系统将配置导出为 JSON
**And** 上传到 Gist
**And** 显示 Gist URL

#### Scenario: 下载配置

**Given** 用户已配置 Gist Token
**When** 用户点击"从 Gist 下载"
**Then** 系统从 Gist 获取配置
**And** 导入到本地

---

### Requirement: 自动更新检查

系统必须支持检查新版本。

#### Scenario: 启动时检查

**Given** 应用启动
**When** 系统检查 GitHub Release
**Then** 如果有新版本，显示更新提示

#### Scenario: 手动检查

**Given** 用户点击"检查更新"
**When** 系统检查 GitHub Release
**Then** 显示当前版本和最新版本
**And** 如果有新版本，提供下载链接

---

### Requirement: CLI 启动日志

系统必须记录 CLI 启动历史。

#### Scenario: 记录启动

**Given** 用户启动 CLI 终端
**When** 系统执行启动命令
**Then** 记录以下信息：
  - 时间戳
  - 配置名称
  - CLI 类型
  - 启动命令
  - 工作目录

#### Scenario: 查看日志

**Given** 用户打开启动日志
**When** 系统加载日志
**Then** 显示最近 100 条启动记录

---

### Requirement: 剪贴板增强

系统必须支持 Win+V 剪贴板历史粘贴。

#### Scenario: 启用剪贴板粘贴

**Given** 用户在文本输入框中
**When** 用户按下 Win+V
**Then** 系统打开 Windows 剪贴板历史
**And** 用户可选择历史项粘贴

#### Scenario: 自动启用

**Given** 应用启动
**When** 系统初始化文本输入框
**Then** 自动为所有 TextField 启用剪贴板粘贴功能

---

### Requirement: 设置管理

系统必须支持应用设置管理。

#### Scenario: 设置项

系统支持以下设置：
- 语言
- 主题
- 默认终端
- 截图快捷键
- 复制路径快捷键
- 回收站保留天数
- 启动时最小化
- 关闭时最小化到托盘
- 自动检查更新
- Gist Token

---

### Requirement: 窗口控制优化

系统必须优化窗口控制按钮响应速度。

#### Scenario: 快速最小化

**Given** 用户点击最小化按钮
**When** 系统处理点击事件
**Then** 使用原生 API 直接操作窗口
**And** 响应时间 < 50ms

---

### Requirement: DPI 感知

系统必须支持高 DPI 显示。

#### Scenario: 自动缩放

**Given** 用户使用高 DPI 显示器
**When** 应用启动
**Then** 自动检测 DPI 设置
**And** 正确缩放 UI 元素

## Data Model

```typescript
interface Settings {
  language: 'zh' | 'en';
  theme: 'light' | 'dark' | 'system';
  default_terminal: string;
  screenshot_hotkey: string;
  copypath_hotkey: string;
  trash_retention_days: number;
  start_minimized: boolean;
  minimize_to_tray: boolean;
  auto_check_update: boolean;
  gist_token?: string;
  last_selected_config?: number;
  last_cli_type?: string;
  work_dir_history?: string[];
  window_position?: { x: number; y: number };
  window_size?: { width: number; height: number };
}

interface ScreenshotConfig {
  color: string;
  width: number;
}

interface UpdateInfo {
  has_update: boolean;
  current_version: string;
  latest_version?: string;
  release_url?: string;
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
async fn load_settings() -> Result<Settings, String>;

#[tauri::command]
async fn save_settings(settings: Settings) -> Result<(), String>;

#[tauri::command]
async fn get_setting(key: String) -> Result<Option<String>, String>;

#[tauri::command]
async fn set_setting(key: String, value: String) -> Result<(), String>;

#[tauri::command]
async fn register_hotkey(id: String, hotkey: String) -> Result<(), String>;

#[tauri::command]
async fn unregister_hotkey(id: String) -> Result<(), String>;

#[tauri::command]
async fn take_screenshot() -> Result<String, String>;

#[tauri::command]
async fn copy_selected_file_path() -> Result<String, String>;

#[tauri::command]
async fn upload_to_gist(token: String, content: String) -> Result<String, String>;

#[tauri::command]
async fn download_from_gist(token: String, gist_id: String) -> Result<String, String>;

#[tauri::command]
async fn check_update(current_version: String) -> Result<UpdateInfo, String>;

#[tauri::command]
async fn log_cli_launch(config: String, cli_type: String, command: String, workdir: String) -> Result<(), String>;

#[tauri::command]
async fn load_launch_log() -> Result<Vec<LaunchLog>, String>;

#[tauri::command]
async fn clear_launch_log() -> Result<(), String>;

#[tauri::command]
async fn load_screenshot_config() -> Result<ScreenshotConfig, String>;

#[tauri::command]
async fn save_screenshot_config(config: ScreenshotConfig) -> Result<(), String>;

#[tauri::command]
async fn cleanup_old_screenshots(days: u32) -> Result<u32, String>;
```
