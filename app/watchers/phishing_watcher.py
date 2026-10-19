"""
NightWatcher — Phishing Watcher
Analyzes a URL or message text for phishing signals.
Checks: lookalike domains, punycode, raw IP, too many subdomains,
        suspicious TLDs, urgency words, young domain age, Safe Browsing API.
"""
from __future__ import annotations
import asyncio
import ipaddress
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

import httpx
import tldextract

log = logging.getLogger(__name__)

# Known brands to check for lookalike (edit distance)
KNOWN_BRANDS = [
    "paypal", "google", "facebook", "apple", "amazon", "microsoft",
    "netflix", "twitter", "instagram", "linkedin", "whatsapp", "telegram",
    "binance", "coinbase", "chase", "wellsfargo", "bankofamerica",
]

SUSPICIOUS_TLDS = {
    ".xyz", ".top", ".click", ".tk", ".ml", ".ga", ".cf", ".gq",
    ".pw", ".cc", ".icu", ".live", ".online", ".site", ".website",
    ".win", ".loan", ".download", ".stream", ".bid", ".trade",
}

URGENCY_WORDS = [
    "urgent", "immediately", "verify now", "account suspended",
    "click here", "confirm your", "update required", "winner",
    "you have been selected", "limited time", "act now", "expires",
    "unusual activity", "security alert", "suspended", "locked",
]

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "goo.gl",
    "short.link", "rebrand.ly", "cutt.ly", "is.gd", "buff.ly",
}


def _levenshtein(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    try:
        import Levenshtein as lev
        return lev.distance(a, b)
    except ImportError:
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev, dp[0] = dp[0], i
            for j in range(1, n + 1):
                prev, dp[j] = dp[j], prev if a[i-1] == b[j-1] else 1 + min(prev, dp[j], dp[j-1])
        return dp[n]


async def expand_url(url: str) -> str:
    """Follow redirects to get the final URL."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            r = await client.head(url)
            return str(r.url)
    except Exception:
        return url


async def check_safe_browsing(url: str, api_key: str) -> bool:
    """Returns True if URL is flagged by Google Safe Browsing."""
    if not api_key:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}",
                json={
                    "client": {"clientId": "nightwatcher", "clientVersion": "1.0"},
                    "threatInfo": {
                        "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
                        "platformTypes": ["ANY_PLATFORM"],
                        "threatEntryTypes": ["URL"],
                        "threatEntries": [{"url": url}],
                    },
                },
            )
            data = resp.json()
            return bool(data.get("matches"))
    except Exception:
        return False


async def check_domain_age(domain: str) -> Optional[int]:
    """Return domain age in days, or None if unavailable."""
    try:
        import whois
        loop = asyncio.get_event_loop()
        w = await loop.run_in_executor(None, whois.whois, domain)
        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]
        if creation:
            if creation.tzinfo is None:
                creation = creation.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - creation).days
    except Exception:
        pass
    return None


async def analyze_url(url: str, safe_browsing_key: str = "") -> Dict[str, Any]:
    """Full phishing analysis. Returns score 0-100 and reasons list."""
    reasons: List[str] = []
    score = 0

    # Expand shortened URLs
    original_url = url
    parsed = urlparse(url)
    if parsed.netloc in URL_SHORTENERS:
        url = await expand_url(url)
        reasons.append(f"Shortened URL expanded: {url}")
        score += 10

    parsed = urlparse(url)
    hostname = parsed.netloc.lower()
    ext = tldextract.extract(url)
    domain = f"{ext.domain}.{ext.suffix}"
    sld = ext.domain.lower()

    # 1. Raw IP address
    try:
        ipaddress.ip_address(hostname.split(":")[0])
        reasons.append("URL uses raw IP address instead of domain name")
        score += 30
    except ValueError:
        pass

    # 2. Punycode (internationalized domain)
    if "xn--" in hostname:
        reasons.append("Domain uses punycode (possible IDN homograph attack)")
        score += 25

    # 3. Too many subdomains
    subdomain_count = len(ext.subdomain.split(".")) if ext.subdomain else 0
    if subdomain_count >= 3:
        reasons.append(f"Excessive subdomains ({subdomain_count}) — often used to spoof legitimate sites")
        score += 15

    # 4. Suspicious TLD
    tld = f".{ext.suffix}"
    if tld in SUSPICIOUS_TLDS:
        reasons.append(f"Suspicious TLD: {tld}")
        score += 15

    # 5. Lookalike brand domain (Levenshtein distance & leetspeak)
    tokens = [sld] + [p for p in re.split(r'[-_]', sld) if p]
    brand_matched = False
    for token in tokens:
        if brand_matched:
            break
        # Leetspeak normalized version
        norm_token = token.replace('1', 'l').replace('0', 'o').replace('3', 'e').replace('5', 's').replace('@', 'a')
        for brand in KNOWN_BRANDS:
            dist = min(_levenshtein(token, brand), _levenshtein(norm_token, brand))
            if 0 < dist <= 2:
                reasons.append(f"Domain segment '{token}' is very similar to '{brand}' (edit distance {dist})")
                score += 35
                brand_matched = True
                break
            elif brand in norm_token and norm_token != brand:
                reasons.append(f"Domain segment '{token}' spoofs brand name '{brand}'")
                score += 30
                brand_matched = True
                break

    # 6. Urgency words in full URL
    url_lower = url.lower()
    for word in URGENCY_WORDS:
        if word in url_lower:
            reasons.append(f"Urgency keyword in URL: '{word}'")
            score += 10
            break

    # 7. Domain age
    age_days = await check_domain_age(domain)
    if age_days is not None and age_days < 30:
        reasons.append(f"Domain is only {age_days} days old (registered very recently)")
        score += 20

    # 8. Google Safe Browsing
    if await check_safe_browsing(url, safe_browsing_key):
        reasons.append("⚠️ Flagged by Google Safe Browsing")
        score += 40

    # Cap at 100
    score = min(score, 100)

    return {
        "url": url,
        "original_url": original_url,
        "phish_score": score,
        "reasons": reasons,
        "verdict": (
            "HIGH RISK — Do not click" if score >= 70
            else "MEDIUM RISK — Exercise caution" if score >= 40
            else "LOW RISK — Appears safe"
        ),
    }


async def analyze_text_for_urls(text: str) -> List[str]:
    """Extract all URLs from a message."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(pattern, text)


async def run_phishing_check(db, text_or_url: str, safe_browsing_key: str = "") -> List[Dict]:
    """Main entry: check all URLs in a text or a single URL. Returns list of results."""
    from app.engine.ingest import ingest_event

    if text_or_url.startswith("http"):
        urls = [text_or_url]
    else:
        urls = await analyze_text_for_urls(text_or_url)

    results = []
    for url in urls:
        result = await analyze_url(url, safe_browsing_key)
        results.append(result)

        # Emit event if risky
        if result["phish_score"] >= 40:
            await ingest_event(db, "phishing_url", f"phishing_watcher:{url}", result)

    return results
