#!/usr/bin/env python3
"""Exp 004 runner. Usage:
  runner.py --models haiku,luna --conds C0,C1 --tasks t1_ratelimit,t2_allocate --reps 1,2,3 [--workers 3]

One run = fresh /tmp workspace (task public files + the condition's skills/context file in the
CLI's native place) -> CLI headless -> grade a copy with the hidden tests -> runs/results.jsonl.
Already-finished run ids are skipped, so the command can be re-run after an interruption.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backends import MODELS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
CONDS = ROOT / "conditions"
RUNS = ROOT / "runs"
RESULTS = RUNS / "results.jsonl"
GRADE = ROOT / "harness" / "grade.sh"
PROMPT = ("Read TASK.md in the current directory and complete the task it describes. "
          "Work only inside the current directory. Do not ask questions; when you are done, stop.")
TIMEOUT = 900
STOP = ROOT / "runs" / "STOP"
lock = threading.Lock()
exhausted = set()
BACKOFF = [180, 600, 1500]


def done_ids():
    ids = set()
    if RESULTS.exists():
        for line in RESULTS.read_text().splitlines():
            r = json.loads(line)
            if not r.get("infra_error"):
                ids.add(r["run_id"])
    return ids


def cond_skills(cond):
    d = CONDS / cond / "skills"
    return sorted(p.name for p in d.iterdir() if (p / "SKILL.md").exists()) if d.exists() else []


def build_ws(backend, task, cond):
    base = Path(tempfile.mkdtemp(prefix="skv.", dir="/tmp")).resolve()
    ws = base / "project"
    shutil.copytree(TASKS / task / "public", ws)
    cdir = CONDS / cond
    if (cdir / "skills").exists():
        shutil.copytree(cdir / "skills", ws / backend.skills_dir)
    if (cdir / "context.md").exists():
        shutil.copy(cdir / "context.md", ws / backend.context_file)
    return base, ws


SUSPECT = re.compile(r"skills_value|ai_compare|test_hidden|expected[12]\.csv|/Users/|\.\./\.\.")


def outside(tools, ws):
    hits = []
    for x in tools:
        s = json.dumps(x.get("input"))
        s2 = s.replace(str(ws), "<WS>").replace(str(ws).replace("/private", ""), "<WS>")
        if SUSPECT.search(s2):
            hits.append(s2[:300])
    return hits


def skill_use(r, installed, backend):
    """Which installed skills did the agent actually open (Skill tool or reading its SKILL.md)?"""
    used = {}
    for x in r["tools"]:
        name = x.get("name") or ""
        s = json.dumps(x.get("input"))
        if name in ("Skill", "skill"):
            inp = x.get("input") or {}
            k = inp.get("skill") or inp.get("name") or inp.get("id") or inp.get("command") or "?"
            used.setdefault(str(k).lstrip("/").split(":")[-1], x["t"])
            continue
        for sk in installed:
            if re.search(r"skills/%s(/|\b)" % re.escape(sk), s):
                used.setdefault(sk, x["t"])
        if "SKILL.md" in s and not any(sk in s for sk in installed):
            used.setdefault("other:" + s[:80], x["t"])
    return used


def grade(task, ws, out):
    g = subprocess.run(["bash", str(GRADE), str(TASKS / task), str(ws)],
                       capture_output=True, text=True)
    txt = g.stdout + g.stderr
    out.write_text(txt)
    p = len(re.findall(r"^PASS", txt, re.M))
    f = len(re.findall(r"^FAIL", txt, re.M))
    return g.returncode == 0, (p / (p + f) if p + f else 0.0), p, f


def run_one(model, cond, task, rep, attempt=1):
    run_id = f"{model}_{cond}_{task}_r{rep}" + (f"_a{attempt}" if attempt > 1 else "")
    backend = MODELS[model](Path("/tmp"))
    base, ws = build_ws(backend, task, cond)
    backend.home_root = base
    installed = cond_skills(cond)
    t0 = time.time()
    r = backend.run(ws, PROMPT, TIMEOUT)
    wall = time.time() - t0
    rd = RUNS / run_id
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "stream.jsonl").write_text("".join(l for _, l in r["raw"]))
    (rd / "stderr.txt").write_text(r["stderr"][-20000:])
    ignore = shutil.ignore_patterns("__pycache__", ".claude", ".agents", ".grok")
    shutil.copytree(ws, rd / "ws", ignore=ignore, symlinks=True)
    passed, partial, np_, nf = grade(task, ws, rd / "grade.txt")
    used = skill_use(r, installed, backend)
    work_done = len(r["tools"]) > 0
    infra = bool((r["error"] and not work_done) or r["limit_hit"])
    rec = dict(
        run_id=run_id, model=model, model_id=backend.model, cli=backend.cli, cond=cond,
        task=task, rep=rep, attempt=attempt, started=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)),
        wall_s=round(wall, 1), passed=passed, partial=round(partial, 3), tests_pass=np_, tests_fail=nf,
        tokens=r["tokens"], cost_usd=r["cost_usd"], turns=r["turns"], tool_calls=len(r["tools"]),
        tool_names=[x.get("name") for x in r["tools"]],
        skills_installed=len(installed), skills_used=sorted(used),
        skill_first_use_s=({k: round(v - t0, 1) for k, v in used.items()}),
        listed_skills=r.get("listed_skills"), timed_out=r["timed_out"], rc=r["rc"],
        error=r["error"], limit_hit=r["limit_hit"], infra_error=infra,
        model_reported=r["model_reported"], outside_access=outside(r["tools"], ws),
        final_text=(r["final_text"] or "")[-1500:],
    )
    with lock:
        with open(RESULTS, "a") as f:
            f.write(json.dumps(rec) + "\n")
    shutil.rmtree(base, ignore_errors=True)
    print(f"{run_id:42s} pass={passed!s:5} part={partial:.2f} {wall:5.0f}s tools={len(r['tools']):3d} "
          f"cost={r['cost_usd']} used={sorted(used)} err={r['error']}", flush=True)
    return rec


def job(model, cond, task, rep):
    for attempt in range(1, len(BACKOFF) + 2):
        if model in exhausted:
            return
        try:
            rec = run_one(model, cond, task, rep, attempt)
        except Exception as e:  # harness bug: log and move on
            print(f"HARNESS ERROR {model} {cond} {task} r{rep}: {e!r}", flush=True)
            return
        if not rec["infra_error"]:
            return
        if attempt > len(BACKOFF):
            print(f"QUOTA? giving up on {model} after {attempt} failed attempts: {rec['error']}", flush=True)
            exhausted.add(model)
            return
        print(f"backoff {BACKOFF[attempt-1]}s for {model}: {rec['error']}", flush=True)
        time.sleep(BACKOFF[attempt - 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", required=True,
                    help="models per lane, lanes split by ';' (lanes run in parallel, max 3), "
                         "e.g. 'haiku,sonnet;luna;grok'")
    ap.add_argument("--conds", required=True)
    ap.add_argument("--tasks", default=",".join(sorted(p.name for p in TASKS.iterdir() if p.is_dir())))
    ap.add_argument("--reps", default="1")
    a = ap.parse_args()
    lanes = [l.split(",") for l in a.lanes.split(";")][:3]
    conds, tasks = a.conds.split(","), a.tasks.split(",")
    reps = [int(x) for x in a.reps.split(",")]
    RUNS.mkdir(exist_ok=True)
    have = done_ids()

    def lane_plan(models):
        plan = []
        for rep in reps:              # rep-major: an early stop still leaves even coverage
            for task in tasks:
                for cond in conds:
                    for model in models:
                        rid = f"{model}_{cond}_{task}_r{rep}"
                        if rid not in have and not any(h.startswith(rid + "_a") for h in have):
                            plan.append((model, cond, task, rep))
        return plan

    def lane(models):
        plan = lane_plan(models)
        print(f"lane {models}: {len(plan)} runs planned", flush=True)
        for j in plan:
            if STOP.exists():
                print("STOP file found, lane exits", flush=True)
                return
            job(*j)

    with ThreadPoolExecutor(len(lanes)) as ex:
        list(ex.map(lane, lanes))
    print("DONE", "exhausted:", sorted(exhausted), flush=True)


if __name__ == "__main__":
    main()
