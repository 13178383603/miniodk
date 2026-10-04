# miniodk

**A minimal ReAct agent that actually runs anywhere.**

One loop. No frameworks. No GPU. Works on Windows, Linux, and macOS — including a 2013 dual-core i3.

```bash
python miniodk.py "how many python files are here, and which one is biggest?"
```

```
  [1] thought  I need to count the .py files first
        action   count({"path": ".", "pattern": "*.py"})
        observe  . matches *.py: 1 file(s)
  [2] thought  now check the size
        action   run({"cmd": "ls -la *.py"})
        observe  -rw-r--r-- 1 user 11340 miniodk.py
  [3] thought  I have enough information

  === answer ===
  There is 1 Python file: miniodk.py, 11340 bytes.
  3 steps | 1.9s | cloud brain
```

---

## Why this exists

Most agent runtimes assume two things you may not have:

| Assumption | Reality for a lot of people |
|:-----------|:----------------------------|
| Linux/macOS | Lots of users are on **Windows** |
| GPU or big RAM | A 2013 **dual-core CPU** with 12 GB is still a working computer |

I built this after trying to compile a popular Go agent runtime on Windows and hitting
`syscall.Kill` / `Setpgid` — Unix-only calls that make it **impossible to build on Windows**,
despite the docs claiming Windows support.

`miniodk` is what I wrote instead. It runs on the machine I actually have.

---

## Features

- **ReAct loop in one file** — think → act → observe → repeat, ~300 lines, zero dependencies beyond the stdlib
- **Two brains, same code**
  - Local: any [Ollama](https://ollama.com) model (`qwen3:1.7b`, `llama3.2`, …) — free, private, offline
  - Cloud: any OpenAI-compatible API (DeepSeek, OpenAI, …) — fast, accurate
- **7 built-in tools** — `ls`, `read`, `write`, `run`, `calc`, `count`, `search`
- **Windows-native** — MSYS path handling, ANSI-safe output, no POSIX-only syscalls
- **Sane step budget** — the loop stops on its own; no runaway agents
- **Tolerant JSON parsing** — survives markdown fences, trailing commas, and small-model sloppiness

---

## Install

Nothing to install. Python 3.9+ and the standard library.

```bash
git clone https://github.com/13178383603/miniodk.git
cd miniodk
```

Pick a brain:

```bash
# Local (free, offline) — needs Ollama running
ollama pull qwen3:1.7b

# Cloud (fast, accurate) — any OpenAI-compatible key
export DEEPSEEK_API_KEY=sk-...
```

---

## Usage

```bash
# Cloud brain (auto-detected when a key is present)
python miniodk.py "find every TODO in this repo and summarise them"

# Local brain
python miniodk.py -m qwen3:1.7b "list the 5 largest files here"

# Custom budget / model
python miniodk.py --max-steps 12 --api-model deepseek-chat "refactor notes.md into a changelog"

# Point at any OpenAI-compatible endpoint
export MINIODK_API_BASE=http://localhost:8000/v1/chat/completions
export MINIODK_API_MODEL=my-model
```

### Environment

| Variable | Default | Purpose |
|:---------|:--------|:--------|
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | — | enables the cloud brain |
| `MINIODK_API_BASE` | `https://api.deepseek.com/chat/completions` | any OpenAI-compatible endpoint |
| `MINIODK_API_MODEL` | `deepseek-chat` | cloud model name |
| `MINIODK_MODEL` | `qwen3:1.7b` | local Ollama model |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama endpoint |
| `MINIODK_MAX_STEPS` | `8` | step budget |

---

## How it works

```
        ┌──────────────┐
        │   task       │
        └──────┬───────┘
               ▼
      ┌─────────────────┐
      │  LLM  (think)   │◄──────────────┐
      └────────┬────────┘               │
               ▼                        │
        one JSON object                 │
       ┌────────┴────────┐              │
       ▼                 ▼              │
  {"answer": ...}   {"action": ...}     │
       │                 │              │
       ▼                 ▼              │
    done          run the tool          │
                         │              │
                         ▼              │
                    observation ────────┘
```

Every turn the model returns exactly one JSON object. If it contains `answer`, we stop.
If it contains `action`, we run that tool and feed the observation back. That is the whole design.

---

## Local vs cloud (measured)

Same code, same machine (**i3-4170, dual-core, 12 GB, no GPU**), task: *count the `.py` files in a directory*.

| Brain | Result | Time | Steps |
|:------|:-------|:----:|:-----:|
| `qwen3:1.7b` (local) | ⚠️ called the right tool, but produced an empty final answer | 77 s | 3 |
| `deepseek-chat` (cloud) | ✅ correct answer | **1.9 s** | 3 |

**Takeaway:** the loop is not the bottleneck — the model is. A 1.7 B model can *act* but often
fails to *summarise*. Use a cloud model for final answers when accuracy matters, and a local
model when the data must not leave the machine.

---

## When to use it

| Good fit | Not a good fit |
|:---------|:---------------|
| Quick file/repo exploration from natural language | Long multi-day autonomous projects |
| Teaching or demoing how ReAct actually works | Replacing a full framework (LangGraph, etc.) |
| Air-gapped / privacy-sensitive environments | High-throughput production pipelines |
| Windows machines where most agent tooling refuses to run | Anything that needs GPU-scale inference |

---

## Licence

MIT — do whatever you want.

---

*If this saved you from a framework install, a star helps other people find it.*
