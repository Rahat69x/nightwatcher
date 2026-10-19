# Master Polish Audit — NightWatcher Web Application

**Date:** 2026-10-20  
**Project:** NightWatcher Autonomous Watchdog & SOC Dashboard (`c:\hackthon\nightwatcher`)  
**Scope:** SOC Web Dashboard (`/`), Customer Portal (`:8001`), API Documentation (`/docs`), Health Check (`/health`).  
**Baseline Test Suite:** 22/22 Passing (`pytest`).

---

## 1. Twenty-Point Polish Checklist Status

| # | Polish Item | Status | Evidence (Files & Screens) | Effort | Recommended Action |
| :-: | :--- | :---: | :--- | :---: | :--- |
| **1** | **Remove horizontal scrolling** | **Needs Fix** | `app/dashboard/templates/index.html`<br>`app/dashboard/static/style.css` | **S** | Add `overflow-x: hidden` to root containers; ensure `.tab-nav` and `.demo-actions` wrap smoothly or support touch scrolling on screens < 360px without expanding parent viewport. |
| **2** | **Find broken links** | **Needs Fix** | `scripts/check_links.py`<br>`index.html` | **S** | Core endpoints (200 OK), but dashboard header lacks outbound navigation links to `/docs`, `/health`, and demo portal (`:8001`). Add verified direct links. |
| **3** | **Add a mobile menu** | **Needs Fix** | `index.html`<br>`style.css`<br>`app.js` | **M** | Desktop navigation uses an inline row of 5 tabs. On mobile (< 768px), implement an accessible hamburger navigation drawer toggling tabs and links. |
| **4** | **Add a favicon** | **Needs Fix** | `index.html`<br>`demo/fake_login_app.py`<br>`app/main.py` | **S** | No `<link rel="icon">` defined; browsers requesting `/favicon.ico` receive 404. Add vector SVG cyber shield favicon and FastAPI favicon route. |
| **5** | **Fix page titles** | **Needs Fix** | `index.html`<br>`demo/fake_login_app.py` | **S** | Update page titles dynamically when switching tabs (e.g. `NightWatcher — Phishing Inspector`) and provide clear branded titles for portal and 404. |
| **6** | **Add meta descriptions** | **Needs Fix** | `index.html`<br>`demo/fake_login_app.py` | **S** | Missing `<meta name="description">`, OpenGraph (`og:title`, `og:description`, `og:image`), and Twitter preview tags. |
| **7** | **Fix footer links** | **Needs Fix** | `index.html`<br>`style.css` | **S** | No footer exists on the dashboard. Add a modern, responsive footer with working links to API Docs, Health Status, SOC Hotline, and Support. |
| **8** | **Add a custom 404 page** | **Needs Fix** | `app/main.py`<br>`app/dashboard/templates/404.html` | **M** | Unknown web routes return raw JSON `{"detail": "Not Found"}`. Implement custom Starlette 404 handler rendering branded HTML with "Go Home" and "Search" buttons. |
| **9** | **Fix the copyright year** | **Needs Fix** | `index.html` | **S** | Add dynamic JavaScript year in footer (`© <span id="year"></span> NightWatcher SOC`) to eliminate hardcoded, stale years. |
| **10** | **Compress images** | **OK** | `scripts/image_audit.py` | **S** | All current icons are lightweight inline SVGs. Total static size is 42.97 KB (well within 150 KB budget). |
| **11** | **Fix broken buttons** | **Needs Fix** | `app.js`<br>`index.html` | **S** | Attack simulator buttons and watcher controls lack debounce protection and visual loading spinners during fetch requests. |
| **12** | **Add success messages** | **Needs Fix** | `app.js`<br>`style.css` | **S** | User actions (copying IP, running attack simulation, unblocking IP, adding site) lack toast confirmation banners. |
| **13** | **Add error messages** | **Needs Fix** | `app.js`<br>`style.css` | **M** | Network disconnects or API errors fail silently to console. Add central toast/banner error mapper with user-friendly retry hints. |
| **14** | **Remove placeholder text** | **Needs Fix** | `scripts/find-placeholders.py`<br>`index.html` | **S** | Found default `placeholder="https://example.com"`. Replace with realistic production examples and ensure no TODO/sample text. |
| **15** | **Remove unused navigation** | **OK** | `index.html`<br>`app.js` | **S** | All 5 tabs and modals correspond to fully implemented features. All tabs verified active. |
| **16** | **Fix mobile overflow** | **Needs Fix** | `index.html`<br>`style.css` | **S** | Detail modal (`#alert-modal`) and IP blocklist table can clip on small landscape mobile viewports. Add `max-height: 85vh` and overflow scrolling. |
| **17** | **Make the logo clickable** | **Needs Fix** | `index.html` | **S** | Top header logo is currently wrapped in a `<div>`. Convert to `<a href="/" aria-label="NightWatcher Home">` with smooth scroll-to-top. |
| **18** | **Make phone number clickable** | **Needs Fix** | `index.html` | **S** | Add emergency SOC on-call hotline (`tel:+18005550199`) with click-to-dial and click-to-copy interactions. |
| **19** | **Make email clickable** | **Needs Fix** | `index.html` | **S** | Add incident response email (`mailto:soc@nightwatcher.io`) with pre-filled subject line and click-to-copy. |
| **20** | **Make every page mobile optimized** | **Needs Fix** | `style.css`<br>`index.html` | **M** | Enforce 44px touch targets on buttons/pills, optimize mobile padding, ensure dark-theme contrast, and verify on 320px-414px viewports. |

---

## 2. Inventories

### A. Screen & Dialog Inventory
1. **SOC Live Operations Dashboard (`http://127.0.0.1:8000/`)**
   - Live metrics summary bar (Active Alerts, Critical & Escalating, Auto-Blocked Attackers, Monitored Assets)
   - Attack Simulator Bar (Brute Force, Credential Stuffing, Breach Alarm, Website Outage, Phishing)
   - Tab 1: Live Alert Incidents Feed & Search Filter
   - Tab 2: Phishing & Scam URL Inspector + Pwned Password Checker (k-Anonymity)
   - Tab 3: Watched Websites & SSL Certificates Monitor
   - Tab 4: Autonomous IP Blocklist & Manual Block Form
   - Tab 5: Escalation Matrix & Notification Channels
2. **Alert Detail Modal (`#alert-modal`)**
   - Severity badge, Title, Timestamp, Fingerprint
   - Structured JSON/Detail metadata viewer
   - Action buttons: Acknowledge Alert, Resolve Alert, Block/Unblock Attacker IP
3. **Customer Demo Portal (`http://127.0.0.1:8001/`)**
   - Secure login form (Username, Password)
   - Client IP detector badge
   - Blocked screen notice (`403 Forbidden` with countdown)
4. **Interactive API Documentation (`http://127.0.0.1:8000/docs`)**
   - OpenAPI / Swagger UI for all REST endpoints
5. **System Health Check (`http://127.0.0.1:8000/health`)**
   - JSON health probe (Status, App, Version, Tagline)
6. **Custom 404 Not Found Screen (`404.html`) — *To be added***
   - Branded cyber shield illustration, diagnostic details, "Go Home" and "Search Incidents" buttons.

### B. Clickable View Inventory
- Header:
  - Brand Logo & Title (`.brand`) — *To be converted to link*
  - Sync / Refresh Button (`#btn-refresh`)
- Attack Simulator:
  - 1. Brute Force (`runAttackSim('brute_force')`)
  - 2. Credential Stuffing (`runAttackSim('credential_stuffing')`)
  - 3. Breach Login Alarm (`runAttackSim('login_success_after_brute')`)
  - 4. Website Outage (`runAttackSim('site_down')`)
  - 5. Phishing Message (`runAttackSim('phishing')`)
- Navigation Tabs:
  - Alerts Tab (`switchTab('tab-alerts')`)
  - Tools Tab (`switchTab('tab-tools')`)
  - Websites Tab (`switchTab('tab-sites')`)
  - Blocklist Tab (`switchTab('tab-blocklist')`)
  - Channels Tab (`switchTab('tab-channels')`)
- Feed Filters:
  - All (`filterAlerts('all')`)
  - Needs Action (`filterAlerts('active')`)
  - Critical (`filterAlerts('critical')`)
  - Acknowledged (`filterAlerts('acknowledged')`)
  - Resolved (`filterAlerts('resolved')`)
- Incident Card Actions:
  - Card expansion / Detail Modal trigger (`viewAlertDetail(id)`)
  - Copy IP Button (`copyToClipboard(ip)`)
  - Quick Acknowledge (`ackAlert(id)`)
- Phishing & Password Tools:
  - Analyze Phishing Risk (`inspectPhishing()`)
  - Phishing Example 1 & 2 (`setPhishExample(1|2)`)
  - Check Password Exposure (`inspectPassword()`)
  - Test 'password123' & 'SolarWinds123!'
- Website Watcher:
  - + Watch Site Button (`addWatchedSite()`)
  - Scan Now Buttons per site (`scanSiteNow(id)`)
- Blocklist:
  - Block IP Button (`manualBlockIP()`)
  - Unblock IP Button per row (`unblockIP(ip)`)
- Modal Actions:
  - Close Modal (`closeModal()`)
  - Acknowledge Button
  - Resolve Button

### C. Icon-Only View Inventory
- `#btn-refresh` contains a sync SVG icon with text "Sync".
- Modal close button (`.btn-close`) displays `&times;` (Needs `aria-label="Close dialog"`).
- Copy IP button displays copy SVG (Needs `aria-label="Copy IP to clipboard"`).

### D. URL & Intent Inventory
- `http://127.0.0.1:8000/` (Home Dashboard)
- `http://127.0.0.1:8000/health` (Health Probe)
- `http://127.0.0.1:8000/docs` (Swagger UI)
- `http://127.0.0.1:8001/` (Demo Login Portal)
- `https://fonts.googleapis.com` (Google Fonts preconnect)
- `https://fonts.gstatic.com` (Fonts CDN)
- `tel:+18005550199` (Emergency SOC Hotline — *To be added*)
- `mailto:soc@nightwatcher.io` (Security Incident Report — *To be added*)

### E. Image & Vector Asset Inventory
- `app/dashboard/static/app.js`: 22.27 KB
- `app/dashboard/static/style.css`: 20.70 KB
- All icons are inline scalable SVG vectors (zero raster image overhead).
- Favicon: Currently missing -> *Adding lightweight vector SVG favicon (`favicon.svg` < 2 KB)*.

### F. Placeholder & Stray Debug Text Inventory
- Scanned with `scripts/find-placeholders.py`.
- Finding: `app/dashboard/templates/index.html` line 207: `placeholder="https://example.com"`.
  - Fix: Replace with contextual label `placeholder="https://my-company-portal.com"`.
- Zero instances of `lorem ipsum`, `TODO`, `FIXME`, or `TBD` detected.

### G. Navigation Graph & Entry Points
```
[User Browser]
   │
   ├──> GET / (Dashboard)
   │     ├──> Tab: Alert Incidents (#tab-alerts) ──> Modal (#alert-modal)
   │     ├──> Tab: Phishing & Pwned Tools (#tab-tools)
   │     ├──> Tab: Website Watcher (#tab-sites)
   │     ├──> Tab: Active Blocklist (#tab-blocklist)
   │     └──> Tab: Escalation Channels (#tab-channels)
   │
   ├──> GET /health (Health Status API)
   ├──> GET /docs (API Documentation)
   ├──> GET /404 (Custom Branded 404 Screen)
   │
   └──> GET http://127.0.0.1:8001/ (Customer Portal)
         ├──> POST /login (Auth handler)
         └──> GET /login?error=... (Sanitized feedback)
```

---

## 3. Automated Re-Runnable Tooling Created
1. [`scripts/check_links.py`](file:///c:/hackthon/nightwatcher/scripts/check_links.py): Verifies all HTTP routes, redirects, and template assets.
2. [`scripts/find-placeholders.py`](file:///c:/hackthon/nightwatcher/scripts/find-placeholders.py): Scans for stray placeholders, debug strings, and TODOs.
3. [`scripts/image_audit.py`](file:///c:/hackthon/nightwatcher/scripts/image_audit.py): Audits static assets against bandwidth budgets.

---

## 4. Phase Execution Blueprint

- **Phase A — Layout & Navigation:** Items 1 (No Horizontal Scroll), 3 (Mobile Hamburger Menu), 16 (Mobile Overflow), 20 (Responsive Layout).
- **Phase B — Links, Intents & Contact:** Items 2 (Link Audit), 4 (Favicon), 7 (Footer), 17 (Clickable Logo), 18 (Clickable Phone), 19 (Clickable Email).
- **Phase C — States, Feedback & Buttons:** Items 8 (Custom 404 Page), 11 (Button Debounce/Spinners), 12 (Success Toasts), 13 (Error Toasts/Banners).
- **Phase D — Content & Identity:** Items 5 (Page Titles), 6 (Meta Descriptions), 9 (Copyright Year), 14 (Remove Placeholders), 15 (Navigation Integrity).
- **Phase E — Performance & Final Mobile Optimization:** Items 10 (Asset Budget), 20 (Touch Targets, Contrast, Fast Startup & Rendering).
