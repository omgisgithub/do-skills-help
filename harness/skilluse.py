"""Recompute which skills each run opened, from the raw stream (same rule for every CLI)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def installed(cond):
    d = ROOT / "conditions" / cond / "skills"
    return sorted(p.name for p in d.iterdir() if (p / "SKILL.md").exists()) if d.exists() else []


def tool_calls(rid, cli):
    p = ROOT / "runs" / rid / "stream.jsonl"
    out = []
    if not p.exists():
        return out
    for line in p.read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ty = d.get("type")
        if cli == "claude" and ty == "assistant":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    out.append((c.get("name"), c.get("input")))
        elif cli == "codex" and ty == "item.completed" and d["item"].get("type") == "command_execution":
            out.append(("shell", d["item"].get("command")))
        elif cli == "grok" and ty == "tool_call":
            out.append((d.get("toolName"), d.get("rawInput")))
        elif cli == "opencode" and ty == "tool_use":
            part = d.get("part") or {}
            out.append((part.get("tool"), (part.get("state") or {}).get("input")))
    return out


def skills_opened(r):
    names = installed(r["cond"])
    used = []
    for name, inp in tool_calls(r["run_id"], r["cli"]):
        s = json.dumps(inp)
        if str(name).lower() == "skill" and isinstance(inp, dict):
            k = inp.get("skill") or inp.get("name") or inp.get("id") or inp.get("command") or "?"
            k = str(k).lstrip("/").split(":")[-1]
            if k not in used:
                used.append(k)
            continue
        for sk in names:
            if re.search(r"skills/%s/" % re.escape(sk), s) and sk not in used:
                used.append(sk)
    return used
