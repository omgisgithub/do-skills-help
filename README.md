# Do AI agent skills actually help? 725 test runs

The data behind the Model Behavior video "Do AI Agent Skills Actually Help? I Ran 725 Tests".

Everyone says: install skills. I gave six coding AIs nine small Python jobs, each checked by hidden tests, under
different setups (nothing installed, my own skill, a community pack, a skill an AI wrote, one long instruction file,
50 public skills at once) and logged every run. All results are from my own setup, on 31 Oct and 8 Nov 2026.

## What came out (in my setup)

- **New jobs:** with nothing installed, 22 of 24 runs passed; with my own skill, 21 of 24. No setup beat its own runs
  with nothing installed.
- **Where it failed:** in the first 473 runs, outside Grok, 24 runs failed. 16 of them were on one job (cleaning a
  spreadsheet), and all 16 broke on the same comma in a date. My 35-line skill names that comma: three failed runs
  passed with it, none went the other way.
- **Who reads a skill:** Claude Sonnet opened no skill in 108 runs (106 of them passed anyway). With one sentence
  added to the request, "Use the spec-check skill if it fits", it opened my skill in 23 of 27 runs; the same day
  without the sentence, 0 of 9. Haiku opened it 20 of 27 times unasked, DeepSeek 19 of 27, GPT-6.1 Sol 27 of 27.
- **50 skills installed:** both Claudes and DeepSeek opened none. Sol opened an off-topic skill in 20 of 27 runs,
  most often a 294-line brainstorming guide, on jobs whose request said "Do not ask questions".
- **Cost** (typical, at API prices, against nothing installed): in the first 473 runs, 50 skills +20 %, the 730-line
  instruction file +60 %. In the follow-up runs, Sol in Codex: 2.05 times with that file.
- **The trap** (a separate test, outcomes only): `TRAP_SUMMARY.md`.

Full tables: `RESULTS.md` (first experiment) and `RESULTS_X.md` (follow-up). The plan written before the runs:
`SPEC.md` and `PREREG_X_20261108_0223.md`.

## What is in this repository

| Path | What it is |
|---|---|
| `tasks/t1_…` to `t9_…` | The nine jobs: the request (`public/TASK.md` and its files) and the hidden tests (`hidden/`). t7–t9 are the "new" jobs: no model had run them before my own skill was finished. |
| `ref_mini/`, `ref_new/` | Reference solutions used to check that every job can be passed. |
| `conditions/C0` … `C6` | The setups. C0 nothing installed; C1 my own 35-line skill (`WHY.md` says which failures it was written from); C2 a community pack; C3 a skill written by an AI (`PROMPT.txt`); C4 one 730-line instruction file; C5 50 public skills (the list only, see below); C6 my 35 lines as an always-on file. |
| `harness/` | The runner, the grader and the analysis scripts. |
| `runs/` | First experiment, 31 Oct 2026: `results.jsonl` (one row per attempt) and one folder per run. 473 valid runs. |
| `runs_x/` | Follow-up, 8 Nov 2026 (X1 GPT-6.1 Sol in Codex, X2 DeepSeek, X3 Claude Sonnet with the skill named in the request). 252 valid runs. |
| `probes/` | One-line "Reply with exactly OK" requests, used to measure what an idle request carries. |
| `tools/export_public.py` | The script that made this public copy. |

One run folder holds `stream.jsonl` (every event the agent's CLI printed: commands, outputs, messages), `grade.txt`
(what the hidden tests said) and `ws/` (the files the model left behind).

## What was left out, and why

- **The 50 public skills of C5.** They belong to their authors. `conditions/C5/SOURCES.tsv` lists each one and where
  it came from; `NOTICE.md` has the links.
- **The agents' own config folders inside each run** (`.claude`, `.agents`, `.opencode`, `.codex`): copies of the
  installed skills.
- **Codex session files** (`rollout.jsonl`): encrypted reasoning blobs and the local agent's instructions.
- **Machine details.** Home and temp paths, the login and the host name are replaced by `<user>`, `<host>`,
  `/tmp/<path>`. From Claude Code's first event in each log, the lists of local tools, MCP servers, commands, agents,
  skills and plugins are removed. Nothing else in the logs was changed.
- **The working trap.** Not the planted line, not the sending command, not the receiver.

## Limits

Small Python jobs. The strong models were near 100 % with nothing installed, so this test can show only big gains.
Grok mostly ran out of its 15-minute limit; its runs are flagged where they count. Costs are API (pay-as-you-go)
prices, not what I paid: the runs went through subscriptions. Sol ran in Codex, which loads only the first 32 KiB of
the long instruction file. All runs come from one setup on two days: treat every number as a measurement of my setup, not of
a model in general.

## Licence

Code: MIT (`LICENSE`). Data: CC BY 4.0 (`LICENSE-DATA.md`). Third-party material: `NOTICE.md`.
