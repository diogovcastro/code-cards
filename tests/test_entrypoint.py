from __future__ import annotations

import subprocess
import sys


def test_help_funciona() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "code_cards", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "code-cards" in result.stdout
