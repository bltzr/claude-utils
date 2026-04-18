# claude-utils

Utilities for Claude Code CLI.

## usage_statusline.py

A status line script for [Claude Code](https://claude.ai/code) that displays your real-time usage and limits directly in the terminal, sourced from Anthropic's servers (same data as the Claude desktop app).

```
🟢 Session [██░░░░░░░░░░░░░░░░░░]  11%  resets in 4h44m (06:00)
🟢  7-days [█████████░░░░░░░░░░░]  45%  resets in 5d19h (Thu Apr 23 21:00)
```

- **Session bar** — 5-hour rolling window utilisation
- **7-days bar** — 7-day rolling window utilisation
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

   If `~/.claude/settings.json` doesn't exist yet, create it with that content.

3. **Reload Claude Code** — open `/hooks` from the Claude Code input, or restart the app.

### How it works

The script:

1. Reads the Claude desktop app's cookie database (`~/Library/Application Support/Claude/Cookies`)
2. Decrypts the session cookie using the key stored in your macOS Keychain under **Claude Safe Storage**
3. Calls `https://claude.ai/api/organizations/{uuid}/usage` with your authenticated session
4. Renders the response as progress bars

The Keychain read will prompt for permission the first time (or whenever macOS requires it). No credentials are stored or transmitted anywhere — the script only reads what the Claude desktop app already has.

### Troubleshooting

**"usage unavailable"** — Make sure the Claude desktop app is installed, running, and you are logged in.

**Permission prompt on every run** — Open Keychain Access, find the **Claude Safe Storage** entry, go to Access Control, and add `python3` (or set to allow all applications).

**Status line not appearing** — Verify the path in `settings.json` is correct for your username, then reload with `/hooks` or restart Claude Code.
