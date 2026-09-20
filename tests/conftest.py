"""Pytest bootstrap.

Sets a dummy OPENROUTER_API_KEY *before* any backend import, since
backend.config reads the key from the environment at import time.
Tests mock the query layer, so no real key or network is ever needed.
"""

import os
import sys

os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test-dummy-key")

# Ensure the repo root is importable so `import backend...` works
# regardless of the cwd pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
