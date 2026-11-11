"""Idle context cost: one 'Reply with OK' call per CLI x condition, no tools needed.
Input tokens of that single request (uncached + cache write + cache read) = what is loaded
before any work starts. (C5 - C0) / 50 = tokens per idle installed skill."""
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backends import MODELS
from runner import build_ws, ROOT

OUT = ROOT / "probes" / "idle.jsonl"
Q = "Reply with exactly OK. Do not use any tools."
models = sys.argv[1].split(",")
conds = sys.argv[2].split(",")
reps = int(sys.argv[3]) if len(sys.argv) > 3 else 2
for m in models:
    for c in conds:
        for rep in range(reps):
            b = MODELS[m](Path("/tmp"))
            base, ws = build_ws(b, "t1_ratelimit", c)
            b.home_root = base
            r = b.run(ws, Q, 300, max_turns=2)
            t = r["tokens"]
            tot = (t["input"] or 0) + (t["cache_write"] or 0) + (t["cache_read"] or 0)
            rec = dict(model=m, cond=c, rep=rep, input_total=tot, tokens=t, cost=r["cost_usd"],
                       tools=len(r["tools"]), text=(r["final_text"] or "")[:80], err=r["error"],
                       listed=r.get("listed_skills"))
            with open(OUT, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(m, c, rep, tot, t, r["cost_usd"], len(r["tools"]), repr((r["final_text"] or "")[:30]), flush=True)
            shutil.rmtree(base, ignore_errors=True)
