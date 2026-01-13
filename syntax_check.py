import ast
import sys
try:
    with open('d:/Dropbox/AI_tools/API_control/app_flet.py', encoding='utf-8') as f:
        ast.parse(f.read())
    print('Syntax OK')
    sys.exit(0)
except SyntaxError as e:
    print(f'Syntax Error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
