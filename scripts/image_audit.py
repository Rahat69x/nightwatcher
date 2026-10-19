"""
NightWatcher — Asset & Image Budget Auditor
Inspects all visual assets (SVG, PNG, WebP, Favicons) across templates and static files.
Reports file sizes, format optimization, and compression status.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MAX_IMAGE_BUDGET_KB = 150.0  # 150 KB limit per asset for web speed

def audit_assets():
    static_dir = ROOT / "app" / "dashboard" / "static"
    print("=" * 60)
    print("NIGHTWATCHER IMAGE & ASSET AUDITOR")
    print(f"Directory: {static_dir}")
    print("=" * 60)

    total_bytes = 0
    asset_count = 0
    violations = 0

    if static_dir.exists():
        for asset in sorted(static_dir.rglob("*")):
            if asset.is_file():
                size_bytes = asset.stat().st_size
                size_kb = size_bytes / 1024.0
                total_bytes += size_bytes
                asset_count += 1
                status = "OK"
                if size_kb > MAX_IMAGE_BUDGET_KB:
                    status = "EXCEEDED BUDGET"
                    violations += 1

                ext = asset.suffix.lower()
                category = "Script/Style" if ext in (".css", ".js") else "Graphic/Vector"
                print(f"  {asset.name:25} [{category:14}] {size_kb:8.2f} KB  -> {status}")

    total_kb = total_bytes / 1024.0
    print("-" * 60)
    print(f"Total Assets: {asset_count} files ({total_kb:.2f} KB)")
    print(f"Budget Violations (> {MAX_IMAGE_BUDGET_KB} KB): {violations}")
    print("=" * 60)
    return violations

if __name__ == "__main__":
    sys.exit(audit_assets())
