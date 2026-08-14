


import time

add_history = []

def add_history_entry(command: str, output: str, risk: str) -> None:
    """Adds a command execution entry to the history log."""
    entry = {
        "command": command,
        "output": output,
        "risk": risk,
        "timestamp": time.time(),
    }
    add_history.append(entry)
