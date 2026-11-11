# Exp 004 — Do agent skills actually help?

Written 2026-10-31 ~13:15 CET, **before** any skill/context condition was run. Only the C0
baseline on tasks t1–t6 had run when this was written (it is the pilot used to write C1).

Productivity benchmark only. No security tests here.

## Question

Same coding job, same model, same CLI. Only the extra context changes. Does the job get solved
more often, cheaper or faster?

## Claims under test (from `../skills_context/RESEARCH.md`, `THEO.md`)

| # | Claim | Source |
|---|---|---|
| A | A short, hand-written, focused skill helps (+16.6 pp avg in SkillsBench) | SkillsBench arXiv 2602.12670 |
| B | AI-written skills hurt (−8 to −11.5 pp) | SkillsBench |
| C | Long "comprehensive" skills barely help (+0.7 pp) | SkillsBench |
| D | Skills often don't trigger (56% never invoked) | Vercel blog 2026-01-27 |
| E | A context file (AGENTS.md / CLAUDE.md) raises cost ~20% without raising success | ETH arXiv 2602.11988 |
| F | An idle installed skill costs ~100 tokens | Anthropic docs |
| G | Most shared skill packs are slop; write your own for your recurring mistakes | Theo |
| H | More installed skills → wrong skill picked (selection degrades with library size) | arXiv 2601.04748 vs 2608.14036 |

## Conditions

Every condition is a set of files dropped into the fresh workspace before the run. Skills go
where each CLI looks for project skills (Claude Code `.claude/skills/`, Codex `.agents/skills/`,
Grok `.grok/skills/`). The context file is `CLAUDE.md` for Claude Code and `AGENTS.md` for Codex
and Grok. Files live in `conditions/<C>/`.

| ID | What is installed | Size |
|---|---|---|
| C0 | nothing | – |
| C1 | 1 hand-written skill (≤ 60 lines) aimed at the mistakes seen in the C0 pilot on t1–t6 | see file |
| C2 | Ponytail pack (DietrichGebert/ponytail @ 96608e0, MIT, popular). Installed as its README says for non-plugin agents: its `AGENTS.md` copied into the project + its 6 skills as project skills. Its hooks are **not** run (untrusted download); the always-on ruleset reaches the model through the AGENTS.md/CLAUDE.md instead, which is the pack's own documented fallback | 1 context file + 6 skills |
| C3 | 1 AI-generated "comprehensive" skill: Claude Sonnet 5.5 was asked to write a comprehensive SKILL.md for this kind of work (prompt in `conditions/C3/PROMPT.txt`), used unedited | 200 lines, ~4k tokens |
| C4 | 1 bloated context file: Sonnet 5.5 asked for a "comprehensive AGENTS.md for a Python repository" (prompt in `conditions/C4/PROMPT.txt`), unedited | 730 lines, ~8.5k tokens (Codex truncates at 32 KiB) |
| C5 | 50 real public skills, mostly irrelevant (13 Anthropic, 14 Superpowers, 12 Matt Pocock, 6 Vercel, 5 OpenAI; list in `conditions/C5/SOURCES.tsv`) | 50 skills |

C5 relevance labels, fixed now: **relevant** = test-driven-development, tdd, systematic-debugging,
diagnosing-bugs, verification-before-completion. **Neutral** = using-superpowers (a meta "use
skills" skill). Everything else is **irrelevant** to these jobs (docx-like, design, deploy,
React, planning, brainstorming, code review of PRs, git worktrees, …).

Not in any condition: Claude Code's own built-in skills (e.g. `simplify`, `debug`, `verify`) and
Codex's 4 system skills (`imagegen`, `openai-docs`, `skill-creator`, `skill-installer`) are
present in **every** condition including C0, because they ship with the CLI. Use of them is
logged.

## Tasks

| ID | Kind | Role |
|---|---|---|
| t1_ratelimit | fix a token-bucket bug | dev (pilot) |
| t2_allocate | implement money allocation to spec | dev |
| t3_csvclean | write a CSV cleaner to a long spec | dev |
| t4_refactor | refactor + add tier, keep exact behaviour | dev |
| t5_duration | implement a duration parser to a grammar | dev |
| t6_vm | work out a toy VM's output | dev |
| t7_semver | npm-style version ranges (new) | **held-out** |
| t8_cron | cron next-run with DOM/DOW OR rule (new) | **held-out** |
| t9_fifo | FIFO inventory, 5 planted bugs, report names 1 symptom (new) | **held-out** |

t1–t6 are reused from `../ai_compare/mini` (frontier models solved 36/36 there). t7–t9 were
written today to get away from the ceiling. C1 is written only from C0 failures on t1–t6, before
any model has seen t7–t9, so t7–t9 measure whether the hand-written skill generalises rather than
memorises.

Pass = all hidden tests pass (`harness/grade.sh`, on a copy, hidden tests copied in after the
run). Also recorded: share of hidden test functions passed (partial).

## Models (real CLIs, subscription logins, headless)

| Key | Model | CLI | Setting |
|---|---|---|---|
| sonnet | Claude Sonnet 5.5 | Claude Code 2.1.312 | CLI default effort |
| haiku | Claude Haiku 5.5 | Claude Code 2.1.312 | CLI default |
| luna | GPT-6 Luna (the model the ChatGPT plan offers headless) | Codex 0.165.0 | reasoning medium |
| grok | Grok 4.7 | grok 1.0.70 | CLI default |

Opus 5.5 optional if quota allows. DeepSeek only if its free quota is back. Gemini not in scope.

Same prompt for all: "Read TASK.md in the current directory and complete the task it describes.
Work only inside the current directory. Do not ask questions; when you are done, stop."

Isolation: fresh `/tmp` workspace per run. Claude Code: `--setting-sources project` (only the
workspace's own CLAUDE.md/skills), parent CLAUDE_* env stripped. Codex: fresh CODEX_HOME with the
auth file symlinked (never opened), memories/plugins/apps off, `--ephemeral`. Grok: fresh HOME,
auth symlinked, bundled skills hidden, `--trust`. Verified with canary probes (`probes/`): each
CLI listed our canary skill and quoted the canary context line, and none saw the owner's
CLAUDE.md, skills or memory. Web tools off. Timeout 900 s.

## Repetitions and order

Target n = 3 per task × condition × model (27 runs per cell). Grok takes ~7 min per run, so it
may get fewer reps (stated in results). Order is rep-major (rep 1 of everything first), so an
early stop still leaves balanced coverage. Max 3 runs at a time (one lane per provider).
Rate-limit errors back off 3/10/25 min; after that the model is marked out of quota.

## Metrics per run

pass, partial; tokens (uncached input, cache write, cache read, output, reasoning); cost estimate
(Claude Code and Grok report their own API-equivalent cost; Codex computed at GPT-6 Luna list
price $0.10 in / $0.01 cached / $0.50 out per 1M — subscription runs cost nothing extra in
cash); wall time; tool calls; turns; skills opened (Claude `Skill` tool calls, or any tool call
that reads `…/skills/<name>/…`); time to first skill use; outside-workspace access.

Idle cost: a separate probe per CLI and condition ("Reply with OK", no tools) measures the
first-request input size; (C5 − C0)/50 = tokens per idle installed skill.

## Analysis

Per condition × model: pass rate with n and a 95% Wilson interval, median tokens, median cost,
median time, skill-use rate. Main comparison: each condition vs C0, paired on (model, task, rep),
pooled over models, reported separately for dev (t1–t6) and held-out (t7–t9). With ~27 paired
runs per model and ~100 pooled, differences under ~10–15 pp are **not detectable**; such results
are reported as "no clear difference", not as "no effect".

## Pre-registered reading of the results

| Claim | Counts as **right** | Counts as **wrong** |
|---|---|---|
| A (focused skill helps) | C1 pooled pass rate ≥ 10 pp above C0 on held-out t7–t9 | C1 within ±5 pp of C0, or below |
| A' (overfit) | – | C1 helps on dev t1–t6 but not on held-out → "helps only on the mistakes it was written for" |
| B (AI skill hurts) | C3 ≥ 5 pp below C0 pooled | C3 ≥ C0 |
| C (comprehensive ≈ no help) | C3 within ±5 pp of C0 | C3 ≥ 10 pp above C0 |
| D (skills don't trigger) | C1/C3 skill opened in < 60% of runs | opened in ≥ 80% |
| E (context file: cost up, success flat) | C4 median cost ≥ +15% vs C0 and pass within ±5 pp | C4 cost < +5%, or pass up ≥ 10 pp |
| F (~100 tokens/idle skill) | (C5−C0)/50 between 50 and 200 tokens | outside that range |
| G (community pack no better than own) | C2 ≤ C0 + 5 pp and C1 ≥ C2 | C2 ≥ C1 + 10 pp |
| H (many skills → wrong picks) | irrelevant C5 skill opened in ≥ 20% of C5 runs, or C5 pass ≥ 10 pp below C0 | irrelevant pick < 5% and pass within ±5 pp |

## Limits known in advance

Small Python tasks, one language. Three new tasks plus six that are near the ceiling for strong
models. One prompt wording. Subscription CLIs, so model versions are whatever the CLI served
today (recorded per run). Cost is API-equivalent, not what the owner pays.

## Addenda (written during the run, clearly not pre-registered)

- **~14:15** GPT-6 Luna stopped with "You've hit your usage limit … try again at Nov 26th"
  (ChatGPT plan's Codex quota). Luna has about one rep per cell; nothing more is possible.
- **~14:20** DeepSeek V4.1 Flash Free's quota was back, so it was added as a 5th model through
  OpenCode 2.2.1 (fresh XDG config, Claude-compat off, skills in `.opencode/skills/`, canary probe
  passed). It runs in the lane Sonnet frees up.
- **~14:25** Grok is limited to t3, t7, t8, t9 × all conditions, reps 1–2 (≈7 min per run).
- **~14:25** Sonnet 5.5 had opened a skill in 0 of 62 skill runs although the skill was listed.
  Added **C6** = C1's exact text as the always-loaded context file instead of a skill, to separate
  "the advice doesn't help" from "the skill never gets read". Run on Haiku and DeepSeek (the
  models that fail sometimes) and Sonnet if time allows. Post-hoc; reported separately.
- Opus 5.5 skipped: Sonnet 5.5 is already at 100% on every cell, and the Claude quota is shared
  with the session running this experiment.
