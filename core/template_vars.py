"""提示词模板变量处理模块"""

import re
from datetime import datetime
from pathlib import Path


def expand_template_vars(content: str, work_dir: str = None) -> str:
    """展开提示词中的模板变量

    支持的变量:
    - {{date}} - 当前日期 YYYY-MM-DD
    - {{time}} - 当前时间 HH:MM
    - {{datetime}} - 完整日期时间
    - {{project}} - 工作目录名称
    - {{path}} - 工作目录完整路径
    - {{year}} - 当前年份
    - {{month}} - 当前月份
    - {{day}} - 当前日期
    """
    if not content:
        return content

    now = datetime.now()
    project_name = Path(work_dir).name if work_dir else ''

    replacements = {
        '{{date}}': now.strftime('%Y-%m-%d'),
        '{{time}}': now.strftime('%H:%M'),
        '{{datetime}}': now.strftime('%Y-%m-%d %H:%M'),
        '{{project}}': project_name,
        '{{path}}': work_dir or '',
        '{{year}}': str(now.year),
        '{{month}}': str(now.month).zfill(2),
        '{{day}}': str(now.day).zfill(2),
    }

    result = content
    for var, value in replacements.items():
        result = result.replace(var, value)

    return result


def get_available_vars() -> list:
    """返回可用的模板变量列表"""
    return [
        ('{{date}}', '当前日期 (YYYY-MM-DD)'),
        ('{{time}}', '当前时间 (HH:MM)'),
        ('{{datetime}}', '日期时间'),
        ('{{project}}', '项目目录名'),
        ('{{path}}', '完整路径'),
        ('{{year}}', '年份'),
        ('{{month}}', '月份'),
        ('{{day}}', '日期'),
    ]
