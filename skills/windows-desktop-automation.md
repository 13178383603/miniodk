# Driving the Windows desktop from an agent

Notes from automating real applications — a browser, a chat app, a media player — on Windows 10,
without stealing the user's mouse and keyboard.

---

## The control stack

| Layer | What it gives you | When to use it |
|:------|:------------------|:---------------|
| **Launch** | Start an app, get its pid/window | Always first |
| **Accessibility tree** | Real element handles + bounds | Native Win32/WPF/UIA apps |
| **Coordinates** | Click anywhere by pixel | Electron/Chromium apps that publish no useful AX nodes |
| **Keyboard** | Text and hotkeys | Text input, shortcuts |
| **Screenshot + vision** | Verify what actually happened | After every state-changing action |

## 1. Launch, don't double-click

Doubling an icon through the desktop shell often yields **zero discoverable elements**. Point the
launcher at the shortcut or executable instead:

```
launch(path=r"C:\Users\...\Desktop\App.lnk")   -> pid, window id
```

Shortcuts (`.lnk`) work fine as the target.

## 2. Chromium apps reject background input

Chat apps and browsers are Chromium (`Chrome_WidgetWin_1`). Background input is refused:

```
Background delivery is not available for target window class 'Chrome_WidgetWin_1'
→ re-call with delivery_mode="foreground"
```

This is not a bug to work around — escalate to foreground input for these apps. It briefly raises
the window; that is the price of typing into Chromium.

**Native apps (Win32/WPF/UIA) accept background input**, so keep background as the default and
escalate only when the driver says so.

## 3. Some apps hide to the tray after any operation

A media/chat app may vanish from the window list right after a click. It is not gone — it went to
the tray.

**Fix: call launch again.** It is usually single-instance and will re-show the existing window.
**Do not kill the process** — you will lose the user's conversation or session.

## 4. Verify with a screenshot, not with hope

Every action returns `effect: unverifiable` until you look. Reading the screen back is also how you
read a chat app's answer:

```
capture(app="App.exe", mode="vision", question="what does the input box contain?")
```

For a long answer, scroll and re-capture. Reading a 50-item reply took several scroll+capture cycles —
budget for it.

## 5. Focus is fragile: click the field, don't trust a shortcut alone

`Ctrl+L` to focus a browser address bar *usually* works. When it silently fails, the typed text goes
nowhere and the page never changes.

**Click the address bar element first, then type.** Belt and braces:

```
click(element=address_bar)     # focus
type("example.com")            # foreground
key("return")
capture(...)                   # confirm the URL actually changed
```

Never assume a keystroke landed. Confirm with a fresh capture.

## 6. Measure where the time actually goes

Real measurements from opening a URL on this machine:

| Step | Cold | Warm |
|:-----|:----:|:----:|
| Start browser | 30 s | 0 s |
| "Restore pages" dialog blocks everything | 30 s | 0 s |
| Helper daemon had crashed and needed restart | 60 s | 0 s |
| Click address bar | 5 s | 2 s |
| Type URL + Enter | 5 s | 3 s |
| Page loads | 5 s | 5 s |
| **Total** | **132 s** | **17 s** |

**The actual work was 10 seconds. The other 122 were environmental.**

Fix the environment, not your clicking speed:
- keep the browser resident (skip 30 s cold start),
- keep the helper daemon alive (skip 60 s recovery),
- pass flags that suppress first-run/restore dialogs (skip 30 s of blockers).

## 7. Health-check the driver before blaming the app

If captures start failing with empty results, check the helper daemon before touching the target app:

```
"daemon is not running on \\.\pipe\..."
```

Register it to start at logon, and make your own check-heal-warm routine part of the workflow.

## 8. Windows gotchas worth remembering

- **`tasklist` for truth.** Wrap it once: `sum(1 for l in output.splitlines() if kw.lower() in l.lower())`.
- **Proxies break loopback.** A system proxy will happily swallow `http://localhost:11434`. Always
  export `no_proxy=localhost,127.0.0.1`.
- **Path translation.** Tool arguments written by a model are often POSIX-style; normalise before use.
- **System proxy can point at a dead port.** Registry `ProxyServer` said `127.0.0.1:7890` while the
  proxy actually listened on `7897` — so every request failed, including to domestic sites. Compare
  the registry value against `netstat` before debugging anything else.

---

## Checklist before automating a desktop task

1. Target is a full path (`.lnk` or `.exe`), not an icon.
2. Helper daemon is running; if not, start it.
3. App is already warm if it is slow to start.
4. Background first; escalate to foreground only on refusal.
5. Click the input field; do not trust shortcuts alone.
6. Capture after every mutation to confirm.
7. Log the elapsed time — and fix the environment, not the clicking.
