"""L57: a local teaching subset of MCP 2026-07-28, not a general MCP SDK."""

import asyncio
import json
import os
from pathlib import Path
import sys

VERSION = "2026-07-28"
PREFIX = "io.modelcontextprotocol/"
CLIENT_INFO = {"name": "l57-host", "version": "1.0"}
SERVER_INFO = {"name": "l57-evidence", "version": "1.0"}
MAX_FRAME = 16_384  # Includes the delimiter.
REQUEST_SECONDS = 3.0
EXIT_SECONDS = 1.0
TOOL_NAME = "read_evidence"

# Server-side allowlist, separate from the evidence read itself.
SOURCE_BY_SCOPE = {"export": "KB-01", "north-campus": "PICKUP-01", "south-campus": "PICKUP-01"}
EXCERPTS = {
    "export": "导出文件生成后保留 7 天。",
    "north-campus": "北校区器材在图书馆东台领取。",
    "south-campus": "南校区器材在体育馆西台领取。",
}
LIMITS = {"scope": 24, "source_id": 24, "excerpt": 120}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string", "minLength": 1, "maxLength": limit}
                   for key, limit in LIMITS.items()},
    "required": list(LIMITS),
    "additionalProperties": False,
}
TOOL = {
    "name": TOOL_NAME,
    "description": "Read one allowlisted synthetic evidence excerpt.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": list(SOURCE_BY_SCOPE)},
            "source_id": {"type": "string", "enum": sorted(set(SOURCE_BY_SCOPE.values()))},
        },
        "required": ["scope", "source_id"],
        "additionalProperties": False,
    },
    "outputSchema": OUTPUT_SCHEMA,
}


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def frame(value):
    return (compact(value) + "\n").encode("utf-8")


def reject_constant(token):
    raise ValueError(f"not a JSON constant: {token}")


def decode(line):
    if len(line) > MAX_FRAME or not line.endswith(b"\n"):
        raise ValueError("expected one bounded, newline-delimited frame")
    return json.loads(line.decode("utf-8"), parse_constant=reject_constant)


def result(request_id, **fields):
    return {"jsonrpc": "2.0", "id": request_id, "result": {
        "resultType": "complete", **fields, "_meta": {PREFIX + "serverInfo": SERVER_INFO},
    }}


def error(request_id, code, message, **data):
    reply = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
    if request_id is not None:
        reply["id"] = request_id
    if data:
        reply["error"]["data"] = data
    return reply


# Child: only this function touches the in-memory evidence. The audit is not RPC data.
def read_evidence(scope, source_id):
    print(f"evidence-read {scope} {source_id}", file=sys.stderr, flush=True)
    return {"scope": scope, "source_id": source_id, "excerpt": EXCERPTS[scope]}


def dispatch(message):
    if not isinstance(message, dict):
        return error(None, -32600, "Invalid request")
    request_id = message.get("id")
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        readable_id = request_id if type(request_id) in (int, str) else None
        return error(readable_id, -32600, "Invalid request")
    if "id" not in message:  # This subset does not act on notifications or reply to them.
        return None
    if type(request_id) not in (int, str):
        return error(None, -32600, "Invalid request ID")
    params = message.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    version = meta.get(PREFIX + "protocolVersion") if isinstance(meta, dict) else None
    if not isinstance(version, str) or not isinstance(meta.get(PREFIX + "clientCapabilities"), dict):
        return error(request_id, -32602, f"Required request metadata missing or invalid; supports {VERSION}")
    if version != VERSION:
        return error(request_id, -32022, "Unsupported protocol version", supported=[VERSION], requested=version)
    if method == "initialize":
        return error(request_id, -32601, f"No initialize handshake; supports {VERSION}")
    if method == "server/discover":
        return result(request_id, supportedVersions=[VERSION], capabilities={"tools": {}},
                      ttlMs=0, cacheScope="public")
    if method == "tools/list":
        return result(request_id, tools=[TOOL], ttlMs=0, cacheScope="public")
    if method != "tools/call":
        return error(request_id, -32601, "Method not implemented in L57")

    name, arguments = params.get("name"), params.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return error(request_id, -32602, "Malformed tools/call parameters")
    if name != TOOL_NAME:
        return error(request_id, -32602, "Unknown tool")
    scope, source_id = arguments.get("scope"), arguments.get("source_id")
    if (arguments.keys() != {"scope", "source_id"} or not isinstance(scope, str)
            or not isinstance(source_id, str) or SOURCE_BY_SCOPE.get(scope) != source_id):
        return result(request_id, isError=True,
                      content=[{"type": "text", "text": "Provide an allowlisted scope and matching source_id."}])
    evidence = read_evidence(scope, source_id)
    return result(request_id, isError=False, content=[{"type": "text", "text": compact(evidence)}],
                  structuredContent=evidence)


def serve():
    while line := sys.stdin.buffer.readline(MAX_FRAME + 1):
        try:
            request = decode(line)
        except (ValueError, RecursionError):
            reply = error(None, -32700, "Invalid UTF-8 JSON frame")
            if not line.endswith(b"\n") or len(line) > MAX_FRAME:
                raise SystemExit("L57: partial or oversized request frame")
        else:
            reply = dispatch(request)
        if reply is not None:
            sys.stdout.buffer.write(frame(reply))
            sys.stdout.buffer.flush()


async def drain(stream):
    captured = bytearray()
    while chunk := await stream.read(4096):
        captured.extend(chunk[: MAX_FRAME + 1 - len(captured)])
    return bytes(captured)


# Client: sequential request/response transport. Launch accepts no path or command from arguments.
class StdioClient:
    def __init__(self):
        self.trace = []
        self.audit = []
        self.returncode = None
        self.next_id = 1

    async def __aenter__(self):
        server_path = Path(__file__).resolve()
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-X", "utf8", str(server_path), "--serve",
            cwd=server_path.parent, env=env, limit=MAX_FRAME,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        # Drain diagnostics during requests, so a busy stderr cannot block stdout.
        self.stderr_task = asyncio.create_task(drain(self.process.stderr))
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        process = self.process
        process.stdin.close()  # EOF requests graceful shutdown.
        cleanup = asyncio.gather(drain(process.stdout), self.stderr_task, process.wait())
        forced = False
        for stop in (None, process.terminate, process.kill):
            if stop is not None and process.returncode is None:
                forced = True
                try:
                    stop()  # May have exited in the meantime.
                except ProcessLookupError:
                    pass
            try:
                tail, diagnostics, self.returncode = await asyncio.wait_for(asyncio.shield(cleanup), EXIT_SECONDS)
                break
            except TimeoutError:
                continue
        else:
            cleanup.cancel()
            raise TimeoutError("L57: child did not exit after forced shutdown")
        if len(diagnostics) > MAX_FRAME:
            raise ValueError("L57: child diagnostics exceeded the capture limit")
        self.audit = diagnostics.decode("utf-8", errors="replace").splitlines()
        if exc_type is None and (forced or self.returncode != 0 or tail):
            raise RuntimeError(f"L57: abnormal child shutdown (exit={self.returncode}, forced={forced})")

    async def request(self, method, **params):
        request_id = self.next_id
        self.next_id += 1
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {
            **params, "_meta": {PREFIX + "protocolVersion": VERSION, PREFIX + "clientInfo": CLIENT_INFO,
                                PREFIX + "clientCapabilities": {}},
        }}
        try:
            return await asyncio.wait_for(self.exchange(request), REQUEST_SECONDS)
        except TimeoutError as exc:
            raise TimeoutError(f"L57: no complete reply for {method} in {REQUEST_SECONDS:g}s") from exc

    async def exchange(self, request):
        payload = frame(request)
        if len(payload) > MAX_FRAME:
            raise ValueError("L57: request exceeded the frame size limit")
        self.process.stdin.write(payload)
        await self.process.stdin.drain()
        line = await self.process.stdout.readline()
        if not line:
            raise EOFError(f"L57: stdout closed before reply to {request['method']}")
        reply = decode(line)
        if (not isinstance(reply, dict) or reply.get("jsonrpc") != "2.0" or type(reply.get("id")) is not int
                or reply["id"] != request["id"] or ("error" in reply) == ("result" in reply)):
            raise ValueError("L57: unexpected JSON-RPC response, envelope or ID")
        if "error" in reply:
            rpc_error = reply["error"]
            if (not isinstance(rpc_error, dict) or type(rpc_error.get("code")) is not int
                    or not isinstance(rpc_error.get("message"), str)):
                raise ValueError("L57: malformed JSON-RPC error")
        self.trace.append((request, reply))
        return reply


def complete(reply):
    body = reply.get("result")
    if not isinstance(body, dict) or body.get("resultType") != "complete":
        raise ValueError("L57: expected a modern complete result")
    return body


# Host: validate just this pinned local schema, not arbitrary schemas returned over MCP.
def validate_shape(reply):
    body = complete(reply)
    evidence = body.get("structuredContent")
    if (body.get("isError", False) is not False or not isinstance(evidence, dict)
            or evidence.keys() != LIMITS.keys()
            or any(not isinstance(evidence[key], str) or not 1 <= len(evidence[key]) <= limit
                   for key, limit in LIMITS.items())):
        raise ValueError("L57: tool error or invalid structured evidence")
    return evidence


def model_evidence(reply, *, expected_scope, expected_source):
    evidence = validate_shape(reply)
    if (evidence["scope"], evidence["source_id"]) != (expected_scope, expected_source):
        raise ValueError("L57: evidence does not belong to this task")
    # Model-facing projection only; no model is called by the lab.
    return {"source_id": evidence["source_id"], "excerpt": evidence["excerpt"]}


async def discover_tools(client):
    discovery = complete(await client.request("server/discover"))
    if VERSION not in discovery.get("supportedVersions", ()) or "tools" not in discovery.get("capabilities", {}):
        raise ValueError("L57: expected modern tools capability")
    catalog = complete(await client.request("tools/list"))
    if catalog.get("tools") != [TOOL]:
        raise ValueError("L57: expected only the locally pinned read_evidence tool and contract")
    for metadata in (discovery, catalog):
        ttl = metadata.get("ttlMs")
        if type(ttl) is not int or ttl != 0 or metadata.get("cacheScope") != "public":
            raise ValueError("L57: expected the fixed public, immediately stale catalog")


async def call(client, scope, source_id):
    return await client.request("tools/call", name=TOOL_NAME, arguments={"scope": scope, "source_id": source_id})


async def worked_report():
    async with StdioClient() as client:
        await discover_tools(client)
        good = await call(client, "export", "KB-01")
        model_view = model_evidence(good, expected_scope="export", expected_source="KB-01")
        bad = await call(client, "export", "PICKUP-01")
        unknown = await client.request("tools/call", name="missing_tool",
                                       arguments={"scope": "export", "source_id": "KB-01"})
    return {"model_view": model_view, "bad": complete(bad), "unknown": unknown.get("error"),
            "audit": client.audit, "returncode": client.returncode, "trace": client.trace}


async def transfer_report():
    async with StdioClient() as client:
        await discover_tools(client)
        north = await call(client, "north-campus", "PICKUP-01")
        south = await call(client, "south-campus", "PICKUP-01")
        north_view = model_evidence(north, expected_scope="north-campus", expected_source="PICKUP-01")
        south_view = model_evidence(south, expected_scope="south-campus", expected_source="PICKUP-01")
        # Candidate snapshot for north has the same schema and source ID, but came from south.
        shape_only = validate_shape(south)
        try:
            wrong_scope_view = model_evidence(south, expected_scope="north-campus", expected_source="PICKUP-01")
        except ValueError:
            wrong_scope_view = None
    return {"north": north_view, "south": south_view, "shape_only": shape_only, "wrong_scope_view": wrong_scope_view,
            "audit": client.audit, "returncode": client.returncode}


def check_worked(report):
    return (report["model_view"] == {"source_id": "KB-01", "excerpt": "导出文件生成后保留 7 天。"}
            and report["bad"].get("isError") is True and "structuredContent" not in report["bad"]
            and report["unknown"] == {"code": -32602, "message": "Unknown tool"}
            and report["audit"] == ["evidence-read export KB-01"] and report["returncode"] == 0)


def check_transfer(report):
    return (report["north"] == {"source_id": "PICKUP-01", "excerpt": "北校区器材在图书馆东台领取。"}
            and report["south"] == {"source_id": "PICKUP-01", "excerpt": "南校区器材在体育馆西台领取。"}
            and report["shape_only"]["scope"] == "south-campus"
            and report["shape_only"]["source_id"] == report["north"]["source_id"] and report["wrong_scope_view"] is None
            and report["audit"] == ["evidence-read north-campus PICKUP-01", "evidence-read south-campus PICKUP-01"]
            and report["returncode"] == 0)


def main():
    if sys.argv[1:] == ["--serve"]:
        serve()
    elif sys.argv[1:] in (["worked"], ["trace"]):
        report = asyncio.run(worked_report())
        if not check_worked(report):
            raise SystemExit("L57: worked acceptance failed")
        if sys.argv[1] == "trace":
            for request, reply in report["trace"]:
                print("stdin ", compact(request))
                print("stdout", compact(reply))
            print("stderr", compact(report["audit"]))
        else:
            print("L57 ACCEPTED")
    elif sys.argv[1:] == ["transfer"]:
        if not check_transfer(asyncio.run(transfer_report())):
            raise SystemExit("L57: transfer acceptance failed")
        print("L57 TRANSFER PASSED")
    else:
        raise SystemExit("Usage: python -I -X utf8 lab.py {worked|transfer|trace}")


if __name__ == "__main__":
    main()
