# 打包脚本 - 自动处理 mcp_data 目录位置
import subprocess
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).parent
DIST = BASE / "dist"

# 1. 运行 PyInstaller
subprocess.run([sys.executable, "-m", "PyInstaller", "AI-CLI-Manager.spec", "--noconfirm"], cwd=BASE, check=True)

# 2. 把 mcp_data 从 _internal 复制到根目录
src = DIST / "_internal" / "mcp_data"
dst = DIST / "mcp_data"
if src.exists():
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"已复制 mcp_data 到 {dst}")

# 3. 复制 icon.ico 到根目录
icon_src = DIST / "_internal" / "icon.ico"
icon_dst = DIST / "icon.ico"
if icon_src.exists() and not icon_dst.exists():
    shutil.copy2(icon_src, icon_dst)
    print(f"已复制 icon.ico 到 {icon_dst}")

print("打包完成！")
