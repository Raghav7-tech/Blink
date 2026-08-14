import re
import re
import shlex
DANGEROUS_PATTERNS = [
    r"\brm\s+(-[a-z]*f[a-z]*r|-[a-z]*r[a-z]*f)\b", 
    r"\brm\s+.*-r\b.*\*",                             
    r"\bfind\s+.*-delete\b",
    r"\bshred\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bfdisk\b",
    r"\bparted\b",
    r">\s*/dev/sd",
    r">\s*/dev/nvme",
    r"\bwipefs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\bhalt\b",
    r"\b(kill|pkill|killall)\s+-9\b",
    r"\bkillall\b",
    r"\bchmod\s+-R\b",
    r"\bchmod\s+777\b",
    r"\bchown\s+-R\b",
    r":\(\)\{.*\};:",
    r"\bwhile\s*\(\s*true\s*\)",
    r"curl\s+.*\|\s*(sh|bash)",
    r"wget\s+.*\|\s*(sh|bash)",
    r"\bnc\s+-e\b",                                  
    r"/dev/tcp/",
    r"\bapt(-get)?\s+(remove|purge|autoremove)\b",
    r"\byum\s+remove\b",
    r"\bpip\s+uninstall\b",
    r"\bnpm\s+uninstall\s+-g\b",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-z]*f[a-z]*d\b",
    r"\bgit\s+branch\s+-D\b",
    r"\b(DROP|DELETE|TRUNCATE)\s+(TABLE|DATABASE)\b",
    r"\bDROP\s+SCHEMA\b",
    r">\s*/etc/passwd",
    r">\s*/etc/shadow",
    r">\s*/boot/",
    r"\bsudo\s+rm\b",
    r"\bsudo\s+dd\b",
    r"\bsudo\s+mkfs\b",
    r"\bhistory\s+-c\b",
    r">\s*~/.bash_history",
]

def is_dangerous(command: str) -> bool:
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return True
    return False



SAFE_COMMANDS = {
    "ls", "pwd", "cat", "grep", "find", "git", "ps", "df", "whoami",
    "date", "echo", "head", "tail", "wc", "file", "du", "tree", "which",
    "env", "uname", "hostname",
}


UNSAFE_FLAGS_BY_COMMAND = {
    "find": {"-delete", "-exec", "-execdir", "-fprintf"},
    "git": None,  
}
SAFE_GIT_SUBCOMMANDS = {"status", "log", "diff", "show", "branch", "remote", "blame"}

def get_risk_level(command: str) -> str:
    """
    Returns 'low', 'medium', or 'high'.
    'low' = safe to auto-run without asking.
    Anything else must go through approval.
    """
    if is_dangerous(command):
        return "high"

    try:
        parts = shlex.split(command)
    except ValueError:
        return "high"

    if not parts:
        return "high"

    base_cmd = parts[0]
    if any(op in command for op in ["&&", "||", ";", "|", "`", "$(", ">", "<"]):
        return "medium"

    if base_cmd not in SAFE_COMMANDS:
        return "medium"
 
    if base_cmd == "git":
        if len(parts) < 2 or parts[1] not in SAFE_GIT_SUBCOMMANDS:
            return "medium"
        return "low"
     
    if base_cmd == "find":
        for flag in parts[1:]:
            if flag in UNSAFE_FLAGS_BY_COMMAND.get("find", set()):
                return "medium"
        return "low"



def is_auto_approved(command: str) -> bool:
    return get_risk_level(command) == "low"





