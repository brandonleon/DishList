# DishList — Claude Code Instructions

**Read `AGENTS.md` for all project conventions, testing commands, directory structure, and agent roles.** That file is the single source of truth for how this project operates.

---

## Claude-Specific Rules

- Always use `uv run` to execute Python commands — never invoke `python` or `pytest` directly; the system Python lacks project dependencies.
- When Claude edits templates or static assets, follow the Potluck Host Agent playbook in `AGENTS.md` and manually verify via `uv run dishlist serve`.
- When Claude touches data or storage code, follow the Data Steward Agent playbook in `AGENTS.md` — always back up `data/dishlist.db` before destructive changes.
- **Claude must never commit code.** Always stop and prompt the user to review `git diff` and commit manually. Do not run `git commit` or `git push` under any circumstance. (This rule applies to Claude only — other agents like pi may commit normally.)