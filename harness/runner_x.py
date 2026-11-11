#!/usr/bin/env python3
"""Video 3 remake experiments X1-X4 (PREREG_X_*.md). Reuses runner.py / backends.py unchanged.

  runner_x.py --exp X3|X1|X2 [--workers 3]      real runs -> runs_x/<run_id>/, runs_x/results.jsonl
  runner_x.py --exp X4                          idle "OK" probe (Sol) -> runs_x/idle_x.jsonl
  runner_x.py --probe sol|dsgo|sonnet           canary isolation probe -> probes/x_<model>_*.txt

Models:
  sonnet  Claude Code, backends.Claude unchanged (claude-sonnet-5-5).
  sol     NEW backend below. Pinned command from ai_compare/hard/runner_codex.py (video 2):
            codex exec --ignore-user-config -m gpt-6.1-sol -c model_reasoning_effort=medium
                       --sandbox workspace-write --skip-git-repo-check --json PROMPT
          plus the skills_value isolation: fresh HOME + CODEX_HOME per run (auth.json symlinked,
          never opened), web search and extra features off. Rollout kept -> rate_limits per run.
  dsgo    backends.OpenCode unchanged, model "opencode-go/deepseek-v4.1-flash#high" (OpenCode 2.2.5).
Grading: harness/grade.sh on a copy, hidden tests copied in after the run (runner.grade).
Guards (stop launching): Plus week > 80 % or 5 h >= 95 % or any limit error (sol);
Go spend at off-peak list > $10 or any limit error (dsgo); X3 36 launches max, any limit error (sonnet).
STOP file: runs_x/STOP stops every lane before its next launch.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import backends  # noqa: E402
from backends import Claude, OpenCode, child_env, stream, _jsonl, CODEX_OFF, OPENCODE_DB  # noqa: E402
from runner import PROMPT, TIMEOUT, build_ws, cond_skills, grade, outside, skill_use, ROOT  # noqa: E402

OUT = ROOT / "runs_x"
RESULTS = OUT / "results.jsonl"
STOPF = OUT / "STOP"
TASKS = ["t1_ratelimit", "t2_allocate", "t3_csvclean", "t4_refactor", "t5_duration", "t6_vm",
         "t7_semver", "t8_cron", "t9_fifo"]
PROMPT_NAMED = PROMPT + " Use the spec-check skill if it fits."
SOL = dict(inp=2.00, cache_read=0.10, cache_write=2.50, out=10.00)          # $/1M, as video 2
DS_OFFPEAK = dict(inp=0.15, cache_read=0.003, cache_write=0.15, out=0.60)   # = Go meter price
DS_PEAK = dict(inp=0.30, cache_read=0.006, cache_write=0.30, out=1.20)
PLUS_WEEK_CAP, GO_CAP, X3_CAP = 80.0, 10.0, 36
PLUS_5H_CAP = float(os.environ.get("PLUS_5H_CAP", "95"))

lock = threading.Lock()
stop = threading.Event()
state = {"launched": 0, "go_offpeak": 0.0, "plus": None}


# ---------------------------------------------------------------- Codex / Sol (new backend)
def read_rollout(path):
    steps, usage, last, rl, ctx = 0, None, None, [], None
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        p = d.get("payload") or {}
        if d.get("type") == "turn_context":
            ctx = {k: p.get(k) for k in ("model", "effort")}
        if p.get("type") == "token_count":
            info = p.get("info") or {}
            if info.get("total_token_usage"):
                steps += 1
                usage = info["total_token_usage"]
                last = info.get("last_token_usage") or last
            if p.get("rate_limits"):
                rl.append(p["rate_limits"])
    return steps, usage, last, rl, ctx


def sol_cost(u):
    inp, cached, cw, out = (u.get("input_tokens", 0), u.get("cached_input_tokens", 0),
                            u.get("cache_write_input_tokens", 0), u.get("output_tokens", 0))
    return (max(inp - cached - cw, 0) * SOL["inp"] + cw * SOL["cache_write"]
            + cached * SOL["cache_read"] + out * SOL["out"]) / 1e6


class CodexSol:
    cli = "codex"
    skills_dir = ".agents/skills"
    context_file = "AGENTS.md"

    def __init__(self, model="gpt-6.1-sol", home_root="/tmp"):
        self.model = model
        self.home_root = Path(home_root)

    def run(self, ws, prompt, timeout, max_turns=None):
        fake_home = self.home_root / "home"
        home = fake_home / ".codex"
        if fake_home.exists():
            shutil.rmtree(fake_home)
        home.mkdir(parents=True)
        (home / "auth.json").symlink_to(Path.home() / ".codex" / "auth.json")  # never opened
        cmd = ["nice", "-n", "10", "codex", "exec", "--ignore-user-config", "-m", self.model,
               "-c", "model_reasoning_effort=medium", "--sandbox", "workspace-write",
               "--skip-git-repo-check", "--json",
               "-c", "web_search=disabled", "-c", "model_reasoning_summary=auto"]
        for f in CODEX_OFF:
            cmd += ["-c", f"features.{f}=false"]
        cmd.append(prompt)
        env = child_env({"HOME": str(fake_home), "CODEX_HOME": str(home), "PWD": str(ws)})
        lines, err, rc, timed = stream(cmd, ws, env, timeout)
        tools, texts, errors, turns, usage = [], [], [], 0, {}
        for t, d in _jsonl(lines):
            ty = d.get("type")
            if ty == "item.completed":
                it = d.get("item", {})
                k = it.get("type")
                if k == "agent_message":
                    texts.append(it.get("text", ""))
                elif k in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                    tools.append({"t": t, "name": k, "input": it.get("command") or it.get("changes")})
            elif ty == "turn.completed":
                turns += 1
                for kk, vv in (d.get("usage") or {}).items():
                    if isinstance(vv, (int, float)):
                        usage[kk] = usage.get(kk, 0) + vv
            elif ty in ("error", "turn.failed"):
                errors.append(json.dumps(d)[:400])
        ro = sorted(glob.glob(str(home / "sessions" / "**" / "rollout-*.jsonl"), recursive=True))
        steps, ru, last, rl, ctx = read_rollout(ro[-1]) if ro else (0, None, None, [], None)
        u = ru or usage
        blob = (" ".join(errors) + err[-2000:]).lower()
        limit = any(s in blob for s in ("usage limit", "rate limit", "rate_limit", "quota", "429",
                                         "too many requests"))
        inp, cached, out = u.get("input_tokens", 0), u.get("cached_input_tokens", 0), u.get("output_tokens", 0)
        return {
            "raw": lines, "stderr": err, "rc": rc, "timed_out": timed,
            "error": ("limit" if limit else (errors[0] if errors else None)) if (errors or not u) else None,
            "limit_hit": limit,
            "tokens": {"input": inp - cached, "cache_write": u.get("cache_write_input_tokens", 0),
                       "cache_read": cached, "output": out, "reasoning": u.get("reasoning_output_tokens")},
            "cost_usd": round(sol_cost(u), 6) if u else None,
            "turns": turns, "tools": tools, "skill_calls": [],
            "final_text": texts[-1] if texts else "", "texts": texts,
            "listed_skills": None, "model_reported": [(ctx or {}).get("model") or self.model],
            "rollout": ro[-1] if ro else None, "steps": steps, "last_usage": last,
            "plus_before": rl[0] if rl else None, "plus_after": rl[-1] if rl else None, "context": ctx,
        }


# OpenCode 2.2.5 also loads ~/.agents/skills (the owner's 4 instabox skills, installed 31 Oct 19:20,
# after the original DeepSeek runs). Give it an empty fake HOME; data/cache/state stay at the real
# XDG paths so the CLI's own login and session DB are used as before. backends.OpenCode unchanged.
_tl = threading.local()
_orig_child_env = backends.child_env


def _child_env(extra=None):
    e = _orig_child_env(extra)
    e.update(getattr(_tl, "env", None) or {})
    return e


backends.child_env = _child_env


class OpenCodeGo(OpenCode):
    def run(self, ws, prompt, timeout, max_turns=None):
        fh = self.home_root / "home"
        fh.mkdir(parents=True, exist_ok=True)
        real = Path.home()
        _tl.env = {"HOME": str(fh), "XDG_DATA_HOME": str(real / ".local/share"),
                   "XDG_CACHE_HOME": str(real / ".cache"), "XDG_STATE_HOME": str(real / ".local/state")}
        try:
            return super().run(ws, prompt, timeout, max_turns)
        finally:
            _tl.env = {}


MODELS = {
    "sonnet": lambda h: Claude("claude-sonnet-5-5", h),
    "sol": lambda h: CodexSol("gpt-6.1-sol", h),
    "dsgo": lambda h: OpenCodeGo("opencode-go/deepseek-v4.1-flash#high", h),
}


def ds_price(t, p):
    return (t["input"] * p["inp"] + t["cache_write"] * p["cache_write"] + t["cache_read"] * p["cache_read"]
            + (t["output"] + (t["reasoning"] or 0)) * p["out"]) / 1e6


def oc_session(r):
    for _, ln in r["raw"]:
        m = re.search(r'"sessionID":"(ses_[^"]+)"', ln)
        if m:
            return m.group(1)
    return None


def oc_cost(sid):
    try:
        con = sqlite3.connect(str(OPENCODE_DB), timeout=30)
        row = con.execute("select cost from session_v2 where id=?", (sid,)).fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None


# ---------------------------------------------------------------- one run
def run_one(exp, model, arm, cond, task, rep, prompt, attempt=1):
    run_id = f"{exp}_{model}_{arm}_{task}_r{rep}" + (f"_a{attempt}" if attempt > 1 else "")
    backend = MODELS[model](Path("/tmp"))
    base, ws = build_ws(backend, task, cond)
    backend.home_root = base
    installed = cond_skills(cond)
    t0 = time.time()
    r = backend.run(ws, prompt, TIMEOUT)
    wall = time.time() - t0
    rd = OUT / run_id
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "stream.jsonl").write_text("".join(l for _, l in r["raw"]))
    (rd / "stderr.txt").write_text(r["stderr"][-20000:])
    if r.get("rollout"):
        shutil.copy(r["rollout"], rd / "rollout.jsonl")
    shutil.copytree(ws, rd / "ws", symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".claude", ".agents", ".opencode"))
    passed, partial, np_, nf = grade(task, ws, rd / "grade.txt")
    used = skill_use(r, installed, backend)
    infra = bool((r["error"] and not r["tools"]) or r["limit_hit"])
    rec = dict(
        exp=exp, run_id=run_id, model=model, model_id=backend.model, cli=backend.cli, arm=arm, cond=cond,
        task=task, rep=rep, attempt=attempt, prompt=prompt,
        started=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0)),
        wall_s=round(wall, 1), passed=passed, partial=round(partial, 3), tests_pass=np_, tests_fail=nf,
        tokens=r["tokens"], cost_usd=r["cost_usd"], turns=r["turns"], tool_calls=len(r["tools"]),
        tool_names=[x.get("name") for x in r["tools"]],
        skills_installed=len(installed), skills_used=sorted(used),
        skill_first_use_s={k: round(v - t0, 1) for k, v in used.items()},
        listed_skills=r.get("listed_skills"), timed_out=r["timed_out"], rc=r["rc"],
        error=r["error"], limit_hit=r["limit_hit"], infra_error=infra,
        model_reported=r["model_reported"], outside_access=outside(r["tools"], ws),
        final_text=(r["final_text"] or "")[-1500:],
    )
    if model == "sol":
        rec.update(steps=r["steps"], context=r["context"], plus_before=r["plus_before"],
                   plus_after=r["plus_after"], cost_basis="API-equivalent at Sol list price")
    if model == "dsgo":
        sid = oc_session(r)
        t = r["tokens"]
        rec.update(session=sid, opencode_cost=oc_cost(sid) if sid else None,
                   cost_go_offpeak=round(ds_price(t, DS_OFFPEAK), 6),
                   cost_if_paid_peak=round(ds_price(t, DS_PEAK), 6), opencode_version="2.2.5")
        rec["cost_usd"] = rec["cost_go_offpeak"]
        rec["cost_basis"] = "Go meter = DeepSeek off-peak list price"
    if model == "sonnet":
        rec["cost_basis"] = "Claude Code total_cost_usd (API-equivalent)"
    with lock:
        with open(RESULTS, "a") as f:
            f.write(json.dumps(rec) + "\n")
    shutil.rmtree(base, ignore_errors=True)
    pa = rec.get("plus_after") or {}
    print(f"{run_id:44s} pass={passed!s:5} part={partial:.2f} {wall:5.0f}s tools={len(r['tools']):3d} "
          f"cost={rec['cost_usd']} used={sorted(used)} err={r['error']} "
          f"plus5h={(pa.get('primary') or {}).get('used_percent')} week={(pa.get('secondary') or {}).get('used_percent')}",
          flush=True)
    return rec


def guard(rec):
    """Budget guards, checked after every run. Sets stop -> no further launches."""
    m = rec["model"]
    blob = json.dumps([rec.get("error"), rec.get("final_text", "")[-400:]]).lower()
    if rec.get("limit_hit"):
        print(f"GUARD {m}: limit/rate error -> stop ({rec.get('error')})", flush=True)
        stop.set()
    if m == "sol":
        pa = rec.get("plus_after") or {}
        p5 = (pa.get("primary") or {}).get("used_percent") or 0
        wk = (pa.get("secondary") or {}).get("used_percent") or 0
        state["plus"] = (p5, wk)
        if wk > PLUS_WEEK_CAP:
            print(f"GUARD sol: Plus week {wk} % > {PLUS_WEEK_CAP} -> stop", flush=True)
            stop.set()
        elif p5 >= PLUS_5H_CAP:   # no launches until the 5 h window has reset
            ra = (pa.get("primary") or {}).get("resets_at") or (time.time() + 3600)
            state["pause_until"] = max(state.get("pause_until", 0), ra + 60)
            print(f"GUARD sol: Plus 5h {p5} % -> no launches until {time.ctime(ra + 60)}", flush=True)
    if m == "dsgo":
        with lock:
            state["go_offpeak"] += rec.get("cost_go_offpeak") or 0
            s = state["go_offpeak"]
        if s > GO_CAP:
            print(f"GUARD dsgo: Go spend ${s:.2f} > ${GO_CAP} -> stop", flush=True)
            stop.set()
    if m == "sonnet" and ("usage limit" in blob or "rate limit" in blob or "session limit" in blob):
        print("GUARD sonnet: limit text -> stop", flush=True)
        stop.set()


def job(exp, model, arm, cond, task, rep, prompt):
    for attempt in (1, 2, 3):
        if stop.is_set() or STOPF.exists():
            return
        while time.time() < state.get("pause_until", 0) and not STOPF.exists():
            time.sleep(30)
        with lock:
            if exp == "X3" and state["launched"] >= X3_CAP:
                print("X3 cap reached, not launching", flush=True)
                return
            state["launched"] += 1
        try:
            rec = run_one(exp, model, arm, cond, task, rep, prompt, attempt)
        except Exception as e:  # harness bug: log and move on
            print(f"HARNESS ERROR {exp} {model} {arm} {task} r{rep}: {e!r}", flush=True)
            return
        guard(rec)
        if not rec["infra_error"] or rec["limit_hit"] or exp == "X3":
            return
        print(f"infra error, retry in 120 s: {rec['error']}", flush=True)
        time.sleep(120)


def done_ids():
    ids = set()
    if RESULTS.exists():
        for line in RESULTS.read_text().splitlines():
            r = json.loads(line)
            if not r.get("infra_error"):
                ids.add(re.sub(r"_a\d+$", "", r["run_id"]))
    return ids


def plan(exp):
    p = []
    if exp == "X3":
        for rep in (1, 2, 3):
            for t in TASKS:
                if rep == 1:
                    p.append(("X3", "sonnet", "plain", "C1", t, rep, PROMPT))
                p.append(("X3", "sonnet", "named", "C1", t, rep, PROMPT_NAMED))
    else:
        model = {"X1": "sol", "X2": "dsgo"}[exp]
        for rep in (1, 2, 3):                 # rep-major, as the original experiment
            for t in TASKS:
                for c in ("C0", "C1", "C4", "C5"):
                    p.append((exp, model, c, c, t, rep, PROMPT))
    have = done_ids()
    return [j for j in p if f"{j[0]}_{j[1]}_{j[2]}_{j[4]}_r{j[5]}" not in have]


# ---------------------------------------------------------------- X4 idle probe, canary probe
IDLE_Q = "Reply with exactly OK. Do not use any tools."


def idle_x():
    out = OUT / "idle_x.jsonl"
    for c in ("C0", "C5", "C4"):
        for rep in (0, 1):
            if STOPF.exists():
                return
            b = CodexSol("gpt-6.1-sol", "/tmp")
            base, ws = build_ws(b, "t1_ratelimit", c)
            b.home_root = base
            r = b.run(ws, IDLE_Q, 300)
            first = None
            if r.get("rollout"):
                for line in open(r["rollout"], errors="replace"):
                    d = json.loads(line)
                    p = d.get("payload") or {}
                    if p.get("type") == "token_count" and (p.get("info") or {}).get("last_token_usage"):
                        first = p["info"]["last_token_usage"]
                        break
            rec = dict(model="sol", cond=c, rep=rep, first_request=first,
                       input_total=(first or {}).get("input_tokens"), tokens=r["tokens"],
                       cost=r["cost_usd"], tools=len(r["tools"]), text=(r["final_text"] or "")[:80],
                       err=r["error"], steps=r["steps"], plus_after=r["plus_after"])
            with open(out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print("idle", c, rep, rec["input_total"], r["cost_usd"], repr(rec["text"][:20]), r["error"], flush=True)
            shutil.rmtree(base, ignore_errors=True)
            pa = r["plus_after"] or {}
            if ((pa.get("secondary") or {}).get("used_percent") or 0) > PLUS_WEEK_CAP or r["limit_hit"]:
                print("GUARD sol idle -> stop", flush=True)
                return


PROBE_Q = ("Answer from your context only, do not use any tools. 1) List the exact names of every skill "
           "available to you (or 'none'). 2) Quote the first line of any project instruction file "
           "(AGENTS.md/CLAUDE.md) you were given, or 'none'. 3) Do any of your instructions mention "
           "DeepSeek, OpenCode, T3 Code, YouTube, instabox or 'Model Behavior'? yes/no and quote. Keep it short.")


def canary(model):
    pdir = ROOT / "probes"
    for can in (True, False):
        base = Path(tempfile.mkdtemp(prefix="skvxprobe.", dir="/tmp")).resolve()
        b = MODELS[model](base)
        ws = base / "project"
        ws.mkdir()
        (ws / "TASK.md").write_text("probe\n")
        if can:
            d = ws / b.skills_dir / "zebra-canary"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text("---\nname: zebra-canary\ndescription: Use when the user mentions zebras.\n---\nSay ZEBRA.\n")
            (ws / b.context_file).write_text("PROJECT CANARY LINE 7731\n")
        r = b.run(ws, PROBE_Q, 300, max_turns=3)
        tag = f"x_{model}_{'canary' if can else 'empty'}"
        (pdir / f"{tag}.raw.jsonl").write_text("".join(l for _, l in r["raw"]))
        txt = (f"rc={r['rc']} err={r['error']} tokens={r['tokens']} cost={r['cost_usd']}\n"
               f"listed={r.get('listed_skills')}\nplus={r.get('plus_after')}\n\n{r['final_text']}\n")
        (pdir / f"{tag}.txt").write_text(txt)
        print("==", tag, txt, flush=True)
        shutil.rmtree(base, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp")
    ap.add_argument("--probe")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.probe:
        return canary(a.probe)
    if a.exp == "X4":
        return idle_x()
    p = plan(a.exp)
    print(f"{a.exp}: {len(p)} runs planned, workers={min(a.workers, 3)}", flush=True)
    if a.dry:
        for j in p:
            print(j[:6])
        return
    with ThreadPoolExecutor(min(a.workers, 3)) as ex:
        list(ex.map(lambda j: job(*j), p))
    print("DONE", a.exp, "stopped" if stop.is_set() else "complete", state, flush=True)


if __name__ == "__main__":
    main()
