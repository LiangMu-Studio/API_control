"""复制路径工具 - 获取资源管理器选中的文件路径"""
import ctypes
import time
from pathlib import Path

import pythoncom
import win32com.client
import win32clipboard
import win32gui


def get_all_files(path: Path) -> list:
    """递归获取文件夹下所有文件路径"""
    files = []
    if path.is_file():
        files.append(str(path))
    elif path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                files.append(str(item))
    return files


def set_clipboard(text: str):
    """设置剪贴板"""
    for _ in range(3):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text)
            win32clipboard.CloseClipboard()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def get_selected_files():
    """获取资源管理器选中的文件"""
    pythoncom.CoInitialize()
    try:
        selected = []
        shell = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()

        # 获取普通资源管理器窗口的选中文件
        for i in range(windows.Count):
            try:
                window = windows.Item(i)
                if window and window.Document:
                    sel = window.Document.SelectedItems()
                    if sel.Count > 0:
                        for j in range(sel.Count):
                            selected.append(sel.Item(j).Path)
            except Exception:
                pass

        # 获取桌面选中的文件
        if not selected:
            selected = _get_desktop_selected_files(shell)

        return selected
    finally:
        pythoncom.CoUninitialize()


def _get_desktop_selected_files(shell):
    """获取桌面选中的文件"""
    selected = []
    try:
        # 查找桌面窗口
        progman = win32gui.FindWindow("Progman", "Program Manager")
        def_view = None

        if progman:
            def_view = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None)

        # 桌面可能在 WorkerW 下（Windows 10/11 壁纸幻灯片模式）
        if not def_view:
            worker = 0
            while True:
                worker = win32gui.FindWindowEx(0, worker, "WorkerW", None)
                if not worker:
                    break
                def_view = win32gui.FindWindowEx(worker, 0, "SHELLDLL_DefView", None)
                if def_view:
                    break

        if not def_view:
            return selected

        # 获取 ListView 控件
        list_view = win32gui.FindWindowEx(def_view, 0, "SysListView32", None)
        if not list_view:
            return selected

        # 使用 SendMessage 获取选中项数��
        LVM_FIRST = 0x1000
        LVM_GETSELECTEDCOUNT = LVM_FIRST + 50
        LVM_GETNEXTITEM = LVM_FIRST + 12
        LVNI_SELECTED = 0x0002

        count = ctypes.windll.user32.SendMessageW(list_view, LVM_GETSELECTEDCOUNT, 0, 0)
        if count == 0:
            return selected

        # 获取桌面文件夹
        desktop = shell.NameSpace(0)  # 0 = ssfDESKTOP
        if not desktop:
            return selected

        items = desktop.Items()
        item_count = items.Count

        # 获取选中项的索引
        idx = -1
        for _ in range(count):
            idx = ctypes.windll.user32.SendMessageW(list_view, LVM_GETNEXTITEM, idx, LVNI_SELECTED)
            if idx == -1:
                break
            if 0 <= idx < item_count:
                item = items.Item(idx)
                if item and item.Path:
                    selected.append(item.Path)

    except Exception:
        pass

    return selected


def main():
    """执行复制"""
    selected = get_selected_files()
    print(f"[CopyPath] 选中 {len(selected)} 个文件")

    if selected:
        all_files = []
        for p in selected:
            all_files.extend(get_all_files(Path(p)))

        if all_files:
            text = ",".join(all_files)
            if set_clipboard(text):
                print(f"[CopyPath] 已复制 {len(all_files)} 个文件:")
                for f in all_files:
                    print(f"[CopyPath]   {f}")
            else:
                print("[CopyPath] 剪贴板写入失败")
    else:
        print("[CopyPath] 未找到选中的文件")


if __name__ == "__main__":
    main()
