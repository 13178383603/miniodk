# A self-reflection loop that actually improves output

Make a model grade its own work, then fix it — with no API cost when you run it locally.

Based on the Reflexion pattern: **generate → critique → revise → critique → … → done.**

---

## The whole idea

```
        ┌──────────┐
        │  draft   │
        └────┬─────┘
             ▼
   ┌──────────────────┐
   │  critic  (1-10)  │──────────────┐
   └────────┬─────────┘              │
            ▼                        │
      score >= 8 ?                   │
       │        │                    │
      yes       no                   │
       │        ▼                    │
       │   ┌──────────┐              │
       │   │  revise  │──────────────┘
       │   └──────────┘
       ▼
    finished
```

Two prompts do all the work:

```python
CRITIC = """You are a harsh reviewer. Judge only, do not flatter.
Task: {task}

Content under review:
{draft}

Analyse briefly, then reply in exactly this format:
SCORE: <integer 1-10>
FEEDBACK: <concrete, actionable improvements>"""

REVISER = """Revise the content using the review.
Task: {task}

Current version:
{draft}

Review:
{critique}

Output the complete revised content only. No explanation, no thinking, no preamble."""
```

## Measured result (i3-4170 dual-core, qwen3:1.7b, zero API cost)

Task: *write a heat-safety reminder for construction workers.*

| Round | Score | What the model said about itself |
|:-----:|:-----:|:---------------------------------|
| draft | — | 5 bullet points, ~180 characters |
| 1 | **7/10** | "covers the points, but the wording is long-winded" |
| revised | — | cut to 49 characters |
| 2 | **7/10** | "missing key protections (sun index, ventilation, heat alerts)" |
| **final** | | one actionable sentence, 68 characters |
| runtime | | ~40–55 s per call, ~3–4 min total |

The loop works. The writing does not always follow the advice — see the limits below.

## Seven things that will bite you

1. **Give the model enough output tokens.** With `num_predict=300` the whole budget went into
   the model's internal reasoning and the visible answer came back **empty**. 800–900 works.

2. **Never strip a reasoning block blindly.**
   `re.sub(r"thinking.*?/thinking", "", text)` deletes the answer, because small models often
   put the answer *inside* the block. Strip conservatively and fall back to the original:

   ```python
   for marker in ("/thinking", "/think>"):
       if marker in text:
           after = text.split(marker, 1)[1].strip()
           if after:
               text = after
   ```

3. **Ask for `/no_think` when revising.** It raises the success rate of getting a clean,
   directly-usable revision.

4. **A 1.7 B model is a better critic than a rewriter.** Its scores and suggestions were
   accurate in every run; its rewrites frequently ignored the feedback.

5. **Scores are not monotonic.** `7 → 7` happened. Treat the score as a *direction*, not a
   measurement.

6. **Parse defensively.** Models emit `**SCORE:** 7` with markdown. Your regex needs
   `[:：*]*`.

7. **Cap the rounds.** Small models can argue with themselves forever. Two rounds is plenty.

## When this is worth it

| Use it | Skip it |
|:-------|:--------|
| Repetitive text: notices, summaries, alerts | Anything needing factual accuracy |
| Polishing local small-model output | Long-form writing (time cost explodes) |
| Batch quality gates on generated content | Interactive, latency-sensitive flows |
| Sanity-checking prompts and rules | Sub-second requirement |

## Where it belongs in a bigger system

Chain it after generation, before delivery. In this repository's sibling project the loop is
wired in as `reflector.py`, sitting between `miniodk`'s generator and its final answer — so
every answer is criticised once before a human sees it.
