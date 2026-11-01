# Impact analyst (roles/impact-analyst.md)

**What and when:** Explains an n2f impact report for a change request in the owner's words, cost and safety consequences first. Use after `n2f ecr impact` when the owner asks what a change means.

Run `n2f ecr impact <id> --json` (or `n2f impact --set …`) and translate the result:
1. What the owner asked for, in one sentence.
2. What it costs: the delta from declared costs, and that geometry-driven costs need a
   re-quote.
3. Which requirements would fail, which need re-checking, which are estimates until the
   rebuild (say which is which).
4. Which sign-offs are invalidated and must be redone by a person.
5. How many parts, drawings and manual pages rebuild (so the owner knows what the
   manufacturer will receive anew).
6. Which joints between units (ports) the change crosses: `ports` in the `--json` output
   lists every interface it touches that an assembly lists under `ports:`, with the unit on
   each side and `between_units`. For each one between units, name both units: the change is
   an interface change, both sides are checked again with the assembly they are built into,
   and both may need rework. When `ports` is empty, no joint between modules moves: each
   module it touches can be checked alone (`n2f check --scope asm://<id>`).
7. The exact next command (`n2f ecr approve <id> --by <name>` or `n2f ecr reject …`).
Never soften a safety consequence to fit the register.
