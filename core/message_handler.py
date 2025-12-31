"""消息处理器 - 检测和执行命令"""

from typing import Dict, Any, Tuple
from core.command_executor import CommandExecutor
from core.system_interface import SystemInterface


class MessageHandler:
    """处理用户消息，检测命令并执行"""

    def __init__(self):
        self.command_executor = CommandExecutor()
        self.system_interface = SystemInterface()
        self.command_prefix = '/'  # 命令前缀

    def process_message(self, message: str) -> Tuple[bool, Dict[str, Any]]:
        """
        处理消息
        返回: (is_command, result)
        """
        message = message.strip()

        # 检测命令
        if message.startswith(self.command_prefix):
            return True, self._execute_command(message[1:])

        # 检测系统命令
        if message.startswith('$'):
            return True, self._execute_system_command(message[1:])

        # 检测文件操作
        if message.startswith('@'):
            return True, self._handle_file_operation(message[1:])

        return False, {}

    def _execute_command(self, cmd_str: str) -> Dict[str, Any]:
        """执行压缩系统命令"""
        result = self.command_executor.execute(cmd_str)
        return {
            'type': 'command',
            'command': cmd_str,
            'result': result
        }

    def _execute_system_command(self, cmd_str: str) -> Dict[str, Any]:
        """执行系统命令"""
        result = self.system_interface.execute_command(cmd_str)
        return {
            'type': 'system_command',
            'command': cmd_str,
            'result': result
        }

    def _handle_file_operation(self, op_str: str) -> Dict[str, Any]:
        """处理文件操作"""
        parts = op_str.split(maxsplit=1)
        if not parts:
            return {'error': '文件操作格式错误'}

        op = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        if op == 'read':
            return {
                'type': 'file_read',
                'result': self.system_interface.read_file(args)
            }
        elif op == 'write':
            # 格式: @write <file> <content>
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                return {'error': '写入格式错误: @write <file> <content>'}
            return {
                'type': 'file_write',
                'result': self.system_interface.write_file(parts[0], parts[1])
            }
        elif op == 'list':
            return {
                'type': 'file_list',
                'result': self.system_interface.list_files(args)
            }
        else:
            return {'error': f'未知文件操作: {op}'}

    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化结果为可读的文本"""
        if 'error' in result:
            return f"错误: {result['error']}"

        result_type = result.get('type', 'unknown')

        if result_type == 'command':
            cmd_result = result.get('result', {})
            if 'output' in cmd_result:
                return cmd_result['output']
            elif 'stats' in cmd_result:
                stats = cmd_result['stats']
                return f"""
压缩统计
{'='*50}
原始 Token:    {stats['original_tokens']}
压缩后 Token:  {stats['compressed_tokens']}
节省 Token:    {stats['saved_tokens']}
压缩率:        {stats['compression_ratio']}
"""
            else:
                return str(cmd_result)

        elif result_type == 'system_command':
            cmd_result = result.get('result', {})
            stdout = cmd_result.get('stdout', '')
            stderr = cmd_result.get('stderr', '')
            if stdout:
                return stdout
            elif stderr:
                return f"错误输出:\n{stderr}"
            else:
                return "命令执行完成"

        elif result_type == 'file_read':
            file_result = result.get('result', {})
            if 'content' in file_result:
                return file_result['content']
            else:
                return str(file_result)

        elif result_type == 'file_write':
            file_result = result.get('result', {})
            return f"文件已写入: {file_result.get('file', 'unknown')}"

        elif result_type == 'file_list':
            file_result = result.get('result', {})
            files = file_result.get('files', [])
            return f"找到 {len(files)} 个文件:\n" + '\n'.join(files)

        return str(result)

    def get_help(self) -> str:
        """获取帮助信息"""
        return """
命令系统帮助

压缩系统命令 (前缀: /)
  /analyze <file>           - 分析消息文件
  /stats <file>             - 显示压缩统计
  /context <file> [msg]     - 获取上下文
  /cards <file>             - 显示话题卡片
  /export <file> [output]   - 导出数据
  /weight                   - 查看权重
  /reset                    - 重置权重
  /help                     - 显示帮助

系统命令 (前缀: $)
  $<command>                - 执行系统命令
  示例: $dir, $python script.py, $git status

文件操作 (前缀: @)
  @read <file>              - 读取文件
  @write <file> <content>   - 写入文件
  @list <directory>         - 列出目录
  示例: @read data.json, @list ./data

使用示例:
  /stats example_messages.json
  $python test_dynamic_weight.py
  @read data/card_weights.json
"""
