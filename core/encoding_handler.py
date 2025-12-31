"""
Encoding handler - auto-detect and handle encoding issues
"""

import sys
import io


class EncodingHandler:
    """Handle encoding issues automatically"""

    @staticmethod
    def setup_console_encoding():
        """Setup console to handle UTF-8 properly"""
        if sys.platform == 'win32':
            # Windows: set UTF-8 encoding for stdout/stderr
            if sys.stdout.encoding != 'utf-8':
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            if sys.stderr.encoding != 'utf-8':
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    @staticmethod
    def safe_print(text: str, *args, **kwargs):
        """Print text safely with encoding handling"""
        try:
            print(text, *args, **kwargs)
        except UnicodeEncodeError:
            # Fallback: encode to ASCII with errors ignored
            print(text.encode('utf-8', errors='replace').decode('utf-8'), *args, **kwargs)

    @staticmethod
    def safe_str(obj) -> str:
        """Convert object to string safely"""
        try:
            return str(obj)
        except UnicodeEncodeError:
            return str(obj).encode('utf-8', errors='replace').decode('utf-8')
