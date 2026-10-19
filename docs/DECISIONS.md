# NightWatcher Architecture & Polish Decisions

This document records architectural assumptions, decisions, and constraints established for the NightWatcher web polish pass, adapting the 20-Point Polish Blueprint to the existing FastAPI + Web Architecture (`c:\hackthon\nightwatcher`).

---

### Decision 1: Target Architecture Alignment
- **Context:** The user requested the 20-point checklist ("20 CHECKS, a website polish list") applied to the existing NightWatcher project (`c:\hackthon\nightwatcher`).
- **Decision:** All 20 items are executed directly across the NightWatcher Web SOC Dashboard (`/`), the API subsystem (`/api/*`, `/health`, `/docs`), and the Customer Demo Portal (`demo/fake_login_app.py` on `:8001`).
- **Principles:**
  - Preserve all existing dark-mode cyber SOC styling, Plus Jakarta Sans typography, and live hackathon attack simulations.
  - Zero disruption to working features, schedulers, and background watchers.
  - Adhere strictly to the phased workflow: Audit -> Plan & STOP -> Execute with baseline tests -> Verify & tag commit.

---

### Decision 2: Mobile Navigation & Responsiveness
- **Context:** Mobile viewports (< 768px) currently display inline tabs that can wrap into multiple lines, and the top navigation bar lacks a collapsed drawer/menu.
- **Decision:** Implement a clean, accessible hamburger menu on mobile screens that toggles a backdrop-blurred sliding navigation drawer providing quick access to:
  1. Live Alert Incidents (`#tab-alerts`)
  2. Phishing & Password Tools (`#tab-tools`)
  3. Watched Websites & SSL (`#tab-sites`)
  4. Autonomous Blocklist (`#tab-blocklist`)
  5. Escalation Matrix (`#tab-channels`)
  6. API Documentation (`/docs`)
  7. System Health (`/health`)
  8. Emergency SOC Contact & About Dialog

---

### Decision 3: Custom Error Handling & 404 Routing
- **Context:** Currently, 404 errors in FastAPI return raw JSON `{"detail": "Not Found"}` regardless of whether the requester is a browser navigating to a web page or an API client.
- **Decision:** In `app/main.py`, register a Starlette 404 exception handler that inspects the request `Accept` header and URL path:
  - If requesting HTML or browser navigation: Renders a branded `404.html` page with "Return to Dashboard" and "Search Incidents" buttons.
  - If requesting `/api/*` or `application/json`: Returns standard sanitized JSON `{"error": "Not Found", "detail": "..."}`.

---

### Decision 4: Interactive Notifications (Success/Error Toasts)
- **Context:** User actions (such as copying an IP, running an attack simulation, unblocking an IP, or submitting a site) lack consistent visual feedback.
- **Decision:** Implement a centralized `showToast(message, type, action)` toast notification system supporting `success`, `error`, `warning`, and `info` with aria-live announcements for screen readers.

---

### Decision 5: Contact Protocols (Phone & Email)
- **Context:** Items 18 & 19 require accessible, clickable phone and email contacts.
- **Decision:**
  - Phone: `tel:+18005550199` (RFC 3966 format) labeled "Emergency SOC Hotline" with click-to-call and click-to-copy.
  - Email: `mailto:soc@nightwatcher.io?subject=Security%20Incident%20Report` labeled "Incident Response Desk" with click-to-mail and click-to-copy fallback.

---

### Decision 6: Asset Optimization & Favicon
- **Context:** Browsers request `/favicon.ico` which currently triggers a 404 error.
- **Decision:** Generate a lightweight, scalable SVG cyber shield favicon in `app/dashboard/static/favicon.svg` and link it in all HTML templates as well as routing `/favicon.ico` directly to avoid 404 logs.
