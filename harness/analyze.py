#!/usr/bin/env python3
"""Summarise runs/results.jsonl into markdown tables (printed to stdout)."""
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from skilluse import skills_opened  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEV = {"t1_ratelimit", "t2_allocate", "t3_csvclean", "t4_refactor", "t5_duration", "t6_vm"}
HELD = {"t7_semver", "t8_cron", "t9_fifo"}
RELEVANT = {"test-driven-development", "tdd", "systematic-debugging", "diagnosing-bugs",
            "verification-before-completion"}
NEUTRAL = {"using-superpowers"}
CLAUDE_BUILTIN = {"opencode", "report", "imagegen", "openai-docs", "skill-creator", "skill-installer",
                  "dataviz", "update-config", "verify", "debug", "code-review", "simplify", "batch",
                  "fewer-permission-prompts", "doctor", "loop", "schedule", "claude-api", "run",
                  "run-skill-generator", "plugin-authoring", "init", "security-review",
                  "keybindings-help"}
CONDS = ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]
MODELS = ["sonnet", "haiku", "luna", "grokm", "grok", "deepseek", "opus"]
C5_SKILLS = {l.split("\t")[0] for l in (ROOT / "conditions/C5/SOURCES.tsv").read_text().splitlines()}


def load():
    best = {}
    for line in (ROOT / "runs/results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r.get("infra_error"):
            continue
        key = (r["model"], r["cond"], r["task"], r["rep"])
        r["skills_used"] = skills_opened(r)  # recomputed from the raw stream, same rule for all CLIs
        best[key] = r  # last valid attempt wins
    return list(best.values())


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def tok_in(r):
    t = r["tokens"]
    return (t.get("input") or 0) + (t.get("cache_write") or 0) + (t.get("cache_read") or 0)


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def own_skills(r):
    """Skills opened that belong to the condition (not CLI built-ins)."""
    out = []
    for s in r.get("skills_used", []):
        if s in CLAUDE_BUILTIN or s.startswith("other:"):
            continue
        out.append(s)
    return out


def fmt(x, nd=0, pre=""):
    if x is None:
        return "–"
    return f"{pre}{x:,.{nd}f}"


def table(rows, title, tasks):
    print(f"\n### {title}\n")
    print("| Model | Cond | Pass | Rate (95% CI) | Partial | Median tokens in | Median out | "
          "Median cost $ | Median time s | Median tool calls | Skill opened |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    g = defaultdict(list)
    for r in rows:
        if r["task"] in tasks:
            g[(r["model"], r["cond"])].append(r)
    for m in MODELS:
        for c in CONDS:
            rs = g.get((m, c))
            if not rs:
                continue
            k, n = sum(r["passed"] for r in rs), len(rs)
            lo, hi = wilson(k, n)
            used = sum(1 for r in rs if own_skills(r))
            su = f"{used}/{n}" if c in ("C1", "C2", "C3", "C5") else "n/a"
            print(f"| {m} | {c} | {k}/{n} | {100*k/n:.0f}% ({100*lo:.0f}–{100*hi:.0f}) | "
                  f"{100*st.mean(r['partial'] for r in rs):.0f}% | {fmt(med(tok_in(r) for r in rs))} | "
                  f"{fmt(med(r['tokens'].get('output') for r in rs))} | "
                  f"{fmt(med(r['cost_usd'] for r in rs), 3)} | {fmt(med(r['wall_s'] for r in rs))} | "
                  f"{fmt(med(r['tool_calls'] for r in rs))} | {su} |")


def pooled(rows, title, tasks):
    print(f"\n### {title}: each condition vs C0, paired on (model, task, rep)\n")
    print("| Cond | Pairs | C0 pass | Cond pass | Δ pp | Only cond passed | Only C0 passed | "
          "Median cost ratio vs C0 | Median tokens-in ratio | Median time ratio |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    idx = {(r["model"], r["cond"], r["task"], r["rep"]): r for r in rows if r["task"] in tasks}
    for c in CONDS[1:]:
        pairs = []
        for (m, cc, t, rep), r in idx.items():
            if cc == c and (m, "C0", t, rep) in idx:
                pairs.append((idx[(m, "C0", t, rep)], r))
        if not pairs:
            continue
        n = len(pairs)
        a = sum(p[0]["passed"] for p in pairs)
        b = sum(p[1]["passed"] for p in pairs)
        oc = sum(1 for p in pairs if p[1]["passed"] and not p[0]["passed"])
        o0 = sum(1 for p in pairs if p[0]["passed"] and not p[1]["passed"])

        def ratio(f):
            xs = [f(p[1]) / f(p[0]) for p in pairs if f(p[0]) and f(p[1]) is not None]
            return med(xs)
        cr = ratio(lambda r: r["cost_usd"])
        tr = ratio(tok_in)
        wr = ratio(lambda r: r["wall_s"])
        print(f"| {c} | {n} | {a}/{n} | {b}/{n} | {100*(b-a)/n:+.0f} | {oc} | {o0} | "
              f"{fmt(cr, 2)}× | {fmt(tr, 2)}× | {fmt(wr, 2)}× |")


def c5_picks(rows):
    rs = [r for r in rows if r["cond"] == "C5"]
    if not rs:
        return
    print("\n### C5 (50 installed skills): what got opened\n")
    print("| Model | Runs | Opened any C5 skill | Opened a relevant one | Opened an irrelevant one | "
          "Skills opened (count) |")
    print("|---|---|---|---|---|---|")
    for m in MODELS:
        mr = [r for r in rs if r["model"] == m]
        if not mr:
            continue
        cnt = defaultdict(int)
        anyu = rel = irr = 0
        for r in mr:
            s = [x for x in own_skills(r) if x in C5_SKILLS]
            for x in s:
                cnt[x] += 1
            anyu += bool(s)
            rel += any(x in RELEVANT for x in s)
            irr += any(x not in RELEVANT and x not in NEUTRAL for x in s)
        top = ", ".join(f"{k} ({v})" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]))
        print(f"| {m} | {len(mr)} | {anyu} | {rel} | {irr} | {top or '–'} |")


def builtin_use(rows):
    cnt = defaultdict(int)
    for r in rows:
        for s in r.get("skills_used", []):
            if s in CLAUDE_BUILTIN or s.startswith("other:"):
                cnt[(r["model"], r["cond"], s)] += 1
    if cnt:
        print("\n### Built-in / other skills opened (present in every condition)\n")
        for k, v in sorted(cnt.items()):
            print(f"- {k}: {v}")


def per_model(rows):
    print("\n### Per model, all tasks: condition vs C0 (paired on task, rep)\n")
    print("| Model | Cond | Pairs | C0 pass | Cond pass | Δ pp | Median cost ratio | Median tokens-in ratio | "
          "Median time ratio | Median tool-call ratio |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    idx = {(r["model"], r["cond"], r["task"], r["rep"]): r for r in rows}
    for m in MODELS:
        for c in CONDS[1:]:
            pairs = [(idx[(m, "C0", t, rep)], r) for (mm, cc, t, rep), r in idx.items()
                     if mm == m and cc == c and (m, "C0", t, rep) in idx]
            if not pairs:
                continue
            n = len(pairs)
            a = sum(p[0]["passed"] for p in pairs)
            b = sum(p[1]["passed"] for p in pairs)

            def ratio(f):
                xs = [f(p[1]) / f(p[0]) for p in pairs if f(p[0]) and f(p[1]) is not None]
                return med(xs)
            print(f"| {m} | {c} | {n} | {a}/{n} | {b}/{n} | {100*(b-a)/n:+.0f} | "
                  f"{fmt(ratio(lambda r: r['cost_usd']), 2)}× | {fmt(ratio(tok_in), 2)}× | "
                  f"{fmt(ratio(lambda r: r['wall_s']), 2)}× | {fmt(ratio(lambda r: r['tool_calls']), 2)}× |")


def main():
    rows = load()
    print(f"Valid runs: {len(rows)}")
    table(rows, "All tasks", DEV | HELD)
    table(rows, "Held-out tasks t7–t9", HELD)
    table(rows, "Dev tasks t1–t6", DEV)
    pooled(rows, "All tasks", DEV | HELD)
    pooled(rows, "Held-out t7–t9", HELD)
    pooled(rows, "Dev t1–t6", DEV)
    per_model(rows)
    c5_picks(rows)
    builtin_use(rows)
    # per task pass matrix
    print("\n### Pass count per task × condition (all models)\n")
    print("| Task | " + " | ".join(CONDS) + " |")
    print("|---|" + "---|" * len(CONDS))
    for t in sorted(DEV | HELD):
        cells = []
        for c in CONDS:
            rs = [r for r in rows if r["task"] == t and r["cond"] == c]
            cells.append(f"{sum(r['passed'] for r in rs)}/{len(rs)}" if rs else "–")
        print(f"| {t} | " + " | ".join(cells) + " |")
    if "--fails" in sys.argv:
        print("\n### Failed runs\n")
        for r in sorted(rows, key=lambda r: r["run_id"]):
            if not r["passed"]:
                g = (ROOT / "runs" / r["run_id"] / "grade.txt")
                fl = [l for l in g.read_text().splitlines() if l.startswith("FAIL")] if g.exists() else []
                print(f"- {r['run_id']}: {r['partial']:.2f} {'; '.join(x[:90] for x in fl)}")


if __name__ == "__main__":
    main()
