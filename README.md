<!--
For AI agents reading this file:
- A person asked you to USE napkin2factory (design a product, change one, or see the example):
  read docs/agent-guide.md and follow it. Online:
  https://raw.githubusercontent.com/osaxma/napkin2factory/main/docs/agent-guide.md
  The prompt people paste is under "Start" below; it points to the same guide.
- You were asked to DEVELOP napkin2factory itself (this repository's code, tests or docs):
  read AGENTS.md instead.
This README is for people. It leaves out the command line and the Python setup on purpose:
those are in the agent guide.
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/osaxma/napkin2factory/main/brand/png/n2f-lockup-on-dark.png">
    <img src="https://raw.githubusercontent.com/osaxma/napkin2factory/main/brand/png/n2f-lockup-on-light.png" width="420" alt="napkin2factory: a pen sketch of a hexagon on a napkin, with the finished part floating above it, beside the name">
  </picture>
</p>

# napkin2factory

**From napkin to factory.** Tell your AI agent about something physical you want made. It
sketches a few rough directions and shows them side by side. You pick one, and it turns that
into a package a workshop can build from: 3D models, drawings, flat patterns, a parts list
with costs, manuals, and one page that shows it all. When you change your mind later, you
see what the change affects before anything moves.

> **Disclaimer.** napkin2factory designs are made with an AI system and have not been
> reviewed by a licensed engineer. Have a qualified person review a design before you build,
> power or use it. Safety requirements never pass by computation alone; a person signs them
> off.

## Start

You need an AI coding agent that can run commands on your computer (macOS or Linux). Paste
this into it, with your idea at the end:

```text
I'd like to design a physical product with napkin2factory. Read its guide for agents and follow it:
https://raw.githubusercontent.com/osaxma/napkin2factory/main/docs/agent-guide.md

My idea: (a sentence or two: what it is, what it is for, where it will live)
```

Your agent asks before it installs anything, makes a folder for your product, and takes it
from there. It asks a few questions, one at a time, then opens a board in your browser with
the rough directions side by side. You answer and choose in plain words. You don't need to
type commands or open files.

## Other ways in

- **See an example first.** Paste this instead:

  ```text
  Show me what napkin2factory does with its kiln example. Read its guide for agents and follow the "Show the example" section:
  https://raw.githubusercontent.com/osaxma/napkin2factory/main/docs/agent-guide.md
  ```

  The example is a 1200 °C test kiln. Its first direction is shown in red: it needs 1236 mm
  of width with the door open, and the alcove it was meant for is about 800 mm. Without the
  napkin stage that problem turned up at hour forty. The board shows it in minute five.
- **You already have a product folder** (one you made earlier, or one someone sent you).
  Open that folder in your agent and say what you want. The folder carries its own
  instructions for the agent.
- **You'd rather do it by hand.** Everything the agent does is in the
  [guide for agents](docs/agent-guide.md). It is written for agents, but you can follow it.
- **Coming later:** a way in from chat apps that have no terminal, and a GitHub template that
  builds on GitHub's machines.

## What you get

- **A board of rough directions** before any detailed design. Every number on it says where
  it comes from: *given* (yours), *computed* (measured from the shapes) or *estimate* (a
  rough engineering formula). A direction with a problem stays on the board, in red, with its
  reasons.
- **A report page** that opens straight from disk: a 3D view you can turn, drawings, the
  parts list with "what to tell the manufacturer", and which requirements pass and which
  need you.
- **A build plan**: what is put together on its own (a door, a control box), in what
  order, with the fixings for each joint counted, and an assembly sheet for each step that a
  workshop can follow.
- **Safe changes.** Each change shows its impact first, waits for your yes, rebuilds only
  what it affects, and ends in a page comparing the two versions.
- **Named versions** (v1.0.0, v1.1.0 …) you can send to a manufacturer, frozen only when
  every check passes and every safety requirement has a person's sign-off. When you want a
  manufacturer to see them, ask your agent to share the pages: you get one folder to send,
  or, if you have a GitHub project for it, a web address.

It runs on your computer, works offline once installed, and needs no account.

## What it does not do yet

Mechanical parts and the parts list are covered. Electrical design, structural simulation
(FEA) and hosted services are not.

## Developing napkin2factory

This repository is the tool itself. If you want to change it (code, tests, docs), start with
[AGENTS.md](AGENTS.md); it is written for whoever does the work, a person or an agent.

## License

MIT. See [LICENSE](LICENSE).
