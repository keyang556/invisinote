# Invisible (off-screen) markdown render — design

**Date:** 2026-05-26
**Status:** Approved, ready for implementation planning
**Builds on:** [2026-05-26-render-note-as-markdown-design.md](2026-05-26-render-note-as-markdown-design.md)

## Summary

The existing `NVDA+ALT+Space` command renders the current note to HTML and opens
it in an NVDA browse-mode document via `ui.browseableMessage(..., isHtml=True)`,
giving full native quick-navigation (headings, links, lists, tables). That
document is hosted in a **visible** on-screen window, which conflicts with
Invisinote's premise that every other feature is in-memory and shows nothing on
screen.

This change keeps the rendered document and all native browse-mode keys exactly
as they are today, but **slides its window off the visible desktop the instant
it opens**, so onlookers see nothing beyond — at most — a brief flash. The
screen reader experience (announcements, focus, quick-nav, Escape) is unchanged.

## Why this approach (Mechanism A)

NVDA's browse-mode quick-nav keys (`h`, `1`–`6`, `k`, `l`, `i`, `t`, `x`,
`NVDA+F7`) are single letters that only function while focus is inside a
browse-mode document — that is why Invisinote's own gestures must be
`NVDA+ALT+` combos. There is no NVDA mechanism to make the bare keys work while
focus stays in the host application. So native browsing requires a real,
focusable document window; the only freedom is whether that window is visible.

`ui.browseableMessage` exposes **no window-position argument**, so "off-screen"
must be achieved by relocating the window after NVDA creates it. Two mechanisms
were considered:

- **A — reuse NVDA's window, then move it off-screen.** Chosen. Reuses the exact
  hosting path verified working in live NVDA on 2026-05-26 (browse mode engages,
  all quick-nav keys land, Escape returns focus). Only adds an off-screen move.
- **B — build our own off-screen window hosting a WebView.** Rejected. Discards
  the verified foundation and risks Windows denying keyboard focus to a
  never-visible window, which would silently break all quick-nav. More code, and
  a real chance of having to abandon it.

The one cost of A is a possible brief flash as the window paints centred and
then jumps off-screen. The user is a screen reader user and cannot perceive the
flash; only sighted onlookers might, momentarily.

## Trigger & scope

- No new gesture. `script_render_markdown` (bound to **NVDA+ALT+Space**) keeps
  its current behaviour; only the windowing is changed.
- Still a one-shot command operating on the current note. It does **not** mutate
  navigation state (note/line/word/char index, selection anchors) and adds no
  persistent setting or toggle.
- The empty-note and render-unavailable paths are **untouched** — they speak via
  `ui.message` and open no window, so there is nothing to move.

## Interaction flow & what gets announced

Identical to the verified current behaviour, minus on-screen visibility:

- `NVDA+ALT+Space` → the note renders → the browse-mode window opens **off the
  visible desktop** → focus moves into it.
- **First announced on arrival:** the dialog title (the note's filename), then
  the top of the document in browse mode.
- Quick-nav as in any web document: `h` / `1`–`6` headings, `k` links, `l`
  lists, `i` list items, `t` tables, `x` blockquotes, arrows by line, `NVDA+F7`
  Elements List.
- **Escape** closes the window and returns focus to the application the user was
  in. Standard NVDA behaviour; nothing custom.

## How the off-screen move works

1. **Snapshot before.** Immediately before rendering, capture the set of
   top-level window handles (`win32gui.EnumWindows`).
2. **Arm a timer, then render.** Schedule a `wx.CallLater(delay, ...)` *before*
   calling `ui.browseableMessage(...)`. `browseableMessage` may block in a modal
   message loop until Escape; the wx timer fires inside that loop (it is
   dispatched by the same Win32 message pump). If `browseableMessage` instead
   returns immediately, the timer still fires normally afterward. Either way is
   covered.
3. **Diff to find the new window.** When the timer fires, re-snapshot top-level
   windows and compute `after − before`. Filter to windows that are (a) owned by
   our own process (`GetWindowThreadProcessId` == our PID), and (b) visible.
   Among the survivors, choose the one whose title matches the note filename; if
   exactly one new window remains, choose it regardless. This snapshot-diff is
   **renderer-agnostic** — it works whether NVDA hosts the document in MSHTML or
   EdgeWebView2 (per `message.html` the install supports both).
4. **Move, never hide.** Relocate the chosen window with
   `win32gui.SetWindowPos` to off-screen coordinates (e.g. far-negative), using
   `SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE` so focus and z-order are
   undisturbed. The window is deliberately **not** hidden (`SW_HIDE`) — a hidden
   window loses focus, and no focus means no browse mode.
5. **Retry briefly, then fall back.** If no new window is found yet, re-arm the
   timer a few times up to a short deadline (~1 second total). If the window
   never appears, or any step raises, **do nothing** — the window stays visible.
   Worst case equals today's behaviour; never worse.

### Robustness & isolation

- The window-selection logic is factored into a **pure function** —
  `(before: set[int], after: set[int], pid: int, title: str) -> int | None` —
  with no win32 calls, so it is unit-testable off-NVDA. The win32 enumeration,
  PID/visibility filtering, and the move are thin wrappers around it.
- All win32 interaction is guarded by `try/except` with `logHandler.log`,
  matching the existing guarded style (e.g. the markdown-conversion guard). The
  gesture must never throw into NVDA.
- `win32gui` / `win32api` ship with NVDA (present in the install). The import is
  guarded; if unavailable, the move is skipped and the window stays visible.

## Open items (resolved during the Phase 0 spike)

- **Taskbar / Alt-Tab entry.** Whether to strip it via `WS_EX_TOOLWINDOW`.
  Decide from the spike; default to leaving it unless it proves to leak.
- **Flash duration.** Measured in the spike. If unacceptable, options are a
  smaller initial timer delay, or accepting the flash. Not expected to be a
  blocker since the user cannot perceive it.

## Testing

- **Phase 0 spike (manual, in NVDA) — gate before building the full feature.**
  Confirm: the render window is found and moved off-screen; quick-nav still works
  after the move; Escape still closes it and returns focus to the host app;
  gauge the flash; check for a lingering taskbar entry.
- **Host-side unit test (off-NVDA).** The pure window-selection function:
  - returns the single new handle when one window appears;
  - prefers the title-matching handle when several new windows appear;
  - returns `None` when no new window appears (drives the visible fallback).
- **Regression (manual, in NVDA).** Empty-note still speaks "Empty note" with no
  window; render-unavailable still speaks its message with no window; the
  rendered content and all quick-nav keys behave as in the 2026-05-26
  verification.

## Docs, strings, version

- Any new user-visible strings wrapped in `_()` (NVDA provides the builtin;
  never imported). This change is not expected to add user-facing strings.
- Update wording to note the render now browses **invisibly / off-screen**:
  - the gesture line in `buildVars.py` (`addon_description`), and
  - `readme.md` / `addon/doc` readme.
- **Version bump** (`1.6` → `1.7`) stays deferred to **release time** per the
  existing release checklist, not part of this change.
