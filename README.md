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

## session_resumers.py

A hook script that automatically maintains double-clickable `.command` resume files for each Claude Code session. Place them in any folder and double-click to jump straight back into a session.

Each `.command` file contains:
- The session title (from first user message)
- A summary of what was done (updated on compaction)
- A one-liner that `cd`s to the project and runs `claude --resume <id> --model <model>`

### Requirements

- macOS
- Python 3
- Claude Code CLI

### Installation

1. **Copy the script:**

   ```bash
   cp session_resumers.py ~/.claude/session_resumers.py
   ```

2. **Choose a folder for your session files** (default: `~/dev/claude sessions`).
   Edit `SESSIONS_DIR` at the top of `session_resumers.py` if you want a different location.

3. **Add hooks to `~/.claude/settings.json`:**

   ```json
   {
     "hooks": {
       "Stop": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "python3 /Users/YOUR_USERNAME/.claude/session_resumers.py",
               "timeout": 10
             }
           ]
         }
       ],
       "PostCompact": [
         {
           "hooks": [
             {
               "type": "command",
               "command": "python3 /Users/YOUR_USERNAME/.claude/session_resumers.py",
               "timeout": 10
             }
           ]
         }
       ]
     }
   }
   ```

4. **Reload Claude Code** — open `/hooks` or restart.

### How it works

- **On Stop**: creates or updates the `.command` file for the current session, preserving any existing summary.
- **On PostCompact**: rewrites the summary block with the compaction summary (the most complete description of what happened).
- File names are slugified from the first user message.
- If you already have sessions, run the script once per session to back-fill:
  ```bash
  echo '{"session_id": "YOUR_SESSION_ID"}' | python3 ~/.claude/session_resumers.py
  ```
