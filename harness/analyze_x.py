#!/usr/bin/env python3
"""Readouts for PREREG_X_20261108_0223.md -> ../RESULTS_X.md (also printed).

Everything here is computed from runs_x/results.jsonl, runs_x/<run_id>/stream.jsonl and
runs_x/idle_x.jsonl. Skill opened = the skilluse.py rule (Skill/skill tool call naming it, or a tool
input containing `skills/<name>/`), recomputed from the raw stream.
"""
import json
import re
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
X = ROOT / "runs_x"
TASKS = ["t1_ratelimit", "t2_allocate", "t3_csvclean", "t4_refactor", "t5_duration", "t6_vm",
         "t7_semver", "t8_cron", "t9_fifo"]
DEV, HELD = set(TASKS[:6]), set(TASKS[6:])
RELEVANT = {"test-driven-development", "tdd", "systematic-debugging", "diagnosing-bugs",
            "verification-before-completion"}


def installed(cond):
    d = ROOT / "conditions" / cond / "skills"
    return sorted(p.name for p in d.iterdir() if (p / "SKILL.md").exists()) if d.exists() else []


def tool_calls(rid, cli):
    p = X / rid / "stream.jsonl"
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


def load():
    allr, best = [], {}
    for line in (X / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        allr.append(r)
        if r.get("infra_error"):
            continue
        r["opened"] = skills_opened(r)
        best[(r["exp"], r["model"], r["arm"], r["task"], r["rep"])] = r
    return allr, list(best.values())


def tok_in(r):
    t = r["tokens"]
    return (t.get("input") or 0) + (t.get("cache_write") or 0) + (t.get("cache_read") or 0)


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def f(x, nd=0, pre=""):
    return "–" if x is None else f"{pre}{x:,.{nd}f}"


def band(n, total):
    if n is None:
        return "–"
    if n >= 20:
        return "opened it nearly every time"
    if n >= 1:
        return "sometimes"
    return "never, like Sonnet"


def paired(rows, arm, fn):
    idx = {(r["arm"], r["task"], r["rep"]): r for r in rows}
    xs = []
    for (a, t, rep), r in idx.items():
        if a == arm and ("C0", t, rep) in idx:
            b = idx[("C0", t, rep)]
            if fn(b) and fn(r) is not None:
                xs.append(fn(r) / fn(b))
    return med(xs), len(xs)


def cell_table(rows, arms, L):
    L.append("| Arm | Runs | Pass | Pass dev t1–t6 | Pass held-out t7–t9 | Opened own skill | "
             "Median tokens in | Median cost $/run | Total cost $ | Median time s | Timed out |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for a in arms:
        rs = [r for r in rows if r["arm"] == a]
        if not rs:
            continue
        own = installed(rs[0]["cond"])
        op = sum(1 for r in rs if any(s in own for s in r["opened"])) if own else None
        k = sum(r["passed"] for r in rs)
        kd = [r for r in rs if r["task"] in DEV]
        kh = [r for r in rs if r["task"] in HELD]
        L.append(f"| {a} | {len(rs)} | {k}/{len(rs)} | {sum(r['passed'] for r in kd)}/{len(kd)} | "
                 f"{sum(r['passed'] for r in kh)}/{len(kh)} | {'n/a' if op is None else f'{op}/{len(rs)}'} | "
                 f"{f(med(tok_in(r) for r in rs))} | {f(med(r['cost_usd'] for r in rs), 4)} | "
                 f"{f(sum(r['cost_usd'] or 0 for r in rs), 2)} | {f(med(r['wall_s'] for r in rs))} | "
                 f"{sum(1 for r in rs if r['timed_out'])} |")


def ratio_table(rows, L):
    L.append("| Arm vs C0 (paired on task, rep) | Pairs | C0 pass | Arm pass | Only arm passed | Only C0 passed | "
             "Cost ×R | Tokens-in ×R | Time ×R |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    idx = {(r["arm"], r["task"], r["rep"]): r for r in rows}
    out = {}
    for a in ("C1", "C4", "C5"):
        prs = [(idx[("C0", t, rep)], r) for (aa, t, rep), r in idx.items() if aa == a and ("C0", t, rep) in idx]
        if not prs:
            continue
        cr, _ = paired(rows, a, lambda r: r["cost_usd"])
        tr, _ = paired(rows, a, tok_in)
        wr, _ = paired(rows, a, lambda r: r["wall_s"])
        out[a] = (cr, tr)
        L.append(f"| {a} | {len(prs)} | {sum(p[0]['passed'] for p in prs)}/{len(prs)} | "
                 f"{sum(p[1]['passed'] for p in prs)}/{len(prs)} | "
                 f"{sum(1 for p in prs if p[1]['passed'] and not p[0]['passed'])} | "
                 f"{sum(1 for p in prs if p[0]['passed'] and not p[1]['passed'])} | "
                 f"{f(cr, 2)}× | {f(tr, 2)}× | {f(wr, 2)}× |")
    return out


def c5_line(rows, L):
    rs = [r for r in rows if r["arm"] == "C5"]
    if not rs:
        return
    c5 = set(installed("C5"))
    cnt = defaultdict(int)
    anyu = rel = irr = 0
    for r in rs:
        s = [x for x in r["opened"] if x in c5]
        for x in s:
            cnt[x] += 1
        anyu += bool(s)
        rel += any(x in RELEVANT for x in s)
        irr += any(x not in RELEVANT and x != "using-superpowers" for x in s)
    top = ", ".join(f"{k} ({v})" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])) or "–"
    L.append(f"C5 (50 skills): opened any {anyu}/{len(rs)}, a relevant one {rel}/{len(rs)}, "
             f"an irrelevant one {irr}/{len(rs)}. Opened: {top}.")


def main():
    allr, rows = load()
    L = [f"# RESULTS X (generated by `harness/analyze_x.py`, {time.strftime('%Y-%m-%d %H:%M %Z')})", "",
         "Pre-registration: `PREREG_X_20261108_0223.md` (sha256 in `PREREG_X.sha256`). Raw data: `runs_x/`.",
         "Costs are API-equivalent / list prices, not cash (plan flat fees already paid).", ""]
    infra = [r for r in allr if r.get("infra_error")]
    L.append(f"Valid runs: {len(rows)}. Infra-error attempts excluded: {len(infra)}"
             + (f" ({', '.join(r['run_id'] + ': ' + str(r['error'])[:60] for r in infra)})" if infra else "") + ".")
    readout = {}

    # ---------------- X3
    x3 = [r for r in rows if r["exp"] == "X3"]
    L += ["", "## X3 — Sonnet 5.5, skill named in the request (Claude Code 2.1.316)", ""]
    if x3:
        cell_table(x3, ["plain", "named"], L)
        nm = [r for r in x3 if r["arm"] == "named"]
        pl = [r for r in x3 if r["arm"] == "plain"]
        n_named = sum(1 for r in nm if "spec-check" in r["opened"])
        n_plain = sum(1 for r in pl if "spec-check" in r["opened"])
        listed = sum(1 for r in pl if "spec-check" in (r.get("listed_skills") or []))
        L += ["", f"- **Named: opened `spec-check` in {n_named}/{len(nm)}** → fixed wording: "
                  f"**\"{band(n_named, len(nm)) if len(nm) == 27 else 'incomplete (n=' + str(len(nm)) + ')'}\"**"
                  + (" · \"name it in your request\" applies" if n_named >= 1 else ""),
              f"- **Plain (today's Claude Code): opened {n_plain}/{len(pl)}** (skill listed to the model in "
              f"{listed}/{len(pl)}) → " + ("**the 0/108 line gets \"on the 31 Oct version\" on screen**"
                                             if n_plain else "**0/108 line unchanged**"),
              f"- Total Claude API-equivalent for X3: ${sum(r['cost_usd'] or 0 for r in x3 + [r for r in infra if r['exp'] == 'X3']):.2f}"]
        readout["X3"] = (n_named, len(nm), n_plain, len(pl))

    # ---------------- X1 / X2
    for exp, title in (("X1", "GPT-6.1 Sol in Codex 0.165.0 (medium), ChatGPT Plus"),
                       ("X2", "DeepSeek V4.1 Flash (high) on OpenCode Go, OpenCode 2.2.5")):
        rs = [r for r in rows if r["exp"] == exp]
        L += ["", f"## {exp} — {title}", ""]
        if not rs:
            L.append("No valid runs.")
            continue
        cell_table(rs, ["C0", "C1", "C4", "C5"], L)
        L.append("")
        rat = ratio_table(rs, L)
        L.append("")
        c5_line(rs, L)
        c1 = [r for r in rs if r["arm"] == "C1"]
        n1 = sum(1 for r in c1 if "spec-check" in r["opened"])
        if exp == "X1":
            L += ["", f"- **Opened mine: {n1}/{len(c1)}** → fixed wording: "
                      f"**\"{band(n1, len(c1)) if len(c1) == 27 else 'incomplete (n=' + str(len(c1)) + ')'}\"**"]
            for a in ("C1", "C4", "C5"):
                if a in rat:
                    L.append(f"- Cost ×{f(rat[a][0], 2)} vs nothing for {a} (stated as is)")
            pl = [r for r in sorted(rs + [r for r in infra if r['exp'] == 'X1'], key=lambda r: r["started"])
                  if r.get("plus_after")]
            if pl:
                a0 = pl[0].get("plus_before") or pl[0]["plus_after"]
                a1 = max(pl, key=lambda r: r["started"])["plus_after"]
                L.append(f"- Plus meter: first run before 5 h {a0['primary']['used_percent']} % / week "
                         f"{a0['secondary']['used_percent']} % → last run after 5 h {a1['primary']['used_percent']} % / "
                         f"week {a1['secondary']['used_percent']} %")
            L.append(f"- API-equivalent total: ${sum(r['cost_usd'] or 0 for r in rs):.2f}")
            readout["X1"] = (n1, len(c1), rat)
        else:
            R = rat.get("C4", (None, None))[1]
            L += ["", f"- **Read-ratio R (C4 ÷ C0 input tokens, median of pairs) = {f(R, 2)}×** → "
                      + ("**line dropped (R < 1.3)**" if R is not None and R < 1.3 else
                         f"**stated with \"on DeepSeek\": ×{f(R, 1)}**"),
                  f"- Opened mine (reported, no wording): {n1}/{len(c1)}",
                  f"- Go spend (off-peak list = Go meter): ${sum(r.get('cost_go_offpeak') or 0 for r in rs + [r for r in infra if r['exp'] == 'X2']):.2f}"
                  f" (peak list would be ${sum(r.get('cost_if_paid_peak') or 0 for r in rs):.2f}); "
                  f"OpenCode's own reported cost: ${sum(r.get('opencode_cost') or 0 for r in rs):.2f}"]
            readout["X2"] = (R, n1, len(c1))

    # ---------------- X4
    L += ["", "## X4 — idle \"OK\" probe, Sol in Codex", ""]
    ip = X / "idle_x.jsonl"
    if ip.exists():
        recs = [json.loads(l) for l in ip.read_text().splitlines()]
        by = defaultdict(list)
        for r in recs:
            if r.get("input_total"):
                by[r["cond"]].append(r["input_total"])
        L.append("| Cond | Requests | First-request input tokens (median) | All |")
        L.append("|---|---|---|---|")
        for c in ("C0", "C5", "C4"):
            L.append(f"| {c} | {len(by[c])} | {f(med(by[c]))} | {', '.join(str(x) for x in by[c])} |")
        if by["C0"] and by["C5"]:
            L.append(f"\n- Per idle skill (C5 − C0)/50 = **{(med(by['C5']) - med(by['C0'])) / 50:.0f} tokens**")
        if by["C0"] and by["C4"]:
            L.append(f"- Bloated file (C4 − C0) = **+{med(by['C4']) - med(by['C0']):,.0f} tokens** per request")
    else:
        L.append("Not run.")

    L += ["", "## Notes and deviations", ""] + [f"- {n}" for n in NOTES]
    txt = "\n".join(L) + "\n"
    (ROOT / "RESULTS_X.md").write_text(txt)
    print(txt)


NOTES = [
    "Canary probes found that OpenCode 2.2.5 also loads `~/.agents/skills` (the owner's 4 instabox skills, "
    "installed 31 Oct 19:20, after the original DeepSeek runs). X2 runs OpenCode with an empty fake HOME "
    "(real XDG data/cache/state for login and DB); re-probe clean. Written into the PREREG before any run.",
    "Sol runs use the video 2 pinned command plus the skills_value Codex isolation (fresh HOME/CODEX_HOME, "
    "web search and extra features off). Not `--ephemeral`, so the rollout with rate_limits is kept per run.",
    "Plus 5-hour guard implemented as a pause (no launches until the window resets), weekly > 80 % as a hard stop.",
    "X3, X1 and X2 ran side by side (separate providers and budgets), launched in the order X3 → X1 → X2; X4 after X1.",
    "X1: at ~03:05 the Plus 5-hour meter crossed 95 % with 3 runs in flight; one run hit the real usage limit "
    "(infra error, excluded, re-run) and the guard stopped X1 after 34 launches. After the 03:15 reset X1 resumed "
    "with the 5-hour pause at 90 % (`PREREG_X_ADDENDUM_20261108_0320.md`, sha256 in `PREREG_X.sha256`).",
    "Outside-workspace flag: 1 run (`X2_dsgo_C5_t7_semver_r1`): DeepSeek loaded npm's bundled `semver` "
    "library from the system Node install to cross-check its answers. It did not touch hidden tests or the harness. "
    "Kept as valid (the grader is hidden; the original runs allowed system tools too).",
    "Plan usage: Plus weekly 54 % → 70 % (probes + X1 + X4); the 5-hour window maxed once (see above). "
    "Go $1.51 at off-peak list. Claude: X3 $4.13 + canary $0.05 API-equivalent, no limit errors.",
    "Sonnet ran on Claude Code 2.1.316 (31 Oct: 2.1.312). Codex 0.165.0 unchanged.",
]

if __name__ == "__main__":
    main()
