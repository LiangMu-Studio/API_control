"""压缩调试工具 - 显示压缩过程和详情"""

from typing import List, Dict
from core.token_counter import TokenCounter


class CompressionDebugger:
    """压缩调试器 - 用于 DEBUG 时查看压缩详情"""

    def __init__(self):
        self.debug_logs = []

    def log_compression(self, card_id: str, topic: str, messages: List, versions: Dict):
        """记录卡片压缩信息"""
        log_entry = {
            'card_id': card_id,
            'topic': topic,
            'message_count': len(messages),
            'versions': {}
        }

        for version_name, version_content in versions.items():
            tokens = TokenCounter.count_tokens(version_content)
            log_entry['versions'][version_name] = {
                'content': version_content[:100] + '...' if len(version_content) > 100 else version_content,
                'tokens': tokens
            }

        self.debug_logs.append(log_entry)

    def log_context_generation(self, context: List[Dict], current_message: str):
        """记录上下文生成信息"""
        log_entry = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'context_messages': len(context),
            'current_message_tokens': TokenCounter.count_tokens(current_message),
            'context_breakdown': []
        }

        for i, msg in enumerate(context):
            tokens = TokenCounter.count_tokens(msg['content'])
            log_entry['context_breakdown'].append({
                'index': i,
                'role': msg['role'],
                'content': msg['content'][:80] + '...' if len(msg['content']) > 80 else msg['content'],
                'tokens': tokens
            })

        self.debug_logs.append(log_entry)

    def print_debug_info(self):
        """打印调试信息"""
        print("\n" + "=" * 80)
        print("压缩系统调试信息")
        print("=" * 80)

        for i, log in enumerate(self.debug_logs, 1):
            if 'card_id' in log:
                self._print_card_log(i, log)
            else:
                self._print_context_log(i, log)

    def _print_card_log(self, index: int, log: Dict):
        """打印卡片压缩日志"""
        print(f"\n[卡片 {index}] {log['topic']}")
        print(f"  ID: {log['card_id']}")
        print(f"  消息数: {log['message_count']}")
        print(f"  版本对比:")

        for version_name, version_info in log['versions'].items():
            print(f"    - {version_name}: {version_info['tokens']}T")
            print(f"      {version_info['content']}")

    def _print_context_log(self, index: int, log: Dict):
        """打印上下文生成日志"""
        print(f"\n[上下文生成 {index}] {log['timestamp']}")
        print(f"  当前消息: {log['current_message_tokens']}T")
        print(f"  上下文消息数: {log['context_messages']}")
        print(f"  上下文明细:")

        total_context_tokens = 0
        for item in log['context_breakdown']:
            print(f"    [{item['index']}] {item['role']}: {item['tokens']}T")
            print(f"        {item['content']}")
            total_context_tokens += item['tokens']

        total = total_context_tokens + log['current_message_tokens']
        print(f"\n  总计: {total_context_tokens}T (上下文) + {log['current_message_tokens']}T (当前) = {total}T")

    def export_debug_report(self) -> str:
        """导出调试报告"""
        report = []
        report.append("=" * 80)
        report.append("压缩系统调试报告")
        report.append("=" * 80)

        for i, log in enumerate(self.debug_logs, 1):
            if 'card_id' in log:
                report.append(f"\n[卡片 {i}] {log['topic']}")
                report.append(f"  ID: {log['card_id']}")
                report.append(f"  消息数: {log['message_count']}")
                for version_name, version_info in log['versions'].items():
                    report.append(f"  {version_name}: {version_info['tokens']}T")
            else:
                report.append(f"\n[上下文 {i}]")
                report.append(f"  当前消息: {log['current_message_tokens']}T")
                total = sum(item['tokens'] for item in log['context_breakdown'])
                report.append(f"  上下文总计: {total}T")

        return '\n'.join(report)


# 全局调试器实例
_debugger = CompressionDebugger()


def get_debugger() -> CompressionDebugger:
    """获取全局调试器"""
    return _debugger


def enable_debug_mode():
    """启用调试模式"""
    global _debugger
    _debugger = CompressionDebugger()
    return _debugger
