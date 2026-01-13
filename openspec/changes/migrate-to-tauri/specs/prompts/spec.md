# Prompts Management

## Overview

提示词管理模块负责管理全局系统提示词和用户自定义提示词，支持模板变量和自动写入 CLI 配置文件。

## ADDED Requirements

### Requirement: 全局系统提示词

系统必须支持管理全局系统提示词。

#### Scenario: 显示全局提示词

**Given** 用户进入提示词页面
**When** 系统加载提示词
**Then** 顶部显示全局系统提示词编辑区
**And** 显示当前保存的内容

#### Scenario: 编辑全局提示词

**Given** 用户在全局提示词编辑区
**When** 用户修改内容
**And** 点击"保存全局提示词"
**Then** 系统保存到数据库
**And** 显示保存成功提示

---

### Requirement: 用户提示词管理

系统必须支持管理用户自定义提示词。

#### Scenario: 显示提示词列表

**Given** 用户进入提示词页面
**When** 系统加载提示词
**Then** 按分类分组显示用户提示词：
  - 编程
  - 写作
  - 分析
  - 绘画
  - 用户
  - 其他

#### Scenario: 添加提示词

**Given** 用户点击"添加"按钮
**When** 用户填写名称、分类、内容
**And** 点击"保存"
**Then** 系统保存提示词
**And** 刷新列表

#### Scenario: 编辑提示词

**Given** 用户选中一个非内置提示词
**When** 用户点击"编辑"按钮
**And** 修改内容
**And** 点击"保存"
**Then** 系统更新提示词
**And** 刷新列表

#### Scenario: 删除提示词

**Given** 用户选中一个非内置提示词
**When** 用户点击"删除"按钮
**Then** 系统删除提示词
**And** 刷新列表

#### Scenario: 内置提示词只读

**Given** 用户选中一个内置提示词
**When** 用户尝试编辑或删除
**Then** 系统显示"内置提示词不可修改"提示

---

### Requirement: 提示词内容编辑

系统必须支持编辑提示词内容。

#### Scenario: 查看提示词内容

**Given** 用户选中一个提示词
**When** 系统加载内容
**Then** 右侧显示提示词内容编辑区

#### Scenario: 编辑提示词内容

**Given** 用户选中一个非内置提示词
**When** 用户在编辑区修改内容
**And** 点击"保存"
**Then** 系统保存内容
**And** 显示保存成功提示

#### Scenario: 复制提示词

**Given** 用户选中一个提示词
**When** 用户点击"复制"按钮
**Then** 系统将内容复制到剪贴板
**And** 显示复制成功提示

---

### Requirement: 内置提示词

系统必须提供内置提示词模板。

#### Scenario: 显示内置提示词

**Given** 用户查看提示词列表
**When** 系统加载内置提示词
**Then** 显示以下内置提示词：
  - 空白
  - 通用编程
  - 代码调试
  - 代码审查
  - 文章写作
  - 创意写作
  - 数据分析
  - 内容总结
  - 绘画提示词

#### Scenario: 内置提示词多语言

**Given** 用户切换语言
**When** 系统重新加载内置提示词
**Then** 内置提示词显示对应语言版本

---

### Requirement: 模板变量

系统必须支持提示词模板变量。

#### Scenario: 支持的模板变量

**Given** 用户编辑提示词
**When** 用户使用模板变量
**Then** 系统支持以下变量：

| 变量 | 说明 | 示例输出 |
|------|------|---------|
| `{{date}}` | 当前日期 | 2026-01-06 |
| `{{time}}` | 当前时间 | 14:30 |
| `{{datetime}}` | 日期时间 | 2026-01-06 14:30 |
| `{{project}}` | 项目目录名 | my-project |
| `{{path}}` | 完整路径 | /home/user/my-project |
| `{{year}}` | 年份 | 2026 |
| `{{month}}` | 月份 | 01 |
| `{{day}}` | 日期 | 06 |

#### Scenario: 变量展开

**Given** 提示词包含模板变量
**When** 系统写入 CLI 配置文件
**Then** 系统将变量替换为实际值

#### Scenario: 显示可用变量

**Given** 用户编辑提示词
**When** 用户点击"变量帮助"按钮
**Then** 显示所有可用变量及其说明

---

### Requirement: 写入 CLI 配置

系统必须支持将提示词写入 CLI 配置文件。

#### Scenario: 写入 CLAUDE.md

**Given** 用户选择了全局提示词和用户提示词
**And** 用户选择了工作目录
**When** 用户启动终端
**Then** 系统将提示词写入工作目录的 `CLAUDE.md`
**And** 使用标记包裹：

```markdown
<!-- GLOBAL_PROMPT_START -->
全局提示词内容
<!-- GLOBAL_PROMPT_END -->

<!-- USER_PROMPT_START:prompt_id -->
用户提示词内容
<!-- USER_PROMPT_END -->
```

#### Scenario: 保留原有内容

**Given** 工作目录已有 `CLAUDE.md`
**When** 系统写入提示词
**Then** 系统保留标记外的原有内容
**And** 只替换标记内的内容

#### Scenario: 检测已有提示词

**Given** 用户选择了工作目录
**When** 系统检测 `CLAUDE.md`
**Then** 如果存在标记，提取并显示当前提示词

---

### Requirement: 提示词分类管理

系统必须支持提示词分类。

#### Scenario: 默认分类

系统提供以下默认分类：
- 编程 (programming)
- 写作 (writing)
- 分析 (analysis)
- 绘画 (drawing)
- 用户 (user)
- 其他 (other)

#### Scenario: 分类筛选

**Given** 提示词列表已显示
**When** 用户选择分类筛选
**Then** 只显示该分类的提示词

## Data Model

```typescript
interface Prompt {
  id: string;
  name: string;
  content: string;
  category: string;
  prompt_type: 'system' | 'user';
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

interface BuiltinPrompt {
  id: string;
  name: Record<string, string>;  // { zh: '...', en: '...' }
  content: Record<string, string>;
  category: Record<string, string>;
  is_builtin: true;
  prompt_type: 'user';
}

interface TemplateVar {
  name: string;      // e.g., "{{date}}"
  description: string;
  example: string;
}

interface DetectedPrompt {
  global_content?: string;
  user_content?: string;
  user_id?: string;
}
```

## Tauri Commands

```rust
#[tauri::command]
async fn load_prompts() -> Result<Vec<Prompt>, String>;

#[tauri::command]
async fn get_system_prompt() -> Result<Option<Prompt>, String>;

#[tauri::command]
async fn save_prompt(prompt: Prompt) -> Result<(), String>;

#[tauri::command]
async fn delete_prompt(id: String) -> Result<(), String>;

#[tauri::command]
async fn get_builtin_prompts(lang: String) -> Result<Vec<Prompt>, String>;

#[tauri::command]
async fn write_prompt_to_cli(
    cli_type: String,
    system_content: String,
    user_content: String,
    user_id: String,
    workdir: Option<String>
) -> Result<String, String>;

#[tauri::command]
async fn detect_prompt_from_file(
    cli_type: String,
    workdir: String
) -> Result<DetectedPrompt, String>;

#[tauri::command]
async fn expand_template_vars(
    content: String,
    workdir: Option<String>
) -> Result<String, String>;

#[tauri::command]
async fn get_available_template_vars() -> Result<Vec<TemplateVar>, String>;
```

## Template Variable Implementation

```rust
use chrono::Local;
use std::path::Path;

fn expand_template_vars(content: &str, workdir: Option<&str>) -> String {
    let now = Local::now();
    let project_name = workdir
        .map(|p| Path::new(p).file_name().unwrap_or_default().to_string_lossy().to_string())
        .unwrap_or_default();

    content
        .replace("{{date}}", &now.format("%Y-%m-%d").to_string())
        .replace("{{time}}", &now.format("%H:%M").to_string())
        .replace("{{datetime}}", &now.format("%Y-%m-%d %H:%M").to_string())
        .replace("{{project}}", &project_name)
        .replace("{{path}}", workdir.unwrap_or(""))
        .replace("{{year}}", &now.format("%Y").to_string())
        .replace("{{month}}", &now.format("%m").to_string())
        .replace("{{day}}", &now.format("%d").to_string())
}
```
