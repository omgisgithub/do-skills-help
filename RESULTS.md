# Exp 004 — Do agent skills actually help? Results

Run Sat 31 Oct 2026, 12:50–17:10 CET, on this Mac, through the real CLIs on the owner's
subscriptions. Design and pre-registered predictions: `SPEC.md` (written before any skill
condition ran; addenda at its end mark what changed during the run). Full auto-generated tables:
`runs/analysis.md`. Candidate quotes: `runs/moments.md`. Raw logs per run: `runs/<run_id>/`.

## Headline

1. **Nothing beat "no skills" on the new tasks.** On the 3 held-out tasks, no skill pack, AI-written
   skill or context file raised the pass rate. Every one of them made runs more expensive.
2. **The bloated AGENTS.md/CLAUDE.md was the worst buy:** same results, **+60% cost** (median,
   paired), +66% input tokens, +33% time. 50 installed skills: same results, +20% cost.
3. **My own 35-line skill fixed exactly the mistake it was written for and nothing else.** It took
   the one task models kept failing from 6/11 to 8/8, but did nothing on new tasks. And Sonnet 5.5
   **never opened a single skill in 108 tries**, even when it was the right one.

In my setup, with these 9 small Python tasks. Strong models were already near 100% without help,
so this shows **costs** clearly and **benefits** only weakly (see Limits).

## What ran

| Model | CLI | Valid runs | Coverage | Stopped because |
|---|---|---|---|---|
| Claude Sonnet 5.5 | Claude Code 2.1.312 | 189 | 9 tasks × 7 conds × 3 reps (complete) | – |
| Claude Haiku 5.5 | Claude Code 2.1.312 | 189 | complete | – |
| GPT-6 Luna (medium) | Codex 0.165.0, ChatGPT plan | 63 | C0 all ×3; C1–C5 ~1 rep each | Codex quota: "You've hit your usage limit… try again at Nov 26th" |
| DeepSeek V4.1 Flash Free | OpenCode 2.2.1 | 18 | t1–t3 rep 1 only | "Free usage limit reached" after 22 runs |
| Grok 4.7 | grok 1.0.70 | 6 default + 8 medium effort | t1–t4, t7, t8 | 12 of 14 runs hit the 15-min limit (see Grok section) |

Conditions (details in SPEC.md): **C0** nothing · **C1** my 35-line hand-written skill
(`conditions/C1/skills/spec-check/SKILL.md`, each rule traced to a logged pilot failure in
`conditions/C1/WHY.md`) · **C2** Ponytail pack (its AGENTS.md + 6 skills) · **C3** a 200-line
"comprehensive" skill written by Sonnet 5.5, unedited · **C4** a 730-line generated AGENTS.md /
CLAUDE.md, unedited · **C5** 50 real public skills · **C6** (added mid-run, not pre-registered)
C1's exact text as an always-loaded CLAUDE.md/AGENTS.md instead of a skill.

Tasks: t1–t6 = the old mini benchmark ("dev": C1 was written from failures on these); t7 semver
ranges, t8 cron next-run, t9 FIFO inventory with 5 planted bugs = new "held-out" tasks no model saw
before C1 was written.

API-equivalent cost of everything (what it would cost on the API; subscriptions charged nothing
extra): Sonnet $23.64, Haiku $2.98, Luna $0.21, Grok ≥ $0.69 (timeouts don't report cost),
DeepSeek $0.

## Main table (all 9 tasks)

Cost = median API-equivalent $ per run. Tokens in = uncached + cache write + cache read.
"Skill opened" = runs where the agent actually opened one of the condition's skills.

| Model | Cond | Pass | Rate (95% CI) | Median tokens in | Median cost $ | Median time s | Skill opened |
|---|---|---|---|---|---|---|---|
| Sonnet 5.5 | C0 none | 27/27 | 100% (88–100) | 88,039 | 0.099 | 18 | – |
| | C1 own skill | 27/27 | 100% (88–100) | 89,993 | 0.102 | 21 | **0/27** |
| | C2 Ponytail | 26/27 | 96% (82–99) | 95,630 | 0.103 | 18 | 0/27 |
| | C3 AI skill | 26/27 | 96% (82–99) | 87,437 | 0.101 | 22 | 0/27 |
| | C4 bloated file | 27/27 | 100% (88–100) | 142,402 | **0.154** | 22 | – |
| | C5 50 skills | 27/27 | 100% (88–100) | 105,792 | 0.118 | 22 | 0/27 |
| | C6 own text as file | 27/27 | 100% (88–100) | 118,870 | 0.115 | 26 | – |
| Haiku 5.5 | C0 none | 25/27 | 93% (77–98) | 172,320 | 0.011 | 43 | – |
| | C1 own skill | **27/27** | 100% (88–100) | 210,158 | 0.011 | 46 | 20/27 |
| | C2 Ponytail | 25/27 | 93% (77–98) | 221,408 | 0.011 | 40 | 1/27 |
| | C3 AI skill | 26/27 | 96% (82–99) | 207,033 | 0.013 | 51 | 12/27 |
| | C4 bloated file | 25/27 | 93% (77–98) | 323,821 | **0.017** | 56 | – |
| | C5 50 skills | 24/27 | 89% (72–96) | 201,791 | 0.011 | 45 | 0/27 |
| | C6 own text as file | **27/27** | 100% (88–100) | 246,637 | 0.014 | 79 | – |
| GPT-6 Luna | C0 none | 17/21 | 81% (60–92) | 44,086 | 0.002 | 17 | – |
| | C1 own skill | 8/9 | 89% (56–98) | 79,866 | 0.003 | 23 | 9/9 |
| | C2 Ponytail | 8/9 | 89% (56–98) | 88,529 | 0.003 | 26 | 3/9 |
| | C3 AI skill | 6/8 | 75% (41–93) | 75,224 | 0.002 | 21 | 1/8 |
| | C4 bloated file | 6/8 | 75% (41–93) | 155,872 | 0.005 | 28 | – |
| | C5 50 skills | 6/8 | 75% (41–93) | 95,424 | 0.003 | 21 | 6/8 |
| DeepSeek V4.1 Flash | C0–C6 | 18/18 | 100% each (n=2–3) | 70k–250k | free | 45–101 | C1 2/3, others 0 |

Luna's and DeepSeek's cells are tiny (quota); read them as anecdotes.

## Each condition vs no skills (paired on same model, task, rep; Sonnet + Haiku + Luna + DeepSeek + Grok)

| Cond | Held-out t7–t9: pass C0 → cond | Dev t1–t6: pass C0 → cond | All: median cost | All: median tokens in | All: median time |
|---|---|---|---|---|---|
| C1 own skill | 22/24 → 21/24 (−4 pp) | 42/45 → 45/45 (**+7 pp**, 3 rescued, 0 lost) | 1.05× | 1.06× | 1.06× |
| C2 Ponytail | 22/23 → 22/23 (0) | 42/45 → 41/45 (−2 pp) | 1.12× | 1.10× | 1.09× |
| C3 AI "comprehensive" skill | 21/22 → 20/22 (−5 pp) | 42/45 → 42/45 (0) | 1.03× | 1.02× | 1.05× |
| C4 bloated context file | 20/20 → 19/20 (−5 pp) | 41/44 → 41/44 (0) | **1.60×** | **1.66×** | **1.33×** |
| C5 50 skills | 20/20 → 18/20 (−10 pp) | 41/44 → 41/44 (0) | 1.20× | 1.24× | 1.08× |
| C6 own text, always on | 18/18 → 18/18 (0) | 36/38 → 38/38 (+5 pp) | 1.24× | 1.37× | 1.57× |

Per model, cost ratio vs C0 for the bloated file (C4): Sonnet 1.58×, Haiku 1.62×, Luna 2.11×
(DeepSeek 3.3× input tokens). For 50 skills (C5): Sonnet 1.20×, Haiku 1.18×, Luna 1.46×.

No pass-rate difference above is statistically clear: with 20–70 pairs, anything under
~10–15 pp is noise. The cost differences are consistent across models and tasks.

**Where all the failures were.** Of 24 failed runs outside Grok, 16 were on one task, t3 (CSV
cleaner), and nearly all for the same reason: the spec lists `Mar 4, 2026` as a date format and the
model also accepted `Mar 4 2026`. C1 names exactly that example. That is why C1 (8/8) and C6 (6/6)
fixed t3 while everything else stayed at 4–6 of 7–8.

## The pre-registered claims

| # | Claim | Verdict in this test | Evidence |
|---|---|---|---|
| A | Hand-written focused skill helps (+16.6 pp) | **Not shown.** Helps only on the mistake it was written for | Dev +7 pp (3 rescues, 0 losses); held-out −4 pp. Held-out C0 was already 22/24, so a big gain was impossible there |
| A′ | …or it just patches known mistakes | **Right** | All 3 rescues (Haiku t3 r1, r2; Luna t3 r1) are the t3 date mistake that C1 names word for word; nothing transferred to t7–t9 |
| B | AI-written skills hurt (−8 to −11.5 pp) | **Not shown** | −1 pp overall, within noise. It was mostly ignored: opened by Sonnet 0/27, Haiku 12/27, Luna 1/8 |
| C | Long "comprehensive" skills barely help | **Right** | C3: −1 pp, +3% cost |
| D | Skills often don't trigger (Vercel: 56% never used) | **Right, and model-dependent** | Own skill opened: Sonnet **0/27**, Haiku 20/27, Luna 9/9, DeepSeek 2/3, Grok 3/3. Sonnet 0 of 108 across all skill conditions |
| E | Context file: cost up ~20%, success flat (ETH) | **Right, and worse here** | C4: +60% cost, +66% tokens, +33% time, pass −2 pp |
| F | Idle skill ≈ 100 tokens | **Right (≈80)** | See idle cost below |
| G | Community packs no better than your own | **Consistent, weakly** | Ponytail −1 pp, +12% cost; own skill +3 pp, +5% cost |
| H | Many skills → wrong skill picked | **Model-dependent** | Claude models opened none of the 50 (0/54). Luna opened `brainstorming` (irrelevant) in 4/8 C5 runs, always together with `using-superpowers` and `test-driven-development` |
| C6 | (post-hoc) Same text, always on vs as a skill | Same pass rate as the skill, **more cost** | Haiku 27/27 both ways, but cost 1.50× vs 1.07× of C0; Sonnet actually follows it (tool calls +33%, time +48%) but was already at 100% |

## Idle cost of installed skills (measured)

One "Reply with exactly OK" request per CLI and condition, 2 repeats, input tokens of that request:

| CLI (model) | C0 | +1 skill (C1) | +50 skills (C5) | per idle skill | + bloated file (C4) |
|---|---|---|---|---|---|
| Claude Code (Haiku) | 14,775 | +82 | +4,054 | **81** | +12,804 |
| OpenCode (DeepSeek) | 5,113 | +87 | +3,925 | **79** | +8,274 |
| Grok CLI (Grok 4.7) | 13,668 | +148 | +3,920 | **78** | +8,102 |
| Codex (Luna, canary probe) | 9,623 | +78 (1 skill + 1-line AGENTS.md) | – | – | – |

So 50 idle skills add ~4k tokens to **every** request. In real runs that showed up as +19–24% input
tokens and +20% cost (C5), even though Claude models never opened one of them. The 730-line file
adds 8–13k tokens per request (Codex truncates it at its 32 KiB limit; the file is 34.5 KB).

## Grok

Grok 4.7 could not be measured fairly. At its default effort, 4 of 6 runs hit the 15-minute limit:
`grok_C0_t1_ratelimit_r1` fixed the bug in its first minutes and then kept thinking until the
timeout (3,781 thinking chunks); on semver it wrote ~100k characters of thinking and no code
(`grok_C0_t7_semver_r1`). Switched to `--effort medium`: **all** runs still hit 15 minutes, but most
had already written a passing solution (t8 cron: C0–C3 all passed). Grok opened the provided skill
every time (C1, C2, C3: 2/2 each). Grok rows are in `runs/analysis.md`; they are not used for any
conclusion above except skill-opening.

## Best moments for the video (verify in the run's `stream.jsonl` before use)

- **"I did not run the script."** — Luna, no skills, fails t3 (`luna_C0_t3_csvclean_r2`). This is the
  sentence my own skill quotes back at it; with the skill Luna says "I'm applying the spec-check
  workflow", runs its code with asserts, and passes (`luna_C1_t3_csvclean_r1`).
- **The same mistake, explained politely:** "Your spec shows `Mar 4, 2026`, but I made the comma
  optional so this row isn't dropped." — Sonnet with the AI-written skill installed (never opened),
  fails (`sonnet_C3_t3_csvclean_r3`). Sonnet's only other failure was with Ponytail:
  "I only eyeballed that output… I also left out the assert-based self-check the project file asks
  for." (`sonnet_C2_t3_csvclean_r2`).
- **Sonnet ignores skills.** In `sonnet_C1_*` the session's own skill list starts with
  `"skills":["spec-check", …]`, and Sonnet never calls it: 0 of 108 skill runs.
- **Haiku reads the room:** "TASK.md is a written spec, so I'll load the spec-check skill before
  implementing." (`haiku_C1_t5_duration_r1`) and "The skill's checklist applies here: run the spec
  examples, add a must-fail case per rule, then re-read the spec." (`haiku_C1_t1_ratelimit_r3`)
- **Ponytail's mandatory "what I skipped" line:** "What I skipped or did not check: I did not look
  for other bugs beyond this one." (`haiku_C2_t1_ratelimit_r2`); "I did not review the
  .claude/skills files; they are unrelated to this task." (`haiku_C2_t2_allocate_r2`);
  "Skipped adding a separate test file" — and fails (`luna_C2_t3_csvclean_r1`).
- **Wrong skill, 7 seconds in:** Luna, with 50 skills installed, gets a fully specified semver
  task and opens `using-superpowers`, `brainstorming` and `test-driven-development` in one command:
  "I'm applying the repository workflow and feature implementation guidance first"
  (`luna_C5_t7_semver_r1`).
- **The expensive file:** same task, same answer, 58% more money for Sonnet with the 730-line
  CLAUDE.md (C4 vs C0, 27 pairs, 27/27 both).
- **Grok overthinks:** solved t1 early, then thought for 15 minutes (`grok_C0_t1_ratelimit_r1`).

## Limits and what was skipped

- **Ceiling.** Sonnet passed 100% with no help; Haiku 93%; the new held-out tasks were not hard
  enough (C0 22/24 pooled). This test can show costs clearly but can only show large benefits.
- **Small n where quotas ran out.** Luna has ~1 run per cell for C1–C5 (Codex quota of the ChatGPT
  plan ended at ~14:15, "try again at Nov 26th"). DeepSeek: 18 valid runs, t1–t3 only. Opus 5.5
  skipped (Sonnet already at 100%, and the Claude quota is shared with this session).
- **Grok** ran into the 15-min limit in 8 of 8 runs at medium effort and 4 of 6 at default; its token
  counts for timed-out runs miss the last step and it reports no cost for them.
- **C1 overfits by design.** It was written from the dev-task failures and literally names the t3
  date example. The dev-task gain is "fixing a known mistake", not general help.
- **Ponytail** was installed the way its README says for non-plugin agents (AGENTS.md + skills); its
  hooks were not run (untrusted download). The real plugin injects the same ruleset via a hook.
- **C4** is a generic generated file, not a repo-specific `/init` file like in the ETH study.
- **C6** was added mid-run after seeing Sonnet ignore skills; not pre-registered.
- **Cost** is API-equivalent (Claude Code and Grok report their own; Luna priced at $0.10/$0.01/
  $0.50 per 1M), not what the owner paid.
- Built-in skills (Claude Code's 15, Codex's 4, OpenCode's 2) were present in every condition; no
  run opened one.
- Harness notes: skill opens are recomputed from the raw logs with one rule for all CLIs
  (`harness/skilluse.py`); one Haiku run was retried because its answer mentioned "rate limit"
  (the task is a rate limiter) and the runner took that for a quota error; the analysis uses the
  valid run. One manual Grok smoke test ("Reply with exactly OK", `--effort` flag check) ran with the
  normal HOME, so it may appear in the owner's Grok session history.
- Nothing was published or pushed. Credentials were never read: Codex and Grok used symlinks to
  their own auth files; `~/.codex/auth.json` is unchanged (mtime 28 Oct).

## Files

- `SPEC.md` — design, predictions, addenda
- `conditions/C0…C6/` — exactly what was installed (C5 sources in `SOURCES.tsv`)
- `tasks/` — t1–t9 (public + hidden tests); `ref_new/` — reference solutions for t7–t9
- `harness/` — `backends.py`, `runner.py`, `analyze.py`, `skilluse.py`, `idle_probe.py`, `moments.py`
- `runs/results.jsonl` — one line per run; `runs/<run_id>/` — stream, stderr, grade, final workspace
- `runs/analysis.md` — all tables; `runs/moments.md` — all candidate quotes; `probes/` — isolation and idle-cost probes
