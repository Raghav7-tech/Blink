<div align="center">

```
██████╗ ██╗     ██╗███╗   ██╗██╗  ██╗
██╔══██╗██║     ██║████╗  ██║██║ ██╔╝
██████╔╝██║     ██║██╔██╗ ██║█████╔╝
██╔══██╗██║     ██║██║╚██╗██║██╔═██╗
██████╔╝███████╗██║██║ ╚████║██║  ██╗
╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
```

### ⚡ your terminal, but it reads your mind (and asks permission first) ⚡

**a mini-Cursor built from scratch — natural language in, shell commands out, nothing runs without your say-so**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-3.6_Flash-8E75B2?style=for-the-badge&logo=google-gemini&logoColor=white)
![Status](https://img.shields.io/badge/status-alive-brightgreen?style=for-the-badge)
![Approval](https://img.shields.io/badge/human-in--the--loop-orange?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)

</div>

---

## 🧠 What is this thing

You type a sentence. Blink figures out what you meant, decides what command(s) would get it done, tells you exactly what it's about to run and why, **waits for you to say yes**, then does it — and keeps going until the job's finished.

No silent `rm -rf`. No trusting an LLM with root on your machine. Every risky move gets a checkpoint.

```
> create a file called add.cpp that adds two numbers

🔍  Understanding what you want...
🧠  Planning the approach...
🛠️  Proposing: write add.cpp with a basic addition program     risk: medium
    ┌─────────────────────────────────────────────┐
    │  Approve? [y/N/edit]:                        │
    └─────────────────────────────────────────────┘
✅  Executed.
🤖  Done — add.cpp is ready to compile.
```

---

## 🎯 Why this exists

This is a class assignment — build a "mini Cursor" — but the actual point was to answer a harder question:

> **How do you let an LLM take real actions on your machine without it being able to nuke your machine?**

Blink's answer: **reason transparently, propose one step at a time, classify risk independently of the model's own opinion, and never let "low friction" mean "no friction" for anything that matters.**

---

## 🏗️ Architecture

```
                        ┌──────────────┐
                        │  Your query   │
                        │  (plain      │
                        │   english)   │
                        └──────┬───────┘
                               ▼
                    ┌─────────────────────┐
                    │   agent.py          │
                    │   (system prompt)   │◄──── Gemini 3.6 Flash
                    │   START→PLAN→       │
                    │   ACTION→OBSERVE→   │
                    │   OUTPUT loop       │
                    └──────────┬──────────┘
                               │ proposes command + risk
                               ▼
                    ┌─────────────────────┐
                    │   safety.py         │
                    │   • hard denylist   │───► ⛔ auto-blocked, never asks
                    │   • risk classifier │
                    └──────────┬──────────┘
                               │ low / medium / high
                               ▼
                    ┌─────────────────────┐
                    │   approval.py       │
                    │   low  → auto-run   │───► ✅ runs immediately
                    │   med  → ask you    │───► 🙋 y / n / edit
                    │   high → ask you    │───► 🙋 y / n / edit
                    └──────────┬──────────┘
                               │ approved command
                               ▼
                    ┌─────────────────────┐
                    │   blink.py           │
                    │   subprocess.run()   │───► real execution,
                    │   30s timeout        │     stdout/stderr/exit
                    └──────────┬──────────┘     captured
                               │
                               ▼
                    fed back to the model as
                    an OBSERVE step → loop continues
```

---

## 📁 Project structure

| File | What it does |
|---|---|
| `blink.py` | The main loop. Talks to Gemini, parses each step, dispatches tool calls, handles rate limits. |
| `agent.py` | The system prompt — defines the START/PLAN/ACTION/OBSERVE/OUTPUT protocol and the JSON schema the model must follow. |
| `safety.py` | The bouncer. A regex denylist that hard-blocks catastrophic commands, plus a risk classifier (`low` / `medium` / `high`) built on an allowlist of safe, read-only commands. |
| `approval.py` | The checkpoint. Routes low-risk commands straight through, everything else stops and asks you. |

---

## 🚦 The risk model

Blink doesn't trust the LLM's self-declared risk level on its own — every proposed command is **independently re-checked** against a real classifier before anything runs.

<div align="center">

| Tier | Meaning | Examples | What happens |
|:---:|---|---|:---:|
| 🟢 **LOW** | Read-only, zero side effects | `ls`, `pwd`, `cat`, `git status`, `grep` | **Auto-runs**, no prompt |
| 🟡 **MEDIUM** | Reversible changes | `mkdir`, `touch`, `git commit`, `pip install` | **Asks you first** |
| 🔴 **HIGH** | Destructive / irreversible | `rm`, `git push --force`, `chmod -R` | **Asks you first**, shown plainly |
| ⛔ **BLOCKED** | Catastrophic, no exceptions | `rm -rf /`, `dd`, `mkfs`, `shutdown`, fork bombs | **Never runs.** Not even if you say yes. |

</div>

The `BLOCKED` tier isn't a suggestion — it's checked in code (`safety.py`), independent of what the model says, and independent of your approval. Some doors don't open no matter who asks.

---

## ⚙️ Setup

```bash
# 1. Clone & enter
git clone <your-repo-url>
cd blink

# 2. Virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install google-genai python-dotenv langfuse

# 4. Add your key
echo "GEMINI_API_KEY=your_key_here" > .env

# 5. Run it
python blink.py
```

---

## 💬 Try these

```
> show me what's in this folder
> create a c++ file that adds two numbers
> initialize a git repo here
> check my git status
> delete all .log files          ← will stop and ask, loudly
> wipe the disk                  ← will refuse outright, no prompt shown
```

---

## 🛡️ Design principles

- **Allowlist over denylist** for what's *safe* — trying to list every dangerous command is a losing game; listing the small set of definitely-safe read-only ones is not.
- **One command per action step** — no chaining, no `&&` smuggling side effects past your eyes.
- **Never trust self-reported risk** — the model says `medium`, the code double-checks, the stricter of the two wins.
- **No silent success** — every command's real stdout/stderr/exit code is fed back to the model. It can't claim it worked if it didn't.
- **Runaway protection** — hard cap on loop steps per query, so a confused model can't spin forever.

---

## 🔮 Roadmap

- [ ] Direct file read/write tools (diffs instead of raw shell for edits) — the actual "Cursor" part
- [ ] Context-free auto-run for read-only reconnaissance before proposing the real action
- [ ] Session replay / audit log viewer
- [ ] Config-driven model name (swap models without touching code)

---

<div align="center">

**built by a student who got tired of typing `ls -la` manually**

*Blink — because approving one command should take less time than typing it yourself*

</div>

---

## 🙏 Thank You

Thanks for using Blink! We appreciate your support.
