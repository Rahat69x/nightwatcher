"""
NightWatcher Tests — Phase E: Images & Mobile Performance
Verifies:
1. Item 10: Asset budgets and image audit script (0 violations, < 150 KB per asset)
2. Item 20: Mobile performance, min 44px touch targets, and performance docs
"""
import pytest
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_image_audit_budget_clean():
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "image_audit.py")],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Budget Violations (> 150.0 KB): 0" in res.stdout


def test_touch_targets_in_css():
    css_content = (ROOT / "app" / "dashboard" / "static" / "style.css").read_text(encoding="utf-8")
    assert "min-height: 44px" in css_content


def test_performance_report_exists():
    perf_path = ROOT / "docs" / "PERFORMANCE.md"
    assert perf_path.exists()
    content = perf_path.read_text(encoding="utf-8")
    assert "54.97 KB" in content
    assert "Touch Target" in content
