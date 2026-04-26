#!/usr/bin/env python3
"""
Claude Code status line — reads real usage data from claude.ai's API.
Decrypts session cookies from the Claude desktop app, then calls:
  GET https://claude.ai/api/organizations/{uuid}/usage

Output: two progress bars (5-hour window + 7-day window) with reset times.
"""
import glob, json, os, shutil, sqlite3, subprocess, tempfile, time, urllib.request
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac

COOKIES_DB = os.path.expanduser("~/Library/Application Support/Claude/Cookies")
KEYCHAIN_SERVICE = "Claude Safe Storage"
AES_IV = b" " * 16  # Chromium macOS AES-CBC IV
PROJECTS_DIR = os.path.expanduser("~/.claude/projects")


# ── Cookie decryption ──────────────────────────────────────────────────────────

def _derive_key():
    pw = subprocess.check_output(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        stderr=subprocess.DEVNULL,
    ).strip()
    return pbkdf2_hmac("sha1", pw, b"saltysalt", 1003, dklen=16)


def _decrypt(ev, key):
    ev = bytes(ev)
    if ev[:3] != b"v10":
        return ev.decode("utf-8", errors="replace")
    proc = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", AES_IV.hex(), "-nopad"],
        input=ev[3:],
        capture_output=True,
    )
    raw = proc.stdout
    if not raw:
        return None
    pad = raw[-1]
    raw = raw[:-pad]
    return raw[32:].lstrip(b"`").decode("ascii", errors="replace").strip("\x00")


def get_session_cookies():
    key = _derive_key()
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(COOKIES_DB, tmp)
    try:
        conn = sqlite3.connect(tmp)
        rows = conn.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude%'"
        ).fetchall()
        conn.close()
    finally:
        os.unlink(tmp)
    return {name: _decrypt(ev, key) for name, ev in rows if _decrypt(ev, key)}


# ── API call ───────────────────────────────────────────────────────────────────

def _api_get(cookies, path):
    org_uuid = cookies.get("lastActiveOrg", "")
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
    req = urllib.request.Request(
        f"https://claude.ai/api/organizations/{org_uuid}{path}",
        headers={
            "Cookie": cookie_header,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())


def fetch_usage(cookies):
    if not cookies.get("lastActiveOrg"):
        return None, None
    usage = _api_get(cookies, "/usage")
    try:
        prepaid = _api_get(cookies, "/prepaid/credits")
    except Exception:
        prepaid = None
    return usage, prepaid


# ── Current model ─────────────────────────────────────────────────────────────

def get_current_model():
    """Read model from the most recently active session JSONL."""
    files = glob.glob(os.path.join(PROJECTS_DIR, "**", "*.jsonl"))
    if not files:
        return None
    recent = max(files, key=os.path.getmtime)
    model = None
    try:
        with open(recent) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get("type") == "assistant":
                        m = (e.get("message") or {}).get("model")
                        if m:
                            model = m
                except Exception:
                    pass
    except Exception:
        pass
    return model

def fmt_model(model_id):
    """Shorten model ID to a compact label."""
    if not model_id:
        return ""
    # claude-sonnet-4-6 → sonnet 4.6  |  claude-opus-4-7 → opus 4.7
    import re
    m = re.match(r"claude-(\w+)-(\d+)-(\d+)", model_id)
    if m:
        name, major, minor = m.group(1), m.group(2), m.group(3)
        return f"{name} {major}.{minor}"
    return model_id


# ── Display ────────────────────────────────────────────────────────────────────

def bar(pct, width=20):
    pct = max(0.0, min(100.0, pct or 0))
    filled = round(width * pct / 100)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def indicator(pct):
    pct = pct or 0
    if pct >= 90: return "🔴"
    if pct >= 70: return "🟡"
    return "🟢"


def fmt_reset(resets_at_str, long=False):
    if not resets_at_str:
        return ""
    try:
        ts = datetime.fromisoformat(resets_at_str.replace("Z", "+00:00"))
        delta = (ts - datetime.now(tz=timezone.utc)).total_seconds()
        if delta <= 0:
            return "resetting…"
        local = ts.astimezone()
        if long:
            d, r = divmod(int(delta), 86400)
            h = r // 3600
            label = f"{d}d{h:02d}h" if d else f"{h}h"
            wall = local.strftime("%a %b %d %H:%M")
            return f"resets in {label} ({wall})"
        else:
            h, r = divmod(int(delta), 3600)
            m = r // 60
            label = f"{h}h{m:02d}m" if h else f"{m}m"
            wall = local.strftime("%H:%M")
            return f"resets in {label} ({wall})"
    except Exception:
        return resets_at_str


def main():
    try:
        cookies       = get_session_cookies()
        data, prepaid = fetch_usage(cookies)
    except Exception as e:
        print(f"⚠ usage unavailable: {e}")
        return

    if not data:
        print("⚠ no usage data returned")
        return

    fh  = data.get("five_hour") or {}
    sd  = data.get("seven_day") or {}
    ex  = data.get("extra_usage") or {}

    fh_pct   = fh.get("utilization")
    sd_pct   = sd.get("utilization")
    ex_pct   = ex.get("utilization")
    fh_reset = fmt_reset(fh.get("resets_at"), long=False)
    sd_reset = fmt_reset(sd.get("resets_at"), long=True)

    fh_pct_display = f"{fh_pct:.0f}%" if fh_pct is not None else "n/a"
    sd_pct_display = f"{sd_pct:.0f}%" if sd_pct is not None else "n/a"

    model_label = fmt_model(get_current_model())
    model_suffix = f"                    ⬡ {model_label}" if model_label else ""

    print(
        f"{indicator(fh_pct)} Session {bar(fh_pct)} {fh_pct_display:>4}"
        f"  {fh_reset}{model_suffix}"
    )
    print(
        f"{indicator(sd_pct)}  7-days {bar(sd_pct)} {sd_pct_display:>4}"
        f"  {sd_reset}"
    )

    # Extra usage (pay-as-you-go top-up) — show only when enabled
    if ex.get("is_enabled"):
        ex_pct_display = f"{ex_pct:.0f}%" if ex_pct is not None else "n/a"
        used   = ex.get("used_credits")
        limit  = ex.get("monthly_limit")
        curr   = ex.get("currency") or ""
        credit_info = ""
        if used is not None and limit is not None:
            balance_str = ""
            if prepaid is not None and prepaid.get("amount") is not None:
                balance_str = f" (Balance: {prepaid['amount']/100:.2f} €)"
            credit_info = f"  {used/100:.2f}/{limit/100:.2f} €{balance_str}"
        print(
            f"{indicator(ex_pct)}   Extra {bar(ex_pct)} {ex_pct_display:>4}"
            f"{credit_info}"
        )
    else:
        print(f"⚪   Extra {'[' + '─' * 20 + ']':22s}   disabled")


if __name__ == "__main__":
    main()
