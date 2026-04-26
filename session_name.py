#!/usr/bin/env python3
"""
session_name.py — Auto-name Claude Code sessions, set terminal title bar.

Hook modes (reads JSON from stdin):
  SessionStart:       restore terminal title from stored name (resumed sessions)
  UserPromptSubmit:   auto-name on first user message, create .command file

CLI modes:
  rename "New Name" [session_id]   rename session and .command file
  get [session_id]                 print current session name
"""
import json, os, re, sys, glob
from datetime import datetime
from pathlib import Path

SESSIONS_DIR  = Path.home() / "dev" / "claude sessions"
NAMES_FILE    = Path.home() / ".claude" / "session_names.json"
PROJECTS_DIR  = Path.home() / ".claude" / "projects"
DEFAULT_MODEL = "claude-sonnet-4-6"

# ── Stop words (EN + FR) ───────────────────────────────────────────────────────

STOP_WORDS = {
    # English
    'a','an','the','can','we','you','i','me','my','please','help','want','need',
    'to','with','on','in','for','is','it','this','that','of','and','or','but',
    'let','make','add','do','go','work','here','us','how','what','when','would',
    'like','could','should','will','now','just','also','about','at','be','by',
    'from','up','use','so','if','as','was','are','were','has','have','had',
    'not','all','they','them','their','then','than','into','out','more','get',
    'its','our','some','each','new','one','two','three','old','very','your',
    # French
    'je','tu','il','elle','nous','vous','ils','elles','le','la','les','un','une',
    'des','du','de','ce','cet','cette','ces','mon','ton','son','notre','votre',
    'leur','que','qui','quoi','est','sont','dans','sur','avec','pour','par',
    'mais','ou','et','donc','ne','pas','plus','bien','aussi','tout','tous',
    'en','au','aux','se','si','car','quand','me','te','lui','ici','là','ya',
}

# ── Name registry ──────────────────────────────────────────────────────────────

def get_names() -> dict:
    try:
        return json.loads(NAMES_FILE.read_text())
    except Exception:
        return {}

def save_names(names: dict):
    NAMES_FILE.write_text(json.dumps(names, indent=2))

# ── Terminal title ─────────────────────────────────────────────────────────────

def fmt_model(model_id: str) -> str:
    """Shorten model ID: claude-sonnet-4-6 → sonnet 4.6"""
    import re
    m = re.match(r"claude-(\w+)-(\d+)-(\d+)", model_id or "")
    if m:
        return f"{m.group(1)} {m.group(2)}.{m.group(3)}"
    return model_id or ""

def set_terminal_title(name: str, model: str = ""):
    label = f"Claude ✦ {name}"
    if model:
        label += f"  [{fmt_model(model)}]"
    try:
        with open('/dev/tty', 'w') as tty:
            tty.write(f'\033]0;{label}\007')
    except Exception:
        pass

# ── Name generation ────────────────────────────────────────────────────────────

def generate_name(prompt: str) -> str:
    """Derive a short, palatable session name from the first user message."""
    # Use first non-empty line only
    first = next((l.strip() for l in prompt.splitlines() if l.strip()), prompt)[:300]

    # Strip file paths and URLs
    first = re.sub(r'https?://\S+', '', first)
    first = re.sub(r'[~]?(?:/[\w./-]+)', '', first)

    # Tokenize (support accented chars)
    words = re.findall(r"[\w'àáâãäåæçèéêëìíîïñòóôõöùúûüýÿÀ-Ö]+", first)

    # Keep meaningful words
    meaningful = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 2]

    # Deduplicate preserving order
    seen, unique = set(), []
    for w in meaningful:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)

    # Title-case up to 4 words
    name = ' '.join(w.capitalize() for w in unique[:4])
    return name or first[:40].split('\n')[0].capitalize()

def slugify(name: str, maxlen=60) -> str:
    s = re.sub(r'[^\w\s-]', '', name.lower())
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    return s[:maxlen] or 'session'

# ── Session / file helpers ────────────────────────────────────────────────────

def find_jsonl(session_id: str) -> Path | None:
    for p in Path(PROJECTS_DIR).glob(f'**/{session_id}.jsonl'):
        return p
    return None

def read_session_info(jsonl_path: Path) -> tuple[str, str]:
    """Return (cwd, model) from a session JSONL."""
    cwd = model = None
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get('cwd') and not cwd:
                        cwd = e['cwd']
                    if e.get('type') == 'assistant' and not model:
                        m = (e.get('message') or {}).get('model')
                        if m:
                            model = m
                    if cwd and model:
                        break
                except Exception:
                    pass
    except Exception:
        pass
    return cwd or str(Path.home()), model or DEFAULT_MODEL

def find_command_file(session_id: str) -> Path | None:
    """Find existing .command file containing this session_id."""
    for p in SESSIONS_DIR.glob('*.command'):
        try:
            if session_id in p.read_text():
                return p
        except Exception:
            pass
    return None

def _extract_summary(content: str) -> str | None:
    lines = content.splitlines()
    in_summary, summary_lines = False, []
    for line in lines:
        if line == '# Summary:':
            in_summary = True
            continue
        if in_summary:
            if line.startswith('# '):
                summary_lines.append(line[2:])
            else:
                break
    return '\n'.join(summary_lines) if summary_lines else None

def write_command_file(session_id: str, name: str, cwd: str, model: str,
                       summary: str | None = None) -> Path:
    """Create or update the .command resume script with the given name."""
    SESSIONS_DIR.mkdir(exist_ok=True)
    target = SESSIONS_DIR / f"{slugify(name)}.command"

    existing = find_command_file(session_id)
    if existing and existing != target:
        # Preserve existing summary before rename
        existing_summary = _extract_summary(existing.read_text())
        summary = summary or existing_summary
        existing.rename(target)
    elif existing:
        summary = summary or _extract_summary(target.read_text())

    effective_summary = summary or name
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    summary_block = '\n'.join(f'# {l}' for l in effective_summary.splitlines())

    script = (
        f'#!/bin/bash\n'
        f'# Session: {name}\n'
        f'# Session ID: {session_id}\n'
        f'# Last updated: {now}\n'
        f'#\n'
        f'# Summary:\n'
        f'{summary_block}\n'
        f'\n'
        f'cd {json.dumps(cwd)}\n'
        f'claude --resume {session_id} --model {model}\n'
    )
    target.write_text(script)
    target.chmod(0o755)
    return target

def find_current_session_id() -> str | None:
    """Heuristic: most recently modified JSONL = active session."""
    files = list(Path(PROJECTS_DIR).glob('**/*.jsonl'))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime).stem

# ── Hook mode ─────────────────────────────────────────────────────────────────

def hook_mode(data: dict):
    session_id = data.get('session_id')
    if not session_id:
        return

    event = data.get('hook_event_name', '')
    names = get_names()

    if event == 'SessionStart':
        name = names.get(session_id)
        jsonl = find_jsonl(session_id)
        _, model = read_session_info(jsonl) if jsonl else (None, "")
        if name:
            set_terminal_title(name, model)
        return

    if event == 'UserPromptSubmit':
        # Already named — nothing to do
        if session_id in names:
            return

        prompt = (data.get('prompt') or data.get('message') or '').strip()
        # Skip system/tool messages
        if not prompt or prompt.startswith('<'):
            return

        name = generate_name(prompt)
        if not name:
            return

        names[session_id] = name
        save_names(names)

        jsonl = find_jsonl(session_id)
        cwd, model = read_session_info(jsonl) if jsonl else (str(Path.home()), DEFAULT_MODEL)
        set_terminal_title(name, model)
        if jsonl:
            write_command_file(session_id, name, cwd, model)

# ── CLI modes ─────────────────────────────────────────────────────────────────

def cli_rename(new_name: str, session_id: str | None = None):
    session_id = session_id or find_current_session_id()
    if not session_id:
        print('Error: could not determine current session', file=sys.stderr)
        sys.exit(1)

    names = get_names()
    old_name = names.get(session_id, 'unnamed')
    names[session_id] = new_name
    save_names(names)

    jsonl = find_jsonl(session_id)
    cwd, model = read_session_info(jsonl) if jsonl else (str(Path.home()), DEFAULT_MODEL)
    set_terminal_title(new_name, model)

    if jsonl:
        path = write_command_file(session_id, new_name, cwd, model)
        print(f"Renamed '{old_name}' → '{new_name}'")
        print(f"Script: {path}")

def cli_get(session_id: str | None = None):
    session_id = session_id or find_current_session_id()
    names = get_names()
    print(names.get(session_id, 'unnamed'))

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'rename' and len(sys.argv) >= 3:
            cli_rename(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        elif cmd == 'get':
            cli_get(sys.argv[2] if len(sys.argv) > 2 else None)
        else:
            print(f'Unknown command: {cmd}', file=sys.stderr)
            sys.exit(1)
    else:
        try:
            data = json.loads(sys.stdin.read())
        except Exception:
            sys.exit(0)
        hook_mode(data)

if __name__ == '__main__':
    main()
