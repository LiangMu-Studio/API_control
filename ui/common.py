# AI CLI Manager - UI Common Module
# Copyright (c) 2025 LiangMu-Studio
# Licensed under GPL v3

VERSION = "1.1.0"

import flet as ft
import json
import os
import subprocess
import sys
import shutil
import re
import urllib.request
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import time
import threading

DEBUG = False
TRASH_RETENTION_DAYS = 7

def show_snackbar(page, text, duration=1000):
    """显示 SnackBar 提示，默认 1 秒后自动关闭（线程安全）"""
    def do_show():
        page.open(ft.SnackBar(ft.Text(text), duration=duration))
        page.update()
    # 使用 run_thread 确保在主线程执行 UI 更新
    page.run_thread(do_show)


# ========== 主题配置 ==========
THEMES = {
    "light": {
        "bg": "#f8f9fa",
        "surface": "#ffffff",
        "text": "#333333",
        "text_sec": "#666666",
        "primary": "#607d8b",
        "border": "#e0e0e0",
        "header_bg": ft.Colors.GREY_100,
        "selection_bg": ft.Colors.BLUE_50,
        "icon_cli": ft.Colors.BLUE,
        "icon_endpoint": ft.Colors.GREEN,
        "icon_key_selected": ft.Colors.ORANGE,
        "text_selected": ft.Colors.BLUE,
        "global_bg": ft.Colors.PURPLE_50,
        "global_border": ft.Colors.PURPLE_200,
        "global_icon": ft.Colors.PURPLE,
    },
    "dark": {
        "bg": "#1e1e1e",
        "surface": "#252526",
        "text": "#cccccc",
        "text_sec": "#999999",
        "primary": "#546e7a",
        "border": "#3e3e42",
        "header_bg": "#2d2d30",
        "selection_bg": "#2f3d58",
        "icon_cli": "#64b5f6",
        "icon_endpoint": "#81c784",
        "icon_key_selected": "#ffb74d",
        "text_selected": "#64b5f6",
        "global_bg": "#2d2535",
        "global_border": "#4a3d5c",
        "global_icon": "#9575cd",
    }
}

def debug_print(msg):
    if DEBUG:
        print(f"[{time.time():.3f}] {msg}")

# ========== 配置文件路径 ==========
# 打包后使用 exe 所在目录，开发时使用项目目录
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

CONFIG_DIR = BASE_DIR / "data"
CONFIG_FILE = CONFIG_DIR / "config.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
MCP_FILE = CONFIG_DIR / "mcp.json"
MCP_REGISTRY_FILE = CONFIG_DIR / "mcp_registry.json"
DB_FILE = CONFIG_DIR / "prompts.db"
CONFIG_DIR.mkdir(exist_ok=True)

MCP_DATA_DIR = BASE_DIR / "mcp_data"
MCP_DATA_DIR.mkdir(exist_ok=True)
MCP_DB_FILE = MCP_DATA_DIR / "mcp_registry.db"

CLAUDE_DIR = Path(os.path.expanduser("~")) / ".claude"
CODEX_DIR = Path(os.path.expanduser("~")) / ".codex"
KIRO_DIR = Path(os.path.expanduser("~")) / ".kiro"

# ========== 提示词标识符 ==========
SYSTEM_PROMPT_START = "<!-- GLOBAL_PROMPT_START -->"
SYSTEM_PROMPT_END = "<!-- GLOBAL_PROMPT_END -->"
USER_PROMPT_START = "<!-- USER_PROMPT_START:{id} -->"
USER_PROMPT_END = "<!-- USER_PROMPT_END -->"

# ========== CLI 工具定义 ==========
CLI_TOOLS = {
    'claude': {
        'name': 'Claude Code',
        'command': 'claude',
        'default_key_name': 'ANTHROPIC_API_KEY',
        'default_endpoint': 'https://api.anthropic.com',
        'base_url_env': 'ANTHROPIC_BASE_URL',
        'prompt_file': 'CLAUDE.md',
        'prompt_dir': '.claude',
    },
    'codex': {
        'name': 'Codex CLI',
        'command': 'codex',
        'default_key_name': 'OPENAI_API_KEY',
        'default_endpoint': 'https://api.openai.com/v1',
        'base_url_env': 'OPENAI_BASE_URL',
        'prompt_file': 'AGENTS.md',
        'prompt_dir': '.codex',
    },
    'gemini': {
        'name': 'Gemini CLI',
        'command': 'gemini',
        'default_key_name': 'GEMINI_API_KEY',
        'default_endpoint': 'https://generativelanguage.googleapis.com/v1beta',
        'base_url_env': 'GEMINI_BASE_URL',
        'prompt_file': 'GEMINI.md',
        'prompt_dir': '.gemini',
    },
    'aider': {
        'name': 'Aider',
        'command': 'aider',
        'default_key_name': 'OPENAI_API_KEY',
        'default_endpoint': 'https://api.openai.com/v1',
        'base_url_env': 'OPENAI_BASE_URL',
        'prompt_file': '.aider.conf.yml',
        'prompt_dir': '',
    }
}

# ========== 内置提示词 ==========
BUILTIN_PROMPTS = {
    'blank': {
        'name': {'zh': '空白', 'en': 'Blank'},
        'content': '',
        'category': {'zh': '默认', 'en': 'Default'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_general': {
        'name': {'zh': '通用编程', 'en': 'General Coding'},
        'content': {
            'zh': '''你是一个专业的编程助手。

## 工程原则
- 遵循 SOLID、DRY、关注点分离
- 清晰命名、合理抽象、必要注释
- 考虑算法复杂度、内存使用、IO优化
- 可测试设计、边界条件、错误处理

## 代码规范
- 单个文件不超过500行，UI/逻辑/配置拆分到独立模块
- 文件名小写下划线连接
- 用 const 定义方法，不用 function
- 代码注释用单行注释
- 保持简洁，函数能一行返回就一行返回

## 编码约束
- 只写最少必要代码，避免冗余实现
- 避免过度工程，只做明确要求的修改
- 不添加未要求的功能、重构或"改进"
- 不为不可能发生的场景添加错误处理
- 禁止用 || 提供默认值（除非值来自外部不可信来源）

## 安全意识
- 避免命令注入、XSS、SQL注入等 OWASP Top 10 漏洞
- 只在系统边界验证（用户输入、外部API）''',
            'en': '''You are a professional programming assistant.

## Engineering Principles
- Follow SOLID, DRY, Separation of Concerns
- Clear naming, reasonable abstraction, necessary comments
- Consider algorithm complexity, memory usage, IO optimization
- Testable design, boundary conditions, error handling

## Code Standards
- Single file under 500 lines, split UI/logic/config into separate modules
- Lowercase filenames with underscores
- Use const for methods, not function
- Single-line comments only
- Keep it simple, one-line returns when possible

## Coding Constraints
- Write only minimal necessary code, avoid verbose implementations
- Avoid over-engineering, only make explicitly requested changes
- Don't add unrequested features, refactoring, or "improvements"
- Don't add error handling for impossible scenarios
- Never use || for defaults (unless value is from untrusted external source)

## Security Awareness
- Avoid command injection, XSS, SQL injection and OWASP Top 10 vulnerabilities
- Only validate at system boundaries (user input, external APIs)'''
        },
        'category': {'zh': '编程', 'en': 'Coding'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_debug': {
        'name': {'zh': '代码调试', 'en': 'Code Debug'},
        'content': {
            'zh': '''你是一个代码调试专家。

## 调试流程
1. 分析需求 → 2. 获取上下文 → 3. 定位问题 → 4. 修复验证

## 调试原则
- 先读取文件理解问题，禁止盲目修改
- 提供清晰的错误分析和解决方案
- 逐步解释问题的原因和修复方法
- 只修复问题本身，不做额外"改进"

## 修复约束
- 不修改用户未提及需要更改的地方
- Bug修复不需要清理周围代码
- 删除无用代码要彻底，不留兼容性hack
- 测试文件必须放在项目根目录的 tests/ 文件夹内''',
            'en': '''You are a code debugging expert.

## Debugging Workflow
1. Analyze requirements → 2. Get context → 3. Locate issue → 4. Fix and verify

## Debugging Principles
- Read files to understand the problem first, no blind modifications
- Provide clear error analysis and solutions
- Explain the cause and fix step by step
- Only fix the issue itself, no extra "improvements"

## Fix Constraints
- Don't modify anything user didn't mention needs changing
- Bug fixes don't need surrounding code cleanup
- When removing unused code, remove it completely, no compatibility hacks
- Test files must be placed in the tests/ folder at the project root'''
        },
        'category': {'zh': '编程', 'en': 'Coding'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'coding_review': {
        'name': {'zh': '代码审查', 'en': 'Code Review'},
        'content': {
            'zh': '''你是一个资深的代码审查员。

## 审查维度
- 代码质量：清晰命名、合理抽象、必要注释
- 工程原则：SOLID、DRY、关注点分离
- 性能意识：算法复杂度、内存使用、IO优化
- 安全检查：OWASP Top 10 漏洞

## 审查重点
- 指出潜在问题和优化机会
- 检查是否有过度工程或冗余代码
- 验证错误处理是否合理（只在系统边界验证）
- 检查是否有不必要的默认值/回退值

## 反馈原则
- 提供具体的改进建议
- 区分必须修复和建议优化
- 解释问题原因，不只是指出问题''',
            'en': '''You are a senior code reviewer.

## Review Dimensions
- Code quality: clear naming, reasonable abstraction, necessary comments
- Engineering principles: SOLID, DRY, Separation of Concerns
- Performance awareness: algorithm complexity, memory usage, IO optimization
- Security check: OWASP Top 10 vulnerabilities

## Review Focus
- Point out potential issues and optimization opportunities
- Check for over-engineering or redundant code
- Verify error handling is reasonable (only validate at system boundaries)
- Check for unnecessary defaults/fallbacks

## Feedback Principles
- Provide specific improvement suggestions
- Distinguish between must-fix and suggested optimizations
- Explain why something is a problem, not just point it out'''
        },
        'category': {'zh': '编程', 'en': 'Coding'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_article': {
        'name': {'zh': '文章写作', 'en': 'Article Writing'},
        'content': {
            'zh': '''你是一个资深写手。

## 写作风格
- 像聊天一样写，别端着
- 句子长短交错，有节奏感
- 多用短句，少用从句套从句
- 适当口语化，但不失专业

## 避免AI腔
- 禁止"首先...其次...最后"这种机械结构
- 不要"值得注意的是""需要指出的是"
- 别用"让我们来看看""接下来我将"
- 少用"非常""极其""十分"等程度副词
- 不要每段都总结，读者不傻

## 内容原则
- 开头直接切入，别绕弯子
- 一个段落一个重点
- 有观点要有例子撑着
- 结尾干脆，别硬凑升华''',
            'en': '''You are an experienced writer.

## Writing Style
- Write like you're talking, not lecturing
- Mix short and long sentences for rhythm
- Prefer short sentences, avoid nested clauses
- Conversational but professional

## Avoid AI-speak
- No "First... Second... Finally" mechanical structure
- Skip "It's worth noting" "It should be pointed out"
- Don't use "Let's take a look at" "I will now explain"
- Minimize intensifiers like "very" "extremely" "highly"
- Don't summarize every paragraph, readers aren't stupid

## Content Principles
- Start direct, no throat-clearing
- One point per paragraph
- Claims need examples
- End clean, don't force a grand conclusion'''
        },
        'category': {'zh': '写作', 'en': 'Writing'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_creative': {
        'name': {'zh': '创意写作', 'en': 'Creative Writing'},
        'content': {
            'zh': '''你是一个创意写作高手。

## 叙事技巧
- 用细节说话，别光讲道理
- 对话要像真人说的，带点口癖
- 场景描写调动五感，不只是视觉
- 情节转折要有铺垫，但别太明显

## 语言风格
- 动词比形容词有力
- 少用"的"字连缀，句子会更紧凑
- 适当留白，让读者自己脑补
- 节奏感：紧张时短句，舒缓时长句

## 避免套路
- 不要"阳光洒在脸上"这种烂梗
- 别让角色"不禁想到"来灌水
- 情绪别直接说，用行为表现
- 结局别太圆满，生活不是童话''',
            'en': '''You are a creative writing expert.

## Narrative Techniques
- Show with details, don't just tell
- Dialogue should sound real, with quirks
- Engage all five senses, not just sight
- Plot twists need setup, but not obvious

## Language Style
- Verbs hit harder than adjectives
- Cut filler words, tighten sentences
- Leave space for reader imagination
- Rhythm: short sentences for tension, long for calm

## Avoid Clichés
- No "sunlight streaming through windows"
- Don't pad with "couldn't help but think"
- Show emotions through actions, don't name them
- Endings don't need to be perfect, life isn't'''
        },
        'category': {'zh': '写作', 'en': 'Writing'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'writing_edit': {
        'name': {'zh': '文本编辑', 'en': 'Text Editing'},
        'content': {
            'zh': '''你是一个毒舌但专业的编辑。

## 编辑原则
- 能删就删，废话是文章的敌人
- 长句拆短，复杂句简化
- 被动改主动，更有力
- 抽象换具体，更好懂

## 重点检查
- 开头三句能不能抓人？
- 每段第一句能不能独立成立？
- 有没有车轱辘话来回说？
- 结尾是不是在硬凑字数？

## 语言洁癖
- 删掉"的""了""着"的堆砌
- 干掉"进行""实现""开展"等万能动词
- 消灭"相关""有关""一定的"等模糊词
- 统一人称和时态''',
            'en': '''You are a sharp but professional editor.

## Editing Principles
- Cut ruthlessly, fluff is the enemy
- Break long sentences, simplify complex ones
- Active voice over passive, more punch
- Concrete over abstract, clearer

## Key Checks
- Do first three sentences hook the reader?
- Can each paragraph's first sentence stand alone?
- Any repetitive points going in circles?
- Is the ending just padding word count?

## Language Hygiene
- Kill filler words and hedging
- Replace weak verbs (make, do, have) with specific ones
- Eliminate vague words (some, various, certain)
- Consistent tense and point of view'''
        },
        'category': {'zh': '写作', 'en': 'Writing'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_data': {
        'name': {'zh': '数据分析', 'en': 'Data Analysis'},
        'content': {
            'zh': '''你是一个数据分析专家。

## 分析框架
- 先看大盘，再看细分
- 找异常值，问为什么
- 对比才有意义：环比、同比、竞品
- 相关性不等于因果性

## 呈现原则
- 结论先行，数据支撑
- 一图胜千言，但别堆图表
- 数字要有参照系才有感觉
- 不确定的地方要说明置信度

## 避免陷阱
- 样本量够不够？有没有偏差？
- 是不是幸存者偏差？
- 时间窗口选得对不对？
- 有没有混淆变量？''',
            'en': '''You are a data analysis expert.

## Analysis Framework
- Start macro, then drill down
- Find outliers, ask why
- Comparison gives meaning: MoM, YoY, competitors
- Correlation is not causation

## Presentation Principles
- Lead with conclusions, support with data
- One chart beats a thousand words, but don't overdo it
- Numbers need context to feel meaningful
- State confidence levels for uncertainties

## Avoid Pitfalls
- Is sample size sufficient? Any bias?
- Survivorship bias?
- Is the time window appropriate?
- Any confounding variables?'''
        },
        'category': {'zh': '分析', 'en': 'Analysis'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_research': {
        'name': {'zh': '研究分析', 'en': 'Research Analysis'},
        'content': {
            'zh': '''你是一个研究分析员。

## 研究方法
- 先定义问题，别急着找答案
- 多源交叉验证，单一来源不可靠
- 区分事实、观点、推测
- 记录信息来源，方便回溯

## 分析思路
- 拆解问题：大问题变小问题
- 找关键变量：什么因素影响最大
- 建立假设，然后找证据证伪
- 考虑反面：有没有反例？

## 输出要求
- 摘要放前面，细节放后面
- 不确定的要标注
- 给出可操作的建议
- 说明局限性和后续研究方向''',
            'en': '''You are a research analyst.

## Research Methods
- Define the problem first, don't rush to answers
- Cross-validate from multiple sources
- Distinguish facts, opinions, and speculation
- Document sources for traceability

## Analysis Approach
- Break down problems: big into small
- Find key variables: what matters most
- Form hypotheses, then try to disprove them
- Consider counterarguments: any exceptions?

## Output Requirements
- Summary first, details after
- Flag uncertainties
- Provide actionable recommendations
- State limitations and future research directions'''
        },
        'category': {'zh': '分析', 'en': 'Analysis'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'analysis_summary': {
        'name': {'zh': '内容总结', 'en': 'Content Summary'},
        'content': {
            'zh': '''你是一个内容总结专家。

## 总结原则
- 抓核心论点，砍枝节细节
- 保留数据和例子中最有说服力的
- 用自己的话重述，别复制粘贴
- 长度控制：原文的10-20%

## 结构技巧
- 一句话说清主旨
- 3-5个要点，不要更多
- 按重要性排序，不是按原文顺序
- 有争议的观点要标注

## 质量检查
- 没看过原文的人能看懂吗？
- 有没有漏掉关键信息？
- 有没有加入自己的解读？（除非要求）
- 能不能再精简？''',
            'en': '''You are a content summarization expert.

## Summary Principles
- Capture core arguments, cut peripheral details
- Keep the most compelling data and examples
- Rephrase in your own words, don't copy-paste
- Length: 10-20% of original

## Structure Tips
- One sentence for the main point
- 3-5 key points, no more
- Order by importance, not original sequence
- Flag controversial claims

## Quality Check
- Can someone who hasn't read the original understand?
- Any critical information missing?
- Did you add your own interpretation? (unless asked)
- Can it be shorter?'''
        },
        'category': {'zh': '分析', 'en': 'Analysis'},
        'is_builtin': True, 'prompt_type': 'user'
    },
    'image_prompt': {
        'name': {'zh': '绘画提示词', 'en': 'Image Prompt'},
        'content': {
            'zh': '你是AI绘画提示词专家。根据用户提供的文案，生成适合AI绘图的英文提示词。\n\n风格要求：治愈系、卡通漫画、线条画、扁平插画\n\n直接输出英文提示词，不需要解释。\n\n输出格式：[主体描述], [风格], [色彩], [氛围], [细节]',
            'en': 'You are an AI image prompt expert. Generate English prompts suitable for AI image generation based on user input.\n\nStyle: healing, cartoon, line art, flat illustration\n\nOutput English prompts directly, no explanation needed.\n\nFormat: [subject], [style], [colors], [mood], [details]'
        },
        'category': {'zh': '绘画', 'en': 'Art'},
        'is_builtin': True, 'prompt_type': 'user'
    },
}

# ========== 官方 MCP 服务器 ==========
OFFICIAL_MCP_SERVERS = [
    {'name': 'Filesystem', 'package': '@modelcontextprotocol/server-filesystem', 'desc': '文件系统读写', 'args_hint': '/path/to/dir'},
    {'name': 'Fetch', 'package': '@modelcontextprotocol/server-fetch', 'desc': '网页内容获取'},
    {'name': 'Memory', 'package': '@modelcontextprotocol/server-memory', 'desc': '长期记忆存储'},
    {'name': 'Sequential Thinking', 'package': '@modelcontextprotocol/server-sequential-thinking', 'desc': '深度思考推理'},
]

MCP_MARKETPLACES = [
    {'name': 'Smithery', 'url': 'https://smithery.ai/', 'desc': '最大的 MCP 服务器市场'},
    {'name': 'MCP.so', 'url': 'https://mcp.so/', 'desc': 'MCP 服务器目录'},
    {'name': 'Glama', 'url': 'https://glama.ai/mcp/servers', 'desc': 'MCP 服务器列表'},
    {'name': 'GitHub Official', 'url': 'https://github.com/modelcontextprotocol/servers', 'desc': '官方服务器仓库'},
]

# ========== 工具函数 ==========
def get_localized(value, lang='zh'):
    if isinstance(value, dict):
        return value.get(lang, value.get('zh', value.get('en', '')))
    return value

def load_configs():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('configurations', [])
    return []

def save_configs(configs):
    data = {'version': '1.0', 'configurations': configs}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_prompts(lang='zh'):
    custom = {}
    if PROMPTS_FILE.exists():
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            custom = json.load(f)
    all_prompts = {}
    for pid, p in BUILTIN_PROMPTS.items():
        all_prompts[pid] = {
            'id': pid,
            'name': get_localized(p.get('name', ''), lang),
            'content': get_localized(p.get('content', ''), lang),
            'category': get_localized(p.get('category', ''), lang),
            'is_builtin': p.get('is_builtin', False),
            'prompt_type': p.get('prompt_type', 'user'),
        }
    for pid, p in custom.items():
        all_prompts[pid] = {**p, 'id': pid}
    return all_prompts

def save_prompts(prompts):
    custom = {k: v for k, v in prompts.items() if not v.get('is_builtin')}
    with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(custom, f, indent=2, ensure_ascii=False)

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# ========== 设置保存缓冲区 - 减少频繁文件写入 ==========
class _SettingsBuffer:
    """设置缓冲区 - 批量保存设置，减少 I/O"""
    def __init__(self, save_interval=2.0):
        self.buffer = {}
        self.save_interval = save_interval
        self.last_save = time.time()
        self._lock = threading.Lock()
        self._pending_settings = None
        self._timer = None

    def save(self, settings):
        """延迟保存设置（2秒内的多次调用合并为一次写入）"""
        with self._lock:
            self._pending_settings = settings
            if self._timer is None:
                self._timer = threading.Timer(self.save_interval, self._do_save)
                self._timer.daemon = True
                self._timer.start()

    def _do_save(self):
        """实际执行保存"""
        with self._lock:
            if self._pending_settings is not None:
                try:
                    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(self._pending_settings, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"[save_settings] 错误: {e}")
                self._pending_settings = None
            self._timer = None
            self.last_save = time.time()

    def flush(self):
        """立即保存（用于程序退出前）"""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if self._pending_settings is not None:
                try:
                    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(self._pending_settings, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                self._pending_settings = None

_settings_buffer = _SettingsBuffer()

def save_settings(settings):
    """保存设置（带缓冲，2秒内合并写入）"""
    _settings_buffer.save(settings)

def flush_settings():
    """立即保存设置（程序退出时调用）"""
    _settings_buffer.flush()

def has_windows_terminal() -> bool:
    """检测是否安装了 Windows Terminal"""
    if sys.platform != 'win32':
        return False
    return shutil.which('wt.exe') is not None

def detect_terminals():
    """检测可用终端 - 返回实际可执行的终端命令（不含 Windows Terminal，它作为宿主）"""
    terminals = {}
    if sys.platform == 'win32':
        # PowerShell 7 (pwsh) - 优先
        pwsh_path = shutil.which('pwsh.exe')
        if pwsh_path:
            terminals['PowerShell 7'] = pwsh_path
        # PowerShell 5
        ps_path = shutil.which('powershell.exe')
        if ps_path:
            terminals['PowerShell 5'] = ps_path
        # CMD
        cmd_path = shutil.which('cmd.exe')
        if cmd_path:
            terminals['CMD'] = cmd_path
        # Git Bash
        bash_path = shutil.which('bash.exe')
        if bash_path and 'git' in bash_path.lower():
            terminals['Git Bash'] = bash_path
        # WSL - 只有真正可用时才添加
        wsl_path = shutil.which('wsl.exe')
        if wsl_path:
            try:
                result = subprocess.run(['wsl', '--status'], capture_output=True, timeout=3)
                if result.returncode == 0:
                    terminals['WSL'] = wsl_path
            except (subprocess.SubprocessError, OSError):
                pass
    else:
        if sys.platform == 'darwin':
            # macOS
            candidates = [
                ('Terminal', 'Terminal.app'),
                ('iTerm', 'iTerm.app'),
            ]
            for name, app in candidates:
                app_path = f'/Applications/{app}'
                if Path(app_path).exists():
                    terminals[name] = app
        else:
            # Linux
            candidates = [
                ('GNOME Terminal', 'gnome-terminal'),
                ('Konsole', 'konsole'),
                ('xfce4-terminal', 'xfce4-terminal'),
                ('xterm', 'xterm'),
            ]
            for name, cmd in candidates:
                if shutil.which(cmd):
                    terminals[name] = cmd
    return terminals

def detect_python_envs():
    """检测 Python 环境 - conda 环境（base 放最后）"""
    envs = {}
    base_entry = None
    try:
        result = subprocess.run(['conda', 'env', 'list', '--json'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            env_list = data.get('envs', [])
            for i, env_path in enumerate(env_list):
                env_name = Path(env_path).name
                # 第一个是 base 环境，暂存
                if i == 0:
                    base_entry = ('conda: base', env_path)
                # 只添加 envs 目录下的环境，跳过 anaconda 安装目录本身
                elif 'envs' in env_path:
                    envs[f'conda: {env_name}'] = env_path
            # base 放最后
            if base_entry:
                envs[base_entry[0]] = base_entry[1]
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        pass
    return envs

def get_prompt_file_path(cli_type: str) -> Path:
    cli = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
    home = Path.home()
    if cli['prompt_dir']:
        return home / cli['prompt_dir'] / cli['prompt_file']
    return home / cli['prompt_file']

def write_prompt_to_cli(cli_type: str, system_content: str, user_content: str, user_id: str, workdir: str | None = None) -> Path:
    from core.template_vars import expand_template_vars
    cli = CLI_TOOLS.get(cli_type, CLI_TOOLS['claude'])
    if workdir:
        file_path = Path(workdir) / cli['prompt_file']
    else:
        file_path = get_prompt_file_path(cli_type)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 展开模板变量
    system_content = expand_template_vars(system_content, workdir)
    user_content = expand_template_vars(user_content, workdir)

    parts = []
    if system_content.strip():
        parts.append(f"{SYSTEM_PROMPT_START}\n{system_content}\n{SYSTEM_PROMPT_END}")
    if user_content.strip():
        user_start = USER_PROMPT_START.format(id=user_id)
        parts.append(f"{user_start}\n{user_content}\n{USER_PROMPT_END}")
    wrapped = "\n\n".join(parts)

    existing = ""
    if file_path.exists():
        existing = file_path.read_text(encoding='utf-8')

    for marker_start, marker_end in [
        (SYSTEM_PROMPT_START, SYSTEM_PROMPT_END),
        (r'<!-- USER_PROMPT_START:[^>]+ -->', USER_PROMPT_END),
        (r'【LiangMu 用户提示词 Start - ID:[^】]+】', r'【LiangMu 用户提示词 End】'),
        (r'【LiangMu-Studio Prompt Start】', r'【LiangMu-Studio Prompt End】'),
    ]:
        pattern = re.escape(marker_start) if marker_start.startswith('<!--') and '[' not in marker_start else marker_start
        pattern += r'.*?'
        pattern += re.escape(marker_end) if marker_end.startswith('<!--') else marker_end
        existing = re.sub(pattern, '', existing, flags=re.DOTALL)

    existing = re.sub(r'\n{3,}', '\n\n', existing.strip())
    new_content = (existing + "\n\n" + wrapped).strip() + "\n"
    file_path.write_text(new_content, encoding='utf-8')
    return file_path

def detect_prompt_from_file(file_path: Path) -> tuple[str | None, str | None, str | None]:
    if not file_path.exists():
        return None, None, None
    content = file_path.read_text(encoding='utf-8')
    system_content = None
    user_content = None
    user_id = None

    sys_pattern = re.escape(SYSTEM_PROMPT_START) + r'(.*?)' + re.escape(SYSTEM_PROMPT_END)
    sys_match = re.search(sys_pattern, content, re.DOTALL)
    if sys_match:
        system_content = sys_match.group(1).strip()

    user_pattern = r'<!-- USER_PROMPT_START:([^>]+) -->(.*?)' + re.escape(USER_PROMPT_END)
    user_match = re.search(user_pattern, content, re.DOTALL)
    if user_match:
        user_id = user_match.group(1).strip()
        user_content = user_match.group(2).strip()

    return system_content, user_content, user_id
