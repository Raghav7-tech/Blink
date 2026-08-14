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
from history import add_history
load_dotenv()
client = genai.Client()


def send_with_retry(chat, message, max_retries=5):
    """Sends a message to the chat, retrying with backoff on 429 rate limits."""
    for attempt in range(max_retries):
        try:
            return chat.send_message(message)
        except APIError as e:
            if getattr(e, "code", None) == 429:
                wait = 30 * (attempt + 1)  # simple linear backoff
                print(f"⏳ Rate limit hit. Waiting {wait}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait)
                continue
            print(f"--- API error: {e}")
            raise
    raise RuntimeError("Exceeded max retries due to repeated rate limiting.")


@observe()
def run_command(command: str, risk: str = "medium", reasoning: str = "") -> str:
    """
    Executes a single shell command inside the project's working directory and
    returns its stdout, stderr, and exit code. Subject to an automated safety
    filter and/or human approval before it runs.
    """ 
    if is_dangerous(command):
        return "⛔ Command blocked by safety filter (hard deny)." 
    actual_risk = get_risk_level(command)
    risk_order = {"low": 0, "medium": 1, "high": 2}
    effective_risk = max([risk, actual_risk], key=lambda r: risk_order.get(r, 1))
    if effective_risk == "low":
        print(f"✅ Auto-approved (read-only): {command}")
        return _execute(command)
 
    approval = request_approval(command, reasoning, effective_risk)

    if approval == "approve":
        return _execute(command)
    elif isinstance(approval, tuple) and approval[0] == "approve":
        return _execute(approval[1])
    else:
        return "Command execution denied by user."


def _execute(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
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

chat = client.chats.create(model="gemini-3.6-flash", config=config)
MAX_LOOP_STEPS = 15

while True:
    user_query = input('> ')
    if not user_query.strip():
        continue

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
            print(f"🔍: {parsed_output.get('content')}")
            try:
                response = send_with_retry(chat, "Continue to the next step.")
            except Exception as e:
                print(f"--- Failed to continue: {e}")
                break
            continue

        if step == "plan":
            print(f"🧠: {parsed_output.get('content')}")
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
            print(f"🤖: {parsed_output.get('content')}")
            
            break

        print(f"--- Unrecognized step '{step}', stopping this turn.")
        break