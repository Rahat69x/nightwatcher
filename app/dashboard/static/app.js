// =====================================================================
// NIGHTWATCHER — DASHBOARD FRONTEND LOGIC
// Real-time polling • Event simulation • Fast actions • Tool integrations
// =====================================================================

let currentFilter = 'all';
let searchQuery = '';
let allAlerts = [];
let pollTimer = null;

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  fetchDashboardData();
  // Poll every 3 seconds for hackathon responsiveness
  pollTimer = setInterval(fetchDashboardData, 3000);
  // Dynamic copyright year
  const yrEl = document.getElementById('copyright-year');
  if (yrEl) yrEl.textContent = new Date().getFullYear();
});

function handleAlertSearch(val) {
  searchQuery = (val || '').toLowerCase().trim();
  renderAlertsList();
}

function copyToClipboard(text, label) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text);
    showToast(`Copied ${label || text} to clipboard!`);
  }
}

async function fetchDashboardData() {
  try {
    const [statsRes, alertsRes, scoreRes] = await Promise.all([
      fetch('/api/watchers/system/stats'),
      fetch('/api/alerts/'),
      fetch('/api/watchers/security-score'),
    ]);

    if (statsRes.ok) {
      const stats = await statsRes.json();
      updateStatsUI(stats);
    }

    if (scoreRes && scoreRes.ok) {
      const scoreData = await scoreRes.json();
      updateScoreUI(scoreData);
    }

    if (alertsRes.ok) {
      allAlerts = await alertsRes.json();
      renderAlertsList();
    }

    document.getElementById('feed-last-updated').textContent =
      `Last sync: ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.error('Data sync failed:', err);
  }
}

function updateScoreUI(data) {
  if (!data) return;
  const scoreEl = document.getElementById('stat-posture-score');
  const gradeEl = document.getElementById('stat-score-grade');
  const statusEl = document.getElementById('stat-posture-status');

  if (scoreEl) {
    scoreEl.innerHTML = `${data.score}<span class="score-max" style="font-size: 0.9rem; color: var(--text-muted); font-weight: normal;">/100</span>`;
  }
  if (gradeEl) {
    gradeEl.textContent = data.grade;
    gradeEl.style.color = data.badge_color || '#38bdf8';
  }
  if (statusEl) {
    statusEl.textContent = `${data.status} • ${data.recommendations && data.recommendations[0] ? data.recommendations[0] : 'Nominal'}`;
  }
}

async function exportSecurityReport() {
  try {
    showToast('Generating security audit report...', 'info');
    const res = await fetch('/api/alerts/export/report');
    if (!res.ok) throw new Error('Failed to generate report');
    const data = await res.json();

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    link.href = url;
    link.download = `nightwatcher-security-audit-${dateStr}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    const total = data.telemetry_summary ? data.telemetry_summary.total_incidents_recorded : 0;
    showToast(`Audit report downloaded successfully (${total} incidents logged)`, 'success');
  } catch (err) {
    console.error('Export report error:', err);
    showToast('Failed to export security report', 'error');
  }
}

function updateStatsUI(stats) {
  const safeSet = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  safeSet('stat-active', stats.active_alerts);
  safeSet('stat-critical', (stats.critical_alerts || 0) + (stats.high_alerts || 0));
  safeSet('stat-blocked', stats.blocked_ips);
  safeSet('stat-sites', stats.watched_sites_total);

  safeSet('tab-count-alerts', stats.active_alerts);
  safeSet('drawer-count-alerts', stats.active_alerts);

  safeSet('tab-count-sites', stats.watched_sites_total);
  safeSet('drawer-count-sites', stats.watched_sites_total);

  safeSet('tab-count-block', stats.blocked_ips);
  safeSet('drawer-count-block', stats.blocked_ips);
}

function renderAlertsList() {
  const container = document.getElementById('alerts-container');
  let filtered = allAlerts;

  if (currentFilter === 'active') {
    filtered = allAlerts.filter(a => a.status === 'new' || a.status === 'notified');
  } else if (currentFilter === 'critical') {
    filtered = allAlerts.filter(a => a.severity === 'critical' || a.severity === 'high');
  } else if (currentFilter === 'acknowledged') {
    filtered = allAlerts.filter(a => a.status === 'acknowledged');
  } else if (currentFilter === 'resolved') {
    filtered = allAlerts.filter(a => a.status === 'resolved');
  }

  if (searchQuery) {
    filtered = filtered.filter(a =>
      (a.summary && a.summary.toLowerCase().includes(searchQuery)) ||
      (a.source_ip && a.source_ip.toLowerCase().includes(searchQuery)) ||
      (a.type && a.type.toLowerCase().includes(searchQuery))
    );
  }

  if (!filtered || filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="#475569" stroke-width="1.5" style="margin-bottom:12px;">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <p>${searchQuery ? 'No alerts matching search filter.' : 'No alerts in this view. Use the simulator buttons above to trigger live attacks!'}</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(alert => {
    const sev = (alert.severity || 'low').toLowerCase();
    const isAck = alert.status === 'acknowledged';
    const isRes = alert.status === 'resolved';

    return `
      <div class="alert-card severity-${sev}" id="alert-card-${alert.id}">
        <div class="alert-top">
          <div class="alert-badges">
            <span class="severity-badge">${sev}</span>
            <span class="status-badge status-${alert.status}">${alert.status}</span>
            ${alert.count > 1 ? `<span class="count-badge">Grouped x${alert.count}</span>` : ''}
          </div>
          <div class="alert-meta">
            <span>Score: <b>${alert.score.toFixed(0)}/100</b></span>
            <span>Alert #${alert.id}</span>
            <span>${timeAgo(alert.last_seen)}</span>
          </div>
        </div>

        <div class="alert-summary">${escapeHtml(alert.summary)}</div>

        <div class="alert-details-row">
          <span>Type: <b>${escapeHtml(alert.type)}</b></span>
          ${alert.source_ip ? `<span>Source IP: <b style="color:#f87171;">${escapeHtml(alert.source_ip)}</b> <button class="copy-btn" title="Copy IP" onclick="copyToClipboard('${escapeHtml(alert.source_ip)}', 'IP')">📋</button></span>` : ''}
          ${alert.acknowledged_by ? `<span>Handled By: <b style="color:#34d399;">${escapeHtml(alert.acknowledged_by)}</b></span>` : ''}
        </div>

        <div class="alert-bottom">
          <div class="escalation-timer">
            ${sev === 'critical' ? '🔴 Voice Call Escalation Active' : sev === 'high' ? '🟠 Telegram & SMS Active' : '🔵 Notification Sent'}
          </div>

          <div class="alert-actions">
            ${!isAck && !isRes ? `
              <button class="btn btn-success btn-sm" onclick="ackAlert(${alert.id})">
                ✅ Acknowledge
              </button>
            ` : ''}
            ${alert.source_ip ? `
              <button class="btn btn-danger btn-sm" onclick="blockAlertIP(${alert.id})">
                🚫 Block IP
              </button>
            ` : ''}
            ${!isRes ? `
              <button class="btn btn-secondary btn-sm" onclick="resolveAlert(${alert.id})">
                ✔️ Resolve
              </button>
            ` : ''}
            <button class="btn btn-secondary btn-sm" onclick="openAlertModal(${alert.id})">
              🔍 Details
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ── Action Handlers ─────────────────────────────────────
async function ackAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' });
    if (res.ok) {
      showToast(`Alert #${alertId} acknowledged.`);
      fetchDashboardData();
    }
  } catch (err) {
    showToast(`Failed to acknowledge: ${err.message}`);
  }
}

async function blockAlertIP(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/block-ip`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(`🚫 Blocked IP ${data.ip} & resolved alert #${alertId}.`);
      fetchDashboardData();
    } else {
      showToast(data.detail || 'Failed to block IP');
    }
  } catch (err) {
    showToast(`Failed to block: ${err.message}`);
  }
}

async function resolveAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/resolve`, { method: 'POST' });
    if (res.ok) {
      showToast(`Alert #${alertId} marked resolved.`);
      fetchDashboardData();
    }
  } catch (err) {
    showToast(`Failed: ${err.message}`);
  }
}

// ── Attack Simulator with Debounce Protection ───────────
let isSimulating = false;

async function runAttackSim(mode) {
  if (isSimulating) {
    showToast('Simulation in progress, please wait...', 'warning');
    return;
  }
  isSimulating = true;

  let eventPayload = {};
  showToast(`⚡ Launching simulated attack: ${mode.replace(/_/g, ' ')}...`, 'info');

  if (mode === 'brute_force') {
    eventPayload = {
      type: 'brute_force',
      source: 'attack_simulator',
      details: {
        source_ip: '198.51.100.42',
        failed_attempts: 15,
        username: 'admin',
        abuse_confidence_score: 85,
        off_hours: true,
      },
    };
  } else if (mode === 'credential_stuffing') {
    eventPayload = {
      type: 'credential_stuffing',
      source: 'attack_simulator',
      details: {
        source_ip: '203.0.113.88',
        unique_usernames: 12,
        failed_attempts: 12,
        off_hours: false,
      },
    };
  } else if (mode === 'login_success_after_brute') {
    eventPayload = {
      type: 'login_success_after_brute',
      source: 'attack_simulator',
      details: {
        source_ip: '198.51.100.42',
        username: 'root',
        failed_attempts_before: 28,
      },
    };
  } else if (mode === 'site_down') {
    eventPayload = {
      type: 'site_down',
      source: 'website_watcher',
      details: {
        url: 'https://core-ecommerce-portal.com',
        consecutive_failures: 2,
      },
    };
  } else if (mode === 'phishing') {
    eventPayload = {
      type: 'phishing_url',
      source: 'phishing_watcher',
      details: {
        url: 'http://paypa1-security-verification.top/login',
        phish_score: 95,
        reasons: [
          'Domain is 1 edit distance from brand "paypal"',
          'Suspicious TLD: .top',
          'Urgency keyword "security" and "login" in path',
          'Domain registered 2 days ago'
        ],
      },
    };
  }

  try {
    const res = await fetch('/api/events/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eventPayload),
    });
    const result = await res.json();
    if (res.ok) {
      showToast(`🚨 Threat Detected: Alert #${result.alert_id} (${result.severity.toUpperCase()})`, 'success');
      fetchDashboardData();
    } else {
      showToast(`Simulation rejected: ${result.detail || 'Validation error'}`, 'error');
    }
  } catch (err) {
    showToast(`Simulation failed: ${err.message}`, 'error');
  } finally {
    setTimeout(() => {
      isSimulating = false;
    }, 500);
  }
}

// ── Interactive Tools ───────────────────────────────────
async function inspectPhishing() {
  const text = document.getElementById('phish-input').value.trim();
  const outBox = document.getElementById('phish-result');
  if (!text) {
    showToast('Please enter a URL or message to analyze.');
    return;
  }

  outBox.style.display = 'block';
  outBox.innerHTML = '<div class="spinner"></div><p>Analyzing phishing signals & lookalikes...</p>';

  try {
    const res = await fetch('/api/watchers/phishing/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text_or_url: text }),
    });
    const data = await res.json();
    const results = data.results;

    if (!results || results.length === 0) {
      outBox.innerHTML = '<p style="color:#64748b;">No URLs detected in the input text.</p>';
      return;
    }

    outBox.innerHTML = results.map(r => {
      const riskClass = r.phish_score >= 70 ? 'risk-high' : r.phish_score >= 40 ? 'risk-med' : 'risk-low';
      return `
        <div style="margin-bottom:12px;">
          <div class="risk-tag ${riskClass}">${r.verdict} (Risk: ${r.phish_score}/100)</div>
          <div style="word-break:break-all; margin-bottom:8px;">Target: <b>${escapeHtml(r.url)}</b></div>
          <ul style="padding-left:18px; color:#cbd5e1;">
            ${r.reasons.length ? r.reasons.map(reason => `<li>${escapeHtml(reason)}</li>`).join('') : '<li>No overt threat markers identified.</li>'}
          </ul>
        </div>
      `;
    }).join('');
  } catch (err) {
    outBox.innerHTML = `<p style="color:#ef4444;">Analysis error: ${err.message}</p>`;
  }
}

function setPhishExample(num) {
  if (num === 1) {
    document.getElementById('phish-input').value =
      'URGENT: Your PayPal account has been suspended! Verify immediately at http://paypa1-security-verification.top/auth';
  } else {
    document.getElementById('phish-input').value =
      'Check your package status now at http://192.168.1.99:8080/secure/tracking.html';
  }
}

async function inspectPassword() {
  const pwd = document.getElementById('pwd-input').value;
  const outBox = document.getElementById('pwd-result');
  if (!pwd) {
    showToast('Enter a password to test.');
    return;
  }

  outBox.style.display = 'block';
  outBox.innerHTML = '<div class="spinner"></div><p>Executing k-anonymity range check on Pwned Passwords API...</p>';

  try {
    const res = await fetch('/api/watchers/breach/check-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pwd }),
    });
    const data = await res.json();

    const tagClass = data.pwned ? 'risk-high' : 'risk-low';
    outBox.innerHTML = `
      <div class="risk-tag ${tagClass}">${data.pwned ? 'EXPOSED IN BREACHES' : 'CLEAN / NOT FOUND'}</div>
      <p style="margin-top:6px; color:#f1f5f9;">${escapeHtml(data.verdict)}</p>
      <p style="margin-top:4px; font-size:0.75rem; color:#64748b;">
        Protected via SHA-1 k-anonymity: only the 5-character prefix was sent over TLS.
      </p>
    `;
  } catch (err) {
    outBox.innerHTML = `<p style="color:#ef4444;">Check failed: ${err.message}</p>`;
  }
}

function setPwdExample(val) {
  document.getElementById('pwd-input').value = val;
  inspectPassword();
}

// ── Watched Sites ───────────────────────────────────────
async function loadWatchedSites() {
  const container = document.getElementById('sites-container');
  try {
    const res = await fetch('/api/watchers/sites');
    const sites = await res.json();

    if (!sites || sites.length === 0) {
      container.innerHTML = `
        <div class="card p-20 empty-state">
          <p>No watched websites added yet. Add a site URL above to monitor uptime and SSL.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = sites.map(s => {
      const isUp = s.consecutive_failures === 0;
      const ms = s.last_response_ms ? Math.round(s.last_response_ms) : null;
      const msClass = ms && ms < 500 ? 'color:#34d399;' : ms && ms < 1500 ? 'color:#fbbf24;' : 'color:#f87171;';

      return `
      <div class="card p-20" style="margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div style="flex:1; min-width:240px;">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <span style="font-weight:700; font-size:1.05rem; color:#f8fafc;">${escapeHtml(s.url)}</span>
            <span class="status-badge ${isUp ? 'status-acknowledged' : 'status-new'}">${isUp ? '● ONLINE' : '● OFFLINE'}</span>
          </div>
          <div class="text-muted" style="display:flex; flex-wrap:wrap; gap:14px; font-size:0.8rem; font-family:var(--font-mono);">
            <span>Latency: <b style="${msClass}">${ms !== null ? ms + 'ms' : 'Not scanned'}</b></span>
            <span>Last Status: <b>${s.last_status_code || 'N/A'}</b></span>
            ${s.owner_note ? `<span>Note: ${escapeHtml(s.owner_note)}</span>` : ''}
          </div>
        </div>
        <div class="flex-gap">
          <button class="btn btn-secondary btn-sm" onclick="checkSiteNow('${escapeHtml(s.url)}')">⚡ Run Scan</button>
          <button class="btn btn-danger btn-sm" onclick="deleteSite(${s.id})">Remove</button>
        </div>
      </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<p>Error loading sites: ${err.message}</p>`;
  }
}

async function addWatchedSite() {
  const input = document.getElementById('new-site-url');
  const url = input.value.trim();
  if (!url) return;

  try {
    const res = await fetch('/api/watchers/sites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (res.ok) {
      input.value = '';
      showToast('Watched site added.');
      loadWatchedSites();
    }
  } catch (err) {
    showToast(`Failed to add: ${err.message}`);
  }
}

async function checkSiteNow(url) {
  showToast(`Scanning ${url}...`);
  try {
    const res = await fetch('/api/watchers/website/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const report = await res.json();
    showToast(`Scan complete: ${report.up ? 'Site is UP' : 'Site is DOWN'} (${report.status_code || 'no response'})`);
    loadWatchedSites();
  } catch (err) {
    showToast(`Scan failed: ${err.message}`);
  }
}

async function deleteSite(siteId) {
  try {
    await fetch(`/api/watchers/sites/${siteId}`, { method: 'DELETE' });
    showToast('Site removed.');
    loadWatchedSites();
  } catch (err) {
    showToast(`Failed to delete: ${err.message}`);
  }
}

// ── Blocklist ───────────────────────────────────────────
async function loadBlocklist() {
  const container = document.getElementById('blocklist-container');
  try {
    const res = await fetch('/api/alerts/blocklist/active');
    const entries = await res.json();

    if (!entries || entries.length === 0) {
      container.innerHTML = `
        <div class="card p-20 empty-state">
          <p>Blocklist is currently clean. Attacking IPs will appear here automatically.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="card" style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.85rem;">
          <thead>
            <tr style="border-bottom:1px solid #24324c; color:#94a3b8;">
              <th style="padding:12px 16px;">IP Address</th>
              <th style="padding:12px 16px;">Reason</th>
              <th style="padding:12px 16px;">Blocked At</th>
              <th style="padding:12px 16px;">Expires At</th>
            </tr>
          </thead>
          <tbody>
            ${entries.map(e => `
              <tr style="border-bottom:1px solid #1c2942;">
                <td style="padding:12px 16px; font-family:var(--font-mono); color:#f87171; font-weight:700;">${escapeHtml(e.ip)}</td>
                <td style="padding:12px 16px;">${escapeHtml(e.reason)}</td>
                <td style="padding:12px 16px; color:#94a3b8;">${e.blocked_at ? new Date(e.blocked_at).toLocaleString() : 'N/A'}</td>
                <td style="padding:12px 16px; color:#94a3b8;">${e.expires_at ? new Date(e.expires_at).toLocaleString() : 'Permanent'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p>Error loading blocklist: ${err.message}</p>`;
  }
}

async function manualBlockIP() {
  const input = document.getElementById('manual-block-ip');
  const ip = input.value.trim();
  if (!ip) return;

  try {
    const res = await fetch('/api/events/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'brute_force',
        source: 'manual_block',
        details: { source_ip: ip, failed_attempts: 10, username: 'manual' },
      }),
    });
    if (res.ok) {
      input.value = '';
      showToast(`Blocked IP ${ip}`);
      loadBlocklist();
      fetchDashboardData();
    }
  } catch (err) {
    showToast(`Block failed: ${err.message}`);
  }
}

// ── Tab Navigation ──────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.drawer-link').forEach(b => b.classList.remove('active'));

  const targetPanel = document.getElementById(tabId);
  if (targetPanel) targetPanel.classList.add('active');

  // Highlight corresponding desktop tab and drawer link
  document.querySelectorAll(`.tab-btn[onclick*="${tabId}"]`).forEach(b => b.classList.add('active'));
  document.querySelectorAll(`.drawer-link[onclick*="${tabId}"]`).forEach(b => b.classList.add('active'));

  if (tabId === 'tab-sites') loadWatchedSites();
  if (tabId === 'tab-blocklist') loadBlocklist();

  // Dynamic tab page title
  const titleMap = {
    'tab-alerts': 'NightWatcher — Alert Incidents & Active Triage',
    'tab-tools': 'NightWatcher — Phishing & Password Tools',
    'tab-sites': 'NightWatcher — Watched Websites & SSL Certificates',
    'tab-blocklist': 'NightWatcher — Autonomous IP Blocklist',
    'tab-channels': 'NightWatcher — Escalation Channels',
  };
  if (titleMap[tabId]) document.title = titleMap[tabId];
}

function filterAlerts(filter) {
  currentFilter = filter;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  event.currentTarget.classList.add('active');
  renderAlertsList();
}

// ── Modal ───────────────────────────────────────────────
function openAlertModal(alertId) {
  const alert = allAlerts.find(a => a.id === alertId);
  if (!alert) return;

  document.getElementById('modal-severity-badge').textContent = (alert.severity || '').toUpperCase();
  document.getElementById('modal-severity-badge').className = `severity-badge severity-${alert.severity}`;
  document.getElementById('modal-title').textContent = `Alert #${alert.id} — ${alert.type}`;

  document.getElementById('modal-content').innerHTML = `
    <div>
      <h4 style="color:#94a3b8; font-size:0.8rem; margin-bottom:4px;">PLAIN LANGUAGE SUMMARY</h4>
      <p style="font-size:1.05rem; font-weight:600; color:#f8fafc;">${escapeHtml(alert.summary)}</p>
    </div>
    <div style="background:#090e18; padding:12px; border-radius:8px; font-family:var(--font-mono); font-size:0.82rem;">
      <div>Severity Score: <b>${alert.score.toFixed(0)}/100</b></div>
      <div>Source IP: <b>${escapeHtml(alert.source_ip || 'N/A')}</b></div>
      <div>First Seen: <b>${alert.first_seen ? new Date(alert.first_seen).toLocaleString() : 'N/A'}</b></div>
      <div>Last Seen: <b>${alert.last_seen ? new Date(alert.last_seen).toLocaleString() : 'N/A'}</b></div>
      <div>Grouped Count: <b>x${alert.count}</b></div>
      <div>Handled By: <b>${escapeHtml(alert.acknowledged_by || 'Unacknowledged')}</b></div>
    </div>
  `;

  document.getElementById('modal-actions').innerHTML = `
    ${alert.source_ip ? `<button class="btn btn-danger" onclick="blockAlertIP(${alert.id}); closeModal();">🚫 Block IP</button>` : ''}
    <button class="btn btn-success" onclick="ackAlert(${alert.id}); closeModal();">✅ Acknowledge</button>
    <button class="btn btn-secondary" onclick="closeModal()">Close</button>
  `;

  document.getElementById('alert-modal').classList.add('active');
}

function closeModal(event) {
  document.getElementById('alert-modal').classList.remove('active');
}

// ── Utilities ───────────────────────────────────────────
function showToast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  const icon = type === 'error' ? '✕' : (type === 'warning' ? '⚠️' : (type === 'info' ? 'ℹ' : '✓'));
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'status');
  toast.innerHTML = `<span class="toast-icon">${icon}</span> <span class="toast-msg">${escapeHtml(msg)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => {
      if (toast.parentNode) toast.remove();
    }, 300);
  }, 3500);
}

function timeAgo(dateString) {
  if (!dateString) return '';
  const now = new Date();
  const date = new Date(dateString);
  const diffSec = Math.floor((now - date) / 1000);
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  return `${diffHr}h ago`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Mobile Drawer Navigation Controls ───────────────────
function toggleMobileMenu() {
  const drawer = document.getElementById('mobile-nav-drawer');
  const overlay = document.getElementById('mobile-drawer-overlay');
  const btn = document.getElementById('btn-mobile-menu');
  if (!drawer) return;
  const isOpen = drawer.classList.contains('active');

  if (isOpen) {
    closeMobileMenu();
  } else {
    drawer.classList.add('active');
    if (overlay) overlay.classList.add('active');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }
}

function closeMobileMenu() {
  const drawer = document.getElementById('mobile-nav-drawer');
  const overlay = document.getElementById('mobile-drawer-overlay');
  const btn = document.getElementById('btn-mobile-menu');
  if (drawer) drawer.classList.remove('active');
  if (overlay) overlay.classList.remove('active');
  if (btn) btn.setAttribute('aria-expanded', 'false');
  document.body.style.overflow = '';
}

function switchTabAndClose(tabId) {
  switchTab(tabId);
  closeMobileMenu();
}

// Global keyboard listeners
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeMobileMenu();
    closeModal();
    closeTourModal();
  }
});

// ── Theme Preferences & Mode Switcher ───────────────────
function initTheme() {
  let theme = 'dark';
  try {
    theme = localStorage.getItem('nw_theme') || 'dark';
  } catch (e) {}
  document.documentElement.setAttribute('data-theme', theme);
  const metaScheme = document.querySelector('meta[name="color-scheme"]');
  if (metaScheme) metaScheme.content = theme;
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const target = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  try {
    localStorage.setItem('nw_theme', target);
  } catch (e) {}
  const metaScheme = document.querySelector('meta[name="color-scheme"]');
  if (metaScheme) metaScheme.content = target;
  showToast(`Switched to ${target === 'dark' ? 'Dark' : 'Light'} Mode`, 'info');
}

window.addEventListener('storage', (e) => {
  if (e.key === 'nw_theme' && e.newValue) {
    document.documentElement.setAttribute('data-theme', e.newValue);
  }
});

// ── Smooth Scrolling Helpers ────────────────────────────
function scrollToSim() {
  const sim = document.getElementById('demo-simulator');
  if (sim) {
    sim.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ── Product Tour Walkthrough Modal ──────────────────────
let currentTourStep = 0;
const tourSteps = [
  {
    badge: 'STEP 1 OF 3',
    title: 'Design-First Security Canvas',
    text: 'NightWatcher acts as an autonomous design canvas running on your codebase. Every layer is a production guardrail that continuously monitors brute force logins, website uptime & SSL, phishing messages, and leaked credentials.',
    highlightIcon: '🎨',
    highlightTitle: 'Continuous Watchdogs',
    highlightSub: 'Shared alert engine powering 4 focused watchers with zero config.'
  },
  {
    badge: 'STEP 2 OF 3',
    title: 'Self-Healing Auto-Block Engine',
    text: 'When brute force or credential stuffing is detected, NightWatcher takes the first response autonomously by blocking the offending IP, resolving immediate threats before waking a human.',
    highlightIcon: '⚡',
    highlightTitle: 'Autonomous Enforcement',
    highlightSub: 'Attacking IPs blocked on the spot with sliding expiration timers.'
  },
  {
    badge: 'STEP 3 OF 3',
    title: 'Tiered Multi-Channel Escalation',
    text: 'If an attack continues or succeeds, alerts escalate in plain language: Email for low/med, interactive Telegram for high, and urgent SMS & Voice Calls that ring your phone at 3 AM.',
    highlightIcon: '🚨',
    highlightTitle: 'Always Watching. Loudest When It Matters.',
    highlightSub: 'Interactive phone controls allow you to acknowledge or block right from your phone.'
  }
];

function openTourModal() {
  currentTourStep = 0;
  renderTourStep();
  const modal = document.getElementById('tour-modal');
  if (modal) modal.classList.add('active');
}

function closeTourModal(event) {
  const modal = document.getElementById('tour-modal');
  if (modal) modal.classList.remove('active');
}

function renderTourStep() {
  const step = tourSteps[currentTourStep];
  if (!step) return;

  const badgeEl = document.getElementById('tour-step-badge');
  const titleEl = document.getElementById('tour-modal-title');
  const textEl = document.getElementById('tour-modal-text');
  if (badgeEl) badgeEl.textContent = step.badge;
  if (titleEl) titleEl.textContent = step.title;
  if (textEl) textEl.textContent = step.text;

  const hl = document.getElementById('tour-modal-highlight');
  if (hl) {
    hl.innerHTML = `
      <span class="tour-highlight-icon">${step.highlightIcon}</span>
      <div>
        <b style="color:var(--text-primary); display:block; margin-bottom:2px;">${escapeHtml(step.highlightTitle)}</b>
        <span style="font-size:0.82rem; color:var(--text-secondary);">${escapeHtml(step.highlightSub)}</span>
      </div>
    `;
  }

  // Dots
  const dots = document.getElementById('tour-dots');
  if (dots) {
    dots.innerHTML = tourSteps.map((_, i) =>
      `<span class="tour-dot ${i === currentTourStep ? 'active' : ''}"></span>`
    ).join('');
  }

  // Back button
  const prevBtn = document.getElementById('btn-tour-prev');
  if (prevBtn) {
    prevBtn.style.display = currentTourStep > 0 ? 'inline-flex' : 'none';
  }

  // Next button text
  const nextBtn = document.getElementById('btn-tour-next');
  if (nextBtn) {
    nextBtn.textContent = currentTourStep === tourSteps.length - 1 ? 'Finish & Explore' : 'Next';
  }
}

function nextTourStep() {
  if (currentTourStep < tourSteps.length - 1) {
    currentTourStep++;
    renderTourStep();
  } else {
    closeTourModal();
    scrollToSim();
    showToast('Explore the interactive watchdog simulator below!', 'info');
  }
}

function prevTourStep() {
  if (currentTourStep > 0) {
    currentTourStep--;
    renderTourStep();
  }
}


