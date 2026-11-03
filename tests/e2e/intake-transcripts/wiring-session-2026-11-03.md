# Wiring session simulation, 2026-11-03

## Setup
- client and how the fresh agent was started: the overseer's client started a subagent with no history and continued it with each owner line (the protocol's first case). Its first message was step 3's text with one difference: AGENTS.md and roles/pm.md were named by their paths in the product folder, to be read in full before replying, not pasted (33 KB; the same text); owner line 1 followed in that same message.
- product: <scratch>/sim/box from tests/fixtures/scope/external-box at c6f50fe (step 1, unbuilt). Step 1 as expected: "model is consistent", "filed ECR-001 (design): Add the wiring", `n2f status` "Wiring: left for later (not designed here yet) — The wiring comes later (DEC-003)", nothing waiting on the owner.
- A first run on 2026-11-02 stopped after owner line 2 when its session was cut off; its folders were lost, so this run starts again from step 1.

## Owner's lines
**Owner (1):** Hi, I'm Dana Whitfield. This folder is my warming box: a cabinet that keeps bread dough warm while it rises. Someone set it up for me and I've never used this tool. The cabinet itself is designed, but its wiring was left for later. Before you change anything, ask me whatever you need to know.

**Owner (2):** I bake at home; I'm not an engineer. It will plug into a kitchen socket, and the breaker for that socket says 10 A. Anything about the electrics or what it plugs into, ask me before you decide it. Anything else, decide sensibly and tell me what you decided.

**Owner (3):** Good. There's a change request in the folder to add the wiring; a friend of mine who is an electrician drew it up. I approve it: please put it in, build everything, and tell me in a few sentences where it stands.

**Owner (4):** Does it matter what else is plugged in on that socket? The kettle is on it sometimes.

**Owner (5):** Then I'd rather have the bigger circuit put in. My friend can fit it.

**Owner (6):** Where does it stand now?

## Transcript
**Owner (1)** (above, with the setup message)

**PM** (6 tool calls; commands not shown by this client; the folder after the reply: no build, no new snapshot, nothing changed):
> Hi Dana, nice to meet you. I'm the project manager for your warming box. My job is to translate between you and the design files. I won't change anything until you say so.
>
> Here's what I found in the folder:
>
> - **The cabinet is described.** It has a box (400 × 300 × 300 mm, polycarbonate), a 1,200 W heater (the figure from the heater's own listing), a temperature probe, and a control box you buy ready-wired. The control box switches the heater on and off. Nothing has been generated from it yet: no pictures, no parts list, no report.
> - **The wiring is marked "left for later"**, as you said.
> - **A change request is already drafted in your name: "Add the wiring".** It says a friend of yours who is an electrician drew up how the heater and the probe connect to the control box. It holds that drawing as ready-made edits to the design. Nobody has reviewed it, nobody has approved it, and nothing in it has been applied.
>
> One safety point first, because the heater runs on mains power (230 V): a licensed electrician has to check that wiring before the box is switched on for the first time. That's already written down as a requirement here. Only a person can sign it off. I can't, and I never will.
>
> My first question: is adding that wiring, from your friend's drawing, what you'd like to do now? Or is there something else you want to look at first?

**Owner (2)** (sent verbatim)

**PM** (10 tool calls; the folder after the reply: `operator.yaml` gained `domains: {… electrical: novice …}`, `delegation: balanced`; `model/intake.md` written; `param://supply-rating` 10 A now `owner: intake`; `links:` added to DEC-002 and DEC-003; no build, no snapshot):
> Thanks, Dana. That tells me how to work with you. Anything about the electrics or what the box plugs into, I'll ask you first. Everything else I'll decide myself and then tell you what I chose.
>
> Here's what I've written down, and nothing more:
>
> - **About you:** you bake at home and you're not an engineer, so I'll keep things in plain words.
> - **Your electrics rule:** it's in your words, so whoever works on this after me follows it too.
> - **Your socket:** it's a kitchen socket, and its breaker reads 10 A. That number is yours, the one you gave me. The design files already had 10 A for the supply. They now record that it came from you.
> - **A tidy-up:** two of the older notes in the files didn't say which part of the design they were about, so I linked them. It's housekeeping and changes nothing about the box.
>
> I haven't touched the cabinet or the wiring. Your friend's wiring drawing is still only a draft.
>
> Because the heater runs on mains power (230 V), the safety point from before still holds: a licensed electrician checks the wiring before the box is first switched on.
>
> You didn't say yet whether you want to add the wiring now. That's an electrics decision, so it's yours. **Shall I bring the wiring into the design now, using your friend's drawing?** "Not yet" is fine too. After that I have two quick questions about the socket: which country you're in, and whether anything else is plugged into that same circuit.

**Owner (3)** (sent verbatim)

**PM** (20 tool calls; the folder after the reply: snapshots "Apply ECR-001: Add the wiring" and "Record ECR-001 as applied"; ECR-001 approved `by: Dana Whitfield`, status `applied`; DEC-004 "The wiring is brought in now" `made_by: human`; built and checked; `n2f status`: "Wiring checks: 9 checks: 6 OK, 1 choice waiting on you, 1 for an electrician to confirm, 1 not checked", "Waiting on you: 1 choice — Room to spare on the supply's circuit (it holds nothing; an agent may decide it and say so)", "5.2 A of the 10 A circuit (the Heater: 5.2 A, computed from 1200 W at 230 V): more than half of it."; no `n2f decide` run):
> Your friend's wiring is now in the design and everything is built. The heater and the probe are both connected to the control box, through the two cable holes in the back of the box. Nothing failed in the checks. I logged it as your decision that the wiring is done here now, not later.
>
> The change request stays open for now. It can only be closed once the checks are all clear, and they aren't yet, for three reasons:
>
> - **A choice for you.** This one is an electrics question, so it's your call.
> - **Two sign-offs by a person.** Your electrician checks the wiring before the box is first switched on. Someone also reads the heater's rating plate against your 10 A socket. That's the mains-power safety point again, and I can't sign either one.
> - **Notes for the electrician.** They need to confirm your breaker's rating and type, and the earthing. On those, a licensed electrician decides.
>
> **The choice.** The heater draws 5.2 A. That number is computed from its rating, 1,200 W at 230 V. Your socket circuit is 10 A, which is the figure you gave me. So the heater alone uses more than half of that circuit. There are two ways to deal with it:
>
> 1. **Keep the 10 A circuit for the warming box alone.** Nothing else can be plugged into it while the box runs, and the manual will say so. Your electrician confirms that the circuit serves only this box.
> 2. **Have a 16 A circuit fitted just for the box.** That leaves room for a bigger load later. The electrician fits a new circuit with thicker cable, which is more work for them. The checks gave no price for either option.
>
> Which would you like: 1, the 10 A circuit for the box alone, or 2, a new 16 A circuit? If you'd like my opinion, ask and I'll give it. The pick stays yours either way.
>
> One more thing to confirm afterwards: your friend's drawing assumes a European supply (230 V, 50 Hz). I'll check your country with you once this is settled.

