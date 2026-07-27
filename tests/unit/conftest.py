# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]  # ansible-claude/

_namespace_root = Path(tempfile.mkdtemp(prefix="ansible_claude_test_"))
_ns_path = _namespace_root / "ansible_collections" / "aknochow" / "claude"
_ns_path.parent.mkdir(parents=True, exist_ok=True)

if not _ns_path.exists():
    _ns_path.symlink_to(_project_root)

sys.path.insert(0, str(_namespace_root))
