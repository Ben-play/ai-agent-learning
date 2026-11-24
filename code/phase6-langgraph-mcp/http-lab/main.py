"""Bounded 2026-07-28 Streamable HTTP teaching subset; never deploy this server."""
import base64
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPMessage
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer
from threading import Thread


VERSION = "2026-07-28"
PREFIX = "io.modelcontextprotocol/"
LOOPBACK = "127.0.0.1"
ENDPOINT = "/mcp"
JSON, SSE = "application/json", "text/event-stream"
LIMIT, TIMEOUT = 8_192, 3
METHODS = {"server/discover", "tools/list", "tools/call"}
READ_TOOL, SAVE_TOOL = "read_evidence", "save_training_draft"
READ_SCOPE, SAVE_SCOPE = "evidence:read", "draft:save"
AUDIENCE = "course-http-lab"  # Local fixture label, not a canonical OAuth resource URI.
EVIDENCE = {
    "KB-01": "导出文件生成后保留 7 天。",
    "KB-02": "超过保留期需重新发起导出。",
    "KB-03": "同步任务每天 02:00 运行。",
}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def identifier(value):
    return type(value) in (str, int)


def rpc(request_id, method, *, version=VERSION, progress=None, **params):
    meta = {
        PREFIX + "protocolVersion": version,
        PREFIX + "clientInfo": {"name": "course-client", "version": "1.0"},
        PREFIX + "clientCapabilities": {},
    }
    if progress is not None:
        meta["progressToken"] = progress
    return {"jsonrpc": "2.0", "id": request_id, "method": method,
            "params": {**params, "_meta": meta}}


@dataclass(frozen=True)
class Actor:
    tenant: str
    user: str


@dataclass(frozen=True)
class StagedDraft:
    owner: Actor
    draft_id: str
    revision: int
    text: str

    def arguments(self):
        return {"draft_id": self.draft_id, "revision": self.revision, "text": self.text}


@dataclass(frozen=True)
class Approval:
    action: str
    snapshot: StagedDraft


@dataclass(frozen=True)
class Grant:
    audience: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class HostContext:
    """Injected by the trusted fixture, never populated from HTTP headers or body."""
    actor: Actor
    draft: StagedDraft | None = None
    approved: Approval | None = None


# Opaque test labels only. No signing/decoding, expiry, provider or real credentials.
FIXTURE_GRANTS = {
    "fixture-01": Grant(AUDIENCE, frozenset({READ_SCOPE})),
    "fixture-02": Grant(AUDIENCE, frozenset({READ_SCOPE, SAVE_SCOPE})),
    "fixture-03": Grant("other-fixture", frozenset({READ_SCOPE, SAVE_SCOPE})),
}


@dataclass
class LabState:
    host: HostContext | None
    read_entries: list[str] = field(default_factory=list)
    save_entries: int = 0
    saved: list[StagedDraft] = field(default_factory=list)

    def read_evidence(self, source_id):
        self.read_entries.append(source_id)  # Actual effect entry, not HTTP attempts.
        return {"source_id": source_id, "quote": EVIDENCE[source_id]}

    def save_training_draft(self, draft):
        self.save_entries += 1  # At the effect boundary, before touching the in-memory ledger.
        self.saved.append(draft)
        return {"status": "saved", "draft_id": draft.draft_id, "revision": draft.revision}

    def save_if_approved(self, args):
        host = self.host
        draft = host.draft if host is not None else None
        draft_id, revision, text = args.get("draft_id"), args.get("revision"), args.get("text")
        if (set(args) != {"draft_id", "revision", "text"}
                or not isinstance(draft_id, str) or not 1 <= len(draft_id) <= 64
                or type(revision) is not int or revision < 1
                or not isinstance(text, str) or not 1 <= len(text) <= 200):
            return {"status": "invalid_arguments"}
        if host is None or draft is None or host.actor != draft.owner or draft_id != draft.draft_id:
            return {"status": "not_available"}
        if args != draft.arguments():
            return {"status": "intent_changed"}
        if host.approved != Approval(SAVE_TOOL, draft):
            return {"status": "approval_required"}
        return self.save_training_draft(draft)


def tool(name, description, properties):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties, "required": list(properties),
        "additionalProperties": False,
    }}


READ_DEF = tool(READ_TOOL, "Read a fixed synthetic knowledge-base excerpt.", {
    "source_id": {"type": "string", "enum": list(EVIDENCE)},
})
SAVE_DEF = tool(SAVE_TOOL, "Save an exactly approved training draft to an in-memory ledger.", {
    "draft_id": {"type": "string", "minLength": 1, "maxLength": 64},
    "revision": {"type": "integer", "minimum": 1},
    "text": {"type": "string", "minLength": 1, "maxLength": 200},
})


def result(request_id, **fields):
    return {"jsonrpc": "2.0", "id": request_id, "result": {
        "resultType": "complete", "_meta": {
            PREFIX + "serverInfo": {"name": "course-http-lab", "version": "1.0"},
        }, **fields,
    }}


def tool_result(request_id, payload, *, denied=False):
    return result(request_id, isError=denied, structuredContent=payload,
                  content=[{"type": "text", "text": encoded(payload).decode("utf-8")}])


def lab_name(value):
    """Decode the standard sentinel before comparison; no custom Mcp-Param headers."""
    if value.startswith("=?base64?") and value.endswith("?="):
        return base64.b64decode(value[len("=?base64?"):-len("?=")], validate=True).decode("utf-8")
    return value


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = TIMEOUT

    def log_message(self, *_):
        pass  # No request headers or synthetic credential values in logs.

    def parse_request(self):
        if not super().parse_request():
            return False
        self.close_connection = True
        return self.check_authority()

    def check_authority(self):
        origin = self.headers.get_all("Origin", [])
        if origin and origin != [f"http://{self.server.authority}"]:
            self.reply(403)
            return False
        if self.headers.get_all("Host") != [self.server.authority]:
            self.reply(400)  # Extra lab policy: exactly the bound loopback authority.
            return False
        return True

    def handle_expect_100(self):
        self.close_connection = True
        if self.check_authority():
            self.reply(417)  # This lab only accepts already-sent Content-Length bodies.
        return False

    def reply(self, status, message=None, *, extra=()):
        body = b"" if message is None else encoded(message)
        self.send_response_only(status)
        if message is not None:
            self.send_header("Content-Type", JSON)
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def error(self, status, code, message, request_id=None, **data):
        response = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
        if identifier(request_id):
            response["id"] = request_id
        if data:
            response["error"]["data"] = data
        self.reply(status, response)

    def do_GET(self):
        if self.path != ENDPOINT:
            return self.reply(404)
        self.reply(405, extra=(("Allow", "POST"),))

    do_DELETE = do_GET

    def do_POST(self):
        if self.path != ENDPOINT:
            return self.reply(404)
        if self.headers.get_content_type() != JSON:
            return self.reply(415)
        lengths = self.headers.get_all("Content-Length", [])
        if (self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1
                or not lengths[0].isascii() or not lengths[0].isdecimal()):
            return self.reply(400)
        if len(lengths[0]) > len(str(LIMIT)) or int(lengths[0]) > LIMIT:
            return self.reply(413)
        length = int(lengths[0])
        body = self.rfile.read(length)
        try:
            request = json.loads(body.decode("utf-8")) if len(body) == length else None
        except (ValueError, RecursionError):
            return self.error(400, -32700, "Parse error")
        if not isinstance(request, dict):
            return self.error(400, -32600, "Expected one JSON-RPC request")
        request_id, method = request.get("id"), request.get("method")
        if (request.get("jsonrpc") != "2.0" or not identifier(request_id)
                or not isinstance(method, str) or "result" in request or "error" in request):
            return self.error(400, -32600, "Expected one JSON-RPC request", request_id)

        params = request.get("params")
        meta = params.get("_meta") if isinstance(params, dict) else None
        mirrors = [("MCP-Protocol-Version", None), ("Mcp-Method", method)]
        if method == "tools/call":
            mirrors.append(("Mcp-Name", params.get("name") if isinstance(params, dict) else None))
        headers = {}
        for header, expected in mirrors:
            values = self.headers.get_all(header, [])
            if len(values) != 1 or not values[0] or not all(32 <= ord(ch) <= 126 for ch in values[0]):
                return self.error(400, -32020, f"Missing or malformed {header}", request_id)
            try:
                value = lab_name(values[0]) if header == "Mcp-Name" else values[0]
            except ValueError:
                return self.error(400, -32020, f"Malformed {header}", request_id)
            if isinstance(expected, str) and value != expected:
                return self.error(400, -32020, f"{header} does not match body", request_id)
            headers[header] = value
        version = meta.get(PREFIX + "protocolVersion") if isinstance(meta, dict) else None
        if not isinstance(version, str):
            return self.error(400, -32602, "Missing or invalid body version", request_id)
        if headers["MCP-Protocol-Version"] != version:
            return self.error(400, -32020, "MCP-Protocol-Version does not match body", request_id)
        if version != VERSION:
            return self.error(400, -32022, "Unsupported protocol version", request_id,
                              supported=[VERSION], requested=version)
        if not isinstance(meta.get(PREFIX + "clientCapabilities"), dict):
            return self.error(400, -32602, "Missing or invalid client capabilities", request_id)
        if "progressToken" in meta and not identifier(meta["progressToken"]):
            return self.error(400, -32602, "Invalid progress token", request_id)
        accepts = {part.strip().lower() for value in self.headers.get_all("Accept", [])
                   for part in value.split(",")}
        if not {JSON, SSE} <= accepts:
            return self.reply(406)  # Lab expects both explicit media types, no quality-value parsing.
        if method not in METHODS:
            return self.error(404, -32601, f"Method not found; supported version: {VERSION}", request_id)

        host = self.server.state.host
        grant = self.authorize() if host is not None else None
        if host is not None and grant is None:
            return  # authorize already sent the fixture's HTTP challenge.
        cache = {"ttlMs": 0, "cacheScope": "private" if host is not None else "public"}
        if method == "server/discover":
            return self.reply(200, result(request_id, supportedVersions=[VERSION],
                                          capabilities={"tools": {}}, **cache))
        if method == "tools/list":
            definitions = [READ_DEF, SAVE_DEF] if host is not None else [READ_DEF]
            return self.reply(200, result(request_id, tools=definitions, **cache))
        self.call_tool(request_id, params, meta, grant)

    def authorize(self):
        values = self.headers.get_all("Authorization", [])
        scheme, _, label = values[0].partition(" ") if len(values) == 1 else ("", "", "")
        grant = FIXTURE_GRANTS.get(label) if scheme.lower() == "bearer" else None
        if grant is None or grant.audience != AUDIENCE:
            challenge = 'Bearer error="invalid_token"' if values else "Bearer"
            self.reply(401, extra=(("WWW-Authenticate", challenge),))
            return None
        return grant

    def call_tool(self, request_id, params, meta, grant):
        state = self.server.state
        name, args = params.get("name"), params.get("arguments", {})
        if name != READ_TOOL and not (state.host is not None and name == SAVE_TOOL):
            return self.error(400, -32602, "Unknown or invalid tool", request_id)
        scope = READ_SCOPE if name == READ_TOOL else SAVE_SCOPE
        if grant is not None and scope not in grant.scopes:
            return self.reply(403, extra=(("WWW-Authenticate", f'Bearer error="insufficient_scope", scope="{scope}"'),))
        if not isinstance(args, dict):
            return self.error(400, -32602, "Expected arguments object", request_id)
        if name == READ_TOOL:
            source_id = args.get("source_id")
            if set(args) != {"source_id"} or not isinstance(source_id, str) or source_id not in EVIDENCE:
                return self.reply(200, tool_result(request_id, {"status": "unknown_evidence"}, denied=True))
            if "progressToken" in meta:
                return self.stream_read(request_id, meta["progressToken"], source_id)
            return self.reply(200, tool_result(request_id, state.read_evidence(source_id)))

        outcome = state.save_if_approved(args)
        self.reply(200, tool_result(request_id, outcome, denied=outcome["status"] != "saved"))

    def stream_read(self, request_id, token, source_id):
        self.send_response_only(200)
        self.send_header("Content-Type", SSE)
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        try:
            self.end_headers()
            self.event({"jsonrpc": "2.0", "method": "notifications/progress",
                        "params": {"progressToken": token, "progress": 1, "total": 2}})
            self.event(tool_result(request_id, self.server.state.read_evidence(source_id)))
        except (ConnectionError, TimeoutError):
            return  # Stop on a detectable disconnect; no resumability or long-running work.

    def event(self, message):
        self.wfile.write(b"data: " + encoded(message) + b"\n\n")
        self.wfile.flush()


@dataclass(frozen=True)
class Exchange:
    status: int
    media_type: str | None
    headers: HTTPMessage
    messages: tuple

    @property
    def final(self):
        return self.messages[-1]


@dataclass(frozen=True)
class Client:
    port: int

    @property
    def origin(self):
        return f"http://{LOOPBACK}:{self.port}"

    def post(self, request, *, bearer=None, headers=None):
        params = request.get("params", {})
        fields = {"Content-Type": JSON, "Accept": f"{JSON}, {SSE}",
                  "MCP-Protocol-Version": params.get("_meta", {}).get(PREFIX + "protocolVersion", VERSION),
                  "Mcp-Method": request["method"]}
        if request["method"] == "tools/call":
            fields["Mcp-Name"] = params["name"]  # This lab builds requests for fixed ASCII tool names.
        if bearer is not None:
            fields["Authorization"] = f"Bearer {bearer}"
        for name, value in (headers or {}).items():
            # Replace case-insensitively; None removes a header for a negative control.
            fields = {key: val for key, val in fields.items() if key.lower() != name.lower()}
            if value is not None:
                fields[name] = value
        exchange = self.exchange("POST", encoded(request), fields)
        if exchange.messages and (exchange.final.get("jsonrpc") != "2.0"
                                  or exchange.final.get("id") != request["id"]
                                  or ("result" in exchange.final) == ("error" in exchange.final)):
            raise ValueError("Invalid final JSON-RPC reply")
        return exchange

    def exchange(self, verb, body=None, headers=None):
        connection = HTTPConnection(LOOPBACK, self.port, timeout=TIMEOUT)
        try:
            connection.request(verb, ENDPOINT, body, headers or {})
            with connection.getresponse() as response:
                media_type = response.getheader("Content-Type")
                if media_type == SSE:
                    messages = self.stream_messages(response)
                else:
                    data = response.read(LIMIT + 1)
                    if len(data) > LIMIT:
                        raise ValueError("Lab response exceeds byte limit")
                    messages = (json.loads(data.decode("utf-8")),) if data else ()
                return Exchange(response.status, media_type, response.headers, messages)
        finally:
            connection.close()

    @staticmethod
    def stream_messages(response):
        # Only the emitted subset (one data line per frame, LF/CRLF, optional comments).
        messages, data, remaining = [], None, LIMIT
        while line := response.readline(remaining + 1):
            remaining -= len(line)
            if remaining < 0 or not line.endswith(b"\n"):
                raise ValueError("Oversized or incomplete lab SSE line")
            line = line.rstrip(b"\r\n")
            if line.startswith(b"data: ") and data is None:
                data = line[6:]
            elif line == b"" and data is not None:
                messages.append(json.loads(data.decode("utf-8")))
                data = None
            elif line and not line.startswith(b":"):
                raise ValueError("Unsupported lab SSE frame")
        if data is not None or not messages:
            raise ValueError("Missing final SSE event")
        return tuple(messages)


@contextmanager
def local_lab(host=None):
    """One short-lived IPv4 loopback server and a client pinned to its allocated port."""
    state = LabState(host)
    # TCPServer with the HTTP handler avoids HTTPServer.server_bind's socket.getfqdn lookup.
    with TCPServer((LOOPBACK, 0), Handler) as server:
        port = server.server_address[1]
        server.state = state
        server.authority = f"{LOOPBACK}:{port}"
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        try:
            yield Client(port), state
        finally:
            server.shutdown()
            thread.join()
