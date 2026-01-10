"""系统托盘快速启动器"""

import threading
from pathlib import Path


def create_tray_icon(state, on_show_window, on_quit, on_screenshot=None, on_copy_path=None):
    """创建系统托盘图标

    Args:
        state: 应用状态对象
        on_show_window: 显示主窗口回调
        on_quit: 退出应用回调
        on_screenshot: 截屏回调
        on_copy_path: 复制路径回调
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
        items = [
            pystray.MenuItem("显示窗口", lambda: on_show_window(), default=True),
            pystray.Menu.SEPARATOR,
        ]
        if on_screenshot:
            items.append(pystray.MenuItem("截屏", lambda: on_screenshot()))
        if on_copy_path:
            items.append(pystray.MenuItem("复制路径", lambda: on_copy_path()))
        if on_screenshot or on_copy_path:
            items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("退出", lambda: on_quit()))
        return items

    icon = pystray.Icon(
        "AI CLI Manager",
        image,
        "AI CLI Manager",
        menu=pystray.Menu(lambda: build_menu())
    )

    return icon


def run_tray_in_background(icon):
    """在后台线程运行托盘图标"""
    if icon:
        def run_with_error_handling():
            try:
                icon.run()
            except Exception as e:
                print(f"[Tray] 托盘运行错误: {e}")
        thread = threading.Thread(target=run_with_error_handling, daemon=True)
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
