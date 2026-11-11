#!/bin/bash
cd /Users/<user>/.t3/projects/youtube/experiments/skills_value
deadline=$(date -j -f "%H:%M" "19:15" +%s)
while [ $(date +%s) -lt $deadline ] && [ $(grep -c "pass=" runs/log_grokm2.txt) -lt 18 ]; do sleep 30; done
pkill -f 'runner.py --lanes grokm'; sleep 1; pkill -f "grok -m grok-4.7 -p Read TASK.md"
echo "watchdog stopped grok $(date)" >> runs/log_grokm2.txt
