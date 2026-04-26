#!/usr/bin/env python3
"""
session_resumers.py — Create and update Claude Code session resume scripts.

Called as a Claude Code hook on Stop and PostCompact events.
Creates/updates .command files in SESSIONS_DIR (double-clickable on macOS)
that cd to the project and resume the session with the correct model.

Hook input (stdin JSON):
  Stop:        {"session_id": "...", "hook_event_name": "Stop"}
  PostCompact: {"session_id": "...", "hook_event_name": "PostCompact", "summary": "..."}
"""
import json, os, sys, glob, re
from datetime import datetime

SESSIONS_DIR = os.path.expanduser("~/dev/claude sessions")
PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
DEFAULT_MODEL = "claude-sonnet-4-6"


def slugify(text, maxlen=60):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:maxlen] or "session"


def find_jsonl(session_id):
    for path in glob.glob(os.path.join(PROJECTS_DIR, "**", f"{session_id}.jsonl")):
        return path
    return None


def analyze_session(jsonl_path):
    """Extract cwd, model, first real user message, and last compaction summary."""
    cwd = model = first_user_msg = last_summary = None
    try:
        with open(jsonl_path) as f:
            entries = [json.loads(l) for l in f if l.strip()]
    except Exception:
        return None

    for e in entries:
        if e.get("cwd") and not cwd:
            cwd = e["cwd"]
        if e.get("type") == "assistant" and not model:
            m = (e.get("message") or {}).get("model")
            if m:
                model = m
        if e.get("type") == "user" and not first_user_msg:
            content = (e.get("message") or {}).get("content", "")
            text = ""
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text = c.get("text", "").strip()
                        break
            elif isinstance(content, str):
                text = content.strip()
            if text and not text.startswith("<") and len(text) > 3:
                first_user_msg = text[:200]
        if e.get("type") == "summary":
            last_summary = e.get("summary", "")

    return {
        "cwd": cwd or os.path.expanduser("~"),
        "model": model or DEFAULT_MODEL,
        "first_user_msg": first_user_msg or "Untitled session",
        "summary": last_summary,
    }


def get_stored_name(session_id):
    """Read the palatable name from session_name.py's registry, if available."""
    try:
        names_file = os.path.expanduser("~/.claude/session_names.json")
        names = json.loads(open(names_file).read())
        return names.get(session_id)
    except Exception:
        return None


def make_title(first_msg, session_id=None):
    """Use stored palatable name if available, else fall back to first message."""
    if session_id:
        stored = get_stored_name(session_id)
        if stored:
            return stored
    return first_msg.strip().split("\n")[0][:60].strip() or "session"


def find_existing_script(session_id):
    """Find an existing .command file that contains this session_id, returning (path, summary)."""
    for path in glob.glob(os.path.join(SESSIONS_DIR, "*.command")):
        try:
            with open(path) as f:
                content = f.read()
            if session_id in content:
                # Extract existing summary block (lines starting with "# " after "# Summary:")
                existing_summary = None
                lines = content.splitlines()
                in_summary = False
                summary_lines = []
                for line in lines:
                    if line == "# Summary:":
                        in_summary = True
                        continue
                    if in_summary:
                        if line.startswith("# "):
                            summary_lines.append(line[2:])
                        else:
                            break
                if summary_lines:
                    existing_summary = "\n".join(summary_lines)
                return path, existing_summary
        except Exception:
            pass
    return None, None


def write_script(session_id, info, new_summary=None):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    title = make_title(info["first_user_msg"], session_id)
    slug = slugify(title)
    target = os.path.join(SESSIONS_DIR, f"{slug}.command")

    existing_path, existing_summary = find_existing_script(session_id)
    if existing_path and existing_path != target:
        os.rename(existing_path, target)

    # Priority: new PostCompact summary > existing file summary > jsonl summary > first message
    effective_summary = (
        new_summary
        or existing_summary
        or info.get("summary")
        or info["first_user_msg"][:300]
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    summary_lines = "\n".join(f"# {l}" for l in effective_summary.splitlines())
    script = (
        f"#!/bin/bash\n"
        f"# Session: {title}\n"
        f"# Session ID: {session_id}\n"
        f"# Last updated: {now}\n"
        f"#\n"
        f"# Summary:\n"
        f"{summary_lines}\n"
        f"\n"
        f"cd {json.dumps(info['cwd'])}\n"
        f"claude --resume {session_id} --model {info['model']}\n"
    )

    with open(target, "w") as f:
        f.write(script)
    os.chmod(target, 0o755)
    return target


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    session_id = data.get("session_id")
    if not session_id:
        sys.exit(0)

    jsonl = find_jsonl(session_id)
    if not jsonl:
        sys.exit(0)

    info = analyze_session(jsonl)
    if not info:
        sys.exit(0)

    summary = data.get("summary")  # set for PostCompact, None for Stop
    write_script(session_id, info, summary)
    sys.exit(0)


if __name__ == "__main__":
    main()
