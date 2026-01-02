"""路径抓取工具 - 点击文件获取绝对路径"""

import sys
import subprocess
import platform

def get_file_path() -> str:
    """跨平台文件选择对话框，返回选中文件的绝对路径"""
    system = platform.system()

    if system == "Windows":
        # 使用 PowerShell 的文件选择对话框
        ps_script = '''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "选择文件获取路径"
$dialog.Filter = "所有文件 (*.*)|*.*"
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.FileName
}
'''
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.stdout.strip()

    elif system == "Darwin":  # macOS
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose file with prompt "选择文件获取路径")'],
            capture_output=True, text=True
        )
        return result.stdout.strip()

    else:  # Linux
        # 尝试 zenity
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--title=选择文件获取路径"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        # 尝试 kdialog
        try:
            result = subprocess.run(
                ["kdialog", "--getopenfilename", ".", "*"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass

    return ""


def copy_to_clipboard(text: str):
    """跨平台复制到剪贴板"""
    system = platform.system()

    if system == "Windows":
        subprocess.run(["clip"], input=text.encode('utf-16le'), check=True)
    elif system == "Darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
    else:
        # Linux - 尝试 xclip 或 xsel
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        except FileNotFoundError:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)


def pick_and_copy() -> str:
    """选择文件并复制路径到剪贴板，返回路径"""
    path = get_file_path()
    if path:
        copy_to_clipboard(path)
    return path


if __name__ == "__main__":
    path = pick_and_copy()
    if path:
        print(path)
