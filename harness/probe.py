"""Isolation probe: does each CLI see our project skill + context file, and nothing of the owner's?"""
import json, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backends import MODELS

OUT = Path(__file__).resolve().parents[1] / "probes"
Q = ("Answer from your context only, do not use any tools. 1) List the exact names of every skill "
     "available to you (or 'none'). 2) Quote the first line of any project instruction file "
     "(AGENTS.md/CLAUDE.md) you were given, or 'none'. 3) Do any of your instructions mention "
     "DeepSeek, OpenCode, T3 Code, YouTube or 'Model Behavior'? yes/no and quote. Keep it short.")

def make_ws(b, canary):
    ws = Path(tempfile.mkdtemp(prefix="skvprobe.", dir="/tmp")).resolve() / "project"
    ws.mkdir()
    (ws / "TASK.md").write_text("probe\n")
    if canary:
        d = ws / b.skills_dir / "zebra-canary"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: zebra-canary\ndescription: Use when the user mentions zebras.\n---\nSay ZEBRA.\n")
        (ws / b.context_file).write_text("PROJECT CANARY LINE 7731\n")
    return ws

for key in sys.argv[1:]:
    for canary in (True, False):
        b = MODELS[key](Path(tempfile.mkdtemp(prefix="skvhome.", dir="/tmp")))
        ws = make_ws(b, canary)
        r = b.run(ws, Q, 300, max_turns=3)
        tag = f"{key}_{'canary' if canary else 'empty'}"
        (OUT / f"{tag}.raw.jsonl").write_text("".join(l for _, l in r["raw"]))
        (OUT / f"{tag}.stderr.txt").write_text(r["stderr"][-5000:])
        print(f"== {tag} rc={r['rc']} err={r['error']} tokens={r['tokens']} cost={r['cost_usd']}")
        print("   listed_skills:", r["listed_skills"])
        print("   ", (r["final_text"] or "")[:700].replace("\n", " | "))
