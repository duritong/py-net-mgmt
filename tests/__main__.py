import sys
import unittest
from pathlib import Path

# Ensure src/ is on sys.path if running uninstalled
src_dir = str(Path(__file__).resolve().parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
