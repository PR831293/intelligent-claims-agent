import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get("RUN_MCP_SMOKE") != "1", reason="Set RUN_MCP_SMOKE=1 to run MCP integration smoke test")
def test_mcp_integration_smoke():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "mcp_integration_smoke.py"
    python = root / ".venv" / "bin" / "python"

    result = subprocess.run(
        [str(python), str(script)],
        cwd=str(root),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        raise AssertionError(
            "MCP integration smoke test failed\n"
            f"stdout:\n{result.stdout}\n\n"
            f"stderr:\n{result.stderr}"
        )
