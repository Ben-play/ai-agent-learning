"""Exercise the local Skill selection and effects boundary using synthetic fixtures."""

from pathlib import Path
import runpy
from string import Template

HERE = Path(__file__).resolve().parent
LAB = runpy.run_path(str(HERE.parent / "http-lab/main.py"))
SKILL = HERE / "training-draft/SKILL.md"


def select_instructions(intent, load_body):
    """The label comes from the teaching host; this is not a Skill runtime or classifier."""
    return load_body() if intent == "draft" else None


def read_course_instructions():
    # Fixed trusted course fixture; not a general SKILL.md/YAML parser.
    return SKILL.read_text(encoding="utf-8").split("---", 2)[2].strip()


def format_preview(instructions, evidence):
    """Use only the marked template in the trusted fixture; never run its text."""
    _, opening, rest = instructions.partition("```text\n")
    template, closing, _ = rest.partition("\n```")
    if not opening or not closing:
        raise ValueError("missing training preview template")
    return Template(template).substitute(source_id=evidence["source_id"], quote=evidence["quote"])


def complete(response):
    if response.status != 200 or not response.messages or "result" not in response.final:
        raise ValueError("expected a successful lab RPC response")
    result = response.final["result"]
    if result["resultType"] != "complete" or result.get("isError", False):
        raise ValueError("no complete result for preview")
    return result


def check():
    if not __debug__:
        raise RuntimeError("run without -O")
    reads = []

    def load():
        reads.append("training-draft")
        return read_course_instructions()

    actor = LAB["Actor"]("team-a", "u1")
    action = "save_training_draft"
    rpc = LAB["rpc"]

    assert select_instructions("answer", load) is None and not reads
    # Discovery and read requests use the same local authorization layer as save.
    # The first instance has no staged draft: the preview depends on the read result.
    with LAB["local_lab"](LAB["HostContext"](actor)) as (client, state):
        discovery = complete(client.post(rpc(1, "server/discover"), bearer="fixture-01"))
        assert discovery["supportedVersions"] == ["2026-07-28"] and "tools" in discovery["capabilities"]
        catalog = complete(client.post(rpc(2, "tools/list"), bearer="fixture-01"))
        names = {tool["name"] for tool in catalog["tools"]}
        assert names == {"read_evidence", action}  # Visible does not mean permitted.
        read = rpc(3, "tools/call", name="read_evidence", arguments={"source_id": "KB-01"})
        evidence = complete(client.post(read, bearer="fixture-01"))["structuredContent"]
        assert evidence == {"source_id": "KB-01", "quote": "导出文件生成后保留 7 天。"}
        assert state.read_entries == ["KB-01"] and (state.save_entries, state.saved) == (0, [])

    instructions = select_instructions("draft", load)
    assert reads == ["training-draft"]
    preview = format_preview(instructions, evidence)
    assert preview == "待确认：导出保留期\n依据 KB-01：导出文件生成后保留 7 天。"
    changed_evidence = {"source_id": "TRAIN-02", "quote": "导出文件生成后保留 14 天。"}
    assert format_preview(instructions, changed_evidence) == (
        "待确认：导出保留期\n依据 TRAIN-02：导出文件生成后保留 14 天。"
    )  # Synthetic formatter-only variation; the HTTP fixture remains unchanged.
    assert format_preview(instructions.replace("待确认：导出保留期", "待确认：培训预览"), evidence).startswith(
        "待确认：培训预览\n"
    )  # A template-only change must also appear in the preview.
    draft = LAB["StagedDraft"](actor, "checkpoint-59", 2, preview)
    save_request = rpc(4, "tools/call", name=action, arguments=draft.arguments())
    with LAB["local_lab"](LAB["HostContext"](actor, draft)) as (client, state):
        no_scope = client.post(save_request, bearer="fixture-01")
        assert no_scope.status == 403 and not no_scope.messages
        assert (state.save_entries, state.saved) == (0, [])
        blocked = client.post(save_request, bearer="fixture-02")
        assert blocked.status == 200 and blocked.final["result"]["isError"]
        assert blocked.final["result"]["structuredContent"] == {"status": "approval_required"}
        assert (state.save_entries, state.saved) == (0, [])

    approved = LAB["HostContext"](actor, draft, LAB["Approval"](action, draft))
    with LAB["local_lab"](approved) as (client, state):
        accepted = client.post(save_request, bearer="fixture-02")
        assert accepted.status == 200 and not accepted.final["result"]["isError"]
        assert accepted.final["result"]["structuredContent"] == {
            "status": "saved", "draft_id": "checkpoint-59", "revision": 2,
        }
        assert (state.save_entries, state.saved) == (1, [draft])
        assert reads == ["training-draft"]  # Approval changed; instructions did not.


if __name__ == "__main__":
    check()
    print("P6 SKILL AND AUTHORITY PASSED")
