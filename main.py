# LiangMu-Studio API Key
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3
# See LICENSE file for details

VERSION = "1.0"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import subprocess
import sys
from pathlib import Path
import copy
import shutil
from datetime import datetime
import threading
import socket
import webbrowser
from git_bash_detector import find_git_bash, is_git_bash_available

# CLI 工具定义
CLI_TOOLS = {
    'claude': {
        'name': 'Claude Code',
        'command': 'claude',
        'default_key_name': 'ANTHROPIC_API_KEY',
        'default_endpoint': 'https://api.anthropic.com',
        'base_url_env': 'ANTHROPIC_BASE_URL'
    },
    'codex': {
        'name': 'Codex CLI',
        'command': 'codex',
        'default_key_name': 'OPENAI_API_KEY',
        'default_endpoint': 'https://api.openai.com/v1',
        'base_url_env': 'OPENAI_BASE_URL'
    },
    'gemini': {
        'name': 'Gemini CLI',
        'command': 'gemini',
        'default_key_name': 'GEMINI_API_KEY',
        'default_endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'base_url_env': 'GEMINI_BASE_URL'
    },
    'aider': {
        'name': 'Aider',
        'command': 'aider',
        'default_key_name': 'OPENAI_API_KEY',
        'default_endpoint': 'https://api.openai.com/v1',
        'base_url_env': 'OPENAI_BASE_URL'
    }
}

# 多语言支持
LANG = {
    'zh': {
        'title': 'LiangMu-Studio API Key v{} - 多CLI集成终端',
        'api_config': 'API 密钥配置',
        'add': '新增',
        'edit': '编辑',
        'delete': '删除',
        'copy_key': '复制密钥',
        'move_up': '↑ 上移',
        'move_down': '↓ 下移',
        'export': '导出',
        'import': '导入',
        'feedback': '反馈: GitHub Issues',
        'terminal': '集成终端',
        'select_terminal': '选择终端:',
        'python_env': 'Python环境:',
        'current_key': '当前KEY:',
        'not_selected': '未选择',
        'work_dir': '工作目录:',
        'browse': '浏览',
        'open_terminal': '打开终端',
        'add_terminal': '+ 添加其他终端',
        'refresh_terminals': '刷新终端列表',
        'refresh_envs': '刷新环境列表',
        'config_edit': '配置编辑',
        'new_config': '新增配置',
        'label': '名称:',
        'cli_type': 'CLI工具:',
        'provider': '提供商:',
        'model': '模型:',
        'api_addr': 'API地址:',
        'key_name': 'KEY名称:',
        'api_key': 'API密钥:',
        'save': '保存',
        'cancel': '取消',
        'error': '错误',
        'success': '成功',
        'warning': '警告',
        'tip': '提示',
        'select_config': '请选择配置',
        'fill_label_key': '请填写名称和API密钥',
        'key_copied': '密钥已复制到剪贴板',
        'terminal_unavailable': '选择的终端不可用',
        'cannot_open_terminal': '无法打开终端: {}',
        'select_work_dir': '选择工作目录',
        'terminals_refreshed': '终端列表已刷新',
        'envs_refreshed': 'Python环境列表已刷新，发现 {} 个环境',
        'no_envs': '没有找到Python环境',
        'add_custom_terminal': '添加自定义终端',
        'terminal_name': '终端名称:',
        'command': '命令:',
        'fill_name_cmd': '请填写终端名称和命令',
        'terminal_added': '终端已添加',
        'exported_to': '配置已导出到: {}',
        'export_failed': '导出失败: {}',
        'no_config_data': '文件中没有配置数据',
        'imported_count': '已导入 {} 个配置',
        'import_failed': '导入失败: {}',
        'dialog_open': '编辑对话框已打开，请先关闭',
        'uncategorized': '未分类',
        'lang_switch': '🌐 EN',
    },
    'en': {
        'title': 'LiangMu-Studio API Key v{} - Multi-CLI Terminal',
        'api_config': 'API Key Configuration',
        'add': 'Add',
        'edit': 'Edit',
        'delete': 'Delete',
        'copy_key': 'Copy Key',
        'move_up': '↑ Up',
        'move_down': '↓ Down',
        'export': 'Export',
        'import': 'Import',
        'feedback': 'Feedback: GitHub Issues',
        'terminal': 'Integrated Terminal',
        'select_terminal': 'Terminal:',
        'python_env': 'Python Env:',
        'current_key': 'Current KEY:',
        'not_selected': 'Not Selected',
        'work_dir': 'Work Dir:',
        'browse': 'Browse',
        'open_terminal': 'Open Terminal',
        'add_terminal': '+ Add Terminal',
        'refresh_terminals': 'Refresh Terminals',
        'refresh_envs': 'Refresh Envs',
        'config_edit': 'Edit Config',
        'new_config': 'New Config',
        'label': 'Name:',
        'cli_type': 'CLI Tool:',
        'provider': 'Provider:',
        'model': 'Model:',
        'api_addr': 'API URL:',
        'key_name': 'KEY Name:',
        'api_key': 'API Key:',
        'save': 'Save',
        'cancel': 'Cancel',
        'error': 'Error',
        'success': 'Success',
        'warning': 'Warning',
        'tip': 'Tip',
        'select_config': 'Please select a config',
        'fill_label_key': 'Please fill in name and API key',
        'key_copied': 'Key copied to clipboard',
        'terminal_unavailable': 'Selected terminal unavailable',
        'cannot_open_terminal': 'Cannot open terminal: {}',
        'select_work_dir': 'Select Work Directory',
        'terminals_refreshed': 'Terminal list refreshed',
        'envs_refreshed': 'Python env list refreshed, found {} envs',
        'no_envs': 'No Python environments found',
        'add_custom_terminal': 'Add Custom Terminal',
        'terminal_name': 'Terminal Name:',
        'command': 'Command:',
        'fill_name_cmd': 'Please fill in name and command',
        'terminal_added': 'Terminal added',
        'exported_to': 'Config exported to: {}',
        'export_failed': 'Export failed: {}',
        'no_config_data': 'No config data in file',
        'imported_count': 'Imported {} configs',
        'import_failed': 'Import failed: {}',
        'dialog_open': 'Edit dialog is open, please close it first',
        'uncategorized': 'Uncategorized',
        'lang_switch': '🌐 中文',
    }
}

# Fix Tkinter data directory for PyInstaller
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    tcl_path = os.path.join(base_path, 'tcl8.6')
    tk_path = os.path.join(base_path, 'tk8.6')
    if os.path.exists(tcl_path):
        os.environ['TCL_LIBRARY'] = tcl_path
    if os.path.exists(tk_path):
        os.environ['TK_LIBRARY'] = tk_path

if getattr(sys, 'frozen', False):
    CONFIG_DIR = Path(sys.executable).parent / "data"
else:
    CONFIG_DIR = Path(__file__).parent / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
MODELS_FILE = CONFIG_DIR / "models.json"
CONFIG_DIR.mkdir(exist_ok=True)

def detect_python_envs():
    """检测系统中的Python环境"""
    python_envs = {}

    # 检测conda环境
    base_env = None
    other_envs = {}

    try:
        result = subprocess.run(['conda', 'env', 'list'],
                              capture_output=True, text=True, check=True)
        lines = result.stdout.split('\n')
        for line in lines:
            # 只显示有效的conda环境，过滤掉注释行和空行
            if not line.strip().startswith('#') and line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    env_name = parts[0]
                    env_path = parts[-1]

                    # 检查是否是当前环境
                    is_current = '*' in line
                    env_info = {
                        'type': 'conda',
                        'path': env_path,
                        'is_current': is_current
                    }

                    if env_name == 'base':
                        base_env = (env_name, env_info)
                    else:
                        other_envs[env_name] = env_info
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 先添加其他环境
    python_envs.update(other_envs)
    # 最后添加base环境
    if base_env:
        python_envs[base_env[0]] = base_env[1]

    # 只检测非conda环境的Python安装
    standard_pythons = []
    python_paths = []

    # 从PATH中查找Python，但排除conda目录中的Python
    for path in os.environ['PATH'].split(os.pathsep):
        python_exe = os.path.join(path, 'python.exe')
        if os.path.exists(python_exe):
            # 检查是否在conda目录中，如果是则跳过
            if 'anaconda' not in path.lower() and 'conda' not in path.lower():
                python_paths.append(python_exe)

    # 去重并添加到列表
    for python_path in list(set(python_paths)):
        try:
            result = subprocess.run([python_path, '--version'],
                                  capture_output=True, text=True, check=True)
            version = result.stdout.strip().replace('Python ', '')
            env_name = f"Python {version}"
            python_envs[env_name] = {
                'type': 'standard',
                'path': python_path,
                'is_current': False
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    return python_envs

def detect_terminals():
    terminals = {}
    # Git Bash
    if is_git_bash_available():
        git_bash_path = find_git_bash()
        terminals['Git Bash'] = git_bash_path
    if shutil.which('pwsh'):
        terminals['PowerShell 7'] = 'pwsh'
    if shutil.which('powershell'):
        terminals['PowerShell 5'] = 'powershell'
    if shutil.which('cmd'):
        terminals['CMD'] = 'cmd'
    return terminals

def has_windows_terminal():
    """检测是否安装了 Windows Terminal"""
    return shutil.which('wt') is not None

def encode_powershell_command(cmd):
    """将 PowerShell 命令编码为 Base64，避免特殊字符被 Windows Terminal 解析"""
    import base64
    # PowerShell -EncodedCommand 需要 UTF-16LE 编码的 Base64
    encoded = base64.b64encode(cmd.encode('utf-16le')).decode('ascii')
    return encoded

def run_terminal(args, env, cwd=None):
    """统一的终端启动函数，自动处理 Windows Terminal"""
    use_wt = has_windows_terminal()

    if use_wt:
        # 检查是否是 PowerShell 命令，如果是则用 EncodedCommand 避免分号问题
        if args[0] in ('pwsh', 'powershell') and '-Command' in args:
            cmd_index = args.index('-Command')
            shell = args[0]
            cmd = args[cmd_index + 1]
            encoded = encode_powershell_command(cmd)
            # 构建新的参数列表，用 -EncodedCommand 替代 -Command
            new_args = [shell, '-NoExit', '-EncodedCommand', encoded]
            wt_args = ['wt', '-d', cwd or '.'] + new_args
            print(f"[DEBUG] 使用 Windows Terminal (EncodedCommand)")
            subprocess.Popen(wt_args, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            wt_args = ['wt', '-d', cwd or '.', '--'] + args
            print(f"[DEBUG] 使用 Windows Terminal: {wt_args}")
            subprocess.Popen(wt_args, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        print(f"[DEBUG] 直接启动: {args}")
        subprocess.Popen(args, env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 如果设置文件是旧格式（没有python_envs），需要更新
            if 'terminals' in data and 'python_envs' not in data:
                python_envs = detect_python_envs()
                default_python_env = get_default_python_env(python_envs)
                data['python_envs'] = python_envs
                data['default_python_env'] = default_python_env
                save_settings(data)
                return data
            elif 'terminals' in data:
                # 更新终端列表，保留用户上次选择的终端
                terminals = detect_terminals()
                data['terminals'] = terminals
                # 如果用户上次选择的终端不存在了，使用第一个可用的
                if data.get('terminal') not in terminals:
                    data['terminal'] = list(terminals.keys())[0] if terminals else 'CMD'
                save_settings(data)
                return data

    terminals = detect_terminals()
    python_envs = detect_python_envs()

    if not terminals:
        terminals = {'CMD': 'cmd'}
    # 首次使用时，默认是 Git Bash（第一个）
    default_terminal = list(terminals.keys())[0]
    default_python_env = get_default_python_env(python_envs)

    settings = {
        'terminal': default_terminal,
        'terminals': terminals,
        'python_envs': python_envs,
        'default_python_env': default_python_env
    }
    save_settings(settings)
    return settings

def get_default_python_env(python_envs):
    """获取默认Python环境，排除BASE环境"""
    if not python_envs:
        return None

    # 获取非BASE环境
    non_base_envs = [env for env in python_envs.keys() if env != 'base']

    # 如果有非BASE环境，返回第一个
    if non_base_envs:
        return non_base_envs[0]

    # 如果只有BASE环境，返回BASE
    return 'base'

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

def load_configs():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('configurations', [])
    return []

def load_models():
    """从 config.json 加载模型配置"""
    from glm_config_mapper import GLM_MODELS
    models_dict = {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for config in data.get('configurations', []):
                provider_type = config.get('provider', {}).get('type')
                if provider_type:
                    models_list = config.get('provider', {}).get('models', [])
                    if models_list:
                        if provider_type not in models_dict:
                            models_dict[provider_type] = {'models': []}
                        seen = {m.get('name', m) for m in models_dict[provider_type]['models']}
                        for m in models_list:
                            if isinstance(m, dict):
                                if m.get('name', m.get('label')) not in seen:
                                    models_dict[provider_type]['models'].append(m)
                                    seen.add(m.get('name', m.get('label')))
                            else:
                                if m not in seen:
                                    models_dict[provider_type]['models'].append({'name': m, 'label': m})
                                    seen.add(m)
            # 为GLM添加thinking_mode选项
            if 'glm' not in models_dict:
                models_dict['glm'] = {'models': []}
            for mode, config in GLM_MODELS.items():
                models_dict['glm']['models'].append({'name': mode, 'label': config['label']})
    except Exception as e:
        print(f"加载模型配置失败: {e}")
    return models_dict

def save_configs(configs):
    for i, config in enumerate(configs):
        if 'order' not in config:
            config['order'] = i
    data = {
        'version': '1.0',
        'configurations': configs,
        'defaultConfiguration': None
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

class App:
    def __init__(self, root):
        self.root = root
        self.lang = 'zh'  # 默认中文
        self.L = LANG[self.lang]
        self.root.title(self.L['title'].format(VERSION))
        self.root.geometry('1000x500')
        self.configs = load_configs()
        self.settings = load_settings()
        self.models = load_models()

        self.editing_index = None
        self.selected_folder = self.load_last_folder()
        self.available_terminals = self.settings.get('terminals', {})
        self.selected_config_id = None
        self.edit_dialog_open = False

        # 保存控件引用用于语言切换
        self.widgets = {}
        self.build_ui()

    def build_ui(self):
        # 清除旧控件
        for widget in self.root.winfo_children():
            widget.destroy()

        L = self.L
        # 上侧：配置管理
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.widgets['api_config'] = ttk.Label(top_frame, text=L['api_config'], font=('微软雅黑', 12, 'bold'))
        self.widgets['api_config'].pack(side=tk.LEFT, padx=5)

        # TreeView 替代 Listbox
        tree_frame = ttk.Frame(top_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.tree = ttk.Treeview(tree_frame, height=15, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_config_select)
        self.tree.bind('<Double-Button-1>', self.on_double_click)
        self.tree.bind('<Delete>', lambda e: self.delete_config())
        self.tree.bind('<Control-c>', lambda e: self.copy_key())
        self.tree.bind('<Control-t>', lambda e: self.open_terminal())
        self.refresh_list()

        # 按钮区域
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.LEFT, padx=5, fill=tk.Y)
        self.widgets['btn_add'] = ttk.Button(btn_frame, text=L['add'], command=self.new_config)
        self.widgets['btn_add'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        self.widgets['btn_edit'] = ttk.Button(btn_frame, text=L['edit'], command=self.edit_config)
        self.widgets['btn_edit'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        self.widgets['btn_delete'] = ttk.Button(btn_frame, text=L['delete'], command=self.delete_config)
        self.widgets['btn_delete'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        self.widgets['btn_copy'] = ttk.Button(btn_frame, text=L['copy_key'], command=self.copy_key)
        self.widgets['btn_copy'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        self.widgets['btn_up'] = ttk.Button(btn_frame, text=L['move_up'], command=self.move_up)
        self.widgets['btn_up'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        self.widgets['btn_down'] = ttk.Button(btn_frame, text=L['move_down'], command=self.move_down)
        self.widgets['btn_down'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, padx=2, pady=5, fill=tk.X)
        self.widgets['btn_export'] = ttk.Button(btn_frame, text=L['export'], command=self.export_configs)
        self.widgets['btn_export'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        self.widgets['btn_import'] = ttk.Button(btn_frame, text=L['import'], command=self.import_configs)
        self.widgets['btn_import'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, padx=2, pady=5, fill=tk.X)

        # 语言切换按钮
        self.widgets['btn_lang'] = ttk.Button(btn_frame, text=L['lang_switch'], command=self.switch_language)
        self.widgets['btn_lang'].pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)

        self.widgets['feedback'] = tk.Label(btn_frame, text=L['feedback'], fg='blue', cursor='hand2', font=('微软雅黑', 9))
        self.widgets['feedback'].pack(side=tk.TOP, padx=2, pady=5)
        self.widgets['feedback'].bind('<Button-1>', lambda e: webbrowser.open('https://github.com/LiangMu-Studio/API_control/issues'))

        # 下侧：终端
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.widgets['terminal_title'] = ttk.Label(bottom_frame, text=L['terminal'], font=('微软雅黑', 11, 'bold'))
        self.widgets['terminal_title'].pack(side=tk.TOP, padx=5, pady=5)

        # 终端选择和管理
        term_frame = ttk.Frame(bottom_frame)
        term_frame.pack(fill=tk.X, padx=5, pady=5)

        self.widgets['lbl_terminal'] = ttk.Label(term_frame, text=L['select_terminal'], font=('微软雅黑', 10))
        self.widgets['lbl_terminal'].pack(side=tk.LEFT, padx=5)
        self.terminal_var = tk.StringVar(value=self.settings.get('terminal', list(self.available_terminals.keys())[0] if self.available_terminals else 'CMD'))
        self.terminal_combo = ttk.Combobox(term_frame, textvariable=self.terminal_var, values=list(self.available_terminals.keys()), width=15, state='readonly')
        self.terminal_combo.pack(side=tk.LEFT, padx=5)

        self.widgets['btn_add_term'] = ttk.Button(term_frame, text=L['add_terminal'], command=self.add_terminal_dialog)
        self.widgets['btn_add_term'].pack(side=tk.LEFT, padx=2)
        self.widgets['btn_refresh_term'] = ttk.Button(term_frame, text=L['refresh_terminals'], command=self.refresh_terminals)
        self.widgets['btn_refresh_term'].pack(side=tk.LEFT, padx=2)

        self.widgets['lbl_python'] = ttk.Label(term_frame, text=L['python_env'], font=('微软雅黑', 10))
        self.widgets['lbl_python'].pack(side=tk.LEFT, padx=5)
        self.python_env_var = tk.StringVar(value=self.settings.get('default_python_env', ''))
        self.python_env_combo = ttk.Combobox(term_frame, textvariable=self.python_env_var, values=list(self.settings.get('python_envs', {}).keys()), width=20, state='readonly')
        self.python_env_combo.pack(side=tk.LEFT, padx=5)

        # 添加环境选择变化时的处理
        def on_env_change(*args):
            selected_env = self.python_env_var.get()
            if selected_env:
                self.settings['default_python_env'] = selected_env
                save_settings(self.settings)

        self.python_env_var.trace('w', on_env_change)

        self.widgets['btn_refresh_env'] = ttk.Button(term_frame, text=L['refresh_envs'], command=self.refresh_python_envs)
        self.widgets['btn_refresh_env'].pack(side=tk.LEFT, padx=2)

        self.widgets['lbl_current'] = ttk.Label(term_frame, text=L['current_key'], font=('微软雅黑', 10))
        self.widgets['lbl_current'].pack(side=tk.LEFT, padx=5)
        self.current_key_label = ttk.Label(term_frame, text=L['not_selected'], font=('微软雅黑', 10), foreground='blue')
        self.current_key_label.pack(side=tk.LEFT, padx=5)

        # 地址选择
        addr_frame = ttk.Frame(bottom_frame)
        addr_frame.pack(fill=tk.X, padx=5, pady=5)

        self.widgets['lbl_workdir'] = ttk.Label(addr_frame, text=L['work_dir'], font=('微软雅黑', 10))
        self.widgets['lbl_workdir'].pack(side=tk.LEFT, padx=5)
        self.work_dir_var = tk.StringVar(value=self.selected_folder or '')
        ttk.Entry(addr_frame, textvariable=self.work_dir_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.widgets['btn_browse'] = ttk.Button(addr_frame, text=L['browse'], command=self.select_work_dir)
        self.widgets['btn_browse'].pack(side=tk.LEFT, padx=2)
        self.widgets['btn_open_term'] = ttk.Button(addr_frame, text=L['open_terminal'], command=self.open_terminal)
        self.widgets['btn_open_term'].pack(side=tk.LEFT, padx=2)

    def switch_language(self):
        self.lang = 'en' if self.lang == 'zh' else 'zh'
        self.L = LANG[self.lang]
        self.root.title(self.L['title'].format(VERSION))
        # 保存当前选择
        saved_terminal = self.terminal_var.get() if hasattr(self, 'terminal_var') else None
        saved_env = self.python_env_var.get() if hasattr(self, 'python_env_var') else None
        saved_workdir = self.work_dir_var.get() if hasattr(self, 'work_dir_var') else None
        # 重建 UI
        self.build_ui()
        # 恢复选择
        if saved_terminal:
            self.terminal_var.set(saved_terminal)
        if saved_env:
            self.python_env_var.set(saved_env)
        if saved_workdir:
            self.work_dir_var.set(saved_workdir)

    def refresh_list(self):
        self.configs = load_configs()
        self.tree.delete(*self.tree.get_children())

        # 三级结构：CLI类型 -> 端点 -> 配置项
        cli_groups = {}
        for c in self.configs:
            cli_type = c.get('cli_type', 'claude')
            endpoint = c['provider'].get('endpoint', self.L['uncategorized'])
            if cli_type not in cli_groups:
                cli_groups[cli_type] = {}
            if endpoint not in cli_groups[cli_type]:
                cli_groups[cli_type][endpoint] = []
            cli_groups[cli_type][endpoint].append(c)

        cli_order = list(CLI_TOOLS.keys())
        sorted_cli_types = sorted(cli_groups.keys(), key=lambda x: cli_order.index(x) if x in cli_order else 999)

        for cli_type in sorted_cli_types:
            cli_info = CLI_TOOLS.get(cli_type, {})
            cli_name = cli_info.get('name') or cli_type
            cli_node = self.tree.insert('', 'end', text=cli_name, open=True)

            for endpoint, configs in cli_groups[cli_type].items():
                endpoint_node = self.tree.insert(cli_node, 'end', text=endpoint, open=True)
                sorted_configs = sorted(configs, key=lambda c: c.get('order', 999))
                for c in sorted_configs:
                    created = c.get('createdAt', '')[:10]
                    text = f"{c['label']} ({created})"
                    self.tree.insert(endpoint_node, 'end', text=text, tags=(c['id'],))

    def on_config_select(self, event):
        sel = self.tree.selection()
        if sel:
            item = sel[0]
            parent = self.tree.parent(item)
            grandparent = self.tree.parent(parent) if parent else ''
            # 只有第三层（有祖父节点）才是配置项
            if grandparent:
                config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
                if config:
                    self.selected_config_id = config['id']
                    self.current_key_label.config(text=config['label'])

    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == 'heading':
            return

        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        parent = self.tree.parent(item)
        grandparent = self.tree.parent(parent) if parent else ''

        # 只有第三层才能编辑
        if grandparent:
            self.edit_config()

    def get_config_by_id(self, config_id):
        for c in self.configs:
            if c['id'] == config_id:
                return c
        return None

    def new_config(self):
        if self.edit_dialog_open:
            messagebox.showwarning(self.L['tip'], self.L['dialog_open'])
            return
        self.show_config_dialog(None)

    def edit_config(self):
        if self.edit_dialog_open:
            messagebox.showwarning(self.L['tip'], self.L['dialog_open'])
            return
        if not self.selected_config_id:
            messagebox.showerror(self.L['error'], self.L['select_config'])
            return
        config = self.get_config_by_id(self.selected_config_id)
        if config:
            index = self.configs.index(config)
            self.show_config_dialog(index)

    def show_config_dialog(self, index):
        self.edit_dialog_open = True
        L = self.L
        dialog = tk.Toplevel(self.root)
        dialog.title(L['config_edit'] if index is not None else L['new_config'])
        dialog.geometry('480x420')

        print(f"\n=== 打开配置对话框 ===")
        print(f"index = {index}")
        if index is not None:
            print(f"编辑配置: {self.configs[index]}")

        def on_dialog_close():
            self.edit_dialog_open = False
            dialog.destroy()

        dialog.protocol('WM_DELETE_WINDOW', on_dialog_close)

        frame = ttk.Frame(dialog, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)

        # CLI 工具选择
        ttk.Label(frame, text=L['cli_type'], font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=4, padx=5)
        cli_options = [(k, v['name']) for k, v in CLI_TOOLS.items()]
        cli_values = [name for _, name in cli_options]
        cli_combo = ttk.Combobox(frame, font=('微软雅黑', 10),
                                  values=cli_values, width=27, state='readonly')
        cli_combo.grid(row=0, column=1, pady=4, padx=5)
        cli_combo.current(0)  # 默认选中第一个

        ttk.Label(frame, text=L['label'], font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=4, padx=5)
        label_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        label_entry.grid(row=1, column=1, pady=4, padx=5)

        ttk.Label(frame, text=L['api_addr'], font=('微软雅黑', 10)).grid(row=2, column=0, sticky=tk.W, pady=4, padx=5)
        endpoint_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        endpoint_entry.grid(row=2, column=1, pady=4, padx=5)

        ttk.Label(frame, text=L['key_name'], font=('微软雅黑', 10)).grid(row=3, column=0, sticky=tk.W, pady=4, padx=5)
        key_name_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        key_name_entry.grid(row=3, column=1, pady=4, padx=5)

        ttk.Label(frame, text=L['api_key'], font=('微软雅黑', 10)).grid(row=4, column=0, sticky=tk.W, pady=4, padx=5)
        api_key_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        api_key_entry.grid(row=4, column=1, pady=4, padx=5)

        # 编辑现有配置时，恢复所有值
        if index is not None:
            config = self.configs[index]
            cli_type = config.get('cli_type', 'claude')
            cli_name = CLI_TOOLS.get(cli_type, {}).get('name', 'Claude Code')
            if cli_name in cli_values:
                cli_combo.current(cli_values.index(cli_name))
            label_entry.insert(0, config['label'])
            endpoint_entry.insert(0, config['provider'].get('endpoint', ''))
            key_name_entry.insert(0, config['provider'].get('key_name', 'API_KEY'))
            api_key = config.get('provider', {}).get('credentials', {}).get('api_key', '')
            if api_key:
                api_key_entry.insert(0, api_key)

        # CLI 类型变化时更新默认设置（仅对新配置生效）
        def update_cli_settings(event=None):
            if index is not None:
                return  # 编辑模式不自动更新
            selected_name = cli_combo.get()
            cli_key = None
            for k, v in CLI_TOOLS.items():
                if v['name'] == selected_name:
                    cli_key = k
                    break
            if not cli_key:
                return
            cli_info = CLI_TOOLS[cli_key]
            endpoint_entry.delete(0, tk.END)
            endpoint_entry.insert(0, cli_info.get('default_endpoint', ''))
            key_name_entry.delete(0, tk.END)
            key_name_entry.insert(0, cli_info.get('default_key_name', 'API_KEY'))

        cli_combo.bind('<<ComboboxSelected>>', update_cli_settings)

        # 新配置时，初始化默认设置
        if index is None:
            update_cli_settings()

        def save():
            label = label_entry.get()
            endpoint = endpoint_entry.get()
            key_name = key_name_entry.get()
            api_key = api_key_entry.get()

            # 获取 CLI 类型 key
            selected_name = cli_combo.get()
            print(f"\n=== 保存配置 ===")
            print(f"cli_combo.get(): '{selected_name}'")
            cli_key = 'claude'
            for k, v in CLI_TOOLS.items():
                if v['name'] == selected_name:
                    cli_key = k
                    break
            print(f"解析得到 cli_key: '{cli_key}'")

            if not label or not api_key:
                messagebox.showerror(L['error'], L['fill_label_key'])
                return

            if index is None:
                config = {
                    'id': f"{label}-{int(__import__('time').time())}",
                    'label': label,
                    'cli_type': cli_key,
                    'provider': {
                        'name': label,
                        'type': cli_key,
                        'endpoint': endpoint,
                        'key_name': key_name,
                        'credentials': {'api_key': api_key}
                    },
                    'createdAt': datetime.now().isoformat(),
                    'updatedAt': datetime.now().isoformat()
                }
                self.configs.append(config)
                print(f"新建配置: {config}")
            else:
                self.configs[index]['label'] = label
                self.configs[index]['cli_type'] = cli_key
                self.configs[index]['provider']['type'] = cli_key
                print(f"更新配置[{index}] cli_type = '{cli_key}'")
                self.configs[index]['provider']['endpoint'] = endpoint
                self.configs[index]['provider']['key_name'] = key_name
                self.configs[index]['provider']['credentials']['api_key'] = api_key
                self.configs[index]['updatedAt'] = datetime.now().isoformat()

            save_configs(self.configs)
            self.refresh_list()
            on_dialog_close()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=12, padx=5)
        ttk.Button(btn_frame, text=L['save'], command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=L['cancel'], command=on_dialog_close).pack(side=tk.LEFT, padx=5)

    def delete_config(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror(self.L['error'], self.L['select_config'])
            return

        item = sel[0]
        parent = self.tree.parent(item)
        grandparent = self.tree.parent(parent) if parent else ''

        if grandparent:
            # 第三层：删除单个配置
            config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
            if config:
                self.configs.remove(config)
        elif parent:
            # 第二层：删除该端点下所有配置
            endpoint = self.tree.item(item, 'text')
            cli_name = self.tree.item(parent, 'text')
            cli_key = None
            for k, v in CLI_TOOLS.items():
                if v['name'] == cli_name:
                    cli_key = k
                    break
            if cli_key:
                self.configs = [c for c in self.configs if not (c.get('cli_type', 'claude') == cli_key and c['provider'].get('endpoint', '') == endpoint)]
        else:
            # 第一层：删除整个 CLI 类型分组
            cli_name = self.tree.item(item, 'text')
            cli_key = None
            for k, v in CLI_TOOLS.items():
                if v['name'] == cli_name:
                    cli_key = k
                    break
            if cli_key:
                self.configs = [c for c in self.configs if c.get('cli_type', 'claude') != cli_key]

        save_configs(self.configs)
        self.refresh_list()

    def copy_key(self):
        if not self.selected_config_id:
            messagebox.showerror(self.L['error'], self.L['select_config'])
            return

        config = self.get_config_by_id(self.selected_config_id)
        if not config:
            return

        api_key = config['provider']['credentials']['api_key']
        key_name = config['provider'].get('key_name', 'ANTHROPIC_API_KEY')
        endpoint = config['provider'].get('endpoint', '')
        cli_type = config.get('cli_type', 'claude')
        cli_info = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
        base_url_env = cli_info.get('base_url_env', 'ANTHROPIC_BASE_URL')

        text = f"{key_name}: {api_key}"
        if endpoint:
            text += f"\n{base_url_env}: {endpoint}"

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo(self.L['success'], self.L['key_copied'])

    def move_up(self):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        parent = self.tree.parent(item)
        grandparent = self.tree.parent(parent) if parent else ''

        # 只有第三层配置项可以移动
        if not grandparent:
            return

        endpoint = self.tree.item(parent, 'text')
        cli_type = self._get_cli_key_from_node(grandparent)

        configs_in_group = sorted([c for c in self.configs if c.get('cli_type', 'claude') == cli_type and c['provider'].get('endpoint', '') == endpoint], key=lambda c: c.get('order', 999))
        config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
        if config and len(configs_in_group) > 1:
            idx = configs_in_group.index(config)
            if idx > 0:
                config['order'], configs_in_group[idx - 1]['order'] = configs_in_group[idx - 1]['order'], config['order']
                save_configs(self.configs)
                self.refresh_list()

    def _get_cli_key_from_node(self, node):
        """从树节点获取 CLI key"""
        cli_name = self.tree.item(node, 'text')
        for k, v in CLI_TOOLS.items():
            if v['name'] == cli_name:
                return k
        return 'claude'

    def move_down(self):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        parent = self.tree.parent(item)
        grandparent = self.tree.parent(parent) if parent else ''

        # 只有第三层配置项可以移动
        if not grandparent:
            return

        endpoint = self.tree.item(parent, 'text')
        cli_type = self._get_cli_key_from_node(grandparent)

        configs_in_group = sorted([c for c in self.configs if c.get('cli_type', 'claude') == cli_type and c['provider'].get('endpoint', '') == endpoint], key=lambda c: c.get('order', 999))
        config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
        if config and len(configs_in_group) > 1:
            idx = configs_in_group.index(config)
            if idx < len(configs_in_group) - 1:
                config['order'], configs_in_group[idx + 1]['order'] = configs_in_group[idx + 1]['order'], config['order']
                save_configs(self.configs)
                self.refresh_list()

    def get_python_activation_command(self, python_env_name):
        """获取Python环境激活命令"""
        if not python_env_name or python_env_name not in self.settings.get('python_envs', {}):
            return ""

        python_env_info = self.settings['python_envs'][python_env_name]
        env_type = python_env_info['type']
        env_path = python_env_info['path']

        if env_type == 'conda':
            # 对于conda环境，使用conda activate命令（不要加&&，让终端保持打开）
            if python_env_name == 'base':
                return "conda activate base"
            else:
                return f"conda activate {python_env_name}"
        elif env_type == 'standard':
            python_dir = os.path.dirname(env_path)
            if os.path.exists(os.path.join(python_dir, 'activate')):
                return f"call \"{os.path.join(python_dir, 'activate')}\" && "

        return ""

    def build_powershell_env_command(self, key_name, api_key, endpoint='', base_url_env='ANTHROPIC_BASE_URL'):
        """构建PowerShell环境变量设置命令"""
        # 检查key_name中是否有特殊字符（如破折号）
        has_special_chars = '-' in key_name or any(c in key_name for c in [':', '.', '[', ']', '$'])

        if has_special_chars:
            # 对于有特殊字符的变量名，使用[System.Environment]::SetEnvironmentVariable()
            cmd_parts = [f'[System.Environment]::SetEnvironmentVariable("{key_name}", "{api_key}", "Process")']
        else:
            # 对于普通变量名，可以直接用$env:
            cmd_parts = [f'$env:{key_name}="{api_key}"']

        if endpoint:
            cmd_parts.append(f'$env:{base_url_env}="{endpoint}"')

        return '; '.join(cmd_parts)

    def build_cmd_env_command(self, key_name, api_key, endpoint='', base_url_env='ANTHROPIC_BASE_URL'):
        """构建CMD环境变量设置命令"""
        cmd_parts = [f'set "{key_name}={api_key}"']

        if endpoint:
            cmd_parts.append(f'set {base_url_env}={endpoint}')

        return ' && '.join(cmd_parts)

    def open_terminal(self):
        if not self.selected_config_id:
            messagebox.showerror(self.L['error'], self.L['select_config'])
            return

        self.configs = load_configs()
        config = self.get_config_by_id(self.selected_config_id)
        if not config:
            return

        api_key = config['provider']['credentials']['api_key']
        key_name = config['provider'].get('key_name', 'ANTHROPIC_API_KEY')
        endpoint = config['provider'].get('endpoint', '')
        cli_type = config.get('cli_type', 'claude')
        cli_info = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
        cli_command = cli_info['command']
        base_url_env = cli_info.get('base_url_env', 'ANTHROPIC_BASE_URL')

        terminal_name = self.terminal_var.get()
        if terminal_name not in self.available_terminals:
            messagebox.showerror(self.L['error'], self.L['terminal_unavailable'])
            return
        terminal_cmd = self.available_terminals[terminal_name]
        python_env_name = self.python_env_var.get()

        # 保存用户选择的终端
        self.settings['terminal'] = terminal_name
        save_settings(self.settings)

        try:
            env = os.environ.copy()
            env[key_name] = api_key
            if endpoint:
                env[base_url_env] = endpoint
            # 设置 UTF-8 编码环境变量，解决 conda 输出编码问题
            env['PYTHONIOENCODING'] = 'utf-8'

            work_dir = self.work_dir_var.get()
            cwd = work_dir if (work_dir and os.path.isdir(work_dir)) else None

            if sys.platform == 'win32':
                # 生成激活命令
                activation_cmd = self.get_python_activation_command(python_env_name)

                # 详细调试输出
                print("=========================================")
                print("=== 终端打开调试信息 ===")
                print(f"CLI工具: {cli_type} ({cli_command})")
                print(f"选择的Python环境: {python_env_name}")
                print(f"激活命令: '{activation_cmd}'")
                print(f"终端类型: {terminal_name}")
                print(f"终端命令: {terminal_cmd}")
                print(f"API密钥变量: {key_name}")
                print(f"端点: {endpoint}")
                print(f"工作目录: {cwd}")
                print("=========================================")

                # UTF-8 编码设置，解决 conda 输出编码问题
                utf8_prefix = 'chcp 65001 > $null; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [Console]::InputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; '

                if terminal_cmd == 'pwsh':
                    if activation_cmd:
                        env_cmd = self.build_powershell_env_command(key_name, api_key, endpoint, base_url_env)
                        full_cmd = f'{utf8_prefix}{env_cmd}; {activation_cmd}; {cli_command}'
                        print(f"PowerShell完整命令: {full_cmd}")
                        run_terminal(['pwsh', '-NoExit', '-Command', full_cmd], env, cwd)
                    else:
                        run_terminal(['pwsh', '-NoExit'], env, cwd)

                elif terminal_cmd == 'powershell':
                    if activation_cmd:
                        env_cmd = self.build_powershell_env_command(key_name, api_key, endpoint, base_url_env)
                        full_cmd = f'{utf8_prefix}{env_cmd}; {activation_cmd}; {cli_command}'
                        print(f"PowerShell完整命令: {full_cmd}")
                        run_terminal(['powershell', '-NoExit', '-Command', full_cmd], env, cwd)
                    else:
                        run_terminal(['powershell', '-NoExit'], env, cwd)

                elif terminal_cmd.endswith('bash.exe') or 'bash' in terminal_cmd:
                    if activation_cmd:
                        env_cmd = f'export {key_name}="{api_key}"'
                        if endpoint:
                            env_cmd += f'; export {base_url_env}="{endpoint}"'
                        full_cmd = f'{env_cmd}; {activation_cmd}; {cli_command}'
                        print(f"Git Bash完整命令: {full_cmd}")
                        run_terminal([terminal_cmd, '-i', '-c', full_cmd], env, cwd)
                    else:
                        run_terminal([terminal_cmd, '-i'], env, cwd)

                else:
                    # CMD
                    if activation_cmd:
                        env_cmd = self.build_cmd_env_command(key_name, api_key, endpoint, base_url_env)
                        full_cmd = f'{env_cmd} && {activation_cmd} && {cli_command}'
                        print(f"CMD完整命令: {full_cmd}")
                        run_terminal(['cmd', '/k', full_cmd], env, cwd)
                    else:
                        run_terminal(['cmd', '/k'], env, cwd)
            else:
                subprocess.Popen(terminal_cmd, env=env, cwd=cwd, shell=True)
        except Exception as e:
            messagebox.showerror(self.L['error'], self.L['cannot_open_terminal'].format(str(e)))

    def select_work_dir(self):
        folder = filedialog.askdirectory(title=self.L['select_work_dir'])
        if folder:
            self.work_dir_var.set(folder)
            folder_file = CONFIG_DIR / 'last_folder.txt'
            with open(folder_file, 'w', encoding='utf-8') as f:
                f.write(folder)

    def refresh_terminals(self):
        self.available_terminals = detect_terminals()
        self.settings['terminals'] = self.available_terminals
        save_settings(self.settings)
        self.terminal_combo['values'] = list(self.available_terminals.keys())
        if self.available_terminals:
            self.terminal_var.set(list(self.available_terminals.keys())[0])
        messagebox.showinfo(self.L['success'], self.L['terminals_refreshed'])

    def refresh_python_envs(self):
        """刷新Python环境列表"""
        new_python_envs = detect_python_envs()
        self.settings['python_envs'] = new_python_envs

        # 获取当前选择的环境和上次保存的环境
        current_selection = self.python_env_var.get()
        last_saved_env = self.settings.get('default_python_env', '')

        # 优先尝试保持上次使用的环境（如果存在）
        if last_saved_env and last_saved_env in new_python_envs:
            self.python_env_var.set(last_saved_env)
        # 如果当前选择的环境还存在，保持当前选择
        elif current_selection in new_python_envs:
            self.settings['default_python_env'] = current_selection
        # 否则选择默认的（非BASE）环境
        elif new_python_envs:
            default_env = get_default_python_env(new_python_envs)
            self.python_env_var.set(default_env)
            self.settings['default_python_env'] = default_env
        else:
            self.python_env_var.set('')
            self.settings['default_python_env'] = ''

        # 更新设置文件
        save_settings(self.settings)

        # 更新下拉列表
        self.python_env_combo['values'] = list(new_python_envs.keys())

        if new_python_envs:
            messagebox.showinfo(self.L['success'], self.L['envs_refreshed'].format(len(new_python_envs)))
        else:
            messagebox.showwarning(self.L['warning'], self.L['no_envs'])

    def add_terminal_dialog(self):
        L = self.L
        dialog = tk.Toplevel(self.root)
        dialog.title(L['add_custom_terminal'])
        dialog.geometry('400x150')

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=L['terminal_name'], font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=L['command'], font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        cmd_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        cmd_entry.grid(row=1, column=1, pady=5)

        def save():
            name = name_entry.get()
            cmd = cmd_entry.get()
            if not name or not cmd:
                messagebox.showerror(L['error'], L['fill_name_cmd'])
                return
            self.available_terminals[name] = cmd
            self.settings['terminals'] = self.available_terminals
            save_settings(self.settings)
            self.terminal_combo['values'] = list(self.available_terminals.keys())
            messagebox.showinfo(L['success'], L['terminal_added'])
            dialog.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=L['save'], command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=L['cancel'], command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def load_last_folder(self):
        folder_file = CONFIG_DIR / 'last_folder.txt'
        if folder_file.exists():
            try:
                with open(folder_file, 'r', encoding='utf-8') as f:
                    folder = f.read().strip()
            except UnicodeDecodeError:
                with open(folder_file, 'r', encoding='gbk') as f:
                    folder = f.read().strip()
            if os.path.isdir(folder):
                return folder
        return None

    def export_configs(self):
        file = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON files', '*.json')])
        if file:
            try:
                data = {
                    'version': '1.0',
                    'configurations': self.configs,
                    'defaultConfiguration': None
                }
                with open(file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                messagebox.showinfo(self.L['success'], self.L['exported_to'].format(file))
            except Exception as e:
                messagebox.showerror(self.L['error'], self.L['export_failed'].format(str(e)))

    def import_configs(self):
        file = filedialog.askopenfilename(filetypes=[('JSON files', '*.json')])
        if file:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    imported = data.get('configurations', [])
                    if not imported:
                        messagebox.showerror(self.L['error'], self.L['no_config_data'])
                        return
                    self.configs.extend(imported)
                    save_configs(self.configs)
                    self.refresh_list()
                    messagebox.showinfo(self.L['success'], self.L['imported_count'].format(len(imported)))
            except Exception as e:
                messagebox.showerror(self.L['error'], self.L['import_failed'].format(str(e)))

if __name__ == '__main__':
    instance_lock = threading.Lock()

    def check_existing_instance():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 9999))
            sock.close()
            return result == 0
        except:
            return False

    def start_listener():
        try:
            listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_sock.bind(('127.0.0.1', 9999))
            listen_sock.listen(1)

            def accept_connections():
                while True:
                    try:
                        conn, addr = listen_sock.accept()
                        conn.close()
                        with instance_lock:
                            root.lift()
                            root.attributes('-topmost', True)
                            root.after(100, lambda: root.attributes('-topmost', False))
                    except:
                        break

            thread = threading.Thread(target=accept_connections, daemon=True)
            thread.start()
        except:
            pass

    if check_existing_instance():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', 9999))
            sock.close()
        except:
            pass
        sys.exit(0)

    root = tk.Tk()
    icon_path = Path(__file__).parent / 'icon.ico'
    if icon_path.exists():
        root.iconbitmap(str(icon_path))
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))
    app = App(root)
    start_listener()
    root.mainloop()
