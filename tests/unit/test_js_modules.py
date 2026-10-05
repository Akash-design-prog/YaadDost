"""Runs the JavaScript unit tests (tests/js) with Node's built-in test runner, so a single `pytest` covers everything.

Skips if Node 22 or newer is not installed (Node 22+ is needed to import the plain .js ES modules without a build step).
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def node_major():
    node = shutil.which("node")
    if not node:
        return 0
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    m = re.match(r"v(\d+)", out.strip())
    return int(m.group(1)) if m else 0


@pytest.mark.skipif(node_major() < 22, reason="Node 22+ is not installed")
def test_javascript_unit_tests_pass():
    # The TAP reporter is plain ASCII, so the result does not depend on the console's text encoding.
    result = subprocess.run(
        [shutil.which("node"), "--test", "--test-reporter=tap", "tests/js/*.test.mjs"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1000:]
    assert re.search(r"^# fail 0$", result.stdout, re.M), result.stdout[-1500:]
    assert int(re.search(r"^# pass (\d+)$", result.stdout, re.M).group(1)) >= 20
