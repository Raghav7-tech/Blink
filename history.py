import json
import os
from datetime import datetime

HISTORY_FILE = "blink_history.jsonl"


def log_entry(entry: dict) -> None:
    """
    Appends one JSON entry to the history log, one per line (JSONL format).
    Adds a timestamp automatically. Never raises — logging failures should
    never crash the agent loop.
    """
    entry = dict(entry)
    entry["timestamp"] = datetime.now().isoformat(timespec="seconds")

    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"⚠️  Failed to write history entry: {e}")


def log_query(user_query: str) -> None:
    log_entry({"type": "query", "content": user_query})


def log_step(step: str, content: str) -> None:
    log_entry({"type": "step", "step": step, "content": content})


def log_action(command: str, risk: str, reasoning: str) -> None:
    log_entry({
        "type": "action",
        "command": command,
        "risk": risk,
        "reasoning": reasoning,
    })


def log_approval(command: str, decision: str) -> None:
    log_entry({
        "type": "approval",
        "command": command,
        "decision": decision,   # "approve" | "deny" | "edit"
    })


def log_observation(command: str, output: str) -> None:
    log_entry({
        "type": "observation",
        "command": command,
        "output": output,
    })


def load_history() -> list[dict]:
    """Reads the full history log back as a list of dicts, oldest first."""
    if not os.path.exists(HISTORY_FILE):
        return []

    entries = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def print_history(limit: int = 20) -> None:
    """Pretty-prints the most recent `limit` history entries."""
    entries = load_history()[-limit:]
    if not entries:
        print("No history yet.")
        return

    for e in entries:
        ts = e.get("timestamp", "")
        etype = e.get("type", "")
        if etype == "query":
            print(f"[{ts}] 💬 QUERY: {e.get('content')}")
        elif etype == "step":
            print(f"[{ts}] ▸ {e.get('step').upper()}: {e.get('content')}")
        elif etype == "action":
            print(f"[{ts}] 🛠️  ACTION ({e.get('risk')}): {e.get('command')}")
        elif etype == "approval":
            print(f"[{ts}] 🙋 APPROVAL: {e.get('decision')} — {e.get('command')}")
        elif etype == "observation":
            out = (e.get("output") or "")[:200]
            print(f"[{ts}] 👁️  OBSERVE: {out}")