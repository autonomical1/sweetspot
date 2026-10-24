# Project conventions (read by every agent: Claude and Codex)

## What this is
<one paragraph - orchestrator fills in after spec approval>

## Commands
- Install: <cmd>
- Run: <cmd>
- Test: <cmd>

## Rules for worker agents
- Edit only files listed in your task's OWNS.txt. Never edit orchestrate/TASKS.md, STATE.md, DECISIONS.md, docs/SPEC.md or docs/API.md; if they are wrong, say so in your HANDOFF.md.
- Do not run git commit/push/checkout/merge. The harness commits.
- Code against docs/API.md. If a contract is missing or wrong, stub minimally and report it in HANDOFF.md; do not invent cross-module changes.
- No network access in the sandbox: do not try to install packages. If you need a dependency that is missing, report it in HANDOFF.md.
- Keep changes small and runnable. Leave the test command passing.

## Code style
<orchestrate fills in: language, formatting, naming>
