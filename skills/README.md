# Skills / playbooks

Not library code — **field notes**. Each file is a procedure that was actually executed on a
dual-core i3 with 12 GB of RAM, including the parts that failed and what they cost.

Use them when you are about to repeat the same painful setup.

| Playbook | Use it when |
|:---------|:------------|
| [windows-cpu-ai-agent.md](windows-cpu-ai-agent.md) | You want to run models or agents on a Windows box without a GPU |
| [self-reflection-loop.md](self-reflection-loop.md) | You want a model to grade and improve its own output for free |
| [windows-desktop-automation.md](windows-desktop-automation.md) | You need to drive real applications (browser, chat app) from an agent |

## Why these exist

Most agent documentation is written by people with a GPU, a Linux box, and a fast connection.
Every note here assumes the opposite: no GPU, Windows, an unreliable network, and a machine old
enough to have shipped with DDR3.

Each playbook ends with the pitfall list, because the pitfalls are the content. The happy path
takes five minutes; the thirty minutes you lose to a restore-tab dialog and a dead helper daemon
is what nobody writes down.

## The pattern behind the writing

Every entry follows the same shape:

1. **What was measured** — real numbers, real machine, real task.
2. **What broke** — with the actual error text.
3. **What fixed it** — minimal, runnable.
4. **What it costs** — latency, tokens, or wall-clock time.

If a number is in these files, it came from a run, not from an estimate.
