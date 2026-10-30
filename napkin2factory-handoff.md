# Napkin2Factory — Project Handoff & Context Package

**Date:** 2026-10-30 · **Status:** Architecture/design phase complete (conversational), founding spec NOT yet written — that's the next task.
**Purpose of this file:** Give any AI model full context to continue exactly where this conversation ended.

---

## 1. What this project is

**Napkin2Factory** (CLI: `n2f`, tagline: *"From napkin to factory."*) — an **open-source, agentic idea-to-manufacturable-design system**. A user describes a product idea (example used throughout: a kiln); the system interviews them to scope it, then generates everything needed to manufacture it: BOM, CAD, schematics, 3D demonstration, technical/installation manuals, manufacturing package. Crucially, it supports **Engineering Changes (ECOs)** that propagate and re-synchronize everything automatically.

**Owner's intent:**
- NOT a commercial product. Open source. Zero hosted infrastructure by the author.
- Cares about: **reliability/robustness** ("as if you had an A+ engineering team") and **impeccable UX**, especially the ECO loop and ease of communicating changes to the AI (e.g. selecting things like in Claude/ChatGPT desktop integrated browser).
- End deliverable: a packaged design sent to a manufacturer (China), possibly with revision rounds with them. Shareable project-as-webpage (GitHub Pages) is a stated win.
- Target users: both non-technical tinkerers ("make my idea real") and pedantic engineers. No git/GitHub knowledge assumed.

**Owner's relevant setup:** uses Claude Code; has a delegation setup where Claude Code hands work to Google's Antigravity CLI (`agy`) on a Google Pro subscription (precedent for subscription-authenticated unattended agents); has a remote headless Ubuntu 24.04.3 server available as build/runner machine.

---

## 2. Core architectural principle

> **One canonical product model; everything else is a compiled, disposable view of it.**

Hardware design treated like a software build system (CI/CD). BOM, drawings, manuals, 3D are never independently authored — they are **generated** from a single structured source. An ECO = edit source → rebuild invalidated artifacts → re-verify. Stale artifacts are rebuilt, not patched, so nothing drifts.

Division of labor (repeated throughout, non-negotiable):
- **Agents decide and author** (write source files, open change requests)
- **Deterministic tools verify** (solvers, rule checkers — agents never *assert* an engineering result)
- **Humans arbitrate** (gates/approvals)
- **The pipeline rebuilds** (zero LLM tokens for regeneration)

## 3. The canonical product model (git repo, all text)

- **Requirements** — atomic, testable, IDs (`REQ-014`), cost targets, standards.
- **Parameters** — one file, named values with units; everything references by name, never hardcodes.
- **Parts & BOM** — records: ID, revision, material, source (real MPN), cost, lead time.
- **Interfaces** — first-class contracts between subsystems (bolt patterns, voltages, pinouts).
- **Decision log** — every choice with rationale, linked to requirements (`DEC-031: chose 50mm ceramic fiber…`). Agents must log decisions made on the user's behalf.
- **CAD and schematics as code** — CadQuery/Build123d (mechanical), KiCad text formats (electrical). Text = diffable, parametric, regenerable, PR-reviewable. Binary CAD is forbidden as source.
- **Stable IDs/URIs on everything**: `part://heater-coil`, `req://REQ-014`, `param://wall-thickness`. Generators carry IDs into every output (GLB node names, BOM rows, drawing callouts, manual anchors). This is the prerequisite for the "point at things" UX (see §8).

## 4. Pipeline (fixed) + agents (contracted) + skills (adaptive)

**Three-layer internals — "fixed contracts, adaptive execution":**

1. **Pipeline is fixed code/state machine, never LLM-decided**: Intake → Architecture → Detail design → Verification → Docs → Release, with gates. No agent can skip/reorder stages ("the constitution"). A stage can auto-pass only when empty ("no electrical content"), never when inconvenient.
2. **Predefined roles as contracts** (not personality prompts): declared `reads/writes/tools/done_when/must_not/stance`. Enforced by sandbox. Why predefined: (a) separation of duties must be structural — designers write `design/`, verifiers write `reports/` and CANNOT touch design (no grading own homework); (b) permissions/ACLs attach to stable identities; (c) debuggability — failures improve a named role + regression test.
3. **Adaptive within contracts**: orchestrator decides *which* roles and *how many* instances per product (kiln spawns thermal+structural+electrical; bracket spawns one mech designer); **skills are the knowledge units** (`sheet-metal-dfm`, `heating-element-sizing`, `kicad-layout`) loaded per task. New domain = new skill, not new agent. Maps 1:1 to Claude Code/Agent SDK conventions (agents as markdown + frontmatter, skills as folders, all in-repo, forkable).

**Agent roster (~8–10):** `orchestrator`, `intake-analyst`, `architect`, `designer` (generic, specialized by skill loadout), `verifier` (adversarial stance, **always fresh context** that never saw the design conversation — context isolation makes independent review real), `impact-analyst`, `doc-compiler`, `librarian` (harvests factory feedback/ECR outcomes into new rules & skills — how the system gets smarter per project).

**Communication rule:** agents communicate **through files, never chat**. Every inter-agent message is a schema'd artifact in the repo → any agent replaceable by a human/different model/script; orchestrator death is resumable from disk.

**Verification stage:** different agents than designers, adversarial instructions, run deterministic tools (FEA/thermal, tolerance stack-ups, interference, ERC/DRC, standards checklists, unit validation).

## 5. ECO engine (the heart of the UX)

Explicit traceability graph: requirement → parameter → part → drawing → manual section (Make/Snakemake-style).

ECO flow: change request filed against the model (structured file referencing stable IDs, not prose) → **impact-analysis agent walks the graph and reports BEFORE anything changes** ("touches heating element sizing, 3 drawings, power budget, violates REQ-021 unless…") → human approves scope → agents regenerate exactly the invalidated artifacts → verification re-runs downstream → revisions bump with changelog.

Loop: **see → point → say → impact report → approve → regenerate → visual diff.** (A 30-second demo GIF of this loop = the marketing.)

## 6. Repo & packaging decisions

- **System repo vs product repos** are separate concepts. Start as one monorepo (`system/` vs `products/` boundary) for iteration speed; split later is mechanical. Product repos pin a system version; a product repo is the handover-able "technical data package."
- **Installed footprint ≈ nothing**: a product repo contains only user data (product model, `operator.yaml`, decision log) + a tiny `factory.yaml` manifest (`system: v1.4.2`, `rulepacks: v2026.10`, `schema: 3`). Engine/agents/templates/checkers are **fetched by version at runtime** (pinned container image by digest = reproducibility: 2026 design rebuilds identically in 2031).
- **Upgrades**: explicit `factory upgrade` with shipped migrations (Rails/ESLint-style codemods); **an upgrade is treated as an ECO** (rebuild, diff outputs, human reviews differences — rule packs can change verdicts on unchanged designs and that must surface). Never auto-upgrade the engine. Split cadences: engine (slow, semver) vs rule packs/data (fast, date-tagged, community-maintained).
- Golden-model regression corpus both ways: system CI rebuilds example projects against release candidates.

### Naming (decided 2026-10-30)
- Name: **Napkin2Factory**; CLI binary: **`n2f`**; lowercase `napkin2factory` for repo/package.
- Checked: no project collision for "Napkin2Factory". BUT: npm `n2f` is **taken** (dormant input-focus utility, 2022). PyPI `n2f` appears **free**. **"N2F" is an established French expense-management SaaS** (n2f.com, PE-backed €24M+) — low legal risk (different domain) but permanent search collision.
- Resolution: publish ONE real package on **PyPI as `napkin2factory`** (Python is where the engine lives) with console-script binary `n2f`. Register `n2f` on PyPI as defensive placeholder depending on `napkin2factory`. Register npm names defensively; only build an `npx` shim later if onboarding data demands it. Docs always say "install napkin2factory".

## 7. Toolchain (audited against Oct 2026 landscape)

**Deterministic layer:** CadQuery/**Build123d** (v0.12 Sep 2026, healthy) or **Zoo KCL** (candidate, see below); FreeCAD headless (TechDraw drawings, sheet-metal); CalculiX + Gmsh (+`cadgmsh` bridge, 2026); OpenFOAM only if genuinely needed; plain codified hand-calcs first; **KiCad 10** (10.0.6, official IPC API) + `kicad-cli` + ngspice; **pint** units everywhere; jsonschema/pydantic schema validation in CI; custom tolerance stack-up lib (worst-case + RSS — nothing good off-the-shelf); BOM validator vs Octopart/Nexar/Digi-Key/McMaster APIs (hallucinated MPNs = #1 embarrassment); standards checklists as YAML data + runner; Sphinx/Quarto or **Typst** for docs.

**Viewer layer (browser is the only review surface):** GLB/glTF via `<model-viewer>`/three.js (also the "3D demonstration" deliverable, exploded views/animations); **KiCanvas** renders .kicad_sch/.kicad_pcb in-browser; kicad-cli SVG/PDF; drawing **image-diffs between revisions** (SVG) — enormously valuable for ECO review; PyVista exports interactive FEA scenes as standalone HTML; per-build self-contained HTML report (3D + schematic + drawings + diffs + sim plots + BOM/cost/mass rollups + check matrix).

**Orchestration:** Claude Code / Agent SDK; GitHub Actions (+ optional self-hosted runner on the user's server for heavy sims); Snakemake-style dependency graph = the rebuild-only-invalidated ECO engine.

**Known gap:** open stack weak at Class-A **surfacing** (consumer-product smooth shells) and sheet-metal unfolds less mature; fine for prismatic industrial equipment (frames, enclosures, weldments, panels — kiln-like). Text-to-CAD tools also still fail at this, so no disadvantage in practice.

## 8. UX & product decisions

- **Web over desktop, decisively.** The system = pipeline + review surface; cockpit jobs (status, review, approve, ECR) are web-native; artifacts already web-native; multi-device approvals; zero update friction; headless server friendly. Desktop tools (KiCad, Zoo Studio) remain *clients of the repo* for deep editing only. If an installed feel is ever wanted → Tauri wrapper later (web-first makes that a day; reverse is a rewrite). v0.1 cockpit = GitHub PR screen + generated HTML report; custom UI only for intake, ECO impact view, 3D/drawing diff gallery. (Later realized: even this may shrink — **the AI provider's own UI is the driver**.)
- **BYOA (bring-your-own-agent)** — "don't build an AI client; build a system any AI client can operate." Three access layers: (1) **git + files** (any coding agent works already — the repo IS the API); (2) **`factory` CLI** — the system's verbs (`init/ecr/impact/build/check/release/publish/upgrade`), where design rules and guardrails live, NOT in prompts; shared by humans, agents, CI; (3) **MCP server** wrapping the same operations for native chat experiences (MCP won the protocol war — all major clients speak it). Peer MCP servers: KiCad's Konnect, Zoo Text-to-CAD.
- **Token economics:** deterministic rebuilds cost zero tokens (plain CI); interactive agent work runs on each user's own AI subscription in their client; unattended server-side work runs a subscription-authenticated CLI (same pattern as owner's agy setup). The project's author hosts and pays for nothing.
- **"PM" is a role the repo installs, not a hosted component**: `CLAUDE.md`/`AGENTS.md` + a PM skill turn whatever client opens the project into the project manager. PM = only agent that talks to the human (intake, register adaptation, translating intent→ECRs and artifacts→explanations, triaging worker questions via question-artifacts, relationship memory = repo state). **Orchestrator is separate and deliberately non-conversational** (headless bureaucrat; PM charm must never leak into pipeline rigor — "user seems impatient, skip thermal re-check" is the failure to prevent). User can switch AI clients mid-project losing nothing. Unattended PM = scheduled job (nightly: stalled questions, part EOL → draft ECR, morning summary).
- **Git hidden, never required**: vocabulary mapping enforced in docs/CLI — branch=draft, commit=snapshot, PR=change request awaiting approval (ECR — mechanical engineers invented this), merge=approved & released, tag=Revision B. Review happens on the generated report page, never on github.com diffs.
- **Solo mode is the default** (`factory init`): plain local git, no GitHub, no accounts; the gate = agent shows impact report in chat, user's "yes" is the merge; `factory build` runs the identical pipeline locally (same container) — CI-in-cloud is an upgrade, not a prerequisite (also enables offline). **Share mode**: `factory publish` → agent creates GitHub repo, wires Actions+Pages; the ONE unavoidable human step is GitHub account creation/OAuth (~2 min, framed as "free website + backups"). Team mode = branch protection config on top. Power users: agent adapts, they can drive git directly (everything is standard underneath — Obsidian-on-markdown philosophy). Do NOT build a hosted sync/accounts service.
- **Adaptive autonomy** ("Owner mode ↔ Engineer mode" framing): `operator.yaml` persisted per project — expertise **per domain** (expert welder may be electronics novice), verbosity, delegation level; inferred from how they talk during intake, upgraded live when user shows depth. **Decisions delegated, never deleted** — every system-made choice logged with rationale regardless of persona. **Question triage by consequence**: high-impact + answerable → ask in their register; high-impact + not meaningfully answerable → decide conservatively and disclose plainly (asking a novice to pick a thermal cutoff is abdication, not respect); low impact → decide silently, log. **Safety floor**: safety-critical facts stated to everyone in plain language regardless of persona (mains power, 1300°C, "needs a dedicated 30A circuit installed by an electrician") — adaptation must never become consent-washing. Same pipeline/checks/gates byte-identical for all personas; only the dialogue and report rendering adapt (novice report leads with pictures/cost/"what to tell the manufacturer"; engineer report leads with check matrices/tolerances — cheap, since generated).
- **Zero-install onboarding, three doors**: (1) **Chat app only** — MCP connector/skill loads PM into user's existing Claude/ChatGPT; agent works in provider's cloud sandbox, clones template there, runs intake, builds, links report; durable home = GitHub after the one OAuth. (2) **GitHub template** ("Use this template") + cloud agent (Claude Code web/Codespaces); Actions = build machine, Pages = product site. (3) **Local CLI** (`uvx napkin2factory`) for power/offline/privacy. **First-run = conversation, not README**: within ~10 min of "I want to design a kiln," user sees scoped requirements + first rough 3D silhouette.
- **Check tiers (forced by sandbox constraints)**: tier-0 pure-Python/pip (schema, units, BOM validation, CadQuery geometry, cost model) runs anywhere incl. chat sandboxes; tier-1 (FEA, KiCad DRC, full doc builds) on Actions; tier-2 heavy sims on optional self-hosted runner.
- **GitHub Pages as the Technical Data Package**: `/kiln/` latest, `/kiln/v1.2.0/` frozen forever (the URL you send to Shenzhen), `/kiln/diff/v1.1.0..v1.2.0/` generated change page (visual drawing diffs, BOM delta with cost impact, agent-written "what this means for manufacturing"). Release = git tag → Actions builds ZIP (STEP, drawings PDF, Gerbers, BOM.xlsx, assembly manual) attached to GitHub Release + deploys site. Manufacturer feedback → Issues → ECRs → full traceability of why each change happened (prevents the classic WeChat-verbal-change/wrong-rev disaster).

## 9. Manufacturability measurement (not one number — a verdict with evidence)

- **Layer 0:** every part must declare `process` (+ material, finish, quantity basis) or the gate can't apply — manufacturability is relative to a process.
- **Layer 1:** deterministic per-process rule packs, binary pass/fail, geometric checks via OCCT (sheet metal: bend radii, hole-to-bend, reliefs, unfold validity; machining: corner radii, depth:dia, tool access; molding: draft, wall uniformity; PCB: DRC against the fab's published capability profile; assembly: joint/fastener access).
- **Layer 2:** tolerance vs process capability tables (ISO 2768-style) — tighter than capable = hard fail; "possible but costly" band = warning + cost multiplier; plus stack-up checker ("does the assembly even need these tolerances?" — over-tolerancing is the #1 novice money-burner).
- **Layer 3:** cost & sourcing as universal proxy — instant-quote oracles (Xometry/Protolabs/JLCPCB APIs return price + machine DFM feedback; a factory's pricing algorithm IS a DFM evaluation), parametric cost model for inner-loop deltas ("your ECR added two setups, +31% unit cost"), BOM sourceability + custom-vs-COTS ratio.
- **Layer 4:** manufacturer verdict harvested as data — every factory note becomes an ECR AND a new rule tagged to a **manufacturer capability profile** (`manufacturers/shenzhen-acme.yaml`: machines, tolerances held, materials stocked); gate runs against the selected profile. Community-maintained DFM rule library + real factory profiles = the project's long-term moat.
- Gate report format: `Process: sheet-metal (profile: shenzhen-acme) · Rules: 47/47 · Tolerances: all capable, 2 premium (+12%) · Est. unit cost @50: $142 vs target $160 ✔ · Quote oracle: $151, 1 DFM note → ECR-019 · BOM: 100% sourceable, 3 custom parts`.
- Agents don't *judge* manufacturability; they *fix* violations and *translate* factory prose into rules/ECRs.

## 10. Post-cutoff landscape (researched 2026-10-30; assistant cutoff was end-Jan-2026)

- **Zoo (ex-KittyCAD)**: Zookeeper conversational CAD agent (Jan 2026, Design Studio v1.1), KCL 3.0 (Oct 2026); own kernel + text language built as LLM target; engine tools (mass, CoM, snapshots); Engine API + Agent API + Text-to-CAD MCP. Strong for single parts (brackets/flanges/housings), not yet assemblies/drawing packages. = commercial candidate for the geometry layer vs build123d (open, mature Python). Prototype both.
- **KiCad 10** + **Konnect** MCP plugin (Oct 2026): 228 tools/21 toolsets — schematic capture, layout/routing, ERC/DRC, design-review audits, JLCPCB part search, manufacturing export; official IPC API; integrates with KiCad undo/redo. Adopt.
- **Quilter** (paid layout engine): automated BGA fanout, custom diff-pair impedance, placement regions/clustering, clearance constraints (2026). Optional accelerator; our DRC stays the gate. (Context: GPT-6 Astra's Sept 2026 "LLM designs PCB" demo; Quilter published critical tests — LLMs alone still not production layout.)
- **FEA/sim agents**: FeaGPT (NL → geometry→mesh→CalculiX→analysis, validated on turbocharger cases); Engineering.ai (leader-orchestrated multi-agent FreeCAD/Gmsh/OpenFOAM/CalculiX + GP-surrogate Bayesian optimization); `awesome-ai-cae` list ranks 100+ CAE tools by AI-readiness (MCP/Python/CLI). Guardrail: surrogates never silently replace solvers — OOD detection, full solver at release gates.
- **PLM/ECO**: **Cascadia PLM** (new, AGPL, self-hosted, git-style versioning, parts/BOM/ECO/where-used) — philosophically identical, evaluate as parts/ECO registry; **OpenBOM** "Product Memory" knowledge graph + change-impact agents; AI-native wave (SPREAD, Cognyx, Trace.Space). **Flow Engineering**: $50M Series B Sept 2026 @ $750M — "AI harness for hardware engineering," agents analyze changes/downstream impact/verify requirements — our ECO engine as a venture-backed category (validation + the reason owning the harness is worth it).
- **MIT industry study** (agentic AI in engineering/mfg): gains cluster in structured/data-intensive checking; adoption gated on reliability/verification/auditability + human-in-the-loop; models still weak at spatial/multi-physics reasoning → confirms our architecture exactly.
- **arXiv RF workflow paper**: Claude in Claude Code drove CST/ADS/KiCad purely via scripting; entire design state as scripts/parameters; everything regenerates with one command — direct proof-of-concept of our model.
- Academic wave validating "agents generate, deterministic tools validate": CADSmith (multi-agent + programmatic geometric validation), CADIR, physics-in-the-loop architectures, MUSE benchmark (manufacturable/assemblable text-to-CAD). Independent testing: text-to-CAD still struggles at medium-high complexity parts.

## 11. v1 scope (ruthless) & open threads

**v1 =** product model + ID/URI system + CI rebuild + Pages site + ECR flow for **mechanical + BOM only**, shipped with the **kiln** as a complete real example in `examples/`. Electrical stage, sim gates, MCP server = v1.1+. (Failed OSS engineering tools die by shipping frameworks before one working product end-to-end.)

**Immediate next step (offered, accepted direction, not yet done):** draft the **founding spec** — repo layout, product-model schema with the ID/URI scheme, v1 feature cut — as a document to iterate on.

**Also to do:** register `napkin2factory` (PyPI, npm, GitHub org) + `n2f` PyPI placeholder.

**Positioning notes:** headline BYOA ("works with Claude Code, Codex, Antigravity, or no AI at all"); boring foundations (git/YAML/Actions/Pages/KiCad/build123d); framing "git-native product engineering" vs PLM dinosaurs; the 30-sec ECO-loop GIF.

## 12. Conversation style notes for the next model

- User thinks out loud, asks **one question at a time**, and explicitly appreciates honest push-back with reasoning (accepted the name critique process, the npm findings, "maybe that's not needed" on custom UI).
- Prefers decisive recommendations with trade-offs stated, not option menus; call out where humans/LLMs are weak honestly.
- Verify recent tech claims with web search rather than answering from memory — this was requested and valued repeatedly.
- The system's own working vocabulary in this chat: "the harness," "product model," "PM role," "doors 1/2/3," "Owner/Engineer mode," "tier-0/1/2 checks," "rule packs," "manufacturer profiles."
