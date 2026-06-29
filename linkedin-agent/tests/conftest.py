"""Shared pytest setup: put the linkedin-agent package root on sys.path so
tests can `import core`, `import agents`, etc. regardless of where pytest runs.
"""

import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))
