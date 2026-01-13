# AI CLI Manager 重构计划

## 目标
将 `app_flet.py` (~4000行) 拆分为模块化结构，主程序变得非常小。

## 已完成

### 1. 基础模块 (ui/)
- ✅ `ui/common.py` - 配置、主题、工具函数
- ✅ `ui/database.py` - PromptDB, MCPRegistry, HistoryManager 类
- ✅ `ui/lang.py` - 多语言支持 (zh/en)
- ✅ `ui/__init__.py` - 模块入口

### 2. 状态管理
- ✅ `ui/state.py` - AppState 类，集中管理应用状态

### 3. 页面模块 (ui/pages/)
- ✅ `ui/pages/__init__.py`
- ✅ `ui/pages/api_keys.py` - API 密钥页面
- ✅ `ui/pages/prompts.py` - 提示词页面
- ✅ `ui/pages/mcp.py` - MCP 服务器页面
- ⏳ `ui/pages/history.py` - 历史记录页面 (待完成)

## 待完成

### 1. 创建 history.py
从 `app_flet.py` 第 3142-3860 行提取历史记录页面代码。

关键函数：
- `get_current_manager()` - 获取当前 CLI 的历史管理器
- `get_history_data()` - 获取历史数据（使用缓存）
- `refresh_history_tree()` - 刷新历史树
- `show_session_detail()` - 显示会话详情
- `delete_sessions()` - 删除会话
- `show_trash_dialog()` - 回收站对话框
- `show_cleanup_dialog()` - 清理对话框

### 2. 重写 app_flet.py
新的主程序结构：

```python
import flet as ft
from ui.state import AppState
from ui.pages.api_keys import create_api_page
from ui.pages.prompts import create_prompts_page
from ui.pages.mcp import create_mcp_page
from ui.pages.history import create_history_page

def main(page: ft.Page):
    # 初始化状态
    state = AppState(page)

    # 创建页面
    api_page, refresh_api = create_api_page(state)
    prompt_page, refresh_prompts = create_prompts_page(state)
    mcp_page, refresh_mcp = create_mcp_page(state)
    history_page, refresh_history = create_history_page(state)

    # 导航和页面切换
    content_area = ft.Container(api_page, expand=True, padding=20)

    def switch_page(e):
        idx = e.control.selected_index
        if idx == 0:
            content_area.content = api_page
            refresh_api()
        elif idx == 1:
            content_area.content = prompt_page
            refresh_prompts()
        elif idx == 2:
            content_area.content = mcp_page
            refresh_mcp()
        elif idx == 3:
            content_area.content = history_page
            refresh_history()
        page.update()

    # 导航栏
    nav_rail = ft.NavigationRail(...)

    # 主布局
    page.add(ft.Row([nav_rail, ft.VerticalDivider(), content_area], expand=True))
    refresh_api()

ft.app(target=main)
```

### 3. 测试和推送
```bash
# 语法检查
powershell -Command "& { conda activate Python_Learning; python -m py_compile app_flet.py }"

# Git 推送
git add .
git commit -m "refactor: 完成 UI 模块化重构"
git push
```

## 文件结构
```
API_control/
├── app_flet.py          # 主程序 (重写后约 100 行)
├── ui/
│   ├── __init__.py
│   ├── common.py        # 配置、主题、工具函数
│   ├── database.py      # 数据库类
│   ├── lang.py          # 多语言
│   ├── state.py         # 状态管理
│   └── pages/
│       ├── __init__.py
│       ├── api_keys.py  # API 密钥页面
│       ├── prompts.py   # 提示词页面
│       ├── mcp.py       # MCP 页面
│       └── history.py   # 历史记录页面
```

## 注意事项

1. **页面函数签名**: 每个页面模块导出 `create_xxx_page(state)` 函数，返回 `(page, refresh_func)` 元组

2. **状态访问**: 通过 `state.xxx` 访问共享状态，如 `state.page`, `state.L`, `state.configs`

3. **主题**: 使用 `state.get_theme()` 获取当前主题配置

4. **数据库**:
   - `state.prompt_db` - 提示词数���库
   - `mcp_registry` - MCP 注册表 (从 database.py 导入)
   - `history_manager`, `codex_history_manager` - 历史管理器

5. **保存数据**:
   - `state.save_configs()` - 保存 API 配置
   - `state.save_mcp()` - 保存 MCP 列表
   - `state.prompt_db.save()` - 保存提示词
