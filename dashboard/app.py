"""SETU control-room dashboard — dependency-free (stdlib http.server).

Renders the operational views a control room needs:
  * metrics strip (cross-center reach, no-name matches, dedup)
  * open cases (missing / found streams)
  * match queue (high-confidence pairs awaiting HUMAN verification, with the
    weight-grounded explanation — the agent proposes, the human disposes)
  * dedup view (suspected duplicate reports of the same person)
  * hotspot heatmap (cases by zone, for predictive pre-positioning)
  * PA console (generate a zone-targeted, own-language script in one click)

Run:  python -m dashboard.app   then open http://localhost:8000

This is a demo UI. It seeds an in-memory store from the synthetic dataset and a
few planted cross-center matches so the queue is populated on first load.
"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from data.generate_dataset import generate, stats
from setu import pa, proactive
from setu.agent import explain_candidate, run_match
from setu.matching import cascade, dedup
from setu.schema import RECORD_FOUND, RECORD_MISSING
from setu.store import Store

# ---- one shared in-memory node for the demo dashboard ---------------------
STORE = Store("central_control")
DS = generate(400, seed=7)  # smaller set keeps the dashboard snappy
for _ck, _rec in DS.records:
    STORE.put_person(_rec)

_QUEUE: list[dict] = []  # populated lazily from rematch


def _refresh_queue():
    _QUEUE.clear()
    persons = STORE.all_persons()
    seen = set()
    for q in [r for r in persons if r.record_type == RECORD_MISSING][:120]:
        cs = cascade.search_candidates(q, persons, limit=1)
        for c in cascade.queue_candidates(cs):
            key = tuple(sorted((q.person_record_id, c.record.person_record_id)))
            if key in seen:
                continue
            seen.add(key)
            _QUEUE.append({
                "query": q, "cand": c.record, "c": c,
                "explanation": explain_candidate(q, c),
            })


_refresh_queue()


# ---- tiny HTML helpers ----------------------------------------------------
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>SETU — Control Room</title>
<style>
 body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:0;background:#0f1220;color:#e7e9f3}}
 header{{background:#161a2e;padding:14px 22px;border-bottom:1px solid #2a3052}}
 h1{{margin:0;font-size:20px;letter-spacing:.5px}}
 .tag{{color:#8b93c0;font-size:12px}}
 .wrap{{padding:18px 22px;display:grid;gap:18px}}
 .metrics{{display:flex;gap:14px;flex-wrap:wrap}}
 .m{{background:#1b2040;border:1px solid #2a3052;border-radius:10px;padding:12px 16px;min-width:150px}}
 .m b{{font-size:22px;display:block}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
 .card{{background:#161a2e;border:1px solid #2a3052;border-radius:12px;padding:16px}}
 .card h2{{margin:0 0 10px;font-size:15px;color:#aeb6e8}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 td,th{{text-align:left;padding:6px 8px;border-bottom:1px solid #232847;vertical-align:top}}
 .pill{{padding:2px 8px;border-radius:20px;font-size:11px}}
 .warm{{background:#3a2f12;color:#f3d27a}} .queue{{background:#123a1e;color:#7af3a0}}
 .noname{{background:#3a1224;color:#f37ab0}}
 .bar{{height:10px;background:#5566dd;border-radius:6px}}
 pre{{white-space:pre-wrap;background:#10132a;padding:10px;border-radius:8px;font-size:12px;color:#cfd6ff}}
 form{{display:flex;gap:8px;flex-wrap:wrap;align-items:end}}
 select,input,button{{background:#10132a;color:#e7e9f3;border:1px solid #2a3052;border-radius:8px;padding:7px 9px}}
 button{{background:#3447c9;cursor:pointer}} button:hover{{background:#4256e0}}
 .rule{{font-size:12px;color:#8b93c0;margin-top:6px}}
</style></head><body>
<header><h1>🌉 SETU — Reunification Control Room
<span class="tag">Nashik–Trimbakeshwar Kumbh 2027 · SYNTHETIC DEMO DATA</span></h1></header>
<div class="wrap">
 <div class="metrics">{metrics}</div>
 <div class="grid">
  <div class="card"><h2>🧭 Match queue — agent proposes, human disposes</h2>
   <div class="rule">No match score can confirm a handover. A human verifies the
   family bond before any reunion.</div>{queue}</div>
  <div class="card"><h2>📣 PA console — zone-targeted, own-language</h2>{pa_console}</div>
 </div>
 <div class="grid">
  <div class="card"><h2>🔁 Dedup view — suspected duplicate reports</h2>{dedup}</div>
  <div class="card"><h2>🗺️ Hotspot heatmap — cases by zone</h2>{heatmap}</div>
 </div>
 <div class="card"><h2>📋 Open cases</h2>{cases}</div>
</div></body></html>"""


def render_metrics() -> str:
    s = stats(DS)
    persons = STORE.all_persons()
    no_name_q = sum(1 for item in _QUEUE if not item["c"].score_obj.name_present)
    cards = [
        ("Open records", len(persons)),
        ("% elderly (61+)", f"{s['pct_elderly']}%"),
        ("% no name", f"{s['pct_no_name']}%"),
        ("Languages", s["languages"]),
        ("In match queue", len(_QUEUE)),
        ("Queued w/o name", no_name_q),
    ]
    return "".join(f'<div class="m"><b>{esc(v)}</b>{esc(k)}</div>' for k, v in cards)


def render_queue() -> str:
    if not _QUEUE:
        return "<p class='tag'>queue empty</p>"
    rows = []
    for i, item in enumerate(_QUEUE[:8]):
        c = item["c"]
        nn = "" if c.score_obj.name_present else "<span class='pill noname'>no-name match</span>"
        rows.append(
            f"<tr><td>{c.total_weight:.1f} bits<br>"
            f"<span class='pill queue'>{esc(c.disposition)}</span> {nn}</td>"
            f"<td><pre>{esc(item['explanation'])}</pre></td></tr>")
    return f"<table><tr><th>Score</th><th>Why (grounded in match weights)</th></tr>{''.join(rows)}</table>"


def render_dedup() -> str:
    persons = STORE.all_persons()
    pairs = dedup.find_duplicates(persons)[:8]
    if not pairs:
        return "<p class='tag'>no duplicates detected</p>"
    rows = []
    for p in pairs:
        rows.append(
            f"<tr><td>{p.total_weight:.1f} bits</td>"
            f"<td>{esc(p.a.origin_domain)} ↔ {esc(p.b.origin_domain)}<br>"
            f"<span class='tag'>{esc(p.a.full_name or 'no name')} · "
            f"{esc(p.a.last_seen_zone)}</span></td></tr>")
    return f"<table><tr><th>Score</th><th>Same person, two centers</th></tr>{''.join(rows)}</table>"


def render_heatmap() -> str:
    hot = proactive.predict_hotspots(STORE.all_persons(), top=10)
    if not hot:
        return "<p class='tag'>no data</p>"
    mx = max(h["cases"] for h in hot) or 1
    rows = []
    for h in hot:
        w = int(100 * h["cases"] / mx)
        rows.append(
            f"<tr><td>{esc(h['zone'])}</td>"
            f"<td><div class='bar' style='width:{w}%'></div></td>"
            f"<td>{h['cases']}</td></tr>")
    return f"<table>{''.join(rows)}</table>"


def render_cases() -> str:
    persons = STORE.all_persons()[:25]
    rows = []
    for r in persons:
        cls = "noname" if not r.full_name else ("queue" if r.record_type == RECORD_FOUND else "warm")
        rows.append(
            f"<tr><td>{esc(r.person_record_id.split('/')[-1])}</td>"
            f"<td>{esc(r.record_type)}</td>"
            f"<td>{esc(r.full_name or '—')}</td>"
            f"<td>{esc(r.age_band)}</td><td>{esc(r.language)}</td>"
            f"<td>{esc(r.home_state)}</td><td>{esc(r.last_seen_zone)}</td>"
            f"<td><span class='pill {cls}'>{esc(r.status)}</span></td></tr>")
    head = ("<tr><th>id</th><th>type</th><th>name</th><th>age</th><th>lang</th>"
            "<th>state</th><th>zone</th><th>status</th></tr>")
    return f"<table>{head}{''.join(rows)}</table>"


def render_pa_console(result: str = "") -> str:
    from setu.config import LANGUAGES, ZONES
    langs = "".join(f"<option value='{l}'>{LANGUAGES[l]['name']}</option>"
                    for l in LANGUAGES)
    zones = "".join(f"<option value='{z}'>{z}</option>" for z in ZONES)
    form = f"""<form method="get" action="/pa">
      <label>Zone<br><select name="zone">{zones}</select></label>
      <label>Language<br><select name="language">{langs}</select></label>
      <label>Age band<br><input name="age_band" value="61-75"></label>
      <label>Home state<br><input name="home_state" value="Bihar"></label>
      <label>Name (optional)<br><input name="name" placeholder="leave blank"></label>
      <button type="submit">Generate PA script</button>
    </form>"""
    return form + (f"<pre>{esc(result)}</pre>" if result else "")


def render_page(pa_result: str = "") -> str:
    return PAGE.format(
        metrics=render_metrics(), queue=render_queue(),
        pa_console=render_pa_console(pa_result), dedup=render_dedup(),
        heatmap=render_heatmap(), cases=render_cases())


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: str, ctype="text/html"):
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(render_page())
        elif parsed.path == "/api/metrics":
            self._send(json.dumps(stats(DS)), "application/json")
        elif parsed.path == "/pa":
            q = parse_qs(parsed.query)
            script = pa.generate_pa_script(
                zone=q.get("zone", ["ramkund"])[0],
                language=q.get("language", ["hindi"])[0],
                age_band=q.get("age_band", ["61-75"])[0],
                home_state=q.get("home_state", ["Bihar"])[0],
                name=(q.get("name", [""])[0] or None))
            result = (f"PA locale: {script.pa_locale}  (templated={script.templated})\n\n"
                      f"{script.native_text}\n\n{script.announcer_latin}")
            self._send(render_page(result))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):  # quiet
        pass


def main(port: int = 8000):
    print(f"SETU control room on http://localhost:{port}  (Ctrl-C to stop)")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
