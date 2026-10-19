# NightWatcher Complete Navigation Map (NAV_MAP)

This document maps all reachable screens, entry points, modals, and destinations within the NightWatcher autonomous security application.

---

## 1. Top-Level Entry Points

```
[Browser / User]
       │
       ├──> GET / (or /dashboard) ─── NightWatcher SOC Live Operations Center
       ├──> GET /docs             ─── Interactive OpenAPI / Swagger Documentation
       ├──> GET /health           ─── Autonomous Engine Health Probe
       ├──> GET /404              ─── Custom Branded Security Target Not Found Screen
       └──> GET :8001/            ─── Apex Vault Customer Monitored Portal
```

---

## 2. Dashboard Internal Tab Structure (`GET /`)

All tabs are accessible via desktop tab bar (`.tab-btn`) AND mobile sliding drawer (`.drawer-link`):

| Tab ID | Tab Display Name | Purpose | Primary Actions |
| :--- | :--- | :--- | :--- |
| **`#tab-alerts`** | 🚨 Alert Incidents | Real-time incident stream & triage | Search filter, View Details modal, Quick Acknowledge, Copy IP. |
| **`#tab-tools`** | 🔍 Phishing & Password Tools | Threat inspection utilities | Analyze Phishing Risk, Have I Been Pwned k-anonymity check, Load Examples. |
| **`#tab-sites`** | 🌐 Website Watcher | Uptime & SSL certificate monitor | + Watch Site form, Scan Now on-demand trigger, latency bars. |
| **`#tab-blocklist`** | 🚫 Active Blocklist | Autonomous firewall containment | Manual IP block form, Unblock IP per active rule, duration countdowns. |
| **`#tab-channels`** | 📱 Escalation Channels | Notification tier status | Review Email, Telegram, SMS, Voice Call setup and trigger thresholds. |

---

## 3. Modal Dialogs & Sub-Views

| Modal / Dialog | Trigger | Purpose | Dismissal Actions |
| :--- | :--- | :--- | :--- |
| **`#alert-modal`** | Click alert card in `#tab-alerts` | Full plain-language threat breakdown, score, grouped count, source IP | `&times;` close button, backdrop click, `Escape` key, Acknowledge, Block IP. |
| **`#mobile-nav-drawer`** | Click `#btn-mobile-menu` | Mobile slide-out navigation menu for screen widths < 768px | `&times;` close button, overlay click, tab selection, `Escape` key. |

---

## 4. External Outbound & Contact Links

- **API Docs:** `href="/docs"` (`target="_blank"`, `rel="noopener"`)
- **Engine Health:** `href="/health"` (`target="_blank"`, `rel="noopener"`)
- **Customer Portal:** `href="http://localhost:8001/"` (`target="_blank"`, `rel="noopener"`)
- **Emergency Hotline:** `href="tel:+18005550199"`
- **Incident Response Email:** `href="mailto:soc@nightwatcher.io?subject=NightWatcher%20Security%20Incident%20Report"`
- **Return to Top / Home Logo:** `href="/"` with smooth scroll-to-top handler.

---

## 5. Reachability Audit Result
- **Dead ends:** 0
- **Stale deep links:** 0
- **Unreachable fragments/views:** 0
- **All 5 tabs:** Reachable from both desktop bar and mobile drawer.
