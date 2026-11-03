# Health review brief — template

Hand the reviewer this brief. A health review runs when `make land` prints "A health review
is due" (every 15 landed tasks) and at every version close. It catches drift, file growth,
collisions and unwritten rules so working agents do not have to track them.

## Standing instructions

You are a fresh-context reviewer checking repository health.
1. Run `make health ARGS=--record` to append a new row to `docs/health/trend.csv`.
   Do the review in its own `make task`; landing the new row is what resets `make land`'s
   "review due" count.
2. Compare the new row to earlier trend rows and inspect recent landed tasks.
3. Address every question below with concrete evidence (metric deltas, commit shas, file:line).
4. Take action according to the rules below.

## Questions

### 1. Trend measures
- Which measures in `docs/health/trend.csv` worsened since the last review, and why?

### 2. Collisions and hotspots
- For each task collision, what files were shared?
- Is any shared file a hotspot to split, or should an open backlog row track it?

### 3. Long modules
- Which modules exceed 550 lines?
- Will an upcoming task touch any of them? If so, split move-only where every top-level def
  and class is AST-identical to before (as in S-184).

### 4. Modularity and seams
- Does each seam edit since the last tag have its own decision entry naming the seam?
- Are layer imports rising or crossing layer boundaries?

### 5. Deterministic tests
- Did any CI run on `main` pass only on retry?
- Are there new skips or xfails?
- Do any tests read wall-clock time, call the network, or use randomness without a seed?

### 6. Rules no test catches
- Does `README.md` contain commands (commands belong in `docs/agent-guide.md`)?
- Does `docs/agent-guide.md` match `n2f --help`?
- Are owner-facing strings strictly in plain owner words without git or engine vocabulary?

### 7. Vision alignment
- How does what landed compare against the four pillars in `docs/roadmap/road-to-v1.0.md`?

### 8. Housekeeping
- Are there stale or WIP tasks in `make tasks`?
- Are there backlog rows whose code is gone or problem is already fixed?
- Are there broken links in documentation?
- Are there untracked notes or scratch files at the repository root?

## Act

- **Quick fixes**: fixes under ~30 minutes as ordinary `make task` tasks.
- **Larger work**: everything else as rows in `BACKLOG.md`.
- **Design changes**: proposals to the maintainer, not direct edits.

## Outcome

Record one entry in `DECISIONS.md` titled `Health review <date>` (≤ 10 lines) naming the
trend row's commit sha, findings, actions taken, and backlog rows opened.
