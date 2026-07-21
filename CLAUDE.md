# CLAUDE.md

This project's agent instructions live in **[AGENTS.md](AGENTS.md)** — read that file and
follow it. It's the onboarding runbook for setting up **skool-kb** with a (possibly
non-technical) user: what to ask for, what to install, and how to run the pipeline.

Quick reminders (full detail in AGENTS.md):
- **Never** commit or echo secrets — `cookies.txt` and `.env` are gitignored; keep them out of git, issues, and PRs.
- Cookies come from the **user's own logged-in browser**. Walk them through the "Get cookies.txt LOCALLY" extension.
- Best results run on the **user's personal computer**, not a VPS (YouTube bot-checks datacenter IPs).
- Be honest about limits: native Skool videos and YouTube-on-a-VPS are not guaranteed.

When the user is just **querying** the finished knowledge base, the instructions for that
live in **[kb/CLAUDE.md](kb/CLAUDE.md)** (search the files, answer, cite filenames).
