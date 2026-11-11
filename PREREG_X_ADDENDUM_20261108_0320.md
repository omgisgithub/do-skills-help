# PREREG X addendum (2026-11-08 03:20 CET, written during X1, after 34 X1 launches)

Not pre-registered. Readouts and wording unchanged.

- At ~03:05 the Plus 5-hour meter crossed 95 % while 3 Sol runs were in flight; they pushed it to
  100 % and one run (`X1_sol_C5_t8_cron_r1`) got "You've hit your usage limit … try again at 3:15 AM".
  That run is an infra error (excluded, re-run). The guard stopped X1 as written.
- The limit was the 5-hour window, which reset at 03:15 (meter 4 %, weekly 59 %, cap 80 %).
  X1 resumes for its remaining runs. To stop in-flight runs overshooting, the 5-hour pause now starts at
  **90 %** instead of 95 % (more conservative). Weekly > 80 % and any further limit error still stop X1.
