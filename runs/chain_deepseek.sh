#!/bin/bash
cd /Users/<user>/.t3/projects/youtube/experiments/skills_value
until [ $(grep -c "^sonnet_" runs/log_main.txt) -ge 144 ]; do sleep 20; done
echo "sonnet done $(date), starting deepseek" > runs/log_deepseek.txt
python3 harness/runner.py --lanes "deepseek" --conds C0,C1,C2,C3,C4,C5,C6 --reps 1,2,3 >> runs/log_deepseek.txt 2>&1
