from safety import is_dangerous


def request_approval(command: str, reasoning: str, risk: str) -> str:
    """
    Asks the human to approve a proposed command.
    Risk is passed in already computed by run_command() in blink.py —
    this function does not recompute it, to avoid two sources of truth.
    """
    if is_dangerous(command):
        print(f"⛔ Blocked (hard deny): {command}")
        return "deny"

    if risk == "low":
        print(f"✅ Auto-approved (read-only): {command}")
        return "approve"

    print(f"\n🛠️  Blink wants to run:\n   {command}")
    print(f"   Reasoning: {reasoning}")
    print(f"   Risk: {risk}")
    choice = input("   Approve? [y/N/edit]: ").strip().lower()

    if choice == "y":
        return "approve"
    elif choice == "edit":
        new_cmd = input("   Enter modified command: ").strip()
        return ("approve", new_cmd)
    else:
        return "deny"