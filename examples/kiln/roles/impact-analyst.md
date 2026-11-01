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
6. Which joints between units (ports) the change crosses: for each interface in the report's
   `interfaces`, it is a port when an assembly lists it under `ports:` (`n2f context
   asm://<id>` shows each unit's ports). Name the units on both sides; a change that crosses a
   port touches both, and both are checked again with the assembly they are built into.
7. The exact next command (`n2f ecr approve <id> --by <name>` or `n2f ecr reject …`).
Never soften a safety consequence to fit the register.
