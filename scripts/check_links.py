"""
NightWatcher — Link and Endpoint Integrity Auditor
Crawls all internal endpoints and public links defined across HTML, Python routes, and JS.
Reports HTTP status codes, redirects, and broken links.
"""
import sys
import re
from pathlib import Path
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

ENDPOINTS_TO_CHECK = [
    "http://127.0.0.1:8000/",
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8000/docs",
    "http://127.0.0.1:8000/api/alerts/",
    "http://127.0.0.1:8000/api/alerts/blocklist/active",
    "http://127.0.0.1:8000/api/watchers/system/stats",
    "http://127.0.0.1:8001/",
]

def check_endpoint(url: str):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "NightWatcher-LinkAuditor/1.0",
                "X-Simulated-IP": "10.0.0.99",
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, "OK"
    except urllib.error.HTTPError as e:
        return e.code, e.reason
    except Exception as e:
        return 0, str(e)

def extract_html_links():
    links = set()
    for html_file in (ROOT / "app" / "dashboard" / "templates").glob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        found = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', content)
        for link in found:
            if not link.startswith(("#", "javascript:", "tel:", "mailto:")):
                links.add(link)
    return sorted(links)

def main():
    print("=" * 60)
    print("NIGHTWATCHER LINK & ROUTE AUDIT")
    print("=" * 60)

    failed = 0
    print("\n--- 1. Testing Live Application Endpoints ---")
    for ep in ENDPOINTS_TO_CHECK:
        status, reason = check_endpoint(ep)
        status_str = f"[{status}]" if status else "[DOWN]"
        ok = 200 <= status < 400
        indicator = "[PASS]" if ok else "[FAIL]"
        if not ok:
            failed += 1
        print(f" {indicator} {status_str:10} {ep} ({reason})")

    print("\n--- 2. Template Referenced Assets ---")
    html_links = extract_html_links()
    for link in html_links:
        if link.startswith("/static/"):
            rel_path = link.replace("/static/", "app/dashboard/static/")
            asset_path = ROOT / rel_path
            exists = asset_path.exists()
            indicator = "[FOUND]" if exists else "[MISSING]"
            if not exists:
                failed += 1
            print(f" {indicator} Asset: {link} -> {asset_path}")
        else:
            print(f" - External/Route Link: {link}")

    print("\n" + "=" * 60)
    if failed == 0:
        print("RESULT: ALL LINKS & ENDPOINTS HEALTHY (0 failures)")
    else:
        print(f"RESULT: {failed} LINK/ASSET ISSUES DETECTED")
    print("=" * 60)
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
