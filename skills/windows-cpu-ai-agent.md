# Running an AI Agent on a Windows CPU box

Everything here was learned the hard way on a **2013 dual-core i3 with 12 GB of RAM and no GPU**.
If you have a better machine, you can skip most of it — but you probably know someone who doesn't.

---

## 1. Pick the right engine, not a bigger machine

The single biggest win is not more RAM. It is picking a runtime that fits the hardware.

Real measurement from this machine, same model, same 15-second output:

| Engine | Time | Verdict |
|:-------|:-----|:--------|
| PyTorch (eager, float32, 2 B params) | **3.4 hours, never finished** | unusable |
| GGML / C++ quantised (Q4_K_M) | **117 seconds** | usable |

**A 100× speedup with zero new hardware.** When something "doesn't run", look for a
quantised or GGML-based implementation before you look for a new computer.

## 2. Serve local models with Ollama

```bash
ollama pull qwen3:1.7b        # ~1.4 GB, the sweet spot for a CPU box
ollama pull deepseek-r1:1.5b  # reasoning, but tiny models reason poorly
ollama pull gemma3:1b         # fastest, weakest
```

Check it is alive:

```bash
curl -s http://localhost:11434/api/tags | head -c 200
```

**Windows gotcha:** if a system-wide proxy is configured, `localhost` requests may be sent
through it and fail. Always exclude loopback:

```bash
export no_proxy=localhost,127.0.0.1
export NO_PROXY=localhost,127.0.0.1
```

## 3. Know what a 1.7 B model can and cannot do

Measured on this box, same task, same prompt:

| Ability | 1.7 B local | cloud model |
|:--------|:-----------:|:-----------:|
| Choosing the right tool | ✅ | ✅ |
| Producing valid JSON | ⚠️ often breaks | ✅ |
| Summarising into a final answer | ❌ returns placeholders | ✅ |
| Latency | 40–170 s | 2 s |

**Practical rule: let the small model act, let a big model conclude.**
Or keep everything local and accept that the final paragraph may need a human.

## 4. Give models tools, not shell-quoting problems

A 1.7 B model asked to run `dir /b *.py | find /c /v ""` will break its own JSON, because
the nested quotes need escaping it cannot handle reliably.

Do not fix this with prompt engineering. **Give it a tool that needs no quoting:**

```python
def tool_count(args):
    import glob, os
    n = len(glob.glob(os.path.join(args.get("path", "."), args.get("pattern", "*"))))
    return f"{n} file(s)"
```

Tool calls went from failing every turn to succeeding on the first try.

## 5. Truncating tool output silently corrupts answers

Early version capped shell output at 700 characters. The agent saw a partial file listing,
counted 17 files instead of 22, and reported 17 confidently.

**An agent is only as correct as its observations.** Cap output — but cap it generously
(3000+ characters), and prefer tools that return aggregates over raw listings.

## 6. Paths: accept both worlds

Models happily emit MSYS-style paths on Windows (`/e/wei`), which Python will not open.
Normalise at the tool boundary:

```python
def _win_path(p: str) -> str:
    if os.name == "nt":
        for a, b in (("/c/", "C:/"), ("/d/", "D:/"), ("/e/", "E:/"), ("/f/", "F:/")):
            if p.lower().startswith(a):
                return b + p[3:]
    return p
```

## 7. The Go-runtime trap

Some popular agent runtimes advertise Windows support and **cannot compile on Windows**:

```
internal\bgproc\bgproc.go:448: undefined: syscall.Kill
internal\bgproc\bgproc.go:301: unknown field Setpgid in struct.syscall.SysProcAttr
internal\events\jsonl.go:68:  undefined: syscall.O_NOFOLLOW
```

`Setpgid`, `syscall.Kill` and `O_NOFOLLOW` are Unix-only. Docs saying "build from source"
do not mean "builds on Windows".

**Before installing any Go/Rust agent tool, check the source for platform-specific syscalls.**
Or use something that never needed them — like the pure-Python loop in this repository.

## 8. Keep the environment alive

Anything that must start cold costs you seconds every single run. Measured cost of opening
a URL with a cold browser and a dead helper daemon: **132 seconds**, of which **10 seconds**
was the actual work.

Warm the pieces and the same task took **17 seconds**. See `desk_keepalive.py` in this repo
for the pattern: check → heal → warm, run on a schedule.

---

## Summary

| Problem | Do this instead |
|:--------|:----------------|
| Model won't run | Find a GGML/quantised build, don't buy hardware |
| Small model talks nonsense | Give it tools + aggregates; let it act, not conclude |
| JSON breaks | Add purpose-built tools, avoid shell quoting |
| Wrong answers | Check your output truncation — observations matter |
| Won't compile | Grep the source for Unix syscalls first |
| Everything is slow | Pre-warm services; measure where time actually goes |
