import { Router, type IRouter } from "express";
import fs from "fs";
import path from "path";

const router: IRouter = Router();

const BOT_DIR = path.resolve("bot");
const USAGE_FILE = path.join(BOT_DIR, "usage.json");
const LIMITS_FILE = path.join(BOT_DIR, "limits.json");
const BLOCKLIST_FILE = path.join(BOT_DIR, "blocklist.json");
const PENDING_RESETS_FILE = path.join(BOT_DIR, "pending_resets.json");

const HEAVY_LIMIT_DEFAULT = 10;

function readJson<T>(filePath: string, fallback: T): T {
  try {
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
    }
  } catch {}
  return fallback;
}

router.get("/dashboard/stats", (_req, res) => {
  const now = Date.now() / 1000;
  const dayAgo = now - 86400;

  const rawUsage = readJson<Record<string, number[]>>(USAGE_FILE, {});
  const customLimits = readJson<Record<string, number>>(LIMITS_FILE, {});
  const blocklist = readJson<number[]>(BLOCKLIST_FILE, []);
  const blockedSet = new Set(blocklist.map(String));

  const allUserIds = new Set([
    ...Object.keys(rawUsage),
    ...Object.keys(customLimits),
    ...blocklist.map(String),
  ]);

  const users = Array.from(allUserIds).map((id) => {
    const timestamps = (rawUsage[id] ?? []).filter((t) => t > dayAgo);
    const limit = customLimits[id] ?? HEAVY_LIMIT_DEFAULT;
    return {
      id,
      used: timestamps.length,
      limit,
      remaining: Math.max(0, limit - timestamps.length),
      blocked: blockedSet.has(id),
      oldestResetsAt:
        timestamps.length > 0
          ? Math.floor(Math.min(...timestamps) + 86400)
          : null,
    };
  });

  users.sort((a, b) => b.used - a.used);

  res.json({
    users,
    totalBlocked: blockedSet.size,
    defaultLimit: HEAVY_LIMIT_DEFAULT,
    generatedAt: Math.floor(now),
  });
});

router.post("/dashboard/reset/:userId", (req, res) => {
  const { userId } = req.params;
  if (!/^\d+$/.test(userId)) {
    res.status(400).json({ error: "Invalid user ID" });
    return;
  }

  const existing = readJson<number[]>(PENDING_RESETS_FILE, []);
  const uid = parseInt(userId, 10);
  if (!existing.includes(uid)) {
    existing.push(uid);
  }
  fs.mkdirSync(BOT_DIR, { recursive: true });
  fs.writeFileSync(PENDING_RESETS_FILE, JSON.stringify(existing));

  res.json({ ok: true, userId });
});

router.get("/dashboard", (_req, res) => {
  res.setHeader("Content-Type", "text/html");
  res.send(DASHBOARD_HTML);
});

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IHTX Bot Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0d0d12;
    --surface: #16161f;
    --border: #2a2a38;
    --accent: #7c6af7;
    --accent-dim: #4e44b0;
    --text: #e4e4f0;
    --muted: #777790;
    --danger: #e05656;
    --success: #4caf7d;
    --warn: #e09940;
  }
  body { background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; min-height: 100vh; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 28px; display: flex; align-items: center; gap: 14px; }
  header h1 { font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; }
  header .status { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; color: var(--muted); margin-left: auto; }
  header .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 6px var(--success); }
  main { max-width: 1100px; margin: 0 auto; padding: 28px 20px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 28px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; }
  .card .label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 8px; }
  .card .value { font-size: 1.8rem; font-weight: 700; }
  .section-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 12px; }
  .table-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 28px; }
  table { width: 100%; border-collapse: collapse; }
  th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border); font-weight: 500; }
  td { padding: 11px 16px; border-bottom: 1px solid var(--border); font-size: 0.88rem; vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.02); }
  .badge { display: inline-block; font-size: 0.7rem; padding: 2px 8px; border-radius: 20px; font-weight: 600; }
  .badge-blocked { background: rgba(224,86,86,0.18); color: var(--danger); }
  .badge-active { background: rgba(76,175,125,0.15); color: var(--success); }
  .badge-at-limit { background: rgba(224,153,64,0.18); color: var(--warn); }
  .bar-wrap { display: flex; align-items: center; gap: 10px; }
  .bar { flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; max-width: 120px; }
  .bar-fill { height: 100%; border-radius: 3px; background: var(--accent); transition: width 0.3s; }
  .bar-fill.full { background: var(--warn); }
  .bar-fill.over { background: var(--danger); }
  .uid { font-family: monospace; font-size: 0.82rem; color: var(--muted); }
  button.reset-btn { background: rgba(124,106,247,0.12); color: var(--accent); border: 1px solid var(--accent-dim); border-radius: 6px; padding: 5px 12px; font-size: 0.78rem; cursor: pointer; font-weight: 600; transition: background 0.15s; }
  button.reset-btn:hover { background: rgba(124,106,247,0.25); }
  button.reset-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  button.reset-btn.done { background: rgba(76,175,125,0.15); color: var(--success); border-color: var(--success); }
  .refresh-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
  .refresh-btn { background: var(--surface); border: 1px solid var(--border); color: var(--text); border-radius: 7px; padding: 6px 14px; font-size: 0.8rem; cursor: pointer; }
  .refresh-btn:hover { border-color: var(--accent); }
  .ts { color: var(--muted); font-size: 0.75rem; }
  .empty { padding: 32px; text-align: center; color: var(--muted); font-size: 0.9rem; }
  .filter-input { background: var(--surface); border: 1px solid var(--border); color: var(--text); border-radius: 7px; padding: 7px 12px; font-size: 0.85rem; outline: none; width: 220px; }
  .filter-input:focus { border-color: var(--accent); }
</style>
</head>
<body>
<header>
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="8" fill="#7c6af7"/><text x="5" y="20" font-size="16" fill="white">🤖</text></svg>
  <h1>IHTX Bot Dashboard</h1>
  <div class="status"><div class="dot"></div> Live</div>
</header>
<main>
  <div class="cards" id="cards">
    <div class="card"><div class="label">Users Tracked</div><div class="value" id="stat-users">—</div></div>
    <div class="card"><div class="label">Blocked Users</div><div class="value" id="stat-blocked">—</div></div>
    <div class="card"><div class="label">Default Limit</div><div class="value" id="stat-limit">—</div></div>
    <div class="card"><div class="label">At/Over Limit</div><div class="value" id="stat-at-limit">—</div></div>
  </div>

  <div class="refresh-bar">
    <div class="section-title" style="margin:0">Users</div>
    <input class="filter-input" id="filter" placeholder="Filter by user ID…" oninput="renderTable()">
    <button class="refresh-btn" onclick="load()">↻ Refresh</button>
    <span class="ts" id="ts"></span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>User ID</th>
          <th>Used (24h)</th>
          <th>Usage</th>
          <th>Limit</th>
          <th>Resets</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</main>
<script>
let allUsers = [];

async function load() {
  try {
    const r = await fetch('/api/dashboard/stats');
    const data = await r.json();
    allUsers = data.users;
    document.getElementById('stat-users').textContent = data.users.length;
    document.getElementById('stat-blocked').textContent = data.totalBlocked;
    document.getElementById('stat-limit').textContent = data.defaultLimit + '/24h';
    document.getElementById('stat-at-limit').textContent = data.users.filter(u => u.used >= u.limit).length;
    const d = new Date(data.generatedAt * 1000);
    document.getElementById('ts').textContent = 'Updated ' + d.toLocaleTimeString();
    renderTable();
  } catch(e) {
    console.error(e);
  }
}

function renderTable() {
  const filter = document.getElementById('filter').value.trim().toLowerCase();
  const users = filter ? allUsers.filter(u => u.id.includes(filter)) : allUsers;
  const tbody = document.getElementById('tbody');
  if (!users.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">No users tracked yet.</td></tr>';
    return;
  }
  tbody.innerHTML = users.map(u => {
    const pct = Math.min(100, Math.round((u.used / u.limit) * 100));
    const fillClass = pct >= 100 ? 'over' : pct >= 80 ? 'full' : '';
    const badge = u.blocked
      ? '<span class="badge badge-blocked">Blocked</span>'
      : u.used >= u.limit
        ? '<span class="badge badge-at-limit">At limit</span>'
        : '<span class="badge badge-active">Active</span>';
    const resetsText = u.oldestResetsAt
      ? new Date(u.oldestResetsAt * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})
      : '—';
    return \`<tr>
      <td class="uid">\${u.id}</td>
      <td>\${u.used}</td>
      <td>
        <div class="bar-wrap">
          <div class="bar"><div class="bar-fill \${fillClass}" style="width:\${pct}%"></div></div>
          <span style="font-size:0.78rem;color:var(--muted)">\${pct}%</span>
        </div>
      </td>
      <td>\${u.limit}</td>
      <td class="ts">\${resetsText}</td>
      <td>\${badge}</td>
      <td><button class="reset-btn" id="btn-\${u.id}" onclick="resetUser('\${u.id}')">Reset</button></td>
    </tr>\`;
  }).join('');
}

async function resetUser(userId) {
  const btn = document.getElementById('btn-' + userId);
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Resetting…';
  try {
    const r = await fetch('/api/dashboard/reset/' + userId, { method: 'POST' });
    const data = await r.json();
    if (data.ok) {
      btn.textContent = 'Done ✓';
      btn.classList.add('done');
      setTimeout(() => load(), 1500);
    } else {
      btn.textContent = 'Error';
      btn.disabled = false;
    }
  } catch {
    btn.textContent = 'Error';
    btn.disabled = false;
  }
}

load();
setInterval(load, 30000);
</script>
</body>
</html>`;

export default router;
