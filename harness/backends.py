"""Drive each coding CLI headless, with its normal built-in tools, in a fresh workspace.

Isolation (so the owner's own CLAUDE.md, skills, memories and plugins never load):
- Claude Code: --setting-sources project (only the workspace's .claude/ and CLAUDE.md),
  CLAUDE_* env vars from the parent session stripped, no session persistence. Login is the
  CLI's own (keychain); we never touch it.
- Codex: fresh CODEX_HOME per run; auth.json is a symlink to the real one (never opened),
  config.toml written by us, memories/plugins/apps off, --ephemeral.
- Grok: fresh HOME per run; ~/.grok/auth.json is a symlink (never opened); bundled skills
  hidden via [skills] ignore; Claude/Cursor compat dirs point into the fake HOME (empty).
Skills go where each CLI natively looks for project skills; the context file is CLAUDE.md for
Claude Code and AGENTS.md for the others.
"""
from __future__ import annotations

import json
import os
import select
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

STRIP_PREFIX = ("CLAUDE", "T3CODE", "AI_AGENT", "ANTHROPIC_", "OPENAI_", "XAI_", "GROK_",
                "CODEX_", "OPENCODE", "DEEPSEEK", "GEMINI")

# USD per 1M tokens. Claude Code reports its own API-equivalent cost; others computed here.
PRICES = {
    "gpt-6-luna": {"input": 0.10, "cached": 0.01, "output": 0.50},
}

CODEX_OFF = ["apps", "plugins", "remote_plugin", "multi_agent", "image_generation", "goals",
             "computer_use", "browser_use", "browser_use_external", "in_app_browser", "hooks",
             "shell_snapshot", "memories", "chronicle", "js_repl"]


def child_env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith(STRIP_PREFIX)}
    env.update(extra or {})
    return env


def stream(cmd, cwd, env, timeout):
    """Run cmd, return (lines[(t, text)], stderr, rc, timed_out)."""
    p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                         start_new_session=True)
    err = []
    th = threading.Thread(target=lambda: err.append(p.stderr.read()), daemon=True)
    th.start()
    lines, deadline, timed = [], time.time() + timeout, False
    while True:
        left = deadline - time.time()
        if left <= 0:
            timed = True
            break
        r, _, _ = select.select([p.stdout], [], [], min(1.0, left))
        if not r:
            if p.poll() is not None:
                break
            continue
        line = p.stdout.readline()
        if line == "" and p.poll() is not None:
            break
        if line:
            lines.append((time.time(), line))
    if timed:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(p.pid, sig)
            except ProcessLookupError:
                break
            try:
                p.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
    else:
        # drain anything left
        rest = p.stdout.read()
        if rest:
            for ln in rest.splitlines(True):
                lines.append((time.time(), ln))
        p.wait(timeout=30)
    th.join(timeout=5)
    return lines, "".join(err), p.returncode, timed


def _jsonl(lines):
    out = []
    for t, ln in lines:
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            out.append((t, json.loads(ln)))
        except json.JSONDecodeError:
            pass
    return out


# ---------------------------------------------------------------- Claude Code
class Claude:
    cli = "claude"
    skills_dir = ".claude/skills"
    context_file = "CLAUDE.md"

    def __init__(self, model, home_root):
        self.model = model

    def run(self, ws, prompt, timeout, max_turns=80):
        cmd = ["nice", "-n", "10", "claude", "-p", "--model", self.model,
               "--setting-sources", "project",
               "--permission-mode", "bypassPermissions", "--dangerously-skip-permissions",
               "--disallowedTools", "WebFetch", "WebSearch",
               "--max-turns", str(max_turns), "--no-session-persistence",
               "--output-format", "stream-json", "--verbose", prompt]
        env = child_env({"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                         "DISABLE_AUTOUPDATER": "1", "PWD": str(ws)})
        lines, err, rc, timed = stream(cmd, ws, env, timeout)
        ev = _jsonl(lines)
        tools, skill_calls, texts, init, result = [], [], [], None, None
        for t, d in ev:
            if d.get("type") == "system" and d.get("subtype") == "init":
                init = d
            elif d.get("type") == "assistant":
                for c in d.get("message", {}).get("content", []):
                    if c.get("type") == "tool_use":
                        tools.append({"t": t, "name": c.get("name"), "input": c.get("input")})
                        if c.get("name") == "Skill":
                            skill_calls.append((c.get("input") or {}).get("skill")
                                               or (c.get("input") or {}).get("command"))
                    elif c.get("type") == "text" and c.get("text"):
                        texts.append(c["text"])
            elif d.get("type") == "result":
                result = d
        u = (result or {}).get("usage") or {}
        blob = str((result or {}).get("result", "")).lower()
        limit = any(s in blob for s in ("session limit", "usage limit", "rate limit",
                                         "limit reached", "out of extra usage"))
        return {
            "raw": lines, "stderr": err, "rc": rc, "timed_out": timed,
            "error": None if result and not result.get("is_error") else
                     ("limit" if limit else ("no result" if not result else "is_error")),
            "limit_hit": limit,
            "tokens": {"input": u.get("input_tokens", 0),
                       "cache_write": u.get("cache_creation_input_tokens", 0),
                       "cache_read": u.get("cache_read_input_tokens", 0),
                       "output": u.get("output_tokens", 0), "reasoning": None},
            "cost_usd": (result or {}).get("total_cost_usd"),
            "turns": (result or {}).get("num_turns"),
            "tools": tools, "skill_calls": skill_calls,
            "final_text": (result or {}).get("result") or (texts[-1] if texts else ""),
            "texts": texts,
            "listed_skills": (init or {}).get("skills"),
            "model_reported": list(((result or {}).get("modelUsage") or {}).keys()),
        }


# ---------------------------------------------------------------- Codex
class Codex:
    cli = "codex"
    skills_dir = ".agents/skills"
    context_file = "AGENTS.md"

    def __init__(self, model, home_root, effort="medium"):
        self.model = model
        self.effort = effort
        self.home_root = Path(home_root)

    def run(self, ws, prompt, timeout, max_turns=None):
        home = self.home_root / "codex_home"
        if home.exists():
            shutil.rmtree(home)
        home.mkdir(parents=True)
        (home / "auth.json").symlink_to(Path.home() / ".codex" / "auth.json")  # never opened
        (home / "config.toml").write_text(
            'suppress_unstable_features_warning = true\n'
            f'[projects."{ws}"]\ntrust_level = "trusted"\n')
        cmd = ["nice", "-n", "10", "codex", "exec", "--json", "--skip-git-repo-check",
               "--ephemeral", "-s", "workspace-write", "-m", self.model, "-C", str(ws),
               "-c", f"model_reasoning_effort={self.effort}",
               "-c", "web_search=disabled", "-c", "model_reasoning_summary=auto"]
        for f in CODEX_OFF:
            cmd += ["-c", f"features.{f}=false"]
        cmd.append(prompt)
        env = child_env({"CODEX_HOME": str(home), "PWD": str(ws)})
        lines, err, rc, timed = stream(cmd, ws, env, timeout)
        ev = _jsonl(lines)
        tools, texts, usage, errors, turns = [], [], {}, [], 0
        for t, d in ev:
            ty = d.get("type")
            if ty == "item.completed":
                it = d.get("item", {})
                k = it.get("type")
                if k == "agent_message":
                    texts.append(it.get("text", ""))
                elif k in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                    tools.append({"t": t, "name": k,
                                  "input": it.get("command") or it.get("changes")})
            elif ty == "turn.completed":
                turns += 1
                for kk, vv in (d.get("usage") or {}).items():
                    if isinstance(vv, (int, float)):
                        usage[kk] = usage.get(kk, 0) + vv
            elif ty in ("error", "turn.failed"):
                errors.append(json.dumps(d)[:400])
        blob = (" ".join(errors) + err[-2000:]).lower()
        limit = any(s in blob for s in ("usage limit", "rate limit", "quota", "429",
                                         "too many requests"))
        inp = usage.get("input_tokens", 0)
        cached = usage.get("cached_input_tokens", 0)
        out = usage.get("output_tokens", 0)
        p = PRICES.get(self.model)
        cost = None
        if p:
            cost = ((inp - cached) * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6
        # skill reads in Codex happen through the shell (cat/sed of SKILL.md)
        skill_calls = []
        for x in tools:
            s = json.dumps(x["input"])
            if "SKILL.md" in s or "/skills/" in s:
                skill_calls.append(s[:200])
        return {
            "raw": lines, "stderr": err, "rc": rc, "timed_out": timed,
            "error": ("limit" if limit else (errors[0] if errors else None)) if (errors or not usage) else None,
            "limit_hit": limit,
            "tokens": {"input": inp - cached, "cache_write": 0, "cache_read": cached,
                       "output": out, "reasoning": usage.get("reasoning_output_tokens")},
            "cost_usd": round(cost, 6) if cost is not None else None,
            "turns": turns, "tools": tools, "skill_calls": skill_calls,
            "final_text": texts[-1] if texts else "", "texts": texts,
            "listed_skills": None, "model_reported": [self.model],
        }


# ---------------------------------------------------------------- Grok
class Grok:
    cli = "grok"
    skills_dir = ".grok/skills"
    context_file = "AGENTS.md"

    def __init__(self, model, home_root, effort=None):
        self.model = model
        self.effort = effort
        self.home_root = Path(home_root)

    def run(self, ws, prompt, timeout, max_turns=80):
        home = self.home_root / "grok_home"
        if home.exists():
            shutil.rmtree(home)
        (home / ".grok").mkdir(parents=True)
        (home / ".grok" / "auth.json").symlink_to(Path.home() / ".grok" / "auth.json")
        bundled = home / ".grok" / "bundled"
        dirs = ", ".join(f'"{bundled / d}"' for d in
                         ("skills", "workflows", "agents", "personas", "roles"))
        (home / ".grok" / "config.toml").write_text(
            f"[skills]\nignore = [{dirs}]\n")
        cmd = ["nice", "-n", "10", "grok", "-m", self.model, "-p", prompt,
               "--cwd", str(ws), "--trust", "--always-approve", "--verbatim",
               "--disable-web-search", "--no-auto-update",
               "--max-turns", str(max_turns), "--output-format", "streaming-json"]
        if self.effort:
            cmd += ["--effort", self.effort]
        env = child_env({"HOME": str(home), "PWD": str(ws)})
        lines, err, rc, timed = stream(cmd, ws, env, timeout)
        ev = _jsonl(lines)
        return parse_grok(ev, lines, err, rc, timed, self.model)


def parse_grok(ev, lines, err, rc, timed, model):
    tools, texts, result, skill_calls, cur = [], [], None, [], []
    for t, d in ev:
        ty = d.get("type")
        if ty == "tool_call":
            tools.append({"t": t, "name": d.get("toolName") or d.get("title"),
                          "input": d.get("rawInput")})
        elif ty == "end":
            result = d
        elif ty == "text":
            cur.append(d.get("data") or "")
        if ty != "text" and cur:
            texts.append("".join(cur))
            cur = []
    if cur:
        texts.append("".join(cur))
    for x in tools:
        s = json.dumps(x["input"])
        if "SKILL.md" in s or "skill" in str(x.get("name", "")).lower() or "/skills/" in s:
            skill_calls.append(str(x.get("name")) + " " + s[:200])
    u = (result or {}).get("usage") or {}
    if not u:  # no final event (timeout): sum the per-step usage events
        for _, d in ev:
            if d.get("type") == "usage":
                for k, v in (d.get("usage") or {}).items():
                    if isinstance(v, (int, float)):
                        u[k] = u.get(k, 0) + v
    blob = (err[-2000:] + json.dumps(result or {})[:2000]).lower()
    limit = any(s in blob for s in ("rate limit", "usage limit", "quota", "429",
                                     "too many requests", "credits"))
    return {
        "raw": lines, "stderr": err, "rc": rc, "timed_out": timed,
        "error": None if result and result.get("stopReason") in ("end_turn", "max_turns", None)
                 else ("limit" if limit else ("no result" if not result else result.get("stopReason"))),
        "limit_hit": limit and not result,
        "tokens": {"input": u.get("input_tokens", 0),
                   "cache_write": u.get("cache_creation_input_tokens", 0),
                   "cache_read": u.get("cache_read_input_tokens", 0),
                   "output": u.get("output_tokens", 0), "reasoning": u.get("reasoning_tokens")},
        "cost_usd": (result or {}).get("total_cost_usd"),
        "turns": (result or {}).get("num_turns"), "tools": tools,
        "skill_calls": skill_calls,
        "final_text": texts[-1] if texts else "", "texts": texts, "listed_skills": None,
        "model_reported": list(((result or {}).get("modelUsage") or {}).keys()) or [model],
    }


# ---------------------------------------------------------------- OpenCode (DeepSeek free)
OPENCODE_DB = Path.home() / ".local/share/opencode/opencode.db"


class OpenCode:
    cli = "opencode"
    skills_dir = ".opencode/skills"
    context_file = "AGENTS.md"

    def __init__(self, model, home_root):
        self.model = model
        self.home_root = Path(home_root)

    def run(self, ws, prompt, timeout, max_turns=None):
        cfg = self.home_root / "xdg_config"
        if cfg.exists():
            shutil.rmtree(cfg)
        (cfg / "opencode").mkdir(parents=True)
        (cfg / "opencode" / "opencode.json").write_text(json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "permission": {"webfetch": "deny", "websearch": "deny"},
        }))
        title = "skv-" + os.path.basename(str(self.home_root))
        cmd = ["nice", "-n", "10", "opencode", "run", "--standalone", "--auto", "--format", "json",
               "-m", self.model, "--title", title, prompt]
        env = child_env({"XDG_CONFIG_HOME": str(cfg), "OPENCODE_DISABLE_CLAUDE_CODE": "1",
                         "PWD": str(ws)})
        lines, err, rc, timed = stream(cmd, ws, env, timeout)
        ev = _jsonl(lines)
        tools, texts, sid, errors = [], [], None, []
        tok = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
        steps = 0
        for t, d in ev:
            sid = sid or d.get("sessionID")
            part = d.get("part") or {}
            ty = d.get("type")
            if ty == "tool_use":
                tools.append({"t": t, "name": part.get("tool"),
                              "input": (part.get("state") or {}).get("input")})
            elif ty == "text" and part.get("text"):
                texts.append(part["text"])
            elif ty == "step_start":
                steps += 1
            elif ty == "step_finish":
                k = part.get("tokens") or {}
                tok["input"] += k.get("input") or 0
                tok["output"] += k.get("output") or 0
                tok["reasoning"] += k.get("reasoning") or 0
                tok["cache_read"] += (k.get("cache") or {}).get("read") or 0
                tok["cache_write"] += (k.get("cache") or {}).get("write") or 0
            elif ty == "error":
                errors.append(json.dumps(d.get("error") or d)[:400])
        # The JSON stream can miss the last step's usage; the session DB has the totals.
        if sid and OPENCODE_DB.exists():
            import sqlite3
            try:
                con = sqlite3.connect(str(OPENCODE_DB), timeout=30)
                row = con.execute("select tokens_input,tokens_output,tokens_reasoning,"
                                  "tokens_cache_read,tokens_cache_write from session_v2 where id=?",
                                  (sid,)).fetchone()
                con.close()
                if row:
                    tok = {"input": row[0], "output": row[1], "reasoning": row[2],
                           "cache_read": row[3], "cache_write": row[4]}
            except Exception:
                pass
        blob = (" ".join(errors) + err[-2000:]).lower()
        limit = any(s in blob for s in ("freeusagelimit", "usage limit", "rate limit", "429",
                                         "too many requests", "quota"))
        skill_calls = [json.dumps(x["input"])[:200] for x in tools
                       if x.get("name") == "skill" or "SKILL.md" in json.dumps(x["input"])]
        return {
            "raw": lines, "stderr": err, "rc": rc, "timed_out": timed,
            "error": ("limit" if limit else errors[0]) if errors else (None if steps else "no steps"),
            "limit_hit": limit,
            "tokens": tok, "cost_usd": 0.0, "turns": steps, "tools": tools,
            "skill_calls": skill_calls,
            "final_text": texts[-1] if texts else "", "texts": texts,
            "listed_skills": None, "model_reported": [self.model],
        }


MODELS = {
    "sonnet": lambda h: Claude("claude-sonnet-5-5", h),
    "haiku": lambda h: Claude("claude-haiku-5-5", h),
    "opus": lambda h: Claude("claude-opus-5-5", h),
    "luna": lambda h: Codex("gpt-6-luna", h),
    "grok": lambda h: Grok("grok-4.7", h),
    "grokm": lambda h: Grok("grok-4.7", h, effort="medium"),
    "deepseek": lambda h: OpenCode("opencode/deepseek-v4.1-flash-free", h),
}
