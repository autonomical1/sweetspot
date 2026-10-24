# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: <name>
- started: <ISO time>
- deadline: <ISO date+time of final demo/submit>
- phase: discover   # discover | spec | plan | build | integrate | polish | done
- gates: key        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 0
- last_checkpoint: <ISO date+time>

## Next action
(one concrete sentence a fresh session can execute)
<...>

## Waiting on user
<none | the exact question>

## Notes for a fresh session
<anything not captured in SPEC/API/TASKS/DECISIONS>
