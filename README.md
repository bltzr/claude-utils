# claude-utils

Utilities for Claude Code CLI.

---

## usage_statusline.py

A status line script for [Claude Code](https://claude.ai/code) that displays your real-time usage and limits directly in the terminal, sourced from Anthropic's servers (same data as the Claude desktop app).

```
🟢 Session [██░░░░░░░░░░░░░░░░░░]  11%  resets in 4h44m (06:00)
🟢  7-days [█████████░░░░░░░░░░░]  45%  resets in 5d19h (Thu Apr 23 21:00)
🟢   Extra [███░░░░░░░░░░░░░░░░░]  16%  3.19/20.00 € (Balance: 39.61 €)
```

- **Session bar** — 5-hour rolling window utilisation
- **7-days bar** — 7-day rolling window utilisation
- **Extra bar** — pay-as-you-go monthly overage (shown only when enabled); displays used/limit and prepaid credit balance
- Colour indicator: 🟢 < 70% · 🟡 70–89% · 🔴 ≥ 90%
- Reset times shown as local time

### Requirements

- macOS (uses the Keychain and the Claude desktop app's cookie store)
- [Claude desktop app](https://claude.ai/download) installed and logged in
- Python 3 (ships with macOS)
- OpenSSL CLI (`/usr/bin/openssl`, present on all macOS systems)
- Claude Code CLI

### Installation

1. **Copy the script to your Claude config directory:**

   ```bash
   cp usage_statusline.py ~/.claude/usage_statusline.py
   ```

2. **Add the `statusLine` entry to `~/.claude/settings.json`:**

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 /Users/YOUR_USERNAME/.claude/usage_statusline.py",
       "refreshInterval": 30
     }
   }
   ```

   Replace `YOUR_USERNAME` with your macOS username (`echo $USER`).

3. **Reload Claude Code** — open `/hooks` from the Claude Code input, or restart the app.

### How it works

1. Reads the Claude desktop app's cookie database (`~/Library/Application Support/Claude/Cookies`)
2. Decrypts the session cookie using the key stored in your macOS Keychain under **Claude Safe Storage**
3. Calls `https://claude.ai/api/organizations/{uuid}/usage` for quota bars
4. Calls `https://claude.ai/api/organizations/{uuid}/prepaid/credits` for the real prepaid balance
5. Renders the response as progress bars

### Troubleshooting

**"usage unavailable"** — Make sure the Claude desktop app is installed, running, and you are logged in.

**Permission prompt on every run** — Open Keychain Access, find the **Claude Safe Storage** entry, go to Access Control, and add `python3` (or set to allow all applications).

**Status line not appearing** — Verify the path in `settings.json` is correct for your username, then reload with `/hooks` or restart Claude Code.

---

## session_name.py + session_resumers.py

Two cooperating hook scripts that manage double-clickable `.command` session resume files with human-friendly names.

```
Claude ✦ AI Mapper and Status Line     ← terminal title bar
```

```
~/dev/claude sessions/
  ai-mapper-and-status-line.command    ← double-click to resume
  granola-midi-addon.command
  sequence-phase-1-data-model.command
```

Each `.command` file:
- Has a short, inferred name (not the raw first prompt)
- Shows a summary of what was done, updated automatically on compaction
- `cd`s to the project folder and runs `claude --resume <id> --model <model>`

### Features

- **Auto-named** from the first user message using a stop-word-filtered heuristic
- **Terminal title** set on every session start and updated on rename
- **Renameable** — just tell Claude: *"rename this session to Granola MIDI Mapper"*
- **Summary auto-updated** on `PostCompact` with the compaction summary
- **Resume preserved** — Stop hook updates timestamp but never overwrites a good summary

### Requirements

- macOS
- Python 3
- Claude Code CLI

### Installation

1. **Copy both scripts:**

   ```bash
   cp session_name.py ~/.claude/session_name.py
   cp session_resumers.py ~/.claude/session_resumers.py
   ```

2. **Choose a sessions folder** (default: `~/dev/claude sessions`).
   Edit `SESSIONS_DIR` at the top of each script if you want a different location.

3. **Add hooks to `~/.claude/settings.json`:**

   ```json
   {
     "hooks": {
       "SessionStart": [
         { "hooks": [{ "type": "command",
             "command": "python3 /Users/YOUR_USERNAME/.claude/session_name.py",
             "timeout": 5 }] }
       ],
       "UserPromptSubmit": [
         { "hooks": [{ "type": "command",
             "command": "python3 /Users/YOUR_USERNAME/.claude/session_name.py",
             "timeout": 10 }] }
       ],
       "Stop": [
         { "hooks": [{ "type": "command",
             "command": "python3 /Users/YOUR_USERNAME/.claude/session_resumers.py",
             "timeout": 10 }] }
       ],
       "PostCompact": [
         { "hooks": [{ "type": "command",
             "command": "python3 /Users/YOUR_USERNAME/.claude/session_resumers.py",
             "timeout": 10 }] }
       ]
     }
   }
   ```

4. **Add rename instructions to `~/.claude/CLAUDE.md`** (create if missing):

   ```markdown
   ## Session Renaming
   When asked to rename the session, run:
   `python3 ~/.claude/session_name.py rename "The New Name"`
   ```

5. **Reload Claude Code** — open `/hooks` or restart.

### How it works

| Hook | Script | Action |
|------|--------|--------|
| `SessionStart` | session_name.py | Restore terminal title from stored name |
| `UserPromptSubmit` | session_name.py | On first message: infer name, set title, create `.command` |
| `Stop` | session_resumers.py | Update `.command` timestamp; preserve existing summary |
| `PostCompact` | session_resumers.py | Replace summary with compaction summary |

### Renaming a session

Tell Claude: *"rename this session to My Better Name"*

Or from the terminal:
```bash
python3 ~/.claude/session_name.py rename "My Better Name"
```

### Back-filling existing sessions

```bash
# List all session IDs
ls ~/.claude/projects/**/*.jsonl

# Name a specific session
echo '{"session_id":"YOUR_ID","hook_event_name":"UserPromptSubmit","prompt":"what this session was about"}' \
  | python3 ~/.claude/session_name.py
```
