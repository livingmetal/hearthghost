"""Loopback-only, read-only operator dashboard for HearthGhost Core status.

This surface intentionally has no write routes and no administrator authority. It
renders only the already-sanitized ``CoreComponents.status()`` document. Remote
administration must remain behind a separately authenticated boundary.
"""

from __future__ import annotations

import ipaddress
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol


class StatusSource(Protocol):
    def status(self) -> dict[str, object]: ...


DASHBOARD_HTML = b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HearthGhost Server</title>
  <link rel="stylesheet" href="/dashboard.css">
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">HearthGhost</p>
        <h1>Server overview</h1>
        <p class="subtitle">Read-only local operator surface</p>
      </div>
      <div class="health" data-overall>Loading</div>
    </header>

    <section class="cards" aria-label="Core summary">
      <article class="card">
        <span class="label">Service</span>
        <strong data-service>HearthGhost Core</strong>
        <span data-service-state>Loading</span>
      </article>
      <article class="card">
        <span class="label">Storage</span>
        <strong data-storage>Unknown</strong>
        <span>Configured runtime backend</span>
      </article>
      <article class="card">
        <span class="label">Contracts</span>
        <strong data-contracts>0</strong>
        <span>Loaded versioned contracts</span>
      </article>
      <article class="card">
        <span class="label">Refresh</span>
        <strong data-updated>Waiting</strong>
        <span>Local status only</span>
      </article>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Boundaries</p>
          <h2>Security and runtime state</h2>
        </div>
        <button type="button" data-refresh>Refresh</button>
      </div>
      <div class="boundary-grid" data-boundaries></div>
    </section>

    <section class="panel">
      <p class="eyebrow">Readiness</p>
      <h2>Why Core is not ready</h2>
      <ul class="reasons" data-reasons></ul>
    </section>

    <footer>
      No secrets, memory text, TODO text, reminder content, private keys, or DSNs are exposed here.
    </footer>
  </main>
  <script src="/dashboard.js" defer></script>
</body>
</html>
"""

DASHBOARD_CSS = b""":root{color:#edf3ef;background:#0b1110;font-family:system-ui,sans-serif;color-scheme:dark}*{box-sizing:border-box}body{margin:0;min-width:320px;min-height:100vh;background:radial-gradient(circle at 20% 0,#19322b 0,transparent 34rem),#0b1110}.shell{width:min(1120px,calc(100% - 2rem));margin:auto;padding:2rem 0 4rem}.hero{display:flex;justify-content:space-between;gap:2rem;align-items:end;margin-bottom:1.5rem}.eyebrow{margin:0 0 .35rem;color:#95b9aa;font-size:.75rem;font-weight:750;letter-spacing:.12em;text-transform:uppercase}h1,h2{margin:0}h1{font-size:clamp(2rem,6vw,4.5rem);line-height:.95;letter-spacing:-.045em}h2{font-size:1.15rem}.subtitle{color:#9eb0a9}.health{padding:.55rem .8rem;border:1px solid #355148;border-radius:999px;color:#b9d8ca;background:#111d1a}.health[data-state=ready]{border-color:#5b8f7b}.health[data-state=degraded]{border-color:#8d7551;color:#dac59d}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;margin-bottom:.75rem}.card,.panel{border:1px solid #263b35;background:rgba(15,25,23,.86);box-shadow:0 1rem 3rem rgba(0,0,0,.18)}.card{display:grid;gap:.35rem;min-height:8rem;padding:1rem;border-radius:1.1rem}.card strong{font-size:1.15rem}.card span:last-child{color:#879a93;font-size:.78rem}.label{color:#9db8ad;font-size:.72rem;text-transform:uppercase;letter-spacing:.09em}.panel{margin-top:.75rem;padding:1.1rem;border-radius:1.1rem}.panel-heading{display:flex;justify-content:space-between;align-items:center;gap:1rem}.panel button{border:1px solid #456258;border-radius:.75rem;background:#bad8cc;color:#12211d;padding:.55rem .8rem;font-weight:700}.boundary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;margin-top:1rem}.boundary{display:grid;gap:.2rem;padding:.75rem;border:1px solid #293e38;border-radius:.8rem;background:#0c1513}.boundary-name{color:#9cb5ab;font-size:.76rem}.boundary-value{overflow-wrap:anywhere}.reasons{margin:.8rem 0 0;padding-left:1.2rem;color:#c9d6d1}.reasons .ready{list-style:none;margin-left:-1.2rem;color:#9ec6b5}footer{margin-top:1rem;color:#70847c;font-size:.75rem}@media(max-width:800px){.hero{align-items:start;flex-direction:column}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.boundary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:480px){.shell{width:min(100% - 1rem,1120px);padding-top:1rem}.cards,.boundary-grid{grid-template-columns:1fr}}
"""

DASHBOARD_JS = b"""'use strict';
const q=(s)=>document.querySelector(s);
const text=(s,v)=>{const e=q(s);if(e)e.textContent=String(v)};
function render(data){
  const status=typeof data?.status==='string'?data.status:'unknown';
  const overall=q('[data-overall]');
  if(overall){overall.textContent=status;overall.dataset.state=status;}
  text('[data-service]',data?.service??'unknown');
  text('[data-service-state]',status);
  text('[data-storage]',data?.storage??'unknown');
  text('[data-contracts]',Number.isInteger(data?.contracts_loaded)?data.contracts_loaded:0);
  text('[data-updated]',new Date().toLocaleTimeString());
  const boundaries=q('[data-boundaries]');
  if(boundaries){
    boundaries.replaceChildren();
    const source=data?.boundaries&&typeof data.boundaries==='object'?data.boundaries:{};
    for(const [name,value] of Object.entries(source).sort(([a],[b])=>a.localeCompare(b))){
      const card=document.createElement('div');card.className='boundary';
      const n=document.createElement('span');n.className='boundary-name';n.textContent=name.replaceAll('_',' ');
      const v=document.createElement('strong');v.className='boundary-value';v.textContent=String(value);
      card.append(n,v);boundaries.append(card);
    }
  }
  const reasons=q('[data-reasons]');
  if(reasons){
    reasons.replaceChildren();
    const items=Array.isArray(data?.readiness_reasons)?data.readiness_reasons:[];
    if(items.length===0){const li=document.createElement('li');li.className='ready';li.textContent='No readiness blockers reported.';reasons.append(li);}
    else for(const reason of items){const li=document.createElement('li');li.textContent=String(reason);reasons.append(li);}
  }
}
async function refresh(){
  try{const response=await fetch('/api/status',{cache:'no-store',credentials:'same-origin'});if(!response.ok)throw new Error('status unavailable');render(await response.json());}
  catch{const overall=q('[data-overall]');if(overall){overall.textContent='unavailable';overall.dataset.state='degraded';}}
}
q('[data-refresh]')?.addEventListener('click',()=>void refresh());
void refresh();
setInterval(()=>void refresh(),5000);
"""


class AdminDashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8
    allow_reuse_address = False

    def __init__(self, server_address: tuple[str, int], status_source: StatusSource) -> None:
        _require_loopback(server_address[0])
        self.status_source = status_source
        super().__init__(server_address, _handler())


def _handler() -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        server: AdminDashboardServer
        server_version = "HearthGhostDashboard"
        sys_version = ""

        def do_GET(self) -> None:
            path = self.path.partition("?")[0]
            if path in {"/", "/admin"}:
                self._send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", DASHBOARD_HTML)
                return
            if path == "/dashboard.css":
                self._send_bytes(HTTPStatus.OK, "text/css; charset=utf-8", DASHBOARD_CSS)
                return
            if path == "/dashboard.js":
                self._send_bytes(HTTPStatus.OK, "text/javascript; charset=utf-8", DASHBOARD_JS)
                return
            if path == "/api/status":
                payload = json.dumps(
                    self.server.status_source.status(), separators=(",", ":"), sort_keys=True
                ).encode("utf-8")
                self._send_bytes(HTTPStatus.OK, "application/json", payload)
                return
            self._send_bytes(
                HTTPStatus.NOT_FOUND,
                "application/json",
                b'{"status":"not_found"}',
            )

        def do_POST(self) -> None:
            self._send_bytes(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "application/json",
                b'{"status":"method_not_allowed"}',
            )

        def do_PUT(self) -> None:
            self.do_POST()

        def do_PATCH(self) -> None:
            self.do_POST()

        def do_DELETE(self) -> None:
            self.do_POST()

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_bytes(self, status: HTTPStatus, content_type: str, payload: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

    return DashboardHandler


def _require_loopback(address: str) -> None:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise ValueError("admin dashboard requires a literal loopback address") from error
    if not parsed.is_loopback:
        raise ValueError("admin dashboard may bind only to loopback")
