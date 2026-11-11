#!/bin/bash
cd /Users/<user>/.t3/projects/youtube/experiments/skills_value
while pgrep -f 'runner.py --lanes haiku;sonnet;luna' > /dev/null; do sleep 20; done
echo "main lanes done $(date), starting C6 for haiku+sonnet" > runs/log_c6.txt
python3 harness/runner.py --lanes "haiku,sonnet" --conds C6 --reps 1,2,3 >> runs/log_c6.txt 2>&1
