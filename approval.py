from safety import is_dangerous, get_risk_level, is_auto_approved 
def request_approval(command: str, reasoning: str) -> str:
    if is_dangerous(command):
        print(f"⛔ Blocked (hard deny): {command}")
        return "deny" 
    risk = get_risk_level(command) 
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