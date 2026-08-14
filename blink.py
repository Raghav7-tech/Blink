import subprocess
import time
import json

from dotenv import load_dotenv
from langfuse import observe
from google import genai
from google.genai import types
from google.genai.errors import APIError

from agent import system_prompt
from safety import is_dangerous, get_risk_level
from approval import request_approval
from history import log_query, log_step, log_action, log_approval, log_observation

load_dotenv()
client = genai.Client()

RETRYABLE_CODES = {429, 503}


def send_with_retry(chat, message, max_retries=5):
    """Sends a message to the chat, retrying with backoff on 429/503 errors."""
    for attempt in range(max_retries):
        try:
            return chat.send_message(message)
        except APIError as e:
            code = getattr(e, "code", None)
            if code in RETRYABLE_CODES:
                wait = 20 * (attempt + 1)  # simple linear backoff
                reason = "Rate limit hit" if code == 429 else "Model overloaded"
                print(f"⏳ {reason}. Waiting {wait}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait)
                continue
            print(f"--- API error: {e}")
            raise
    raise RuntimeError("Exceeded max retries due to repeated API errors.")


@observe()
def run_command(command: str, risk: str = "medium", reasoning: str = "") -> str:
    """
    Executes a single shell command inside the project's working directory and
    returns its stdout, stderr, and exit code. Subject to an automated safety
    filter and/or human approval before it runs. Every step is logged to history.
    """
    log_action(command, risk, reasoning)

    if is_dangerous(command):
        log_approval(command, "blocked")
        output = "⛔ Command blocked by safety filter (hard deny)."
        log_observation(command, output)
        return output

    actual_risk = get_risk_level(command)
    risk_order = {"low": 0, "medium": 1, "high": 2}
    effective_risk = max([risk, actual_risk], key=lambda r: risk_order.get(r, 1))

    if effective_risk == "low":
        print(f"✅ Auto-approved (read-only): {command}")
        log_approval(command, "auto-approve")
        output = _execute(command)
        log_observation(command, output)
        return output

    approval = request_approval(command, reasoning, effective_risk)

    if approval == "approve":
        log_approval(command, "approve")
        output = _execute(command)
    elif isinstance(approval, tuple) and approval[0] == "approve":
        new_command = approval[1]
        log_approval(new_command, "approve-edited")
        output = _execute(new_command)
    else:
        log_approval(command, "deny")
        output = "Command execution denied by user."

    log_observation(command, output)
    return output


def _execute(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",       )
        return f"Exit Code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s."
    except Exception as e:
        return f"Error executing command: {e}"


available_tools = {
    "run_command": {
        "fn": run_command,
        "description": "Executes a shell command in the project's working directory."
    }
}


config = types.GenerateContentConfig(
    system_instruction=system_prompt,
    response_mime_type="application/json",
)

chat = client.chats.create(model="gemini-3.1-flash-lite", config=config)
MAX_LOOP_STEPS = 15

while True:
    user_query = input('> ')
    if not user_query.strip():
        continue

    if user_query.strip().lower() == "/history":
        from history import print_history
        print_history()
        continue

    log_query(user_query)

    try:
        response = send_with_retry(chat, user_query)
    except Exception as e:
        print(f"--- Failed to get response: {e}")
        continue

    loop_count = 0
    while True:
        loop_count += 1
        if loop_count > MAX_LOOP_STEPS:
            print("Too many steps without a final answer — stopping to avoid a runaway loop.")
            break

        try:
            parsed_output = json.loads(response.text)
        except json.JSONDecodeError:
            print(f"--- Response: {response.text}")
            break

        step = parsed_output.get("step")

        if step == "start":
            content = parsed_output.get("content")
            print(f"🔍: {content}")
            log_step("start", content)
            try:
                response = send_with_retry(chat, "Continue to the next step.")
            except Exception as e:
                print(f"--- Failed to continue: {e}")
                break
            continue

        if step == "plan":
            content = parsed_output.get("content")
            print(f"🧠: {content}")
            log_step("plan", content)
            time.sleep(2)
            try:
                response = send_with_retry(chat, "Continue to the next step.")
            except Exception as e:
                print(f"--- Failed to continue: {e}")
                break
            continue

        if step == "action":
            tool_name = parsed_output.get("function")
            tool_input = parsed_output.get("input")
            risk = parsed_output.get("risk", "medium")
            reasoning = parsed_output.get("content", "")

            print(f"🛠️: {reasoning} [{tool_name}({tool_input!r})] risk={risk}")

            if tool_name not in available_tools:
                observation_msg = json.dumps({
                    "step": "observe",
                    "output": f"Error: unknown tool '{tool_name}'."
                })
                try:
                    response = send_with_retry(chat, observation_msg)
                except Exception as e:
                    print(f"--- Failed to continue: {e}")
                    break
                continue

            try:
                output = available_tools[tool_name]["fn"](tool_input, risk, reasoning)
            except Exception as e:
                output = f"Error while running tool '{tool_name}': {e}"

            observation_msg = json.dumps({"step": "observe", "output": output})
            time.sleep(2)
            try:
                response = send_with_retry(chat, observation_msg)
            except Exception as e:
                print(f"--- Failed to continue: {e}")
                break
            continue

        if step == "output":
            content = parsed_output.get("content")
            print(f"🤖: {content}")
            log_step("output", content)
            break

        print(f"--- Unrecognized step '{step}', stopping this turn.")
        break