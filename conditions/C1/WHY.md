# Where each C1 rule comes from (C0 pilot on dev tasks t1–t6 only, 2026-10-31)

Written after 54 C0 runs on t1–t6 (Haiku 18, Sonnet 18, Luna 18) + 5 Grok runs, before any
model had run t7–t9. Every rule traces to an observed failure:

| Rule | Observed in |
|---|---|
| 1. Run every spec example / the sample file | luna_C0_t5_duration_r2 never executed its parser and rejected the spec's own examples ("1h30m"); luna_C0_t3_csvclean_r2 ended with "I did not run the script." |
| 2. Closed list of accepted forms, strict patterns | 5 of 6 failures (haiku r1/r2, luna r1/r2/r3 on t3) accepted "Mar 4 2026", which the spec does not list; the sample row's own note says "bad date form" |
| 3. One must-fail case per rule | same t3 failures: only positive cases were checked (haiku_C0_t3_csvclean_r2: "output matches what I worked out by hand") |
| 4. Stop when checks pass | grok_C0_t1_ratelimit_r1 and grok_C0_t3_csvclean_r1 solved the task, then kept thinking until the 900 s timeout |

Two drafted rules were removed before any run because they came from my knowledge of the
held-out task design (t9's planted bugs, money rounding), not from pilot failures.
