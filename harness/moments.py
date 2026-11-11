#!/usr/bin/env python3
"""Pull candidate video moments out of the run logs -> runs/moments.md"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
KEYS = re.compile(r"skill|ponytail|AGENTS\.md|CLAUDE\.md|did not run|didn.t run|skipped|shortcut:|"
                  r"lazy|guidance|instructions|brainstorm|superpowers|TDD|test-driven", re.I)
C4_TOOLS = re.compile(r"\b(pytest|ruff|mypy|black|isort|pre-commit|tox|nox|pip install|poetry|uv |"
                      r"git (status|diff|log|add|commit)|make )", re.I)


def texts_and_tools(rid, cli):
    texts, tools = [], []
    p = RUNS / rid / "stream.jsonl"
    if not p.exists():
        return texts, tools
    cur = []
    for line in p.read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ty = d.get("type")
        if cli == "claude" and ty == "assistant":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "text":
                    texts.append(c["text"])
                elif c.get("type") == "tool_use":
                    tools.append(json.dumps(c.get("input"))[:300])
        elif cli == "codex" and ty == "item.completed":
            it = d.get("item", {})
            if it.get("type") == "agent_message":
                texts.append(it.get("text", ""))
            elif it.get("type") == "command_execution":
                tools.append(it.get("command", "")[:300])
        elif cli == "grok":
            if ty == "text":
                cur.append(d.get("data", ""))
            else:
                if cur:
                    texts.append("".join(cur))
                    cur = []
                if ty == "tool_call":
                    tools.append(json.dumps(d.get("rawInput"))[:300])
        elif cli == "opencode":
            part = d.get("part") or {}
            if ty == "text":
                texts.append(part.get("text", ""))
            elif ty == "tool_use":
                tools.append(json.dumps((part.get("state") or {}).get("input"))[:300])
    if cur:
        texts.append("".join(cur))
    return texts, tools


def main():
    rows = {}
    for line in (RUNS / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if not r.get("infra_error"):
            rows[r["run_id"]] = r
    out = ["# Candidate moments (auto-extracted; verify in the stream before use)\n"]
    out.append("\n## Model sentences that mention skills / context files / skipping work\n")
    for rid, r in sorted(rows.items()):
        texts, tools = texts_and_tools(rid, r["cli"])
        for t in texts:
            for sent in re.split(r"(?<=[.!?])\s+|\n", t):
                if KEYS.search(sent) and 20 < len(sent) < 400:
                    out.append(f"- `{rid}` ({'pass' if r['passed'] else 'FAIL'}): {sent.strip()}")
    out.append("\n## C4 (bloated context file): tool calls that follow its generic advice\n")
    for rid, r in sorted(rows.items()):
        if r["cond"] != "C4":
            continue
        _, tools = texts_and_tools(rid, r["cli"])
        hits = [t for t in tools if C4_TOOLS.search(t)]
        if hits:
            out.append(f"- `{rid}`: " + " | ".join(h[:140] for h in hits[:4]))
    out.append("\n## C0 runs for comparison: same kind of tool calls\n")
    n0 = sum(1 for rid, r in rows.items() if r["cond"] == "C0"
             and any(C4_TOOLS.search(t) for t in texts_and_tools(rid, r["cli"])[1]))
    n4 = sum(1 for rid, r in rows.items() if r["cond"] == "C4"
             and any(C4_TOOLS.search(t) for t in texts_and_tools(rid, r["cli"])[1]))
    t0 = sum(1 for r in rows.values() if r["cond"] == "C0")
    t4 = sum(1 for r in rows.values() if r["cond"] == "C4")
    out.append(f"- runs with pytest/ruff/mypy/git/pip-style calls: C0 {n0}/{t0}, C4 {n4}/{t4}")
    out.append("\n## Skill opens with timing\n")
    for rid, r in sorted(rows.items()):
        su = {k: v for k, v in (r.get("skill_first_use_s") or {}).items() if not k.startswith("other:")}
        if su:
            out.append(f"- `{rid}` ({'pass' if r['passed'] else 'FAIL'}): {su}")
    (RUNS / "moments.md").write_text("\n".join(out) + "\n")
    print("wrote", RUNS / "moments.md", len(out), "lines")


if __name__ == "__main__":
    main()
