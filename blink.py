import subprocess
from turtle import st
from safety import is_dangerous
from approval import request_approval
def run_command(command: str) -> str:
    """
    Executes a single shell command inside the project's working directory and
    returns its stdout, stderr, and exit code. Subject to an automated safety
    filter and/or human approval before it runs.
    """
    if is_dangerous(command):
        return "⛔ Command blocked by safety filter."

    reasoning = "User requested this command."
    approval = request_approval(command, reasoning) 
    if approval == "approve":
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return f"Exit Code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        except Exception as e:
            return f"Error executing command: {e}"
    elif isinstance(approval, tuple) and approval[0] == "approve":
        new_command = approval[1]
        try:
            result = subprocess.run(new_command, shell=True, capture_output=True, text=True)
            return f"Exit Code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        except Exception as e:
            return f"Error executing modified command: {e}"
    else:
        return "Command execution denied by user."




run_command("ls -la")
run_command("rm -rf /")
run_command("echo 'Hello, World!' > hello.txt")








