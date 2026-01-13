"""复制路径工具 - 获取资源管理器选中的文件路径"""
import time
from pathlib import Path

import pythoncom
import win32com.client
import win32clipboard


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
        return selected
    finally:
        pythoncom.CoUninitialize()


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
