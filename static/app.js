const POLL_MS = 3000;
const NODE_ID = "node-1";

const el = (id) => document.getElementById(id);

function fmt(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return Number(value).toFixed(digits);
}

function timeAgo(isoString) {
  const diffSec = Math.round((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return `${Math.floor(diffSec / 3600)}h ago`;
}

function applyStatus(status) {
  const card = el("status-card");
  const value = el("status-value");
  const banner = el("alert-banner");
  const icon = el("alert-icon");
  const text = el("alert-text");

  card.className = "status-card status-" + status;
  value.textContent = status.toUpperCase();

  if (status === "critical") {
    banner.className = "alert-banner";
    icon.textContent = "🚨";
    text.textContent = "CRITICAL FLOOD ALERT — water level has reached a dangerous threshold. Take immediate action.";
  } else if (status === "warning") {
    banner.className = "alert-banner warning-level";
    icon.textContent = "⚠";
    text.textContent = "WARNING — water level is rising toward a critical threshold. Monitor closely.";
  } else {
    banner.className = "alert-banner hidden";
  }
}

async function fetchLatest() {
  const res = await fetch(`/api/latest?node_id=${encodeURIComponent(NODE_ID)}`);
  const data = await res.json();
  const conn = el("connection");

  if (!data) {
    conn.textContent = "No data yet";
    conn.className = "pill pill-muted";
    return;
  }

  conn.textContent = "Live";
  conn.className = "pill pill-live";
  el("last-updated").textContent = "Updated " + timeAgo(data.iso_time);
  el("status-node").textContent = data.node_id;

  el("m-depth").textContent = fmt(data.water_depth_cm);
  el("m-flow").textContent = fmt(data.flow_rate_lpm);
  el("m-temp").textContent = fmt(data.temperature_c);
  el("m-hum").textContent = fmt(data.humidity_pct);
  el("m-batt").textContent = fmt(data.battery_v, 2);
  el("m-rssi").textContent = data.rssi ?? "--";

  applyStatus(data.status);
}

async function fetchHistory() {
  const res = await fetch(`/api/history?node_id=${encodeURIComponent(NODE_ID)}&limit=60`);
  const rows = await res.json();
  drawChart(rows);
}

async function fetchAlerts() {
  const res = await fetch("/api/alerts?limit=15");
  const rows = await res.json();
  const log = el("alert-log");

  if (!rows.length) {
    log.innerHTML = '<li class="muted-text">No alerts yet.</li>';
    return;
  }

  log.innerHTML = rows
    .map((a) => {
      const level = a.status === "critical" ? "level-critical" : "level-warning";
      const time = new Date(a.ts * 1000).toLocaleString();
      return `<li class="${level}"><span>${a.message}</span><span class="alert-time">${time}</span></li>`;
    })
    .join("");
}

// minimal dependency-free line chart 
function drawChart(rows) {
  const canvas = el("depth-chart");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight || 90;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  const values = rows.map((r) => r.water_depth_cm).filter((v) => v !== null && v !== undefined);
  if (values.length < 2) {
    ctx.fillStyle = "#8ba0c2";
    ctx.font = "13px sans-serif";
    ctx.fillText("Waiting for more data points…", 10, height / 2);
    return;
  }

  const padding = 10;
  const max = Math.max(...values, 100);
  const min = Math.min(...values, 0);
  const range = max - min || 1;

  const stepX = (width - padding * 2) / (values.length - 1);
  const yFor = (v) => height - padding - ((v - min) / range) * (height - padding * 2);

  // threshold lines
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = "#eab30866";
  ctx.beginPath();
  ctx.moveTo(padding, yFor(70));
  ctx.lineTo(width - padding, yFor(70));
  ctx.stroke();

  ctx.strokeStyle = "#ef444466";
  ctx.beginPath();
  ctx.moveTo(padding, yFor(100));
  ctx.lineTo(width - padding, yFor(100));
  ctx.stroke();
  ctx.setLineDash([]);

  // depth line
  ctx.strokeStyle = "#3b82f6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = padding + i * stepX;
    const y = yFor(v);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // fill under line
  ctx.lineTo(padding + (values.length - 1) * stepX, height - padding);
  ctx.lineTo(padding, height - padding);
  ctx.closePath();
  ctx.fillStyle = "#3b82f622";
  ctx.fill();
}

function tick() {
  fetchLatest();
  fetchHistory();
  fetchAlerts();
}

tick();
setInterval(tick, POLL_MS);
window.addEventListener("resize", fetchHistory);