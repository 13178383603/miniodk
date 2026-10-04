#!/usr/bin/env python3
"""
miniodk — a minimal ReAct agent that actually runs anywhere.

One loop. No frameworks. No GPU. Works on Windows, Linux and macOS.
Drives local models (Ollama) or any OpenAI-compatible cloud API.

    python miniodk.py "how many python files are in this directory?"

Why: most agent runtimes assume Linux + GPU. This one assumes nothing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

__version__ = "0.1.0"

# ---------------------------------------------------------------- config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
LOCAL_MODEL = os.environ.get("MINIODK_MODEL", "qwen3:1.7b")
DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
DS_BASE = os.environ.get("MINIODK_API_BASE", "https://api.deepseek.com/chat/completions")
DS_MODEL = os.environ.get("MINIODK_API_MODEL", "deepseek-chat")
MAX_STEPS = int(os.environ.get("MINIODK_MAX_STEPS", "8"))
CWD = os.getcwd()

C_GREEN, C_YELLOW, C_CYAN, C_DIM, C_RESET = "\033[32m", "\033[33m", "\033[36m", "\033[2m", "\033[0m"
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    C_GREEN = C_YELLOW = C_CYAN = C_DIM = C_RESET = ""   # legacy conhost


def c(txt: str, color: str) -> str:
    return f"{color}{txt}{C_RESET}"


# ---------------------------------------------------------------- tools
def _win_path(p: str) -> str:
    """Accept MSYS-style paths (/c/foo) on Windows."""
    p = str(p or ".")
    if os.name == "nt":
        for a, b in (("/c/", "C:/"), ("/d/", "D:/"), ("/e/", "E:/"), ("/f/", "F:/")):
            if p.lower().startswith(a):
                return b + p[3:]
    return p


def tool_ls(args):
    path = _win_path(args.get("path", "."))
    try:
        items = sorted(os.listdir(path))
        head = items[:60]
        more = "" if len(items) <= 60 else f" ... (+{len(items)-60} more)"
        return f"{path} has {len(items)} entries: " + ", ".join(head) + more
    except Exception as e:
        return f"ls failed: {e}"


def tool_read(args):
    path = _win_path(args.get("path", ""))
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f"--- {path} ---\n" + f.read(int(args.get("limit", 3000)))
    except Exception as e:
        return f"read failed: {e}"


def tool_write(args):
    path = _win_path(args.get("path", ""))
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(args.get("content", "")))
        return f"wrote {os.path.getsize(path)} bytes to {path}"
    except Exception as e:
        return f"write failed: {e}"


def tool_run(args):
    cmd = str(args.get("cmd", ""))
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=20,
                           cwd=CWD, errors="replace")
        out = ((r.stdout or "") + (r.stderr or "")).strip()[:3000]
        return f"$ {cmd}\n{out}" if out else f"$ {cmd}\n(no output)"
    except Exception as e:
        return f"run failed: {e}"


def tool_calc(args):
    expr = str(args.get("expr", "0"))
    if not re.fullmatch(r"[\d\s+\-*/().%,]+", expr):
        return "calc: only numbers and + - * / ( ) are allowed"
    try:
        return f"{expr} = {eval(expr, {'__builtins__': {}}, {})}"
    except Exception as e:
        return f"calc failed: {e}"


def tool_count(args):
    path = _win_path(args.get("path", "."))
    pat = str(args.get("pattern", "*"))
    try:
        n = len(glob.glob(os.path.join(path, pat), recursive=True))
        return f"{path} matches {pat}: {n} file(s)"
    except Exception as e:
        return f"count failed: {e}"


def tool_search(args):
    """grep-like search across files."""
    path = _win_path(args.get("path", "."))
    needle = str(args.get("text", ""))
    if not needle:
        return "search: 'text' is required"
    hits, scanned = [], 0
    for root, _dirs, files in os.walk(path):
        for fn in files:
            if len(hits) >= 20:
                break
            fp = os.path.join(root, fn)
            try:
                if os.path.getsize(fp) > 2_000_000:
                    continue
                scanned += 1
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if needle.lower() in line.lower():
                            hits.append(f"{fp}:{i}: {line.strip()[:120]}")
                            break
            except Exception:
                continue
    return (f"found {len(hits)} file(s) containing {needle!r}:\n" + "\n".join(hits)
            if hits else f"no match for {needle!r} ({scanned} files scanned)")


TOOLS = {
    "ls":     (tool_ls,     "list a directory",            {"path": "dir"}),
    "read":   (tool_read,   "read a text file",            {"path": "file"}),
    "write":  (tool_write,  "write a file",                {"path": "file", "content": "text"}),
    "run":    (tool_run,    "run a shell command",         {"cmd": "command"}),
    "calc":   (tool_calc,   "evaluate arithmetic",         {"expr": "1+2"}),
    "count":  (tool_count,  "count files by pattern",      {"path": "dir", "pattern": "*.py"}),
    "search": (tool_search, "search text inside files",    {"path": "dir", "text": "needle"}),
}

SYSTEM = """You are a ReAct agent. Solve the task by alternating thought and action.

Reply with EXACTLY ONE JSON object per turn, nothing else.

Action turn:
{"thought": "why I need this", "action": "count", "args": {"path": ".", "pattern": "*.py"}}

Final turn:
{"thought": "I have enough information", "answer": "the final answer"}

Available tools:
__TOOLS__

Rules:
- ONE action per turn.
- Use "answer" as soon as you have what you need. Never invent results.
- Prefer `count` over counting a listing by eye.
- Paths: use forward slashes. os is __OSNAME__.
- Output JSON only - no markdown fences, no prose."""


def build_system() -> str:
    lines = [f"- {name}: {desc}  args={json.dumps(sig)}" for name, (_, desc, sig) in TOOLS.items()]
    return SYSTEM.replace("__TOOLS__", "\n".join(lines)).replace("__OSNAME__", os.name)


# ---------------------------------------------------------------- llm
def _strip_fences(txt: str) -> str:
    t = (txt or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    # some small models wrap the answer in a thinking block
    for mk in ("/thinking", "/think>"):
        if mk in t:
            after = t.split(mk, 1)[1].strip()
            if after:
                t = after
    return t.strip()


def _post(url: str, payload: dict, headers: dict, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ask(messages: list) -> str:
    """Call the configured brain: cloud API when a key exists, else local Ollama."""
    if DS_KEY:
        data = _post(DS_BASE, {"model": DS_MODEL, "messages": messages,
                              "stream": False, "temperature": 0.3},
                     {"Authorization": f"Bearer {DS_KEY}"}, timeout=180)
        return _strip_fences(data["choices"][0]["message"]["content"])

    data = _post(OLLAMA_URL, {"model": LOCAL_MODEL, "messages": messages,
                              "stream": False,
                              "options": {"num_predict": 900, "temperature": 0.4}},
                 {})
    return _strip_fences(data["message"]["content"])


def parse_json(txt: str):
    """Extract the first JSON object, tolerating small-model sloppiness."""
    m = re.search(r"\{[\s\S]*\}", txt or "")
    if not m:
        return None
    raw = m.group(0)
    for candidate in (raw,
                      re.sub(r",\s*([}\]])", r"\1", raw),
                      re.sub(r"(?<=[{,])\s*'([^']*)'\s*:", r'"\1":', raw)):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- loop
def run(task: str, quiet: bool = False) -> str | None:
    print(c(f"\n  task  {task}", C_CYAN))
    print(c("  " + "-" * 60, C_DIM))
    messages = [{"role": "system", "content": build_system()},
                {"role": "user", "content": f"Task: {task}"}]
    started = time.time()

    for step in range(1, MAX_STEPS + 1):
        try:
            reply = ask(messages)
        except Exception as e:
            print(c(f"  [{step}] model error: {e}", C_YELLOW))
            return None

        obj = parse_json(reply)
        if not obj:
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user",
                             "content": "Invalid JSON. Reply with exactly one JSON object."})
            print(c(f"  [{step}] malformed reply, retrying", C_YELLOW))
            continue

        thought = str(obj.get("thought", "")).strip()
        if obj.get("answer"):
            print(c(f"  [{step}] thought  {thought}", C_DIM))
            print(c(f"\n  === answer ===\n  {obj['answer']}", C_GREEN))
            print(c(f"  {step} steps | {time.time()-started:.1f}s | "
                    f"{'cloud' if DS_KEY else 'local'} brain\n", C_DIM))
            return str(obj["answer"])

        action = obj.get("action")
        args = obj.get("args") or {}
        print(c(f"  [{step}] thought  {thought}", C_DIM))
        print(c(f"        action   {action}({json.dumps(args, ensure_ascii=False)[:80]})", C_CYAN))

        if action not in TOOLS:
            obs = f"unknown tool {action!r}. available: {list(TOOLS)}"
        else:
            obs = TOOLS[action][0](args)
        print(c(f"        observe  {obs[:180]}", C_DIM))

        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": f"Observation:\n{obs}\nNext step."})

    print(c(f"  stopped: hit the {MAX_STEPS}-step limit", C_YELLOW))
    return None


def main() -> None:
    p = argparse.ArgumentParser(
        prog="miniodk",
        description="A minimal ReAct agent that runs anywhere (Windows/CPU friendly).")
    p.add_argument("task", nargs="*", help="what you want done")
    p.add_argument("-m", "--model", help="local Ollama model (default qwen3:1.7b)")
    p.add_argument("--api-model", help="cloud model name")
    p.add_argument("--max-steps", type=int, help="step budget (default 8)")
    p.add_argument("-v", "--version", action="version", version=f"miniodk {__version__}")
    a = p.parse_args()

    if a.model:
        globals()["LOCAL_MODEL"] = a.model
    if a.api_model:
        globals()["DS_MODEL"] = a.api_model
    if a.max_steps:
        globals()["MAX_STEPS"] = a.max_steps

    task = " ".join(a.task).strip()
    if not task:
        p.print_help()
        sys.exit(0)

    brain = f"cloud ({DS_MODEL})" if DS_KEY else f"local ({LOCAL_MODEL} @ {OLLAMA_URL})"
    print(c(f"\n  miniodk v{__version__}  |  brain: {brain}  |  cwd: {CWD}", C_DIM))
    run(task)


if __name__ == "__main__":
    main()
