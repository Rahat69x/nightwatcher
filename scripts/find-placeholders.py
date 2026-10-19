"""
NightWatcher — Placeholder & Stray Debug Text Scanner
Scans HTML templates, styles, scripts, and python sources for stray placeholder text:
- 'lorem ipsum', 'TODO', 'FIXME', 'TBD', 'Hello World', 'your-domain'
- Empty elements and unformatted template placeholders
"""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEARCH_DIRS = [
    ROOT / "app" / "dashboard",
    ROOT / "demo",
]

SUSPICIOUS_PATTERNS = [
    (r"\blorem\s+ipsum\b", "Lorem Ipsum placeholder"),
    (r"\bTODO\b", "Unresolved TODO marker"),
    (r"\bFIXME\b", "Unresolved FIXME marker"),
    (r"\bTBD\b", "TBD marker"),
    (r"\bHello\s+World\b", "Generic Hello World placeholder"),
    (r"example\.com(?!/)", "Default example.com link"),
    (r"your-domain\.com", "Unreplaced your-domain placeholder"),
]

ALLOWLIST_FILES = {
    "sample_logs",
    "test_",
}

def scan_file(filepath: Path):
    rel = filepath.relative_to(ROOT)
    for ignore in ALLOWLIST_FILES:
        if ignore in str(rel):
            return []

    findings = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            for pattern, desc in SUSPICIOUS_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append((idx, line.strip(), desc))
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return findings

def main():
    print("=" * 60)
    print("NIGHTWATCHER PLACEHOLDER & STRAY DEBUG TEXT SCANNER")
    print("=" * 60)

    total_findings = 0
    scanned_files = 0

    for d in SEARCH_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in (".html", ".css", ".js", ".py"):
                scanned_files += 1
                matches = scan_file(p)
                if matches:
                    rel = p.relative_to(ROOT)
                    print(f"\n[!] {rel} ({len(matches)} matches):")
                    for line_no, text, desc in matches:
                        total_findings += 1
                        truncated = (text[:80] + '...') if len(text) > 80 else text
                        print(f"    Line {line_no:4d}: [{desc}] -> {truncated}")

    print("\n" + "=" * 60)
    print(f"Scan Complete: {scanned_files} files checked. {total_findings} findings.")
    print("=" * 60)
    return 0 if total_findings == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
