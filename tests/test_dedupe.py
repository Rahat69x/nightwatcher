"""
NightWatcher Tests — Deduplication & Fingerprinting
"""
from app.engine.dedupe import make_fingerprint


def test_fingerprint_stability():
    fp1 = make_fingerprint("brute_force", {"source_ip": "198.51.100.42", "failed_attempts": 5})
    fp2 = make_fingerprint("brute_force", {"source_ip": "198.51.100.42", "failed_attempts": 10})
    # Same attack type and IP must yield the exact same fingerprint to group duplicates
    assert fp1 == fp2


def test_fingerprint_differentiation():
    fp1 = make_fingerprint("brute_force", {"source_ip": "198.51.100.42"})
    fp2 = make_fingerprint("brute_force", {"source_ip": "203.0.113.88"})
    assert fp1 != fp2


def test_url_fingerprint():
    fp1 = make_fingerprint("site_down", {"url": "https://example.com", "consecutive_failures": 2})
    fp2 = make_fingerprint("site_down", {"url": "https://example.com", "consecutive_failures": 4})
    assert fp1 == fp2
