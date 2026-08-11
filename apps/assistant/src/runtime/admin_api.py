"""Loopback-only authenticated administrator API and memory-only browser console."""

from __future__ import annotations

import ipaddress
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import UUID

from apps.assistant.src.modules.capability_administration import (
    AdvertisementAdministrationRequest,
    CapabilityAdvertisementAdministration,
)
from apps.assistant.src.modules.node_administration import (
    AdministrationAction,
    AdministrationRequest,
    NodeAdministration,
)
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    IDENTIFIER_PATTERN,
    CapabilityAdvertisement,
    NodeTrustState,
)
from apps.assistant.src.runtime.admin_auth import AdministratorToken


MAX_BODY_BYTES = 16 * 1024
MAX_ADVERTISEMENTS = 32


class AdminApiServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4
    allow_reuse_address = False

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        token: AdministratorToken,
        admin_context: object,
        node_administration: NodeAdministration,
        registry: object,
        advertisement_administration: CapabilityAdvertisementAdministration,
    ) -> None:
        _require_loopback(server_address[0])
        if not isinstance(token, AdministratorToken):
            raise TypeError("administrator token is required")
        self.token = token
        self.admin_context = admin_context
        self.node_administration = node_administration
        self.registry = registry
        self.advertisement_administration = advertisement_administration
        super().__init__(server_address, _handler())


def _handler() -> type[BaseHTTPRequestHandler]:
    class AdminHandler(BaseHTTPRequestHandler):
        server: AdminApiServer
        server_version = "HearthGhostAdmin"
        sys_version = ""

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.query or parsed.fragment:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "malformed_request"})
                return
            if parsed.path == "/":
                self._html(_ADMIN_HTML)
                return
            if parsed.path == "/admin.js":
                self._javascript(_ADMIN_JS)
                return
            if not self._authenticated():
                self._unauthorized()
                return
            node_id = _node_path(parsed.path)
            if node_id is None:
                self._json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
                return
            self._get_node(node_id)

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.query or parsed.fragment:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "malformed_request"})
                return
            if not self._authenticated():
                self._discard_bounded_body()
                self._unauthorized()
                return
            route = _mutation_path(parsed.path)
            if route is None:
                self._discard_bounded_body()
                self._json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
                return
            document = self._read_json_body()
            if document is None:
                return
            node_id, operation = route
            if operation == "administration":
                self._administer_node(node_id, document)
            else:
                self._replace_advertisements(node_id, document)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _authenticated(self) -> bool:
            return self.server.token.accepts_authorization_header(
                self.headers.get("Authorization")
            )

        def _unauthorized(self) -> None:
            self._json(
                HTTPStatus.UNAUTHORIZED,
                {"status": "unauthorized"},
                extra_headers=(("WWW-Authenticate", 'Bearer realm="hearthghost-admin"'),),
            )

        def _get_node(self, node_id: str) -> None:
            try:
                admin_record = self.server.registry.get_node(node_id)
                gateway_record = self.server.registry.get(node_id)
            except Exception:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "state_unavailable"})
                return
            if admin_record is None or gateway_record is None:
                self._json(HTTPStatus.NOT_FOUND, {"status": "not_found"})
                return
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "node": {
                        "node_id": admin_record.node_id,
                        "trust_state": admin_record.trust_state.value,
                        "revision": admin_record.revision,
                        "granted_capabilities": sorted(admin_record.granted_capabilities),
                        "advertised_capabilities": [
                            {
                                "name": item.name,
                                "local_authorization_required": item.local_authorization_required,
                            }
                            for item in gateway_record.advertised_capabilities
                        ],
                        "enrolled_at": admin_record.enrolled_at.isoformat(),
                        "updated_at": admin_record.updated_at.isoformat(),
                    },
                },
            )

        def _administer_node(self, node_id: str, document: object) -> None:
            request = _parse_administration_document(node_id, document)
            if request is None:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "malformed_request"})
                return
            result = self.server.node_administration.administer(
                self.server.admin_context,
                request,
            )
            status = HTTPStatus.OK if result.succeeded else _administration_status(result.reason.value)
            body: dict[str, object] = {
                "status": "ok" if result.succeeded else "denied",
                "reason": result.reason.value,
                "changed": result.changed,
                "idempotent": result.idempotent,
            }
            if result.record is not None:
                body["node"] = _public_administration_record(result.record)
            self._json(status, body)

        def _replace_advertisements(self, node_id: str, document: object) -> None:
            request = _parse_advertisement_document(node_id, document)
            if request is None:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "malformed_request"})
                return
            result = self.server.advertisement_administration.replace(
                self.server.admin_context,
                request,
            )
            status = HTTPStatus.OK if result.succeeded else _advertisement_status(result.reason)
            self._json(
                status,
                {
                    "status": "ok" if result.succeeded else "denied",
                    "reason": result.reason,
                    "advertised_capabilities": [
                        {
                            "name": item.name,
                            "local_authorization_required": item.local_authorization_required,
                        }
                        for item in result.advertisements
                    ],
                },
            )

        def _read_json_body(self) -> object | None:
            content_type = self.headers.get("Content-Type", "").partition(";")[0].strip().lower()
            if content_type != "application/json":
                self._discard_bounded_body()
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"status": "json_required"})
                return None
            if self.headers.get("Transfer-Encoding") is not None:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "chunked_body_not_supported"})
                return None
            length_value = self.headers.get("Content-Length")
            try:
                length = int(length_value) if length_value is not None else -1
            except ValueError:
                length = -1
            if length < 2:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "body_required"})
                return None
            if length > MAX_BODY_BYTES:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"status": "body_too_large"})
                return None
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"status": "invalid_json"})
                return None

        def _discard_bounded_body(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return
            if 0 < length <= MAX_BODY_BYTES:
                self.rfile.read(length)

        def _json(
            self,
            status: HTTPStatus,
            body: dict[str, object],
            *,
            extra_headers: tuple[tuple[str, str], ...] = (),
        ) -> None:
            payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            for name, value in extra_headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(payload)

        def _html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(payload)

        def _javascript(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

    return AdminHandler


def _parse_administration_document(
    node_id: str,
    document: object,
) -> AdministrationRequest | None:
    if not isinstance(document, dict):
        return None
    base = {"operation_id", "correlation_id", "action", "expected_revision"}
    action_value = document.get("action")
    try:
        action = AdministrationAction(action_value)
    except (TypeError, ValueError):
        return None
    expected = set(base)
    trust_state = None
    capability = None
    if action is AdministrationAction.SET_TRUST:
        expected.add("trust_state")
        try:
            trust_state = NodeTrustState(document.get("trust_state"))
        except (TypeError, ValueError):
            return None
    elif action in {AdministrationAction.GRANT_CAPABILITY, AdministrationAction.REVOKE_CAPABILITY}:
        expected.add("capability")
        capability = document.get("capability")
        if not isinstance(capability, str) or CAPABILITY_PATTERN.fullmatch(capability) is None:
            return None
    if set(document) != expected:
        return None
    operation_id = document.get("operation_id")
    correlation_id = document.get("correlation_id")
    expected_revision = document.get("expected_revision")
    if (
        not _canonical_uuid(operation_id)
        or not _printable_correlation(correlation_id)
        or not isinstance(expected_revision, int)
        or isinstance(expected_revision, bool)
        or expected_revision < 0
    ):
        return None
    return AdministrationRequest(
        operation_id=operation_id,
        correlation_id=correlation_id,
        action=action,
        node_id=node_id,
        expected_revision=expected_revision,
        trust_state=trust_state,
        capability=capability,
    )


def _parse_advertisement_document(
    node_id: str,
    document: object,
) -> AdvertisementAdministrationRequest | None:
    if not isinstance(document, dict) or set(document) != {
        "correlation_id",
        "expected_node_revision",
        "advertisements",
    }:
        return None
    correlation_id = document.get("correlation_id")
    revision = document.get("expected_node_revision")
    values = document.get("advertisements")
    if (
        not _printable_correlation(correlation_id)
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision <= 0
        or not isinstance(values, list)
        or len(values) > MAX_ADVERTISEMENTS
    ):
        return None
    advertisements: list[CapabilityAdvertisement] = []
    names: set[str] = set()
    for value in values:
        if not isinstance(value, dict) or set(value) != {"name", "local_authorization_required"}:
            return None
        name = value.get("name")
        local = value.get("local_authorization_required")
        if (
            not isinstance(name, str)
            or CAPABILITY_PATTERN.fullmatch(name) is None
            or not isinstance(local, bool)
            or name in names
        ):
            return None
        names.add(name)
        advertisements.append(CapabilityAdvertisement(name, local))
    return AdvertisementAdministrationRequest(
        correlation_id=correlation_id,
        node_id=node_id,
        expected_node_revision=revision,
        advertisements=tuple(advertisements),
    )


def _public_administration_record(record) -> dict[str, object]:
    return {
        "node_id": record.node_id,
        "trust_state": record.trust_state.value,
        "granted_capabilities": sorted(record.granted_capabilities),
        "revision": record.revision,
        "enrolled_at": record.enrolled_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _node_path(path: str) -> str | None:
    prefix = "/api/v1/nodes/"
    if not path.startswith(prefix):
        return None
    suffix = path[len(prefix):]
    return suffix if IDENTIFIER_PATTERN.fullmatch(suffix or "") else None


def _mutation_path(path: str) -> tuple[str, str] | None:
    prefix = "/api/v1/nodes/"
    if not path.startswith(prefix):
        return None
    parts = path[len(prefix):].split("/")
    if len(parts) != 2 or IDENTIFIER_PATTERN.fullmatch(parts[0]) is None:
        return None
    if parts[1] not in {"administration", "advertisements"}:
        return None
    return parts[0], parts[1]


def _administration_status(reason: str) -> HTTPStatus:
    if reason in {"revision_conflict", "idempotency_conflict", "node_already_enrolled"}:
        return HTTPStatus.CONFLICT
    if reason == "administration_denied":
        return HTTPStatus.FORBIDDEN
    if reason in {"state_unavailable", "authorizer_unavailable", "capability_state_unavailable"}:
        return HTTPStatus.SERVICE_UNAVAILABLE
    return HTTPStatus.BAD_REQUEST


def _advertisement_status(reason: str) -> HTTPStatus:
    if reason == "revision_conflict":
        return HTTPStatus.CONFLICT
    if reason == "administration_denied":
        return HTTPStatus.FORBIDDEN
    if reason in {"state_unavailable", "clock_unavailable"}:
        return HTTPStatus.SERVICE_UNAVAILABLE
    return HTTPStatus.BAD_REQUEST


def _canonical_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return UUID(value).version is not None and str(UUID(value)) == value
    except ValueError:
        return False


def _printable_correlation(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 128 and value.isprintable()


def _require_loopback(address: str) -> None:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise ValueError("administrator listener requires a literal loopback address") from error
    if not parsed.is_loopback:
        raise ValueError("administrator listener may bind only to loopback")


_ADMIN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HearthGhost Admin</title><style>
body{font:14px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;background:#111916;color:#e5eee9}input,button,select{font:inherit;padding:.55rem;margin:.2rem}input{min-width:18rem}button{cursor:pointer}pre{white-space:pre-wrap;background:#0b100e;padding:1rem;border-radius:.5rem}fieldset{margin:1rem 0}
</style></head><body>
<h1>HearthGhost Admin</h1><p>Loopback-only privileged console. The bearer token stays in this page's JavaScript memory only.</p>
<fieldset><legend>Session</legend><input id="token" type="password" autocomplete="off" placeholder="Paste administrator token"><input id="node" value="android-development-01" autocomplete="off"><button id="load">Load Node</button></fieldset>
<fieldset><legend>Reviewed Android capability surface</legend><button id="ads">Register conversation.text + notification.local</button></fieldset>
<fieldset><legend>Node administration</legend><select id="action"><option value="node.enroll">Enroll</option><option value="node.trust.set">Trust</option><option value="node.capability.grant">Grant capability</option><option value="node.capability.revoke">Revoke capability</option><option value="node.revoke">Revoke Node</option></select><input id="value" placeholder="trusted or capability name"><button id="apply">Apply</button></fieldset>
<pre id="output">No privileged request sent.</pre><script type="module" src="/admin.js"></script></body></html>"""

_ADMIN_JS = r"""
let token = "";
let current = null;
const byId = (id) => document.getElementById(id);
const output = byId("output");
function nodeId(){ return byId("node").value.trim(); }
function headers(){ return {"Authorization": `Bearer ${token}`, "Content-Type":"application/json"}; }
async function request(path, options={}){
  token = byId("token").value;
  const response = await fetch(path, {...options, headers:{...(options.headers||{}), "Authorization":`Bearer ${token}`}, cache:"no-store", credentials:"omit", referrerPolicy:"no-referrer"});
  const body = await response.json();
  output.textContent = JSON.stringify(body,null,2);
  if(response.ok && body.node) current=body.node;
  return {response,body};
}
async function load(){ await request(`/api/v1/nodes/${encodeURIComponent(nodeId())}`); }
byId("load").addEventListener("click",()=>void load());
byId("ads").addEventListener("click",()=>void (async()=>{
  if(!current) await load(); if(!current) return;
  await request(`/api/v1/nodes/${encodeURIComponent(nodeId())}/advertisements`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({correlation_id:`admin-${crypto.randomUUID()}`,expected_node_revision:current.revision,advertisements:[{name:"conversation.text",local_authorization_required:false},{name:"notification.local",local_authorization_required:true}]})});
  await load();
})());
byId("apply").addEventListener("click",()=>void (async()=>{
  const action=byId("action").value; if(!current && action!=="node.enroll") await load();
  const revision=action==="node.enroll"?0:(current?.revision??-1); const body={operation_id:crypto.randomUUID(),correlation_id:`admin-${crypto.randomUUID()}`,action,expected_revision:revision};
  const value=byId("value").value.trim(); if(action==="node.trust.set") body.trust_state=value||"trusted"; if(action==="node.capability.grant"||action==="node.capability.revoke") body.capability=value;
  await request(`/api/v1/nodes/${encodeURIComponent(nodeId())}/administration`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); await load();
})());
window.addEventListener("pagehide",()=>{token=""; current=null; byId("token").value="";});
"""
