# """
# external_api.py — TIZIMNING INTERFEYSI. ATAYLAB main.py'dan ALOHIDA
# fayl va alohida jarayon sifatida ishga tushiriladi.

# Bu fayl HECH QANDAY ma'lumot yig'ish/tahlil qilish ishini bajarmaydi
# (bu — main.py'ning vazifasi). Bu fayl FAQAT bazani o'qiydi (GET) va
# brauzerda chiroyli ko'rsatadi. Shuning uchun uni istalgan vaqtda
# ochish, yopish mumkin — main.py'da ishlayotgan asosiy quvurga (video
# yozish, AI tahlil) hech qanday ta'sir qilmaydi.

# ISHGA TUSHIRISH (alohida terminalda, main.py bilan bir vaqtda yoki
# undan mustaqil ravishda xohlagan paytda):
#     py external_api.py

# Server manzili:              http://localhost:5001
# Interaktiv (Swagger) hujjat: http://localhost:5001/docs
# """

# from fastapi.responses import HTMLResponse
# from fastapi import FastAPI

# from database import get_connection, init_all_tables

# app = FastAPI(title="SCADA AI Monitoring — Interfeys")


# # ─────────────────────────── RO'YXATLAR (GET, faqat o'qish) ─────────────

# @app.get("/api/reports")
# def list_reports():
#     """vision_reports jadvalidan so'nggi 20 ta yozuv."""
#     conn = get_connection()
#     with conn.cursor() as cur:
#         cur.execute("""
#             SELECT id, ts, video_segment_id, model, payload
#             FROM vision_reports ORDER BY id DESC LIMIT 20
#         """)
#         rows = cur.fetchall()
#     conn.close()
#     return [
#         {"id": r[0], "ts": r[1].isoformat(), "video_segment_id": r[2], "model": r[3], "payload": r[4]}
#         for r in rows
#     ]


# @app.get("/api/insights")
# def list_insights():
#     """AI advisor yozgan so'nggi xulosalarni ko'rish uchun."""
#     conn = get_connection()
#     with conn.cursor() as cur:
#         cur.execute("""
#             SELECT id, ts, severity, summary, trend_analysis, recommendation
#             FROM advisor_insights ORDER BY id DESC LIMIT 5
#         """)
#         rows = cur.fetchall()
#     conn.close()
#     return [
#         {
#             "id": r[0], "ts": r[1].isoformat(), "severity": r[2],
#             "summary": r[3], "trend_analysis": r[4], "recommendation": r[5],
#         }
#         for r in rows
#     ]


# @app.get("/api/videos")
# def list_videos():
#     conn = get_connection()
#     with conn.cursor() as cur:
#         cur.execute("""
#             SELECT id, started_at, ended_at, filepath
#             FROM video_segments ORDER BY id DESC LIMIT 20
#         """)
#         rows = cur.fetchall()
#     conn.close()
#     return [
#         {
#             "id": r[0],
#             "started_at": r[1].isoformat() if r[1] else None,
#             "ended_at": r[2].isoformat() if r[2] else None,
#             "filepath": r[3],
#         }
#         for r in rows
#     ]


# # ─────────────────────────── BOSH SAHIFA (HTML) ─────────────────────────

# DASHBOARD_HTML = """<!DOCTYPE html>
# <html lang="uz">
# <head>
# <meta charset="UTF-8">
# <meta name="viewport" content="width=device-width, initial-scale=1.0">
# <title>SCADA AI Monitoring</title>
# <style>
#   :root {
#     --bg: #0f1115; --panel: #171a21; --panel-2: #1e222b; --border: #2a2f3a;
#     --text: #e6e8eb; --muted: #8b93a3; --accent: #4f8ff7;
#     --green: #2ecc71; --orange: #f39c12; --red: #e74c3c;
#   }
#   * { box-sizing: border-box; }
#   body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); }
#   header { display: flex; align-items: center; justify-content: space-between; padding: 16px 28px; border-bottom: 1px solid var(--border); background: var(--panel); position: sticky; top: 0; z-index: 10; }
#   header h1 { font-size: 18px; margin: 0; font-weight: 600; }
#   .status { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
#   .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
#   @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(46,204,113,.5); } 70% { box-shadow: 0 0 0 8px rgba(46,204,113,0); } 100% { box-shadow: 0 0 0 0 rgba(46,204,113,0); } }
#   main { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }
#   .section-title { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 32px 0 12px; }
#   .advisor-card { border-radius: 12px; padding: 20px 22px; border: 1px solid var(--border); background: var(--panel); border-left: 5px solid var(--muted); }
#   .advisor-card.CRITICAL { border-left-color: var(--red); }
#   .advisor-card.WARNING  { border-left-color: var(--orange); }
#   .advisor-card.NORMAL   { border-left-color: var(--green); }
#   .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: .04em; margin-bottom: 10px; }
#   .badge.CRITICAL { background: rgba(231,76,60,.15); color: var(--red); }
#   .badge.WARNING  { background: rgba(243,156,18,.15); color: var(--orange); }
#   .badge.NORMAL   { background: rgba(46,204,113,.15); color: var(--green); }
#   .advisor-card .summary { font-size: 17px; margin: 4px 0 10px; }
#   .advisor-card .trend, .advisor-card .rec { font-size: 13.5px; color: var(--muted); margin: 4px 0; }
#   .advisor-card .rec b { color: var(--text); }
#   .advisor-ts { font-size: 12px; color: var(--muted); margin-top: 10px; }
#   .insight-list { display: flex; flex-direction: column; gap: 10px; margin-top: 14px; }
#   .insight-row { padding: 10px 14px; background: var(--panel-2); border-radius: 8px; border-left: 3px solid var(--muted); font-size: 13px; }
#   .insight-row.CRITICAL { border-left-color: var(--red); }
#   .insight-row.WARNING  { border-left-color: var(--orange); }
#   .insight-row.NORMAL   { border-left-color: var(--green); }
#   .insight-row .t { color: var(--muted); font-size: 11.5px; }
#   .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; }
#   .panel h3 { margin: 0 0 4px; font-size: 14px; font-weight: 600; }
#   .panel .sub { font-size: 12px; color: var(--muted); margin-bottom: 14px; }
#   .readings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
#   .reading-item { background: var(--panel-2); border-radius: 8px; padding: 8px 10px; }
#   .reading-item .k { font-size: 11px; color: var(--muted); }
#   .reading-item .v { font-size: 14px; font-weight: 600; margin-top: 2px; }
#   .equip-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
#   .pill { font-size: 11.5px; padding: 4px 10px; border-radius: 20px; background: var(--panel-2); color: var(--muted); border: 1px solid var(--border); }
#   .pill.on  { color: var(--green); border-color: rgba(46,204,113,.35); }
#   .pill.off { color: var(--red); border-color: rgba(231,76,60,.35); }
#   .alarms { margin-top: 10px; }
#   .alarm-item { font-size: 12.5px; color: var(--orange); background: rgba(243,156,18,.1); border-radius: 6px; padding: 6px 10px; margin-top: 6px; }
#   .no-alarms { font-size: 12.5px; color: var(--muted); margin-top: 8px; }
#   table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
#   th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }
#   th { color: var(--muted); font-weight: 500; font-size: 11.5px; text-transform: uppercase; }
#   .status-live { color: var(--orange); }
#   .status-done { color: var(--green); }
#   .empty { color: var(--muted); font-size: 13px; padding: 10px 0; }
#   .report-panel { margin-bottom: 14px; }
#   .report-panel .sub { display:flex; justify-content: space-between; align-items:center; }
#   .json-block {
#     background: var(--panel-2);
#     border: 1px solid var(--border);
#     border-radius: 8px;
#     padding: 12px 14px;
#     margin-bottom: 10px;
#     font-family: "Consolas", "Courier New", monospace;
#     font-size: 11.5px;
#     color: #9fd8a0;
#     overflow-x: auto;
#     white-space: pre;
#   }
#   .json-block .json-ts { color: var(--muted); font-family: -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 11.5px; margin-bottom: 6px; }
# </style>
# </head>
# <body>

# <header>
#   <h1>SCADA AI Monitoring — Nazorat Paneli</h1>
#   <div class="status">
#     <span class="dot"></span>
#     <span id="last-updated">yuklanmoqda...</span>
#     &nbsp;|&nbsp;
#     <a href="/docs" style="color:var(--accent); text-decoration:none;">API hujjatlari</a>
#   </div>
# </header>

# <main>
#   <div class="section-title">AI Maslahatchi — joriy xulosa</div>
#   <div id="advisor-latest"><div class="empty">Yuklanmoqda...</div></div>

#   <div class="section-title">So'nggi xulosalar tarixi</div>
#   <div id="advisor-history" class="insight-list"><div class="empty">Yuklanmoqda...</div></div>

#   <div class="section-title">Jonli ma'lumotlar (so'nggi 5 ta hisobot)</div>
#   <div id="reports-list"><div class="empty">Yuklanmoqda...</div></div>

#   <div class="section-title">Xom JSON ma'lumotlar (so'nggi 5 ta)</div>
#   <div id="reports-json-list"><div class="empty">Yuklanmoqda...</div></div>

#   <div class="section-title">Video segmentlar</div>
#   <div class="panel">
#     <table>
#       <thead><tr><th>ID</th><th>Boshlangan</th><th>Tugagan</th><th>Holati</th><th>Fayl</th></tr></thead>
#       <tbody id="videos-table"><tr><td colspan="5" class="empty">Yuklanmoqda...</td></tr></tbody>
#     </table>
#   </div>
# </main>

# <script>
# const REFRESH_MS = 20000;
# const SEV_LABEL = { CRITICAL: "XAVFLI", WARNING: "OGOHLANTIRISH", NORMAL: "NORMAL" };

# function esc(s) {
#   if (s === null || s === undefined) return "";
#   return String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
# }
# function fmtTime(iso) {
#   if (!iso) return "—";
#   return new Date(iso).toLocaleString("uz-UZ", { hour12: false });
# }
# function sevLabel(sev) { return SEV_LABEL[sev] || sev || "NOMA'LUM"; }

# function renderAdvisorLatest(items) {
#   const el = document.getElementById("advisor-latest");
#   if (!items || items.length === 0) {
#     el.innerHTML = '<div class="empty">Hozircha xulosa yo\\'q — AI maslahatchi yetarli tarix to\\'planishini kutmoqda.</div>';
#     return;
#   }
#   const it = items[0];
#   const sev = it.severity || "NORMAL";
#   el.innerHTML = `<div class="advisor-card ${esc(sev)}">
#       <span class="badge ${esc(sev)}">${esc(sevLabel(sev))}</span>
#       <div class="summary">${esc(it.summary || "")}</div>
#       ${it.trend_analysis ? `<div class="trend"><i>Tendentsiya:</i> ${esc(it.trend_analysis)}</div>` : ""}
#       ${it.recommendation ? `<div class="rec"><b>Tavsiya:</b> ${esc(it.recommendation)}</div>` : ""}
#       <div class="advisor-ts">${fmtTime(it.ts)}</div>
#     </div>`;
# }

# function renderAdvisorHistory(items) {
#   const el = document.getElementById("advisor-history");
#   if (!items || items.length <= 1) {
#     el.innerHTML = '<div class="empty">Hali tarix yetarli emas.</div>';
#     return;
#   }
#   el.innerHTML = items.slice(1).map(it => {
#     const sev = it.severity || "NORMAL";
#     return `<div class="insight-row ${esc(sev)}">
#       <span class="badge ${esc(sev)}">${esc(sevLabel(sev))}</span>
#       <div>${esc(it.summary || "")}</div>
#       <div class="t">${fmtTime(it.ts)}</div>
#     </div>`;
#   }).join("");
# }

# function renderOneReportPanel(report) {
#   const payload = report.payload || {};
#   const readings = payload.readings || {};
#   const equipment = payload.equipment_states || {};
#   const alarms = payload.alarms || [];

#   const readingKeys = Object.keys(readings);
#   const readingsHtml = readingKeys.length === 0
#     ? '<div class="empty">O\\'lchov qiymatlari yo\\'q.</div>'
#     : '<div class="readings-grid">' + readingKeys.map(k =>
#         `<div class="reading-item"><div class="k">${esc(k)}</div><div class="v">${esc(readings[k])}</div></div>`
#       ).join("") + "</div>";

#   const equipHtml = Object.keys(equipment).map(k => {
#     const val = String(equipment[k] || "").toUpperCase();
#     const cls = (val.includes("ON") || val.includes("RUNNING") || val.includes("FILTERING")) ? "on" : (val.includes("OFF") || val.includes("STOP")) ? "off" : "";
#     return `<span class="pill ${cls}">${esc(k)}: ${esc(equipment[k])}</span>`;
#   }).join("");

#   const alarmsHtml = alarms.length === 0
#     ? '<div class="no-alarms">Faol alarm yo\\'q</div>'
#     : alarms.map(a => `<div class="alarm-item">⚠ ${esc(a)}</div>`).join("");

#   const meta = fmtTime(report.ts)
#     + (report.model ? "  ·  model: " + report.model : "")
#     + (report.video_segment_id ? "  ·  segment #" + report.video_segment_id : "");

#   return `<div class="panel report-panel">
#     <div class="sub">${meta}</div>
#     ${readingsHtml}
#     <div class="equip-grid">${equipHtml}</div>
#     <div class="alarms">${alarmsHtml}</div>
#   </div>`;
# }

# function renderReportsList(reports) {
#   const el = document.getElementById("reports-list");
#   if (!reports || reports.length === 0) {
#     el.innerHTML = '<div class="empty">Hali hisobot yo\\'q.</div>';
#     return;
#   }
#   el.innerHTML = reports.slice(0, 5).map(renderOneReportPanel).join("");
# }

# function renderReportsJson(reports) {
#   const el = document.getElementById("reports-json-list");
#   if (!reports || reports.length === 0) {
#     el.innerHTML = '<div class="empty">Hali hisobot yo\\'q.</div>';
#     return;
#   }
#   el.innerHTML = reports.slice(0, 5).map(r => {
#     const meta = fmtTime(r.ts) + (r.video_segment_id ? "  ·  segment #" + r.video_segment_id : "");
#     const jsonText = JSON.stringify(r.payload || {}, null, 2);
#     return `<div class="json-block"><div class="json-ts">${esc(meta)}</div>${esc(jsonText)}</div>`;
#   }).join("");
# }

# function renderVideos(items) {
#   const el = document.getElementById("videos-table");
#   if (!items || items.length === 0) {
#     el.innerHTML = '<tr><td colspan="5" class="empty">Hozircha video yo\\'q.</td></tr>';
#     return;
#   }
#   el.innerHTML = items.map(v => {
#     const live = !v.ended_at;
#     return `<tr>
#       <td>${v.id}</td><td>${fmtTime(v.started_at)}</td><td>${v.ended_at ? fmtTime(v.ended_at) : "—"}</td>
#       <td class="${live ? "status-live" : "status-done"}">${live ? "● yozilmoqda" : "✓ yakunlandi"}</td>
#       <td style="max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(v.filepath || "—")}</td>
#     </tr>`;
#   }).join("");
# }

# async function getJSON(url) {
#   const res = await fetch(url);
#   if (!res.ok) throw new Error(url + " -> " + res.status);
#   return res.json();
# }

# async function refreshAll() {
#   try {
#     const [insights, reports, videos] = await Promise.all([
#       getJSON("/api/insights"), getJSON("/api/reports"), getJSON("/api/videos"),
#     ]);
#     renderAdvisorLatest(insights);
#     renderAdvisorHistory(insights);
#     renderReportsList(reports);
#     renderReportsJson(reports);
#     renderVideos(videos);
#     document.getElementById("last-updated").textContent = "so'nggi yangilanish: " + new Date().toLocaleTimeString("uz-UZ", { hour12: false });
#   } catch (e) {
#     console.error(e);
#     document.getElementById("last-updated").textContent = "ulanishda xato — qayta urinilmoqda...";
#   }
# }

# refreshAll();
# setInterval(refreshAll, REFRESH_MS);
# </script>
# </body>
# </html>
# """


# @app.get("/", response_class=HTMLResponse)
# def home():
#     return DASHBOARD_HTML


# if __name__ == "__main__":
#     import uvicorn

#     init_all_tables()
#     print("Interfeys ishga tushdi: http://localhost:5001")
#     print("Interaktiv (Swagger) interfeys: http://localhost:5001/docs")
#     print("\nESLATMA: bu — faqat KO'RISH uchun interfeys. Ma'lumot yig'ish")
#     print("va AI tahlili boshqa terminalda 'py main.py' orqali ishlaydi.")
#     uvicorn.run(app, host="0.0.0.0", port=5001)
















"""
external_api.py — TIZIMNING INTERFEYSI. ATAYLAB main.py'dan ALOHIDA
fayl va alohida jarayon sifatida ishga tushiriladi.

Bu fayl HECH QANDAY ma'lumot yig'ish/tahlil qilish ishini bajarmaydi
(bu — main.py'ning vazifasi). Bu fayl FAQAT bazani o'qiydi (GET) va
brauzerda chiroyli ko'rsatadi. Shuning uchun uni istalgan vaqtda
ochish, yopish mumkin — main.py'da ishlayotgan asosiy quvurga (video
yozish, AI tahlil) hech qanday ta'sir qilmaydi.

ISHGA TUSHIRISH (alohida terminalda, main.py bilan bir vaqtda yoki
undan mustaqil ravishda xohlagan paytda):
    py external_api.py

Server manzili:              http://localhost:5001
Interaktiv (Swagger) hujjat: http://localhost:5001/docs
"""

from fastapi.responses import HTMLResponse
from fastapi import FastAPI

from database import get_connection, init_all_tables

app = FastAPI(title="SCADA AI Monitoring — Interfeys")


# ─────────────────────────── RO'YXATLAR (GET, faqat o'qish) ─────────────

@app.get("/api/reports")
def list_reports():
    """vision_reports jadvalidan so'nggi 20 ta yozuv."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, model, payload
            FROM vision_reports ORDER BY id DESC LIMIT 20
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(), "model": r[2], "payload": r[3]}
        for r in rows
    ]


@app.get("/api/insights")
def list_insights():
    """AI advisor yozgan so'nggi xulosalarni ko'rish uchun."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, severity, summary, trend_analysis, recommendation
            FROM advisor_insights ORDER BY id DESC LIMIT 5
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "ts": r[1].isoformat(), "severity": r[2],
            "summary": r[3], "trend_analysis": r[4], "recommendation": r[5],
        }
        for r in rows
    ]



# ─────────────────────────── BOSH SAHIFA (HTML) ─────────────────────────

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
    --green: #2ecc71; --orange: #f39c12; --red: #e74c3c;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); }
  header { display: flex; align-items: center; justify-content: space-between; padding: 16px 28px; border-bottom: 1px solid var(--border); background: var(--panel); position: sticky; top: 0; z-index: 10; }
  header h1 { font-size: 18px; margin: 0; font-weight: 600; }
  .status { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(46,204,113,.5); } 70% { box-shadow: 0 0 0 8px rgba(46,204,113,0); } 100% { box-shadow: 0 0 0 0 rgba(46,204,113,0); } }
  main { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }
  .section-title { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 32px 0 12px; }
  .advisor-card { border-radius: 12px; padding: 20px 22px; border: 1px solid var(--border); background: var(--panel); border-left: 5px solid var(--muted); }
  .advisor-card.CRITICAL { border-left-color: var(--red); }
  .advisor-card.WARNING  { border-left-color: var(--orange); }
  .advisor-card.NORMAL   { border-left-color: var(--green); }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: .04em; margin-bottom: 10px; }
  .badge.CRITICAL { background: rgba(231,76,60,.15); color: var(--red); }
  .badge.WARNING  { background: rgba(243,156,18,.15); color: var(--orange); }
  .badge.NORMAL   { background: rgba(46,204,113,.15); color: var(--green); }
  .advisor-card .summary { font-size: 17px; margin: 4px 0 10px; }
  .advisor-card .trend, .advisor-card .rec { font-size: 13.5px; color: var(--muted); margin: 4px 0; }
  .advisor-card .rec b { color: var(--text); }
  .advisor-ts { font-size: 12px; color: var(--muted); margin-top: 10px; }
  .insight-list { display: flex; flex-direction: column; gap: 10px; margin-top: 14px; }
  .insight-row { padding: 10px 14px; background: var(--panel-2); border-radius: 8px; border-left: 3px solid var(--muted); font-size: 13px; }
  .insight-row.CRITICAL { border-left-color: var(--red); }
  .insight-row.WARNING  { border-left-color: var(--orange); }
  .insight-row.NORMAL   { border-left-color: var(--green); }
  .insight-row .t { color: var(--muted); font-size: 11.5px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; }
  .panel h3 { margin: 0 0 4px; font-size: 14px; font-weight: 600; }
  .panel .sub { font-size: 12px; color: var(--muted); margin-bottom: 14px; }
  .readings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
  .reading-item { background: var(--panel-2); border-radius: 8px; padding: 8px 10px; }
  .reading-item .k { font-size: 11px; color: var(--muted); }
  .reading-item .v { font-size: 14px; font-weight: 600; margin-top: 2px; }
  .equip-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .pill { font-size: 11.5px; padding: 4px 10px; border-radius: 20px; background: var(--panel-2); color: var(--muted); border: 1px solid var(--border); }
  .pill.on  { color: var(--green); border-color: rgba(46,204,113,.35); }
  .pill.off { color: var(--red); border-color: rgba(231,76,60,.35); }
  .alarms { margin-top: 10px; }
  .alarm-item { font-size: 12.5px; color: var(--orange); background: rgba(243,156,18,.1); border-radius: 6px; padding: 6px 10px; margin-top: 6px; }
  .no-alarms { font-size: 12.5px; color: var(--muted); margin-top: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; font-size: 11.5px; text-transform: uppercase; }
  .status-live { color: var(--orange); }
  .status-done { color: var(--green); }
  .empty { color: var(--muted); font-size: 13px; padding: 10px 0; }
  .report-panel { margin-bottom: 14px; }
  .report-panel .sub { display:flex; justify-content: space-between; align-items:center; }
  .json-block {
    background: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11.5px;
    color: #9fd8a0;
    overflow-x: auto;
    white-space: pre;
  }
  .json-block .json-ts { color: var(--muted); font-family: -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 11.5px; margin-bottom: 6px; }
</style>
</head>
<body>

<header>
  <h1>SCADA AI Monitoring — Nazorat Paneli</h1>
  <div class="status">
    <span class="dot"></span>
    <span id="last-updated">yuklanmoqda...</span>
    &nbsp;|&nbsp;
    <a href="/docs" style="color:var(--accent); text-decoration:none;">API hujjatlari</a>
  </div>
</header>

<main>
  <div class="section-title">AI Maslahatchi — joriy xulosa</div>
  <div id="advisor-latest"><div class="empty">Yuklanmoqda...</div></div>

  <div class="section-title">So'nggi xulosalar tarixi</div>
  <div id="advisor-history" class="insight-list"><div class="empty">Yuklanmoqda...</div></div>

  <div class="section-title">Jonli ma'lumotlar (so'nggi 5 ta hisobot)</div>
  <div id="reports-list"><div class="empty">Yuklanmoqda...</div></div>

  <div class="section-title">Xom JSON ma'lumotlar (so'nggi 5 ta)</div>
  <div id="reports-json-list"><div class="empty">Yuklanmoqda...</div></div>
</main>

<script>
const REFRESH_MS = 20000;
const SEV_LABEL = { CRITICAL: "XAVFLI", WARNING: "OGOHLANTIRISH", NORMAL: "NORMAL" };

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}
function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uz-UZ", { hour12: false });
}
function sevLabel(sev) { return SEV_LABEL[sev] || sev || "NOMA'LUM"; }

function renderAdvisorLatest(items) {
  const el = document.getElementById("advisor-latest");
  if (!items || items.length === 0) {
    el.innerHTML = '<div class="empty">Hozircha xulosa yo\\'q — AI maslahatchi yetarli tarix to\\'planishini kutmoqda.</div>';
    return;
  }
  const it = items[0];
  const sev = it.severity || "NORMAL";
  el.innerHTML = `<div class="advisor-card ${esc(sev)}">
      <span class="badge ${esc(sev)}">${esc(sevLabel(sev))}</span>
      <div class="summary">${esc(it.summary || "")}</div>
      ${it.trend_analysis ? `<div class="trend"><i>Tendentsiya:</i> ${esc(it.trend_analysis)}</div>` : ""}
      ${it.recommendation ? `<div class="rec"><b>Tavsiya:</b> ${esc(it.recommendation)}</div>` : ""}
      <div class="advisor-ts">${fmtTime(it.ts)}</div>
    </div>`;
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
      <div class="t">${fmtTime(it.ts)}</div>
    </div>`;
  }).join("");
}

function renderOneReportPanel(report) {
  const payload = report.payload || {};
  const readings = payload.readings || {};
  const equipment = payload.equipment_states || {};
  const alarms = payload.alarms || [];

  const readingKeys = Object.keys(readings);
  const readingsHtml = readingKeys.length === 0
    ? '<div class="empty">O\\'lchov qiymatlari yo\\'q.</div>'
    : '<div class="readings-grid">' + readingKeys.map(k =>
        `<div class="reading-item"><div class="k">${esc(k)}</div><div class="v">${esc(readings[k])}</div></div>`
      ).join("") + "</div>";

  const equipHtml = Object.keys(equipment).map(k => {
    const val = String(equipment[k] || "").toUpperCase();
    const cls = (val.includes("ON") || val.includes("RUNNING") || val.includes("FILTERING")) ? "on" : (val.includes("OFF") || val.includes("STOP")) ? "off" : "";
    return `<span class="pill ${cls}">${esc(k)}: ${esc(equipment[k])}</span>`;
  }).join("");

  const alarmsHtml = alarms.length === 0
    ? '<div class="no-alarms">Faol alarm yo\\'q</div>'
    : alarms.map(a => `<div class="alarm-item">⚠ ${esc(a)}</div>`).join("");

  const meta = fmtTime(report.ts)
    + (report.model ? "  ·  model: " + report.model : "");

  return `<div class="panel report-panel">
    <div class="sub">${meta}</div>
    ${readingsHtml}
    <div class="equip-grid">${equipHtml}</div>
    <div class="alarms">${alarmsHtml}</div>
  </div>`;
}

function renderReportsList(reports) {
  const el = document.getElementById("reports-list");
  if (!reports || reports.length === 0) {
    el.innerHTML = '<div class="empty">Hali hisobot yo\\'q.</div>';
    return;
  }
  el.innerHTML = reports.slice(0, 5).map(renderOneReportPanel).join("");
}

function renderReportsJson(reports) {
  const el = document.getElementById("reports-json-list");
  if (!reports || reports.length === 0) {
    el.innerHTML = '<div class="empty">Hali hisobot yo\\'q.</div>';
    return;
  }
  el.innerHTML = reports.slice(0, 5).map(r => {
    const meta = fmtTime(r.ts);
    const jsonText = JSON.stringify(r.payload || {}, null, 2);
    return `<div class="json-block"><div class="json-ts">${esc(meta)}</div>${esc(jsonText)}</div>`;
  }).join("");
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + " -> " + res.status);
  return res.json();
}

async function refreshAll() {
  try {
    const [insights, reports] = await Promise.all([
      getJSON("/api/insights"), getJSON("/api/reports"),
    ]);
    renderAdvisorLatest(insights);
    renderAdvisorHistory(insights);
    renderReportsList(reports);
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
    print("\nESLATMA: bu — faqat KO'RISH uchun interfeys. Ma'lumot yig'ish")
    print("va AI tahlili boshqa terminalda 'py main.py' orqali ishlaydi.")
    uvicorn.run(app, host="0.0.0.0", port=5001)