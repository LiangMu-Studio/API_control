"""AI CLI Manager - Entry point for pip installation"""
import sys
from pathlib import Path

# Add package root to path
pkg_root = Path(__file__).parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

def main():
    """Main entry point"""
    from main import main as app_main
    app_main()

if __name__ == "__main__":
    main()
