"""Make a clean, publishable copy of this experiment (the skills test, 725 runs).

  python tools/export_public.py <destination>

Copies tasks, conditions, harness, results and every run (its event log, grade and the files the model left), skips
local-only files, and removes personal and machine data from every text file in the copy. The source is never written
to. The copy is built in a temporary sibling folder and only replaces <destination> if the leak check passes.

Left out on purpose:
- conditions/C5/skills (50 third-party skills; conditions/C5/SOURCES.tsv says where each came from);
- the agent's own config folders inside a run's workspace (.claude, .agents, .opencode, .codex: copies of the installed skills);
- rollout.jsonl (Codex session files: encrypted reasoning blobs and the local agent's own instructions);
- from Claude Code's first event in each log: the lists of local tools, MCP servers, commands, agents, skills and plugins.
"""
import getpass, json, re, shutil, socket, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_NAMES = {".venv", ".env", "__pycache__", ".pytest_cache", ".DS_Store", "rollout.jsonl", ".git"}
SKIP_PREFIX = ("conditions/C5/skills",)
WS_SKIP = {".claude", ".agents", ".opencode", ".codex", "node_modules"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".txt", ".csv", ".tsv", ".sh", ".log", ".toml", ".yaml", ".yml", ".sha256", ".cfg", ".ini", ""}
REDACTIONS = [
    (re.compile(r"/Users/[A-Za-z0-9._-]+/(?:[A-Za-z0-9._-]+/)*?skills_value/"), "<repo>/"),
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "/Users/<user>"),
    (re.compile(r"/private/tmp/[A-Za-z0-9._/-]+"), "/tmp/<path>"),
    (re.compile(r"/private/var/folders/[A-Za-z0-9._/-]+"), "/tmp/<path>"),
    (re.compile(r"/var/folders/[A-Za-z0-9._/-]+"), "/tmp/<path>"),
    (re.compile(r"/data/(?:home|workspace)/[A-Za-z0-9._/-]+"), "/box/<path>"),
    (re.compile(r"org-[A-Za-z0-9]{16,}"), "org-<redacted>"),
    (re.compile(r"MacBook-[A-Za-z0-9-]+(?:\.local)?"), "<host>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-<redacted>"),
]
def _identity():
    rules = []
    try: login = getpass.getuser()
    except Exception: login = ""
    host = socket.gethostname().split(".")[0]
    if len(login) >= 3 and login.lower() not in {"root", "user", "admin", "runner", "ubuntu", "agent"}:
        rules.append((re.compile(rf"(?i)(?<![A-Za-z0-9]){re.escape(login)}(?![A-Za-z0-9])"), "<user>"))
    if len(host) >= 3 and host.lower() not in {"localhost", "runner"}:
        rules.append((re.compile(rf"(?i)(?<![A-Za-z0-9-]){re.escape(host)}(?:\.local)?(?![A-Za-z0-9-])"), "<host>"))
    return rules
REDACTIONS += _identity()
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
INIT_KEEP = ("type", "subtype", "model", "claude_code_version", "permissionMode", "apiKeySource", "output_style")
INIT_NOTE = "removed from the public copy: the lists of local tools, MCP servers, commands, agents, skills and plugins"
LEAKS = re.compile(r"sk-[A-Za-z0-9_-]{20,}|org-(?!<redacted>)[A-Za-z0-9]{16,}|/Users/(?!<user>)[A-Za-z0-9._-]+|/private/tmp/[A-Za-z0-9]"
                   r"|MacBook-[A-Za-z0-9-]+|\"mcp_servers\"|\"slash_commands\"|gh[pousr]_[A-Za-z0-9]{20,}")

def skipped(rel):
    parts = rel.parts
    if any(p in SKIP_NAMES for p in parts) or parts[-1].endswith(".pyc"): return True
    if str(rel).startswith(SKIP_PREFIX): return True
    if "ws" in parts and any(p in WS_SKIP for p in parts[parts.index("ws"):]): return True
    return False

def scrub_events(text):
    """Claude Code's first events carry the local machine's tool, server, command, agent, skill and plugin lists: keep the rest."""
    out = []
    for line in text.split("\n"):
        if '"type":"system"' in line.replace(" ", "") and ('"init"' in line or '"commands_changed"' in line):
            try:
                d = json.loads(line)
                if d.get("type") == "system" and d.get("subtype") in ("init", "commands_changed"):
                    line = json.dumps(dict({k: d[k] for k in INIT_KEEP if k in d}, note=INIT_NOTE))
            except Exception:
                pass
        out.append(line)
    return "\n".join(out)

def transform(rel, text, allowed):
    if rel.suffix == ".jsonl": text = scrub_events(text)
    for pat, repl in REDACTIONS: text = pat.sub(repl, text)
    return EMAIL_RE.sub(lambda m: m.group(0) if m.group(1).lower() in allowed else "<email>", text)

def task_domains(src):
    """E-mail domains that are test data: everything in tasks/, the reference solutions and the conditions we ship."""
    dom = {"example.com", "example.org", "example.net", "users.noreply.github.com"}
    for sub in ("tasks", "ref_mini", "ref_new"):
        for f in (src / sub).rglob("*"):
            if f.is_file():
                dom |= {m.group(1).lower() for m in EMAIL_RE.finditer(f.read_text(errors="replace"))}
    return dom

def leak_check(root, allowed):
    bad = []
    pats = [("leak", LEAKS)] + [("identity:" + r, p) for p, r in _identity()]
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in TEXT_SUFFIXES: continue
        rel = f.relative_to(root); text = f.read_text(errors="replace")
        for name, pat in pats:
            n = len(pat.findall(text))
            if rel == Path("tools/export_public.py") and name == "leak": n = 0
            if n: bad.append(f"{rel}: {n} {name}")
        if any(m.group(1).lower() not in allowed for m in EMAIL_RE.finditer(text)): bad.append(f"{rel}: e-mail outside the test data")
    return bad

def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    dest = Path(sys.argv[1]).resolve()
    if dest == ROOT or ROOT in dest.parents: sys.exit("destination must be outside the source tree")
    allowed = task_domains(ROOT)
    tmp = dest.with_name(dest.name + ".export-tmp")
    if tmp.exists(): shutil.rmtree(tmp)
    copied = redacted = binary = 0; kinds = {}
    for src in sorted(ROOT.rglob("*")):
        rel = src.relative_to(ROOT)
        if src.is_dir() or src.is_symlink() or skipped(rel): continue
        out = tmp / rel; out.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in TEXT_SUFFIXES:
            text = src.read_text(errors="replace"); new = transform(rel, text, allowed); redacted += new != text; out.write_text(new)
        else:
            shutil.copy2(src, out); binary += 1; kinds[src.suffix] = kinds.get(src.suffix, 0) + 1
        copied += 1
    (tmp / ".gitignore").write_text(".env\n.venv/\n__pycache__/\n*.pyc\n.DS_Store\n.pytest_cache/\n")
    bad = leak_check(tmp, allowed)
    if bad:
        print("export stopped, leak check failed (copy left in " + str(tmp) + "):"); print("\n".join(bad[:40])); print(len(bad), "files"); sys.exit(1)
    if dest.exists():
        keep = dest / ".git"
        if keep.exists(): shutil.move(str(keep), str(tmp / ".git"))
        shutil.rmtree(dest)
    tmp.rename(dest)
    print(f"copied {copied} files to {dest} ({redacted} redacted, {binary} copied as binary: {kinds}), leak check clean")

if __name__ == "__main__":
    main()
