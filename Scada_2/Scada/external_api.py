"""
external_api.py — TIZIMNING INTERFEYSI. main.py'dan ALOHIDA jarayon
sifatida ishga tushiriladi, faqat bazani o'qiydi (GET), yozmaydi.

ISHGA TUSHIRISH (development):
    py external_api.py
    -> http://localhost:5001

ISHGA TUSHIRISH (production, tavsiya etiladi):
    uvicorn external_api:app --host 0.0.0.0 --port 5001
"""

from fastapi.responses import HTMLResponse
from fastapi import FastAPI

from database import init_all_tables, get_connection

app = FastAPI(title="SCADA AI Monitoring — Interfeys")


# ─────────────────────────── RO'YXATLAR (GET, faqat o'qish) ─────────────

@app.get("/api/reports")
def list_reports():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, model, payload
            FROM vision_reports ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "ts": r[1].isoformat(), "model": r[2], "payload": r[3]} for r in rows]


@app.get("/api/insights")
def list_insights():
    """To'liq bo'lim uchun — oxirgi 10 ta xulosa (home sahifada esa
    faqat birinchisi ishlatiladi)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, severity, summary, trend_analysis, recommendation
            FROM advisor_insights ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(), "severity": r[2], "summary": r[3],
         "trend_analysis": r[4], "recommendation": r[5]}
        for r in rows
    ]


@app.get("/api/plant-state")
def get_plant_state_api():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT ts, state FROM plant_state WHERE id = 1")
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"ts": row[0].isoformat(), "state": row[1]}


@app.get("/api/predictions")
def list_predictions():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, interval_seconds, risk_level, summary, details
            FROM plant_predictions ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(), "interval_seconds": r[2],
         "risk_level": r[3], "summary": r[4], "details": r[5]}
        for r in rows
    ]


@app.get("/api/shift-reports")
def list_shift_reports():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, period_start, period_end, report
            FROM shift_reports ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(),
         "period_start": r[2].isoformat() if r[2] else None,
         "period_end": r[3].isoformat() if r[3] else None,
         "report": r[4]}
        for r in rows
    ]


# ─────────────────────────── BOSH SAHIFA (HTML) ─────────────────────────
# Dizayn: chap tomonda doimiy SIDEBAR (bo'limlar ro'yxati). "Bosh sahifa"
# — barcha bo'limlarning QISQA umumiy ko'rinishi. Sidebar'dan istalgan
# bo'limni bossangiz — o'sha bo'lim TO'LIQ ekranga chiqadi, sidebar esa
# joyida qoladi (boshqa bo'limlarga tez o'tish uchun).

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SCADA AI Monitoring</title>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --panel-2: #1e222b; --border: #2a2f3a;
    --text: #e6e8eb; --muted: #8b93a3; --accent: #4f8ff7;
    --green: #2ecc71; --orange: #f39c12; --red: #e74c3c; --blue: #4f8ff7;
    --sidebar-w: 240px;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); }

  /* ── SIDEBAR ── */
  #sidebar {
    position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w);
    background: var(--panel); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; padding: 18px 0; z-index: 20;
  }
  #sidebar .brand { padding: 0 20px 18px; font-size: 15px; font-weight: 700; border-bottom: 1px solid var(--border); margin-bottom: 10px; }
  #sidebar .brand small { display: block; font-size: 11px; color: var(--muted); font-weight: 400; margin-top: 3px; }
  .nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 11px 20px; font-size: 13.5px; color: var(--muted);
    cursor: pointer; border-left: 3px solid transparent; user-select: none;
  }
  .nav-item:hover { background: var(--panel-2); color: var(--text); }
  .nav-item.active { background: var(--panel-2); color: var(--text); border-left-color: var(--accent); font-weight: 600; }
  .nav-item .dot-ind { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
  .nav-item .dot-ind.CRITICAL, .nav-item .dot-ind.HIGH { background: var(--red); }
  .nav-item .dot-ind.WARNING, .nav-item .dot-ind.MEDIUM { background: var(--orange); }
  .nav-item .dot-ind.NORMAL, .nav-item .dot-ind.LOW { background: var(--green); }
  #sidebar .footer-note { margin-top: auto; padding: 14px 20px 0; font-size: 11px; color: var(--muted); border-top: 1px solid var(--border); }
  #sidebar .footer-note a { color: var(--accent); text-decoration: none; }

  /* ── CONTENT ── */
  #content { margin-left: var(--sidebar-w); min-height: 100vh; }
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 28px; border-bottom: 1px solid var(--border); background: var(--panel);
    position: sticky; top: 0; z-index: 10;
  }
  header h1 { font-size: 17px; margin: 0; font-weight: 600; }
  .status { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--muted); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(46,204,113,.5); } 70% { box-shadow: 0 0 0 8px rgba(46,204,113,0); } 100% { box-shadow: 0 0 0 0 rgba(46,204,113,0); } }
  main { max-width: 1100px; margin: 0 auto; padding: 24px 28px 60px; }

  .view { display: none; }
  .view.active { display: block; }

  .view-header { margin-bottom: 18px; }
  .view-header h2 { font-size: 20px; margin: 0 0 4px; }
  .view-header p { font-size: 13px; color: var(--muted); margin: 0; }

  .section-title { font-size: 12.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 28px 0 12px; display: flex; align-items: center; justify-content: space-between; }
  .section-title .more-link { text-transform: none; letter-spacing: 0; font-size: 12.5px; color: var(--accent); cursor: pointer; }

  .card { border-radius: 12px; padding: 20px 22px; border: 1px solid var(--border); background: var(--panel); border-left: 5px solid var(--muted); }
  .card.CRITICAL, .card.HIGH { border-left-color: var(--red); }
  .card.WARNING, .card.MEDIUM { border-left-color: var(--orange); }
  .card.NORMAL, .card.LOW { border-left-color: var(--green); }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: .04em; margin-bottom: 10px; margin-right: 6px; }
  .badge.CRITICAL, .badge.HIGH { background: rgba(231,76,60,.15); color: var(--red); }
  .badge.WARNING, .badge.MEDIUM { background: rgba(243,156,18,.15); color: var(--orange); }
  .badge.NORMAL, .badge.LOW { background: rgba(46,204,113,.15); color: var(--green); }
  .card .summary { font-size: 16.5px; margin: 4px 0 10px; }
  .card .trend, .card .rec { font-size: 13.5px; color: var(--muted); margin: 4px 0; }
  .card .rec b { color: var(--text); }
  .card-ts { font-size: 12px; color: var(--muted); margin-top: 10px; font-weight: 600; }

  .insight-list { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }
  .insight-row { padding: 12px 14px; background: var(--panel-2); border-radius: 8px; border-left: 3px solid var(--muted); font-size: 13px; }
  .insight-row.CRITICAL, .insight-row.HIGH { border-left-color: var(--red); }
  .insight-row.WARNING, .insight-row.MEDIUM  { border-left-color: var(--orange); }
  .insight-row.NORMAL, .insight-row.LOW   { border-left-color: var(--green); }
  .insight-row .t { color: var(--muted); font-size: 11.5px; margin-top: 4px; font-weight: 600; }

  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; margin-bottom: 14px; }
  .panel h3 { margin: 0 0 4px; font-size: 14px; font-weight: 600; }
  .panel .sub { font-size: 12px; color: var(--muted); margin-bottom: 14px; font-weight: 600; }

  .readings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
  .reading-item { background: var(--panel-2); border-radius: 8px; padding: 8px 10px; }
  .reading-item .k { font-size: 11px; color: var(--muted); }
  .reading-item .v { font-size: 14px; font-weight: 600; margin-top: 2px; }
  .equip-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .pill { font-size: 11.5px; padding: 4px 10px; border-radius: 20px; background: var(--panel-2); color: var(--muted); border: 1px solid var(--border); }
  .pill.on  { color: var(--green); border-color: rgba(46,204,113,.35); }
  .pill.off { color: var(--red); border-color: rgba(231,76,60,.35); }
  .no-alarms { font-size: 12.5px; color: var(--muted); margin-top: 8px; }

  .empty { color: var(--muted); font-size: 13px; padding: 10px 0; }
  .json-block { background: var(--panel-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; font-family: "Consolas", "Courier New", monospace; font-size: 11.5px; color: #9fd8a0; overflow-x: auto; white-space: pre; }
  .json-block .json-ts { color: var(--muted); font-family: -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 11.5px; margin-bottom: 6px; font-weight: 600; }

  .forecast-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-top: 10px; }
  .forecast-item { background: var(--panel-2); border-radius: 8px; padding: 10px 12px; }
  .forecast-item .name { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .forecast-item .row { display: flex; justify-content: space-between; font-size: 12.5px; padding: 2px 0; }
  .forecast-item .row b { color: var(--text); }

  .list-item-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .tag { font-size: 11px; padding: 3px 8px; border-radius: 12px; background: rgba(79,143,247,.12); color: var(--blue); }
  .shift-report { white-space: pre-wrap; font-size: 13px; line-height: 1.55; }

  /* Home — mini overview grid */
  .home-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 800px) { .home-grid { grid-template-columns: 1fr; } }
  .home-card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; cursor: pointer; transition: border-color .15s; }
  .home-card:hover { border-color: var(--accent); }
  .home-card .htitle { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); margin-bottom: 10px; display:flex; justify-content:space-between; }
  .home-card .htitle .go { color: var(--accent); font-size: 11.5px; text-transform: none; }
  .home-card .hbody { font-size: 14px; }
</style>
</head>
<body>

<div id="sidebar">
  <div class="brand">SCADA AI Monitoring<small>Nazorat paneli</small></div>
  <div class="nav-item active" data-view="home"><span class="dot-ind" id="nav-dot-home"></span> Bosh sahifa</div>
  <div class="nav-item" data-view="advisor"><span class="dot-ind" id="nav-dot-advisor"></span> AI Maslahatchi</div>
  <div class="nav-item" data-view="state"><span class="dot-ind" id="nav-dot-state"></span> Zavod xotirasi</div>
  <div class="nav-item" data-view="predictions"><span class="dot-ind" id="nav-dot-predictions"></span> Bashorat</div>
  <div class="nav-item" data-view="shift"><span class="dot-ind"></span> Smena hisobotlari</div>
  <div class="nav-item" data-view="json"><span class="dot-ind"></span> Xom JSON ma'lumotlar</div>
  <div class="footer-note">API hujjatlari: <a href="/docs" target="_blank">/docs</a></div>
</div>

<div id="content">
  <header>
    <h1 id="view-title">Bosh sahifa</h1>
    <div class="status">
      <span class="dot"></span>
      <span id="last-updated">yuklanmoqda...</span>
    </div>
  </header>

  <main>

    <!-- ═══════════════ BOSH SAHIFA ═══════════════ -->
    <div class="view active" id="view-home">
      <div class="view-header">
        <p>Barcha bo'limlarning qisqa umumiy ko'rinishi. Batafsil ma'lumot uchun kartani bosing yoki chapdagi ro'yxatdan tanlang.</p>
      </div>
      <div class="home-grid">

        <div class="home-card" data-goto="advisor">
          <div class="htitle">AI Maslahatchi — joriy xulosa <span class="go">Batafsil →</span></div>
          <div class="hbody" id="home-advisor">Yuklanmoqda...</div>
        </div>

        <div class="home-card" data-goto="state">
          <div class="htitle">Zavod xotirasi — joriy holat <span class="go">Batafsil →</span></div>
          <div class="hbody" id="home-state">Yuklanmoqda...</div>
        </div>

        <div class="home-card" data-goto="predictions">
          <div class="htitle">Bashorat — eng so'nggi <span class="go">Batafsil →</span></div>
          <div class="hbody" id="home-predictions">Yuklanmoqda...</div>
        </div>

        <div class="home-card" data-goto="shift">
          <div class="htitle">So'nggi smena hisoboti <span class="go">Batafsil →</span></div>
          <div class="hbody" id="home-shift">Yuklanmoqda...</div>
        </div>

      </div>
    </div>

    <!-- ═══════════════ AI MASLAHATCHI ═══════════════ -->
    <div class="view" id="view-advisor">
      <div class="view-header">
        <h2>AI Maslahatchi</h2>
        <p>Zavod holati bo'yicha AI tomonidan chiqarilgan xulosalar — eng yangisidan eng eskisigacha. Har birida: vaziyat darajasi, qisqa tavsif, tendentsiya va operator uchun tavsiya, ANIQ VAQT bilan.</p>
      </div>
      <div class="section-title">Joriy (eng so'nggi) xulosa</div>
      <div id="advisor-latest"><div class="empty">Yuklanmoqda...</div></div>
      <div class="section-title">Barcha xulosalar tarixi (vaqt bo'yicha, yangidan eskiga)</div>
      <div id="advisor-history" class="insight-list"><div class="empty">Yuklanmoqda...</div></div>
    </div>

    <!-- ═══════════════ ZAVOD XOTIRASI ═══════════════ -->
    <div class="view" id="view-state">
      <div class="view-header">
        <h2>Zavod xotirasi (Plant State)</h2>
        <p>AI Maslahatchi har safar tahlil qilganda yangilaydigan "xotira" — joriy holat, kuzatilayotgan tendentsiyalar, faol anomaliyalar va operator tekshirishi kerak bo'lgan narsalar.</p>
      </div>
      <div id="plant-state-full"><div class="empty">Yuklanmoqda...</div></div>
    </div>

    <!-- ═══════════════ BASHORAT ═══════════════ -->
    <div class="view" id="view-predictions">
      <div class="view-header">
        <h2>Bashorat (10 / 20 / 30 daqiqa)</h2>
        <p>Oxirgi metrikalar tendentsiyasi asosida kelajakdagi qiymatlarni bashorat qiladi. Holat tez o'zgarsa tezroq (1 daqiqagacha), barqaror bo'lsa kamroq tez-tez (15 daqiqada bir) yangilanadi.</p>
      </div>
      <div id="predictions-full"><div class="empty">Yuklanmoqda...</div></div>
    </div>

    <!-- ═══════════════ SMENA HISOBOTLARI ═══════════════ -->
    <div class="view" id="view-shift">
      <div class="view-header">
        <h2>Smena hisobotlari</h2>
        <p>Har smena davri uchun avtomatik tayyorlangan qisqa hisobot — davr davomidagi holat, muhim voqealar va keyingi smenaga tavsiyalar.</p>
      </div>
      <div id="shift-reports-full"><div class="empty">Yuklanmoqda...</div></div>
    </div>

    <!-- ═══════════════ XOM JSON ═══════════════ -->
    <div class="view" id="view-json">
      <div class="view-header">
        <h2>Xom JSON ma'lumotlar</h2>
        <p>SCADA skrinshotidan AI tomonidan o'qilgan, hech qanday o'zgartirishsiz JSON natijalar — texnik tekshirish uchun.</p>
      </div>
      <div id="reports-json-full"><div class="empty">Yuklanmoqda...</div></div>
    </div>

  </main>
</div>

<script>
const REFRESH_MS = 20000;
const SEV_LABEL = { CRITICAL: "XAVFLI", WARNING: "OGOHLANTIRISH", NORMAL: "NORMAL",
                     HIGH: "YUQORI XAVF", MEDIUM: "O'RTA XAVF", LOW: "PAST XAVF" };
const VIEW_TITLES = { home: "Bosh sahifa", advisor: "AI Maslahatchi", state: "Zavod xotirasi",
                       predictions: "Bashorat", shift: "Smena hisobotlari", json: "Xom JSON ma'lumotlar" };

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}
function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uz-UZ", { hour12: false });
}
function sevLabel(sev) { return SEV_LABEL[sev] || sev || "NOMA'LUM"; }

// ── NAVIGATSIYA ──
function switchView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById("view-" + name).classList.add("active");
  document.querySelectorAll(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.view === name));
  document.getElementById("view-title").textContent = VIEW_TITLES[name] || name;
  window.scrollTo(0, 0);
}
document.querySelectorAll(".nav-item").forEach(item => {
  item.addEventListener("click", () => switchView(item.dataset.view));
});
document.querySelectorAll(".home-card").forEach(card => {
  card.addEventListener("click", () => switchView(card.dataset.goto));
});

// ── ADVISOR ──
function renderAdvisorLatest(items) {
  const latestEl = document.getElementById("advisor-latest");
  const homeEl = document.getElementById("home-advisor");
  const dot = document.getElementById("nav-dot-advisor");

  if (!items || items.length === 0) {
    latestEl.innerHTML = '<div class="empty">Hozircha xulosa yo\\'q.</div>';
    homeEl.innerHTML = '<div class="empty">Hozircha xulosa yo\\'q.</div>';
    return;
  }
  const it = items[0];
  const sev = it.severity || "NORMAL";
  dot.className = "dot-ind " + esc(sev);

  latestEl.innerHTML = `<div class="card ${esc(sev)}">
      <span class="badge ${esc(sev)}">${esc(sevLabel(sev))}</span>
      <div class="summary">${esc(it.summary || "")}</div>
      ${it.trend_analysis ? `<div class="trend"><i>Tendentsiya:</i> ${esc(it.trend_analysis)}</div>` : ""}
      ${it.recommendation ? `<div class="rec"><b>Tavsiya:</b> ${esc(it.recommendation)}</div>` : ""}
      <div class="card-ts">🕒 ${fmtTime(it.ts)}</div>
    </div>`;

  homeEl.innerHTML = `<span class="badge ${esc(sev)}">${esc(sevLabel(sev))}</span><br>
      ${esc(it.summary || "")}<br><span style="color:var(--muted); font-size:12px;">🕒 ${fmtTime(it.ts)}</span>`;
}

function renderAdvisorHistory(items) {
  const el = document.getElementById("advisor-history");
  if (!items || items.length <= 1) {
    el.innerHTML = '<div class="empty">Hali tarix yetarli emas.</div>';
    return;
  }
  el.innerHTML = items.slice(1).map(it => {
    const sev = it.severity || "NORMAL";
    return `<div class="insight-row ${esc(sev)}">
      <span class="badge ${esc(sev)}">${esc(sevLabel(sev))}</span>
      <div>${esc(it.summary || "")}</div>
      ${it.recommendation ? `<div style="font-size:12.5px; color:var(--muted); margin-top:4px;"><b style="color:var(--text);">Tavsiya:</b> ${esc(it.recommendation)}</div>` : ""}
      <div class="t">🕒 ${fmtTime(it.ts)}</div>
    </div>`;
  }).join("");
}

// ── PLANT STATE ──
function renderPlantState(data) {
  const fullEl = document.getElementById("plant-state-full");
  const homeEl = document.getElementById("home-state");
  const dot = document.getElementById("nav-dot-state");

  if (!data || !data.state) {
    const msg = '<div class="empty">Hali zavod xotirasi shakllanmagan (birinchi advisor sikli kutilmoqda).</div>';
    fullEl.innerHTML = msg; homeEl.innerHTML = msg;
    return;
  }
  const s = data.state;
  const status = (s.current_state && s.current_state.status) || "NOMA'LUM";
  dot.className = "dot-ind " + esc(status);
  const trends = s.trends || {};
  const anomalies = s.active_anomalies || [];
  const checks = s.recommended_checks || [];
  const score = s.statistical_anomaly_score !== undefined ? s.statistical_anomaly_score : null;

  const trendsHtml = Object.keys(trends).length
    ? Object.entries(trends).map(([k, v]) => `<span class="pill">${esc(k)}: ${esc(v)}</span>`).join("")
    : '<span class="empty">Aniq tendentsiya yo\\'q</span>';
  const anomaliesHtml = anomalies.length
    ? anomalies.map(a => `<span class="tag">${esc(a)}</span>`).join("")
    : '<span class="empty">Faol anomaliya yo\\'q</span>';
  const checksHtml = checks.length
    ? '<ul style="margin:6px 0 0; padding-left:18px; font-size:13px;">' + checks.map(c => `<li>${esc(c)}</li>`).join("") + '</ul>'
    : '<div class="empty">Tavsiya yo\\'q</div>';

  fullEl.innerHTML = `<div class="panel">
      <div><b>Joriy holat:</b> <span class="badge ${esc(status)}">${esc(sevLabel(status))}</span>
      ${score !== null ? `<span style="color:var(--muted); font-size:12px; margin-left:8px;">Statistik anomaliya darajasi: ${esc(score)}</span>` : ""}</div>
      <div class="sub" style="margin-top:14px;">Tendentsiyalar:</div>
      <div class="equip-grid">${trendsHtml}</div>
      <div class="sub" style="margin-top:14px;">Faol anomaliyalar:</div>
      <div class="list-item-tags">${anomaliesHtml}</div>
      <div class="sub" style="margin-top:14px;">Tavsiya etilgan tekshiruvlar:</div>
      ${checksHtml}
      <div class="card-ts" style="margin-top:12px;">🕒 ${fmtTime(data.ts)}</div>
    </div>`;

  homeEl.innerHTML = `<span class="badge ${esc(status)}">${esc(sevLabel(status))}</span><br>
      ${anomalies.length ? anomalies.slice(0,2).map(a=>esc(a)).join(", ") : "Faol anomaliya yo'q"}<br>
      <span style="color:var(--muted); font-size:12px;">🕒 ${fmtTime(data.ts)}</span>`;
}

// ── PREDICTIONS ──
function renderPredictionCard(p, big) {
  const risk = p.risk_level || "LOW";
  const details = p.details || {};
  const forecastHtml = Object.entries(details).map(([metric, f]) => {
    const rows = Object.entries(f.forecast || {}).map(([h, v]) =>
      `<div class="row"><span>${esc(h)}</span><b>${esc(v)}</b></div>`
    ).join("");
    return `<div class="forecast-item">
      <div class="name">${esc(metric)} (hozir: ${esc(f.current)})</div>
      ${rows}
    </div>`;
  }).join("");

  if (big) {
    return `<div class="card ${esc(risk)}">
      <span class="badge ${esc(risk)}">${esc(sevLabel(risk))}</span>
      <div class="summary">${esc(p.summary || "")}</div>
      <div class="forecast-grid">${forecastHtml}</div>
      <div class="card-ts">🕒 ${fmtTime(p.ts)} · keyingi tekshiruv ~${Math.round((p.interval_seconds||0)/60)} daqiqada</div>
    </div>`;
  }
  return `<div class="insight-row ${esc(risk)}" style="margin-top:10px;">
    <span class="badge ${esc(risk)}">${esc(sevLabel(risk))}</span>
    <div>${esc(p.summary || "")}</div>
    <div class="t">🕒 ${fmtTime(p.ts)}</div>
  </div>`;
}

function renderPredictions(items) {
  const fullEl = document.getElementById("predictions-full");
  const homeEl = document.getElementById("home-predictions");
  const dot = document.getElementById("nav-dot-predictions");

  if (!items || items.length === 0) {
    const msg = '<div class="empty">Hali bashorat yo\\'q — yetarli tarix to\\'planishini kutmoqda.</div>';
    fullEl.innerHTML = msg; homeEl.innerHTML = msg;
    return;
  }
  dot.className = "dot-ind " + esc(items[0].risk_level || "LOW");

  fullEl.innerHTML = renderPredictionCard(items[0], true) +
    items.slice(1).map(p => renderPredictionCard(p, false)).join("");

  const risk = items[0].risk_level || "LOW";
  homeEl.innerHTML = `<span class="badge ${esc(risk)}">${esc(sevLabel(risk))}</span><br>
      ${esc(items[0].summary || "")}<br>
      <span style="color:var(--muted); font-size:12px;">🕒 ${fmtTime(items[0].ts)}</span>`;
}

// ── SHIFT REPORTS ──
function renderShiftReports(items) {
  const fullEl = document.getElementById("shift-reports-full");
  const homeEl = document.getElementById("home-shift");

  if (!items || items.length === 0) {
    const msg = '<div class="empty">Hali smena hisoboti yo\\'q.</div>';
    fullEl.innerHTML = msg; homeEl.innerHTML = msg;
    return;
  }
  fullEl.innerHTML = items.map(r => `<div class="panel">
      <div class="sub">🕒 ${fmtTime(r.period_start)} — ${fmtTime(r.period_end)}</div>
      <div class="shift-report">${esc(r.report)}</div>
    </div>`).join("");

  homeEl.innerHTML = `<span style="color:var(--muted); font-size:12px;">🕒 ${fmtTime(items[0].period_start)} — ${fmtTime(items[0].period_end)}</span><br>
      ${esc((items[0].report || "").slice(0, 140))}${(items[0].report || "").length > 140 ? "…" : ""}`;
}

// ── XOM JSON ──
function renderReportsJson(reports) {
  const el = document.getElementById("reports-json-full");
  if (!reports || reports.length === 0) {
    el.innerHTML = '<div class="empty">Hali hisobot yo\\'q.</div>';
    return;
  }
  el.innerHTML = reports.map(r => {
    const meta = fmtTime(r.ts) + (r.model ? "  ·  model: " + r.model : "");
    const jsonText = JSON.stringify(r.payload || {}, null, 2);
    return `<div class="json-block"><div class="json-ts">🕒 ${esc(meta)}</div>${esc(jsonText)}</div>`;
  }).join("");
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + " -> " + res.status);
  return res.json();
}

async function refreshAll() {
  try {
    const [insights, reports, plantState, predictions, shiftReports] = await Promise.all([
      getJSON("/api/insights"),
      getJSON("/api/reports"),
      getJSON("/api/plant-state"),
      getJSON("/api/predictions"),
      getJSON("/api/shift-reports"),
    ]);
    renderAdvisorLatest(insights);
    renderAdvisorHistory(insights);
    renderPlantState(plantState);
    renderPredictions(predictions);
    renderShiftReports(shiftReports);
    renderReportsJson(reports);
    document.getElementById("last-updated").textContent = "so'nggi yangilanish: " + new Date().toLocaleTimeString("uz-UZ", { hour12: false });
  } catch (e) {
    console.error(e);
    document.getElementById("last-updated").textContent = "ulanishda xato — qayta urinilmoqda...";
  }
}

refreshAll();
setInterval(refreshAll, REFRESH_MS);
</script>

</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return DASHBOARD_HTML


if __name__ == "__main__":
    import uvicorn

    init_all_tables()
    print("Interfeys ishga tushdi: http://localhost:5001")
    print("Interaktiv (Swagger) interfeys: http://localhost:5001/docs")
    uvicorn.run(app, host="0.0.0.0", port=5001)