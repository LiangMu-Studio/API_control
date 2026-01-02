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
        return [
            pystray.MenuItem("显示窗口", lambda: on_show_window()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda: on_quit()),
        ]

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
