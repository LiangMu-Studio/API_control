# 白名单打包脚本
# 只打包明确需要的模块，类似 electron-builder 的 files 白名单方式

import subprocess
import sys
import os

# ========== 白名单配置 ==========
# 只有这些模块会被打包

WHITELIST = [
    # 核心框架
    'flet',
    'flet_desktop',

    # 网络请求
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',

    # SSL/加密
    'ssl',
    'cryptography',
    'cffi',
    '_ssl',

    # 标准库扩展
    'asyncio',
    'sqlite3',
    'json',
    'pathlib',
    'datetime',
    'threading',
    'subprocess',
    'shutil',
    're',
    'os',
    'sys',

    # 类型提示
    'typing',
    'typing_extensions',

    # 其他必需
    'httpx',
    'httpcore',
    'anyio',
    'sniffio',
    'h11',
    'websockets',
]

# 数据文件
DATAS = [
    ('mcp_data', 'mcp_data'),
]

# 打包配置
CONFIG = {
    'name': 'LiangMu-API-Key',
    'icon': 'icon.ico',
    'entry': 'app_flet.py',
    'onefile': True,
    'windowed': True,
    'console': False,  # 改为 True 可调试
}


def build():
    # 构建 hiddenimports 参数
    hidden_args = []
    for mod in WHITELIST:
        hidden_args.extend(['--hidden-import', mod])

    # 构建 datas 参数
    data_args = []
    for src, dst in DATAS:
        data_args.extend(['--add-data', f'{src};{dst}'])

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', CONFIG['name'],
        '--icon', CONFIG['icon'],
        '--noconfirm',
        '--clean',
    ]

    if CONFIG['onefile']:
        cmd.append('--onefile')

    if CONFIG['windowed'] and not CONFIG['console']:
        cmd.append('--windowed')

    cmd.extend(hidden_args)
    cmd.extend(data_args)
    cmd.append(CONFIG['entry'])

    print('=' * 60)
    print('白名单打包模式')
    print(f'入口文件: {CONFIG["entry"]}')
    print(f'白名单模块数: {len(WHITELIST)}')
    print('=' * 60)

    subprocess.run(cmd, check=True)

    # 显示结果
    dist_path = os.path.join('dist', f'{CONFIG["name"]}.exe')
    if os.path.exists(dist_path):
        size_mb = os.path.getsize(dist_path) / (1024 * 1024)
        print(f'\n打包完成: {dist_path}')
        print(f'文件大小: {size_mb:.1f} MB')


if __name__ == '__main__':
    build()
