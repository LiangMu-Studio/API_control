"""测试复制路径功能"""
import subprocess
import time


def test_get_selected():
    """测试获取资源管理器选中的文件"""
    ps_script = '''
$shell = New-Object -ComObject Shell.Application
$windows = $shell.Windows()
Write-Output "找到 $($windows.Count) 个窗口"
foreach ($window in $windows) {
    try {
        $loc = $window.LocationURL
        Write-Output "窗口: $loc"
        $selected = $window.Document.SelectedItems()
        Write-Output "选中数量: $($selected.Count)"
        if ($selected.Count -gt 0) {
            $item = $selected.Item(0)
            Write-Output "Path: $($item.Path)"
            Write-Output "IsFolder: $($item.IsFolder)"
        }
    } catch {
        Write-Output "Error: $_"
    }
}
'''
    print("正在检测资源管理器中选中的文件...")
    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True, text=True, check=False
    )
    print(f"stdout:\n{result.stdout}")
    if result.stderr:
        print(f"stderr:\n{result.stderr}")


def test_with_click():
    """监听点击后获取选中文件"""
    try:
        from pynput import mouse
    except ImportError:
        print("需要安装 pynput")
        return

    print("请点击资源管理器中的任意文件...")

    def on_click(x, y, button, pressed):
        if not pressed and button == mouse.Button.left:
            time.sleep(0.2)
            print(f"\n检测到点击 ({x}, {y})")
            test_get_selected()
            return False

    with mouse.Listener(on_click=on_click) as listener:
        listener.join(timeout=30)


if __name__ == "__main__":
    print("=" * 50)
    print("测试1: 直接检测当前选中")
    print("=" * 50)
    test_get_selected()

    print("\n" + "=" * 50)
    print("测试2: 点击后检测")
    print("=" * 50)
    test_with_click()
