#!/usr/bin/env python3
"""Resolve the board checkout through the installed skill symlink, from any CWD."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[4]
if sys.argv[1:] == ['root']:
    print(root)
    raise SystemExit(0)
node = shutil.which('node')
if not node:
    raise SystemExit('Install Node.js 22+ and run npm ci in %s' % root)
raise SystemExit(subprocess.call([node, str(root / 'scripts' / 'board.mjs')] + sys.argv[1:]))
