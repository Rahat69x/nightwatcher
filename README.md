# 🛡️ NightWatcher
> **Always watching. Loudest when it matters.**

An autonomous security watchdog built for small businesses, schools, and teams without dedicated 24/7 security operations. It continuously monitors authentication logs, digital assets, phishing lures, and leaked credentials, takes instant automated response actions (such as auto-blocking offending IPs), and notifies administrators with plain-language alerts that escalate across Email, Telegram, SMS, and Voice Calls until someone answers.

---

## 🚀 The 3-Minute Hackathon Demo

| Step | Action | What You See & Hear |
|---|---|---|
| **1. Baseline (20s)** | Open NightWatcher Dashboard | Dark-mode interface showing 0 active alerts, watchdog status **ONLINE**, watched sites healthy. |
| **2. Attack (30s)** | Click **⚡ 1. Brute Force** or run `python demo/attack_simulator.py --mode brute` | Attacker sends 15 rapid SSH/Web logins against demo portal (`http://localhost:8001`). |
| **3. Auto-Defense (20s)** | Watch target app respond | At attempt #5, NightWatcher **automatically neutralizes and blocks the attacker IP**. Subsequent attempts receive **HTTP 403 Forbidden**. |
| **4. Tier 2 Alert (30s)** | Check Telegram & Email | Phone buzzes with Telegram alert and interactive buttons: `[✅ Acknowledge]` `[🚫 Block IP]` `[📋 Details]`. |
| **5. Escalation & Voice (40s)** | Ignore Telegram button | No acknowledgement within window ➔ Alert engine escalates to **Tier 4 Voice Call**. Phone rings with Polly Amy voice: *"Security alert. Press 1 to acknowledge, Press 2 to block"*. |
| **6. Two-Way Reply (20s)** | Press `1` on call or Telegram | Voice confirms acknowledgement. Dashboard badge instantly flips to **ACKNOWLEDGED**. Threat neutralized! |
| **7. Bonus Tools (20s)** | Click **Phishing / Password Tools** | Paste a scam link or test password to demonstrate live k-anonymity SHA-1 range checks and heuristic URL analysis. |

---

## 🏗️ Architecture

```
                    ┌────────────────────────────────────────────────────────┐
                    │                      FOUR WATCHERS                     │
                    │                                                        │
                    │  [1. Login Watcher]       [2. Website Watcher]         │
                    │   • 5+ fails in 60s        • Uptime checks (5m)        │
                    │   • Credential stuffing    • SSL certificate expiry    │
                    │   • Success after brute    • Security headers / HTTPS  │
                    │                                                        │
                    │  [3. Phishing Watcher]    [4. Breach Watcher]          │
                    │   • Brand lookalikes       • Consent-based email check │
                    │   • Punycode & raw IP      • Pwned Passwords           │
                    │   • Suspicious TLDs / words  (k-anonymity SHA-1 range) │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                                    POST /api/events/
                                                │
                                                ▼
                    ┌────────────────────────────────────────────────────────┐
                    │                  NIGHTWATCHER ENGINE                   │
                    │                                                        │
                    │   1. Raw Ingestion & Fingerprinting                    │
                    │   2. Severity Scoring (0 - 100 Scale)                  │
                    │   3. Duplicate Grouping (10-min sliding window)        │
                    │   4. Autonomous Action: Instant IP Blocklist Ban       │
                    │   5. Plain-Language Translation (Gemini AI / Fallback) │
                    │   6. Intelligent Notification Router                   │
                    └───────────┬────────────────────────────────┬───────────┘
                                │                                │
                                ▼                                ▼
              ┌───────────────────────────────────┐    ┌─────────────────────┐
              │    ESCALATING NOTIFIERS           │    │  AUTONOMOUS ACTIONS │
              │                                   │    │                     │
              │  🔵 Low (0-39):      Email        │    │  • Block IP in DB   │
              │  🟡 Medium (40-69):  Telegram     │    │  • Enforce in Apps  │
              │                      + Email      │    │  • Opt-in Firewall  │
              │  🟠 High (70-89):    Telegram     │    │    (ufw / iptables) │
              │                      + SMS        │    │  • Auto-unblock     │
              │  🔴 Critical (90+):  Voice Call   │    │    expiry timer     │
              │                      + Telegram   │    └─────────────────────┘
              └─────────────────┬─────────────────┘
                                │
                                ▼
              ┌───────────────────────────────────┐
              │   TWO-WAY HUMAN RESPONSE CHANNELS │
              │                                   │
              │   • Telegram: Inline Callbacks    │
              │   • Twilio Call: TwiML Keypress   │
              │     (Press 1 = ACK, 2 = Block)    │
              │   • Twilio SMS: Text ACK or BLOCK │
              │   • Dashboard: One-Click Triage   │
              └───────────────────────────────────┘
```

---

## ⚡ Quickstart

### 1. Requirements
- Python 3.11+
- Virtual environment with dependencies:
```bash
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy the template and fill in optional external provider credentials (system works fully with offline demo fallbacks if keys are left blank):
```bash
cp .env.example .env
```
Key configuration parameters:
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_ADMIN_CHAT_IDS` (Telegram BotFather)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBERS`
- `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_TO_EMAILS` (Gmail App Password or SMTP)
- `GEMINI_API_KEY` (Optional: AI plain-language summarization)
- `ABUSEIPDB_API_KEY`, `HIBP_API_KEY`, `SAFE_BROWSING_API_KEY`

### 3. Run the Watchdog Engine & Dashboard
```bash
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** to view the real-time security operations center.

### 4. (Optional) Run Demo Target Application
In a separate terminal:
```bash
.\.venv\Scripts\python demo/fake_login_app.py
```
Runs the simulated customer portal on **[http://localhost:8001](http://localhost:8001)**.

### 5. Launch Attack Simulator
```bash
# Brute force attack scenario:
.\.venv\Scripts\python demo/attack_simulator.py --mode brute

# Credential stuffing scenario:
.\.venv\Scripts\python demo/attack_simulator.py --mode stuffing

# Critical breach intrusion scenario:
.\.venv\Scripts\python demo/attack_simulator.py --mode critical

# Run all scenarios:
.\.venv\Scripts\python demo/attack_simulator.py --mode all
```

*(You can also trigger all attacks with a single click using the simulation buttons at the top of the web dashboard!)*

---

## 🧪 Running Automated Tests

All core modules have unit and integration test coverage:
```bash
.\.venv\Scripts\pytest -v
```
Checks:
- Severity scoring and escalation boundaries
- Duplicate event grouping & fingerprint stability
- Autonomous blocklist actions and expiration
- Watcher heuristics (Levenshtein lookalike brand detection, raw IP URLs)
- Live k-anonymity SHA-1 range checks on the Pwned Passwords API
- End-to-end API event ingest and Twilio webhooks

---

## 📡 API Reference

### Event Ingest
- `POST /api/events/` — Submit a raw event from any watcher or application.
```json
{
  "type": "brute_force",
  "source": "auth_proxy",
  "details": {
    "source_ip": "198.51.100.42",
    "failed_attempts": 15,
    "username": "admin"
  }
}
```

### Alert Triage
- `GET /api/alerts/` — List alerts with optional `?status=` and `?severity=` filters.
- `POST /api/alerts/{id}/acknowledge` — Human acknowledgement stops the escalation timer.
- `POST /api/alerts/{id}/block-ip` — Manually block the source IP across all systems.
- `POST /api/alerts/{id}/resolve` — Mark incident resolved.
- `GET /api/alerts/blocklist/active` — Active firewall blocklist entries.

### Two-Way Webhooks
- `GET /api/twilio/voice-twiml?alert_id={id}` — Serves spoken Polly.Amy TwiML instructions.
- `POST /api/twilio/voice-action?alert_id={id}` — Handles DTMF phone keypress (1=ACK, 2=Block).
- `POST /api/twilio/sms-reply` — Handles incoming SMS commands (`ACK`, `BLOCK`, `STATUS`).
- `POST /api/watchers/telegram/webhook` — Handles Telegram inline button callbacks.

### Watcher Tool APIs
- `POST /api/watchers/website/check` — On-demand uptime, SSL expiry, and header scan.
- `POST /api/watchers/phishing/check` — URL and message phishing risk analysis.
- `POST /api/watchers/breach/check-password` — k-Anonymity password exposure check.
- `POST /api/watchers/breach/check-email` — Have I Been Pwned email check.
- `GET /api/watchers/system/stats` — Live operational metrics.

---

## ⚖️ Ethics & Defensive Scope
NightWatcher is strictly defensive software designed to protect vulnerable digital infrastructure. It scans only monitored assets you own or have permission to inspect. Password exposure checks utilize k-anonymity where full passwords or hashes are never exposed.
