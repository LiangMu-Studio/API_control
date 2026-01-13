# 最小化打包脚本
# 只包含实际需要的依赖

import subprocess
import sys

# 实际需要的依赖白名单
REQUIRED_PACKAGES = [
    'flet',           # UI 框架
    'requests',       # HTTP 请求
    'anthropic',      # Anthropic API (可选，但 services 里有引用)
]

# 需要排除的大型包（这些被 flet 或其他包间接引入但不需要）
EXCLUDES = [
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PyQt5',
    'PyQt6',
    'PySide6',
    'PySide2',
    'IPython',
    'jupyter',
    'notebook',
    'nbformat',
    'sphinx',
    'docutils',
    'babel',
    'jedi',
    'parso',
    'astroid',
    'pylint',
    'black',
    'yapf',
    'pytest',
    'coverage',
    'zmq',
    'tornado',
    'tkinter',
    '_tkinter',
]

def build():
    excludes_args = []
    for pkg in EXCLUDES:
        excludes_args.extend(['--exclude-module', pkg])

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--console',  # 调试模式，显示控制台
        '--name', 'AI-CLI-Manager',
        '--icon', 'icon.ico',
        '--add-data', 'mcp_data;mcp_data',
        '--hidden-import', 'pystray',
        '--hidden-import', 'PIL',
        '--noconfirm',
        '--clean',
    ] + excludes_args + ['main.py']

    print('Running:', ' '.join(cmd))
    subprocess.run(cmd, check=True)

if __name__ == '__main__':
    build()
