#!/bin/bash
# usage: grade.sh <task_dir> <workspace_dir>   -> runs hidden tests on a COPY of the workspace; exit 0 = pass
set -u
task="$1"; ws="$2"
g=$(mktemp -d /tmp/aicmp_grade.XXXXXX)
cp -R "$ws"/. "$g"/
cp -R "$task"/hidden/. "$g"/
cd "$g" && perl -e 'alarm shift; exec @ARGV' 120 python3 -E -s test_hidden.py
rc=$?
rm -rf "$g"
exit $rc
