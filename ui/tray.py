"""系统托盘快速启动器"""

import threading
from pathlib import Path


def create_tray_icon(state, on_show_window, on_quit):
    """创建系统托盘图标

    Args:
        state: 应用状态对象
        on_show_window: 显示主窗口回调
        on_quit: 退出应用回调
    """
    try:
        import pystray
        from PIL import Image
    except ImportError:
        print("[Tray] pystray 或 PIL 未安装，跳过托盘图标")
        return None

    # 加载图标
    icon_path = Path(__file__).parent.parent / "icon.ico"
    if not icon_path.exists():
        icon_path = Path(__file__).parent.parent.parent / "icon.ico"

    try:
        image = Image.open(icon_path)
    except Exception:
        # 创建简单的默认图标
        image = Image.new('RGB', (64, 64), color='#607d8b')

    def build_menu():
        """构建托盘菜单"""
        items = [pystray.MenuItem("显示窗口", lambda: on_show_window())]

        # 添加配置快速启动
        configs = state.configs if hasattr(state, 'configs') else []
        if configs:
            items.append(pystray.Menu.SEPARATOR)
            # 最多显示 10 个配置
            for i, cfg in enumerate(configs[:10]):
                label = cfg.get('label', f'配置 {i+1}')
                items.append(pystray.MenuItem(
                    f"▶ {label}",
                    lambda _, idx=i: quick_launch(state, idx)
                ))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("退出", lambda: on_quit()))
        return items

    def quick_launch(state, config_idx):
        """快速启动指定配置"""
        import subprocess
        import sys
        import os

        if config_idx >= len(state.configs):
            return

        cfg = state.configs[config_idx]
        cli_type = cfg.get('cli_type', 'claude')

        # CLI 工具信息
        CLI_TOOLS = {
            'claude': {'command': 'claude', 'default_key_name': 'ANTHROPIC_API_KEY', 'base_url_env': 'ANTHROPIC_BASE_URL'},
            'codex': {'command': 'codex', 'default_key_name': 'OPENAI_API_KEY', 'base_url_env': 'OPENAI_BASE_URL'},
            'gemini': {'command': 'gemini', 'default_key_name': 'GEMINI_API_KEY', 'base_url_env': 'GEMINI_API_BASE'},
            'aider': {'command': 'aider', 'default_key_name': 'ANTHROPIC_API_KEY', 'base_url_env': 'ANTHROPIC_BASE_URL'},
        }

        cli_info = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
        api_key = cfg.get('provider', {}).get('credentials', {}).get('api_key', '')
        key_name = cfg.get('provider', {}).get('key_name', cli_info['default_key_name'])
        endpoint = cfg.get('provider', {}).get('endpoint', '')
        base_url_env = cfg.get('provider', {}).get('base_url_env', cli_info['base_url_env'])
        selected_model = cfg.get('provider', {}).get('selected_model', '')

        cli_cmd = cli_info.get('command', 'claude')
        if selected_model:
            cli_cmd = f"{cli_cmd} --model {selected_model}"

        # Windows 启动
        if sys.platform == 'win32':
            set_cmds = [f'set {key_name}={api_key}']
            if endpoint:
                set_cmds.append(f'set {base_url_env}={endpoint}')
            full_cmd = ' && '.join(set_cmds + [cli_cmd])
            subprocess.Popen(['cmd', '/k', full_cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            env = os.environ.copy()
            env[key_name] = api_key
            if endpoint:
                env[base_url_env] = endpoint
            subprocess.Popen(['bash', '-c', cli_cmd], env=env)

    icon = pystray.Icon(
        "AI CLI Manager",
        image,
        "AI CLI Manager",
        menu=pystray.Menu(lambda: build_menu())
    )

    # 双击显示窗口
    icon.on_activate = lambda: on_show_window()

    return icon


def run_tray_in_background(icon):
    """在后台线程运行托盘图标"""
    if icon:
        thread = threading.Thread(target=icon.run, daemon=True)
        thread.start()
        return thread
    return None


def stop_tray(icon):
    """停止托盘图标"""
    if icon:
        try:
            icon.stop()
        except Exception:
            pass
