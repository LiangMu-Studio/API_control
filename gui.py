# LiangMu-Studio API Key
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3
# See LICENSE file for details

VERSION = "0.9"

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

if getattr(sys, 'frozen', False):
    CONFIG_DIR = Path(sys.executable).parent / "data"
else:
    CONFIG_DIR = Path(__file__).parent / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
CONFIG_DIR.mkdir(exist_ok=True)

def detect_python_envs():
    """检测系统中的Python环境"""
    python_envs = {}

    # 检测conda环境
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

                    # 只显示你关心的环境，避免重复
                    if env_name in ['base', 'python_learning']:
                        # 检查是否是当前环境
                        is_current = '*' in line
                        python_envs[env_name] = {
                            'type': 'conda',
                            'path': env_path,
                            'is_current': is_current
                        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

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
    if shutil.which('pwsh'):
        terminals['PowerShell 7'] = 'pwsh'
    if shutil.which('powershell'):
        terminals['PowerShell 5'] = 'powershell'
    if shutil.which('cmd'):
        terminals['CMD'] = 'cmd'
    return terminals

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
            # 如果设置文件是旧格式（没有python_envs），需要更新
            if 'terminals' in data and 'python_envs' not in data:
                python_envs = detect_python_envs()
                default_python_env = list(python_envs.keys())[0] if python_envs else None
                data['python_envs'] = python_envs
                data['default_python_env'] = default_python_env
                save_settings(data)
                return data
            elif 'terminals' in data:
                return data
    terminals = detect_terminals()
    python_envs = detect_python_envs()

    if not terminals:
        terminals = {'CMD': 'cmd'}
    default_terminal = list(terminals.keys())[0]
    default_python_env = list(python_envs.keys())[0] if python_envs else None

    settings = {
        'terminal': default_terminal,
        'terminals': terminals,
        'python_envs': python_envs,
        'default_python_env': default_python_env
    }
    save_settings(settings)
    return settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def load_configs():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return data.get('configurations', [])
    return []

def save_configs(configs):
    for i, config in enumerate(configs):
        if 'order' not in config:
            config['order'] = i
    data = {
        'version': '1.0',
        'configurations': configs,
        'defaultConfiguration': None
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f'LiangMu-Studio API Key v{VERSION} - PowerShell 集成终端')
        self.root.geometry('1000x500')
        self.configs = load_configs()
        self.settings = load_settings()

        self.editing_index = None
        self.selected_folder = self.load_last_folder()
        self.available_terminals = self.settings.get('terminals', {})
        self.selected_config_id = None

        # 上侧：配置管理
        top_frame = ttk.Frame(root)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(top_frame, text='API 密钥配置', font=('微软雅黑', 12, 'bold')).pack(side=tk.LEFT, padx=5)

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
        ttk.Button(btn_frame, text='新增', command=self.new_config).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Button(btn_frame, text='编辑', command=self.edit_config).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Button(btn_frame, text='删除', command=self.delete_config).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Button(btn_frame, text='复制密钥', command=self.copy_key).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Button(btn_frame, text='↑ 上移', command=self.move_up).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Button(btn_frame, text='↓ 下移', command=self.move_down).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, padx=2, pady=5, fill=tk.X)
        ttk.Button(btn_frame, text='导出', command=self.export_configs).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Button(btn_frame, text='导入', command=self.import_configs).pack(side=tk.TOP, padx=2, pady=2, fill=tk.X)
        ttk.Separator(btn_frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, padx=2, pady=5, fill=tk.X)
        feedback_label = tk.Label(btn_frame, text='反馈: GitHub Issues', fg='blue', cursor='hand2', font=('微软雅黑', 9))
        feedback_label.pack(side=tk.TOP, padx=2, pady=5)
        feedback_label.bind('<Button-1>', lambda e: webbrowser.open('https://github.com/LiangMu-Studio/API_control/issues'))

        # 下侧：终端
        bottom_frame = ttk.Frame(root)
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(bottom_frame, text='集成终端', font=('微软雅黑', 11, 'bold')).pack(side=tk.TOP, padx=5, pady=5)

        # 终端选择和管理
        term_frame = ttk.Frame(bottom_frame)
        term_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(term_frame, text='选择终端:', font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=5)
        self.terminal_var = tk.StringVar(value=self.settings.get('terminal', list(self.available_terminals.keys())[0] if self.available_terminals else 'CMD'))
        self.terminal_combo = ttk.Combobox(term_frame, textvariable=self.terminal_var, values=list(self.available_terminals.keys()), width=15, state='readonly')
        self.terminal_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(term_frame, text='+ 添加其他终端', command=self.add_terminal_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(term_frame, text='刷新终端列表', command=self.refresh_terminals).pack(side=tk.LEFT, padx=2)

        ttk.Label(term_frame, text='Python环境:', font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=5)
        self.python_env_var = tk.StringVar(value=self.settings.get('default_python_env', ''))
        self.python_env_combo = ttk.Combobox(term_frame, textvariable=self.python_env_var, values=list(self.settings.get('python_envs', {}).keys()), width=20, state='readonly')
        self.python_env_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(term_frame, text='刷新环境列表', command=self.refresh_python_envs).pack(side=tk.LEFT, padx=2)

        ttk.Label(term_frame, text='当前KEY:', font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=5)
        self.current_key_label = ttk.Label(term_frame, text='未选择', font=('微软雅黑', 10), foreground='blue')
        self.current_key_label.pack(side=tk.LEFT, padx=5)

        # 地址选择
        addr_frame = ttk.Frame(bottom_frame)
        addr_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(addr_frame, text='工作目录:', font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=5)
        self.work_dir_var = tk.StringVar(value=self.selected_folder or '')
        ttk.Entry(addr_frame, textvariable=self.work_dir_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(addr_frame, text='浏览', command=self.select_work_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(addr_frame, text='打开终端', command=self.open_terminal).pack(side=tk.LEFT, padx=2)

    def refresh_list(self):
        self.configs = load_configs()
        self.tree.delete(*self.tree.get_children())

        endpoints = {}
        for c in self.configs:
            endpoint = c['provider'].get('endpoint', '未分类')
            if endpoint not in endpoints:
                endpoints[endpoint] = []
            endpoints[endpoint].append(c)

        sorted_endpoints = sorted(endpoints.items(), key=lambda x: min(c.get('order', 999) for c in x[1]))
        for endpoint, configs in sorted_endpoints:
            parent = self.tree.insert('', 'end', text=endpoint, open=True)
            sorted_configs = sorted(configs, key=lambda c: c.get('order', 999))
            for c in sorted_configs:
                created = c.get('createdAt', '')[:10]
                text = f"{c['label']} ({created})"
                self.tree.insert(parent, 'end', text=text, tags=(c['id'],))

    def on_config_select(self, event):
        sel = self.tree.selection()
        if sel:
            item = sel[0]
            parent = self.tree.parent(item)
            if parent:
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

        if parent:
            self.edit_config()

    def get_config_by_id(self, config_id):
        for c in self.configs:
            if c['id'] == config_id:
                return c
        return None

    def new_config(self):
        self.show_config_dialog(None)

    def edit_config(self):
        if not self.selected_config_id:
            messagebox.showerror('错误', '请选择配置')
            return
        config = self.get_config_by_id(self.selected_config_id)
        if config:
            index = self.configs.index(config)
            self.show_config_dialog(index)

    def show_config_dialog(self, index):
        dialog = tk.Toplevel(self.root)
        dialog.title('配置编辑' if index is not None else '新增配置')
        dialog.geometry('500x300')

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text='标签:', font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        label_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        label_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text='提供商:', font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        provider_var = tk.StringVar(value='anthropic')
        provider_combo = ttk.Combobox(frame, textvariable=provider_var, font=('微软雅黑', 10),
                                      values=['openai', 'azure', 'anthropic', 'custom'], width=27)
        provider_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text='API地址:', font=('微软雅黑', 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        endpoint_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        endpoint_entry.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text='KEY名称:', font=('微软雅黑', 10)).grid(row=3, column=0, sticky=tk.W, pady=5)
        key_name_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        key_name_entry.insert(0, 'ANTHROPIC_AUTH_TOKEN')
        key_name_entry.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text='API密钥:', font=('微软雅黑', 10)).grid(row=4, column=0, sticky=tk.W, pady=5)
        api_key_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        api_key_entry.grid(row=4, column=1, pady=5)

        if index is not None:
            config = self.configs[index]
            label_entry.insert(0, config['label'])
            provider_var.set(config['provider']['type'])
            endpoint_entry.insert(0, config['provider'].get('endpoint', ''))
            key_name_entry.delete(0, tk.END)
            key_name_entry.insert(0, config['provider'].get('key_name', 'ANTHROPIC_AUTH_TOKEN'))
            api_key_entry.insert(0, config['provider']['credentials']['api_key'])

        def save():
            label = label_entry.get()
            provider = provider_var.get()
            endpoint = endpoint_entry.get()
            key_name = key_name_entry.get()
            api_key = api_key_entry.get()

            if not label or not api_key:
                messagebox.showerror('错误', '请填写标签和API密钥')
                return

            # 检查 KEY 名称在同一 API 下是否重名
            for i, c in enumerate(self.configs):
                if index is not None and i == index:
                    continue
                if c['provider'].get('endpoint') == endpoint and c['provider'].get('key_name') == key_name:
                    messagebox.showerror('错误', f'该地址下已存在 KEY 名称 "{key_name}"，不允许重名')
                    return

            if index is None:
                config = {
                    'id': f"{label}-{int(__import__('time').time())}",
                    'label': label,
                    'provider': {
                        'name': label,
                        'type': provider,
                        'endpoint': endpoint,
                        'key_name': key_name,
                        'credentials': {'api_key': api_key}
                    },
                    'createdAt': datetime.now().isoformat(),
                    'updatedAt': datetime.now().isoformat()
                }
                self.configs.append(config)
            else:
                self.configs[index]['label'] = label
                self.configs[index]['provider']['type'] = provider
                self.configs[index]['provider']['endpoint'] = endpoint
                self.configs[index]['provider']['key_name'] = key_name
                self.configs[index]['provider']['credentials']['api_key'] = api_key
                self.configs[index]['updatedAt'] = datetime.now().isoformat()

            save_configs(self.configs)
            self.refresh_list()
            dialog.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text='保存', command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='取消', command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def delete_config(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror('错误', '请选择配置')
            return

        item = sel[0]
        parent = self.tree.parent(item)

        if parent:
            config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
            if config:
                self.configs.remove(config)
        else:
            endpoint = self.tree.item(item, 'text')
            self.configs = [c for c in self.configs if c['provider'].get('endpoint', '未分类') != endpoint]

        save_configs(self.configs)
        self.refresh_list()

    def copy_key(self):
        if not self.selected_config_id:
            messagebox.showerror('错误', '请选择配置')
            return

        config = self.get_config_by_id(self.selected_config_id)
        if not config:
            return

        api_key = config['provider']['credentials']['api_key']
        key_name = config['provider'].get('key_name', 'ANTHROPIC_AUTH_TOKEN')
        endpoint = config['provider'].get('endpoint', '')

        text = f"{key_name}: {api_key}"
        if endpoint:
            text += f"\nANTHROPIC_BASE_URL: {endpoint}"

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo('成功', '密钥已复制到剪贴板')

    def move_up(self):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        parent = self.tree.parent(item)

        if parent:
            endpoint = self.tree.item(parent, 'text')
            configs_in_group = sorted([c for c in self.configs if c['provider'].get('endpoint', '未分类') == endpoint], key=lambda c: c.get('order', 999))
            config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
            if config and len(configs_in_group) > 1:
                idx = configs_in_group.index(config)
                if idx > 0:
                    config['order'], configs_in_group[idx - 1]['order'] = configs_in_group[idx - 1]['order'], config['order']
                    save_configs(self.configs)
                    self.refresh_list()
        else:
            endpoint = self.tree.item(item, 'text')
            current_group = [c for c in self.configs if c['provider'].get('endpoint', '未分类') == endpoint]
            all_endpoints = sorted(set(c['provider'].get('endpoint', '未分类') for c in self.configs), key=lambda e: min(c.get('order', 999) for c in self.configs if c['provider'].get('endpoint', '未分类') == e))

            if endpoint in all_endpoints:
                idx = all_endpoints.index(endpoint)
                if idx > 0:
                    prev_endpoint = all_endpoints[idx - 1]
                    prev_group = [c for c in self.configs if c['provider'].get('endpoint', '未分类') == prev_endpoint]
                    min_order_current = min(c.get('order', 999) for c in current_group)
                    min_order_prev = min(c.get('order', 999) for c in prev_group)
                    for c in current_group:
                        c['order'] = c['order'] - (min_order_current - min_order_prev)
                    for c in prev_group:
                        c['order'] = c['order'] + (min_order_current - min_order_prev)
                    save_configs(self.configs)
                    self.refresh_list()

    def move_down(self):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        parent = self.tree.parent(item)

        if parent:
            endpoint = self.tree.item(parent, 'text')
            configs_in_group = sorted([c for c in self.configs if c['provider'].get('endpoint', '未分类') == endpoint], key=lambda c: c.get('order', 999))
            config = self.get_config_by_id(self.tree.item(item, 'tags')[0])
            if config and len(configs_in_group) > 1:
                idx = configs_in_group.index(config)
                if idx < len(configs_in_group) - 1:
                    config['order'], configs_in_group[idx + 1]['order'] = configs_in_group[idx + 1]['order'], config['order']
                    save_configs(self.configs)
                    self.refresh_list()
        else:
            endpoint = self.tree.item(item, 'text')
            current_group = [c for c in self.configs if c['provider'].get('endpoint', '未分类') == endpoint]
            all_endpoints = sorted(set(c['provider'].get('endpoint', '未分类') for c in self.configs), key=lambda e: min(c.get('order', 999) for c in self.configs if c['provider'].get('endpoint', '未分类') == e))

            if endpoint in all_endpoints:
                idx = all_endpoints.index(endpoint)
                if idx < len(all_endpoints) - 1:
                    next_endpoint = all_endpoints[idx + 1]
                    next_group = [c for c in self.configs if c['provider'].get('endpoint', '未分类') == next_endpoint]
                    min_order_current = min(c.get('order', 999) for c in current_group)
                    min_order_next = min(c.get('order', 999) for c in next_group)
                    for c in current_group:
                        c['order'] = c['order'] + (min_order_next - min_order_current)
                    for c in next_group:
                        c['order'] = c['order'] - (min_order_next - min_order_current)
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

    def open_terminal(self):
        if not self.selected_config_id:
            messagebox.showerror('错误', '请选择配置')
            return

        self.configs = load_configs()
        config = self.get_config_by_id(self.selected_config_id)
        if not config:
            return

        api_key = config['provider']['credentials']['api_key']
        key_name = config['provider'].get('key_name', 'ANTHROPIC_AUTH_TOKEN')
        endpoint = config['provider'].get('endpoint', '')
        terminal_name = self.terminal_var.get()
        if terminal_name not in self.available_terminals:
            messagebox.showerror('错误', '选择的终端不可用')
            return
        terminal_cmd = self.available_terminals[terminal_name]
        python_env_name = self.python_env_var.get()

        try:
            env = os.environ.copy()
            env[key_name] = api_key
            if endpoint:
                env['ANTHROPIC_BASE_URL'] = endpoint

            work_dir = self.work_dir_var.get()
            cwd = work_dir if (work_dir and os.path.isdir(work_dir)) else None

            if sys.platform == 'win32':
                # 生成激活命令
                activation_cmd = self.get_python_activation_command(python_env_name)

                # 详细调试输出
                print("=========================================")
                print("=== 终端打开调试信息 ===")
                print(f"选择的Python环境: {python_env_name}")
                print(f"激活命令: '{activation_cmd}'")
                print(f"终端类型: {terminal_name}")
                print(f"终端命令: {terminal_cmd}")
                print(f"API密钥: {key_name}")
                print(f"端点: {endpoint}")
                print(f"工作目录: {cwd}")
                print("=========================================")

                if terminal_cmd == 'pwsh':
                    if activation_cmd:
                        # 只在选择Anthropic提供商时自动进入Claude
                        is_anthropic = config['provider'].get('type') == 'anthropic'

                        if endpoint:
                            cmd_suffix = '; claude' if is_anthropic else ''
                            full_cmd = f'$env:{key_name}="{api_key}"; $env:ANTHROPIC_BASE_URL="{endpoint}"; {activation_cmd}{cmd_suffix}'
                        else:
                            cmd_suffix = '; claude' if is_anthropic else ''
                            full_cmd = f'$env:{key_name}="{api_key}"; {activation_cmd}{cmd_suffix}'
                        print(f"PowerShell完整命令: {full_cmd}")
                        subprocess.Popen(['pwsh', '-NoExit', '-Command', full_cmd], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen(['pwsh', '-NoExit'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                elif terminal_cmd == 'powershell':
                    if activation_cmd:
                        # 只在选择Anthropic提供商时自动进入Claude
                        is_anthropic = config['provider'].get('type') == 'anthropic'

                        if endpoint:
                            cmd_suffix = '; claude' if is_anthropic else ''
                            full_cmd = f'$env:{key_name}="{api_key}"; $env:ANTHROPIC_BASE_URL="{endpoint}"; {activation_cmd}{cmd_suffix}'
                        else:
                            cmd_suffix = '; claude' if is_anthropic else ''
                            full_cmd = f'$env:{key_name}="{api_key}"; {activation_cmd}{cmd_suffix}'
                        print(f"PowerShell完整命令: {full_cmd}")
                        subprocess.Popen(['powershell', '-NoExit', '-Command', full_cmd], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen(['powershell', '-NoExit'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    # CMD
                    if activation_cmd:
                        # 只在选择Anthropic提供商时自动进入Claude
                        is_anthropic = config['provider'].get('type') == 'anthropic'

                        if endpoint:
                            cmd_suffix = ' && claude' if is_anthropic else ''
                            full_cmd = f'set "{key_name}={api_key}" && set ANTHROPIC_BASE_URL={endpoint} && {activation_cmd}{cmd_suffix}'
                        else:
                            cmd_suffix = ' && claude' if is_anthropic else ''
                            full_cmd = f'set "{key_name}={api_key}" && {activation_cmd}{cmd_suffix}'
                        print(f"CMD完整命令: {full_cmd}")
                        subprocess.Popen(['cmd', '/k', full_cmd], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen(['cmd', '/k'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(terminal_cmd, env=env, cwd=cwd, shell=True)
        except Exception as e:
            messagebox.showerror('错误', f'无法打开终端: {str(e)}')

    def select_work_dir(self):
        folder = filedialog.askdirectory(title='选择工作目录')
        if folder:
            self.work_dir_var.set(folder)
            folder_file = CONFIG_DIR / 'last_folder.txt'
            with open(folder_file, 'w') as f:
                f.write(folder)

    def refresh_terminals(self):
        self.available_terminals = detect_terminals()
        self.settings['terminals'] = self.available_terminals
        save_settings(self.settings)
        self.terminal_combo['values'] = list(self.available_terminals.keys())
        if self.available_terminals:
            self.terminal_var.set(list(self.available_terminals.keys())[0])
        messagebox.showinfo('成功', '终端列表已刷新')

    def refresh_python_envs(self):
        """刷新Python环境列表"""
        new_python_envs = detect_python_envs()
        self.settings['python_envs'] = new_python_envs

        # 如果当前选择的环境不存在了，选择第一个可用的
        current_selection = self.python_env_var.get()
        if current_selection not in new_python_envs:
            if new_python_envs:
                self.python_env_var.set(list(new_python_envs.keys())[0])
            else:
                self.python_env_var.set('')

        # 更新设置文件
        self.settings['default_python_env'] = self.python_env_var.get()
        save_settings(self.settings)

        # 更新下拉列表
        self.python_env_combo['values'] = list(new_python_envs.keys())

        if new_python_envs:
            messagebox.showinfo('成功', f'Python环境列表已刷新，发现 {len(new_python_envs)} 个环境')
        else:
            messagebox.showwarning('警告', '没有找到Python环境')

    def add_terminal_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('添加自定义终端')
        dialog.geometry('400x150')

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text='终端名称:', font=('微软雅黑', 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text='命令:', font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        cmd_entry = ttk.Entry(frame, width=30, font=('微软雅黑', 10))
        cmd_entry.grid(row=1, column=1, pady=5)

        def save():
            name = name_entry.get()
            cmd = cmd_entry.get()
            if not name or not cmd:
                messagebox.showerror('错误', '请填写终端名称和命令')
                return
            self.available_terminals[name] = cmd
            self.settings['terminals'] = self.available_terminals
            save_settings(self.settings)
            self.terminal_combo['values'] = list(self.available_terminals.keys())
            messagebox.showinfo('成功', '终端已添加')
            dialog.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text='保存', command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='取消', command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def load_last_folder(self):
        folder_file = CONFIG_DIR / 'last_folder.txt'
        if folder_file.exists():
            with open(folder_file, 'r') as f:
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
                with open(file, 'w') as f:
                    json.dump(data, f, indent=2)
                messagebox.showinfo('成功', f'配置已导出到: {file}')
            except Exception as e:
                messagebox.showerror('错误', f'导出失败: {str(e)}')

    def import_configs(self):
        file = filedialog.askopenfilename(filetypes=[('JSON files', '*.json')])
        if file:
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    imported = data.get('configurations', [])
                    if not imported:
                        messagebox.showerror('错误', '文件中没有配置数据')
                        return
                    self.configs.extend(imported)
                    save_configs(self.configs)
                    self.refresh_list()
                    messagebox.showinfo('成功', f'已导入 {len(imported)} 个配置')
            except Exception as e:
                messagebox.showerror('错误', f'导入失败: {str(e)}')

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
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))
    app = App(root)
    start_listener()
    root.mainloop()
