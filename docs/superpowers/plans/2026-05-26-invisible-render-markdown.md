# Invisible (off-screen) markdown render — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `NVDA+ALT+Space` render the current note into NVDA's browse-mode document exactly as today, but slide that document's window off the visible desktop so onlookers see nothing while the screen-reader user keeps full native quick-nav.

**Architecture:** Keep the verified `ui.browseableMessage(..., isHtml=True)` path untouched. Immediately before rendering, snapshot all top-level windows; arm a `wx.CallLater` that (during `browseableMessage`'s modal loop) re-snapshots, finds the newly-opened window by a before/after diff filtered to our own process, and relocates it off-screen with `SetWindowPos` — **moving, never hiding**, because a hidden window loses focus and loses browse mode. If the window can't be found/moved within ~1s, it's left visible (never worse than today). All window logic lives in a new stdlib-only `ctypes` module so the selection rule is unit-testable off-NVDA.

**Tech Stack:** Python 3.11+/3.13 (NVDA's interpreter), `ctypes` → `user32.dll`, `wx` (NVDA-bundled), NVDA `ui`/`scriptHandler`/`logHandler`, vendored Python-Markdown (already present). Tests use stdlib `unittest`.

---

## Context an implementer needs

- The add-on's logic is in one file: `addon/globalPlugins/invisinote/__init__.py`. The plugin directory is a Python package (it has `__init__.py`), so `from . import _window` works at runtime in NVDA.
- Code style: **tabs** for indentation, max line length **110**. `_()` is a builtin NVDA injects for translation — never import it.
- The repo runs `ruff` via **pre-commit**, so every commit must be lint-clean. Two rules bite here: `F401` (unused import) and `E402` (module-level import not at top of file). Keep imports at the top of each file and don't commit a file whose imports aren't yet used.
- This NVDA build is **64-bit** (Python 3.13). Window handles are pointer-sized, so every `ctypes` call that takes/returns an `HWND` MUST declare `argtypes`/`restype` with `wintypes.HWND` (a `c_void_p`). Passing handles to a function without declared `argtypes` truncates them to 32 bits and fails silently.
- `ui.browseableMessage(html, title=..., isHtml=True)` opens a browse-mode document window hosted (per the install's `message.html`) in either MSHTML or EdgeWebView2. The host window is in NVDA's own process regardless. The before/after snapshot diff is therefore renderer-agnostic.
- A manual test note `render-test.txt` (headings, link, lists, blockquote, fenced code, table) already exists in both watched notes folders: `%APPDATA%\nvda\invisinote\notes` and `%APPDATA%\nvda\scratchpad\invisinote\notes`.
- Branch is already `feat/invisible-render-markdown`. Commit there.

## File structure

- **Create** `addon/globalPlugins/invisinote/_window.py` — stdlib-only. `ctypes`/`user32` wrappers for enumerating, inspecting, and moving top-level windows, plus the pure window-selection rule. No NVDA imports.
- **Create** `tests/test_window_select.py` — `unittest` cases for the pure selection rule. Runs off-NVDA on any platform.
- **Modify** `addon/globalPlugins/invisinote/__init__.py` — add `import time` and `from . import _window`; add three timing constants; add the `_hide_render_window` orchestration method; modify `script_render_markdown` to snapshot + arm the mover + render.
- **Modify** `buildVars.py` and `readme.md` — note the render now browses off-screen/invisibly.

---

## Task 1: Window module — pure selection rule (TDD) + ctypes helpers

**Files:**
- Create: `addon/globalPlugins/invisinote/_window.py`
- Test: `tests/test_window_select.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_window_select.py` (use tabs):

```python
import os
import sys
import unittest

_MOD_DIR = os.path.abspath(
	os.path.join(os.path.dirname(__file__), "..", "addon", "globalPlugins", "invisinote")
)
if _MOD_DIR not in sys.path:
	sys.path.insert(0, _MOD_DIR)

import _window  # noqa: E402


class SelectRenderWindowTests(unittest.TestCase):
	def test_single_new_visible_window_is_selected(self):
		before = {10, 20, 30}
		after = [10, 20, 30, 99]
		metadata = {99: (True, "note.txt")}
		self.assertEqual(_window.select_render_window(before, after, metadata, "note.txt"), 99)

	def test_title_match_wins_when_several_new_windows(self):
		before = {1}
		after = [1, 2, 3]
		metadata = {2: (True, "other"), 3: (True, "note.txt")}
		self.assertEqual(_window.select_render_window(before, after, metadata, "note.txt"), 3)

	def test_no_title_match_and_multiple_candidates_returns_none(self):
		before = {1}
		after = [1, 2, 3]
		metadata = {2: (True, "a"), 3: (True, "b")}
		self.assertIsNone(_window.select_render_window(before, after, metadata, "note.txt"))

	def test_other_process_window_is_ignored(self):
		before = {1}
		after = [1, 42]
		metadata = {}  # 42 belongs to another process -> absent from metadata
		self.assertIsNone(_window.select_render_window(before, after, metadata, "note.txt"))

	def test_invisible_window_is_ignored(self):
		before = {1}
		after = [1, 7]
		metadata = {7: (False, "note.txt")}
		self.assertIsNone(_window.select_render_window(before, after, metadata, "note.txt"))

	def test_no_new_windows_returns_none(self):
		before = {1, 2}
		after = [1, 2]
		self.assertIsNone(_window.select_render_window(before, after, {}, "note.txt"))


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python tests\test_window_select.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_window'` (the module doesn't exist yet).

- [ ] **Step 3: Create the complete `_window.py`**

Create `addon/globalPlugins/invisinote/_window.py` (use tabs). Imports at the top (so `E402` is satisfied) and every import is used (so `F401` is satisfied):

```python
"""Top-level window discovery and relocation for the off-screen markdown render.

No NVDA imports: only the standard library + user32.dll. The selection rule is
pure, and ctypes.windll is touched lazily, so this module imports and the rule
unit-tests off-NVDA on any platform.
"""

import ctypes
from ctypes import wintypes

_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_OFFSCREEN_X = -32000
_OFFSCREEN_Y = -32000

_user32 = None
_WNDENUMPROC = None


def _u32():
	"""Lazily resolve user32 with explicit 64-bit-safe prototypes.

	Deferred so merely importing this module (e.g. in off-NVDA unit tests on a
	non-Windows box) never touches ctypes.windll or ctypes.WINFUNCTYPE, both of
	which are Windows-only.
	"""
	global _user32, _WNDENUMPROC
	if _user32 is not None:
		return _user32
	_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
	u = ctypes.windll.user32
	u.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
	u.EnumWindows.restype = wintypes.BOOL
	u.IsWindowVisible.argtypes = (wintypes.HWND,)
	u.IsWindowVisible.restype = wintypes.BOOL
	u.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
	u.GetWindowTextLengthW.restype = ctypes.c_int
	u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
	u.GetWindowTextW.restype = ctypes.c_int
	u.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
	u.GetWindowThreadProcessId.restype = wintypes.DWORD
	u.SetWindowPos.argtypes = (
		wintypes.HWND,
		wintypes.HWND,
		ctypes.c_int,
		ctypes.c_int,
		ctypes.c_int,
		ctypes.c_int,
		wintypes.UINT,
	)
	u.SetWindowPos.restype = wintypes.BOOL
	_user32 = u
	return _user32


def enum_top_level_windows():
	"""Return a list of all top-level window handles (ints)."""
	u = _u32()
	handles = []

	@_WNDENUMPROC
	def _cb(hwnd, _lparam):
		handles.append(int(hwnd))
		return True

	u.EnumWindows(_cb, 0)
	return handles


def is_window_visible(hwnd):
	return bool(_u32().IsWindowVisible(hwnd))


def window_title(hwnd):
	u = _u32()
	length = u.GetWindowTextLengthW(hwnd)
	if length <= 0:
		return ""
	buf = ctypes.create_unicode_buffer(length + 1)
	u.GetWindowTextW(hwnd, buf, length + 1)
	return buf.value


def window_pid(hwnd):
	pid = wintypes.DWORD()
	_u32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
	return pid.value


def move_window_offscreen(hwnd):
	_u32().SetWindowPos(
		hwnd, 0, _OFFSCREEN_X, _OFFSCREEN_Y, 0, 0, _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE
	)


def collect_candidate_metadata(handles, exclude, our_pid):
	"""Return {hwnd: (is_visible, title)} for handles not in `exclude` that
	belong to `our_pid`. Builds the `metadata` arg for select_render_window."""
	exclude_set = set(exclude)
	meta = {}
	for h in handles:
		if h in exclude_set:
			continue
		if window_pid(h) != our_pid:
			continue
		meta[h] = (is_window_visible(h), window_title(h))
	return meta


def select_render_window(before, after, metadata, expected_title):
	"""Pick the window opened by the render out of a before/after snapshot.

	`before`, `after`: iterables of top-level window handles (ints) captured
		immediately before and after rendering.
	`metadata`: dict mapping handle -> (is_visible: bool, title: str). It should
		contain only handles belonging to our own process; handles missing from
		it are ignored (treated as another process's windows).
	`expected_title`: the dialog title we asked NVDA to use (the note filename).

	Returns the chosen handle, or None when the choice is ambiguous or nothing
	new appeared (the caller then leaves the window visible as a safe fallback).
	"""
	before_set = set(before)
	candidates = [h for h in after if h not in before_set and h in metadata and metadata[h][0]]
	titled = [h for h in candidates if metadata[h][1] == expected_title]
	if titled:
		return titled[0]
	if len(candidates) == 1:
		return candidates[0]
	return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python tests\test_window_select.py -v`
Expected: PASS — all 6 tests OK. (The test only calls the pure `select_render_window`; the ctypes helpers are defined but not exercised here.)

- [ ] **Step 5: Off-NVDA smoke check of the real win32 helpers (read-only)**

Run (Windows, from repo root — works in any Python session because it only uses user32):

```bash
python -c "import sys; sys.path.insert(0,'addon/globalPlugins/invisinote'); import _window, os; ws=_window.enum_top_level_windows(); titled=[(h,_window.window_title(h)) for h in ws if _window.window_title(h)]; print('total windows:', len(ws)); print('first titles:', [t for _,t in titled[:5]]); print('our pid windows:', sum(1 for h in ws if _window.window_pid(h)==os.getpid()))"
```

Expected: `total windows:` is a number > 0; `first titles:` lists a few real window titles (proving 64-bit handles marshal correctly); `our pid windows:` prints a number without error. This is read-only — it moves nothing.

- [ ] **Step 6: Lint**

Run: `ruff check addon/globalPlugins/invisinote/_window.py tests/test_window_select.py` then `ruff format addon/globalPlugins/invisinote/_window.py tests/test_window_select.py`
Expected: no errors (re-run `ruff check` after formatting until clean).

- [ ] **Step 7: Commit**

```bash
git add addon/globalPlugins/invisinote/_window.py tests/test_window_select.py
git commit -m "feat: add window-finding/move helpers and render-window selection rule"
```

---

## Task 2: Wire the off-screen move into the render script

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py` (imports near lines 1-21; `script_render_markdown` at lines 321-332)

- [ ] **Step 1: Add the `time` and `_window` imports**

Both imports MUST go in the top import block, not after the `sys.path` vendor block — a module-level import after executable code trips `E402`. `_window` is stdlib-only and does not need the vendor path, so this is safe.

In `addon/globalPlugins/invisinote/__init__.py`, find:

```python
import re
import os
import sys
```

Replace with:

```python
import re
import os
import sys
import time
```

Then find the last import line:

```python
from logHandler import log
```

Replace with:

```python
from logHandler import log

from . import _window
```

- [ ] **Step 2: Add the timing constants**

Find the end of the vendored-markdown block:

```python
_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vendor")
if _VENDOR_DIR not in sys.path:
	sys.path.insert(0, _VENDOR_DIR)
```

Add directly below it:

```python

# Off-screen relocation timing for the markdown render window.
_RENDER_HIDE_DELAY_MS = 30
_RENDER_HIDE_RETRY_MS = 50
_RENDER_HIDE_TIMEOUT_S = 1.0
```

- [ ] **Step 3: Add the `_hide_render_window` orchestration method**

In `__init__.py`, the `_render_markdown` method ends with `return None` inside its `except Exception:` block (currently line 319), followed by a blank line, then `@script(description=_("Render note as markdown"))` (line 321). Insert this method between them (use tabs; it is a method of `GlobalPlugin`, so one tab of indentation):

```python
	def _hide_render_window(self, before, expected_title, our_pid, deadline):
		try:
			after = _window.enum_top_level_windows()
			metadata = _window.collect_candidate_metadata(after, before, our_pid)
			hwnd = _window.select_render_window(before, after, metadata, expected_title)
			if hwnd:
				_window.move_window_offscreen(hwnd)
				return
			if time.time() < deadline:
				wx.CallLater(
					_RENDER_HIDE_RETRY_MS,
					self._hide_render_window,
					before,
					expected_title,
					our_pid,
					deadline,
				)
		except Exception:
			log.exception("invisinote: could not move render window off-screen; leaving it visible")
```

- [ ] **Step 4: Modify `script_render_markdown` to snapshot, arm the mover, then render**

Find (currently lines 321-332):

```python
	@script(description=_("Render note as markdown"))
	def script_render_markdown(self, gesture):
		content = self._get_current_note_content()
		if not content:
			ui.message(_("Empty note"))
			return
		html = self._render_markdown(content)
		if html is None:
			ui.message(_("Markdown rendering unavailable"))
			return
		title = os.path.basename(self.notes[self.currentNoteIndex])
		ui.browseableMessage(html, title=title, isHtml=True)
```

Replace with:

```python
	@script(description=_("Render note as markdown"))
	def script_render_markdown(self, gesture):
		content = self._get_current_note_content()
		if not content:
			ui.message(_("Empty note"))
			return
		html = self._render_markdown(content)
		if html is None:
			ui.message(_("Markdown rendering unavailable"))
			return
		title = os.path.basename(self.notes[self.currentNoteIndex])
		# Snapshot windows, then arm a timer that finds the about-to-open
		# browse-mode window and slides it off-screen. browseableMessage may
		# block in a modal loop until Escape; the wx timer fires inside it.
		try:
			before = set(_window.enum_top_level_windows())
			deadline = time.time() + _RENDER_HIDE_TIMEOUT_S
			wx.CallLater(
				_RENDER_HIDE_DELAY_MS,
				self._hide_render_window,
				before,
				title,
				os.getpid(),
				deadline,
			)
		except Exception:
			log.exception("invisinote: could not arm off-screen mover; render window will be visible")
		ui.browseableMessage(html, title=title, isHtml=True)
```

- [ ] **Step 5: Lint**

Run: `ruff check addon/globalPlugins/invisinote/__init__.py` then `ruff format addon/globalPlugins/invisinote/__init__.py`
Expected: no errors. If ruff reorders the `from . import _window` import, accept its ordering and re-run until clean.

- [ ] **Step 6: Confirm the package still builds**

Run: `scons`
Expected: builds `invisinote-1.6.nvda-addon` with no error (confirms packaging/import-time syntax; runtime behaviour is verified in Task 3).

- [ ] **Step 7: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: slide the markdown render window off-screen after it opens"
```

---

## Task 3: Phase 0 manual NVDA spike — GATE before docs

This is a manual verification in live NVDA. **Do not proceed to Task 5 until rows A–F pass.** If the move fails or quick-nav breaks, stop and debug (see "If it fails"). The visible-window fallback means a failure here is no worse than today's behaviour, but the feature isn't done until the move works.

- [ ] **Step 1: Load the new build into NVDA**

First set NVDA log level to **Debug** (Settings → General) so the diagnostic lines used to verify row D are captured.

Either: run `scons -c && scons` (plain `scons` can report "up to date" and skip a source change here, shipping a stale package), install `invisinote-1.6.nvda-addon` via NVDA's Add-ons store ("Install from external source"), restart NVDA.
Or (dev): copy `addon\globalPlugins\invisinote` into `%APPDATA%\nvda\scratchpad\globalPlugins\`, enable **Allow custom code (developer scratchpad)** in NVDA → Settings → Advanced, restart NVDA. (The scratchpad route copies source directly, sidestepping the scons staleness.)

- [ ] **Step 2: Stage and render**

1. Open Notepad, type a few characters, leave the caret there.
2. `NVDA+ALT+N` to load notes; `NVDA+ALT+O` / `NVDA+ALT+U` to reach **render-test.txt**.
3. Press `NVDA+ALT+Space`.

- [ ] **Step 3: Verify the checklist and record findings**

Rows A, B, C, F are verifiable non-visually (audio / focus / log / Alt-Tab). Row D is verified by reading the NVDA log. Row E (flash) is visual and onlooker-only — not user-verifiable and does NOT gate.

| Row | Check | How to verify non-visually | Pass condition |
|-----|-------|----------------------------|----------------|
| A | Browse mode engages | Listen on render | Announces the filename title then the document top; browse mode active |
| B | Quick-nav after the move | Press `h`/`1`-`6`/`k`/`l`/`i`/`t`/`x` and `NVDA+F7` | All behave as in the pre-change verification |
| C | Escape returns focus | Press `Escape` | Doc closes; focus back in Notepad, you can type |
| D | Off-screen (not visible) | Read the NVDA log (`NVDA+F1`) | An `invisinote: render window ... rect after move:` line shows coords near `(-32000, -32000, ...)` |
| F | Taskbar / Alt-Tab | `Alt+Tab` through windows; navigate the taskbar | The render window does NOT appear in the switcher/taskbar (note if it does) |
| E | Flash (visual, onlooker-only) | Not user-verifiable — skip | Informational only; does not gate. A sighted glance can confirm if ever needed |

The log also emits a `rect before move:` line (an on-screen position); the before→after pair is the evidence the right window was found and relocated. Row F decides whether Task 4 is needed.

**If it fails:**
- Quick-nav dead / no announcement (A or B fails) → the window was moved but lost focus, or the wrong window was moved. Open the NVDA log viewer (`NVDA+F1`) and search for `invisinote:` messages (set NVDA log level to Debug to capture the timeout line). Confirm `move_window_offscreen` uses `SWP_NOACTIVATE` (it must not change activation). Temporarily raise `_RENDER_HIDE_DELAY_MS` to `100` in case the window wasn't created yet at the first attempt.
- Still fully visible (D fails) → the timer isn't firing inside the modal loop, or selection returned None. Check the log; verify `before`/`after` differ and a candidate matched the title (the title NVDA shows equals the filename you set).
- **Move works but misbehaves** (e.g. on a multi-monitor desktop `-32000` lands on a real monitor, or a ghost lingers) → keep finding the window the same way, but instead of relocating it, make it transparent in place. This is the agreed fallback (chosen over rebuilding our own window). It keeps `WS_VISIBLE` so focus/browse mode survive, but renders nothing to onlookers. Replace the body of `move_window_offscreen` with a transparency call:

  ```python
  def make_window_transparent(hwnd):
  	"""Keep hwnd visible/focusable but render it fully transparent."""
  	u = _u32()
  	ex = u.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
  	u.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, ex | _WS_EX_LAYERED)
  	u.SetLayeredWindowAttributes(hwnd, 0, 0, _LWA_ALPHA)
  ```

  Requires the `GetWindowLongPtrW`/`SetWindowLongPtrW` prototypes from Task 4 plus a `SetLayeredWindowAttributes` prototype (`argtypes=(HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD)`), and constants `_WS_EX_LAYERED = 0x00080000`, `_LWA_ALPHA = 0x00000002` (reuse `_GWL_EXSTYLE = -20`). Note transparency does **not** remove the taskbar/Alt-Tab entry, so Task 4 may still apply on top. Like the move, it can't avoid the brief flash (applied post-creation).

- [ ] **Step 4: Clean up test artifacts (optional)**

The `render-test.txt` notes can be deleted from both watched folders once satisfied.

---

## Task 4: (Conditional) Strip the taskbar/Alt-Tab entry

**Do this only if Task 3 row F showed a lingering taskbar or Alt-Tab entry AND you decide it matters.** Otherwise skip — the window is already off-screen, and post-hoc ex-style changes can be finicky, so YAGNI applies.

**Files:**
- Modify: `addon/globalPlugins/invisinote/_window.py`
- Modify: `addon/globalPlugins/invisinote/__init__.py` (`_hide_render_window`)

- [ ] **Step 1: Add tool-window constants to `_window.py`**

Add near the other `_SWP_*` constants:

```python
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_SWP_FRAMECHANGED = 0x0020
```

- [ ] **Step 2: Add the GetWindowLongPtrW/SetWindowLongPtrW prototypes**

In `_u32()`, immediately before `_user32 = u`, add:

```python
	u.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
	u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
	u.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
	u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
```

- [ ] **Step 3: Add the `hide_from_taskbar` function**

Add at the end of `_window.py`:

```python
def hide_from_taskbar(hwnd):
	"""Add WS_EX_TOOLWINDOW so the off-screen window drops its taskbar/Alt-Tab
	entry. The SWP_FRAMECHANGED nudge makes the ex-style change take effect."""
	u = _u32()
	ex = u.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
	u.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, ex | _WS_EX_TOOLWINDOW)
	u.SetWindowPos(
		hwnd, 0, 0, 0, 0, 0, _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED
	)
```

- [ ] **Step 4: Call it from `_hide_render_window`**

In `__init__.py`, change the move block from:

```python
			if hwnd:
				_window.move_window_offscreen(hwnd)
				return
```

to:

```python
			if hwnd:
				_window.move_window_offscreen(hwnd)
				_window.hide_from_taskbar(hwnd)
				return
```

- [ ] **Step 5: Lint, rebuild, re-verify in NVDA**

Run: `ruff check addon/globalPlugins/invisinote/` then `ruff format addon/globalPlugins/invisinote/` then `scons`.
Then repeat Task 3 Steps 1-3 and confirm row F now shows no taskbar/Alt-Tab entry **and** rows A-C still pass (the frame change must not break browse mode/focus). If it breaks focus, revert this task — the off-screen move alone is the shippable result.

- [ ] **Step 6: Commit**

```bash
git add addon/globalPlugins/invisinote/_window.py addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: drop taskbar entry for the off-screen render window"
```

---

## Task 5: Docs + final regression

**Files:**
- Modify: `buildVars.py` (gesture list in `addon_description`)
- Modify: `readme.md` (gesture list)

- [ ] **Step 1: Locate the existing gesture-list lines**

Run: `git grep -n "render note as markdown"`
Expected: at least `buildVars.py` and `readme.md` (the prior feature documented this gesture). Note the exact file:line of each.

- [ ] **Step 2: Update `buildVars.py`**

In `buildVars.py`, find:

```python
- NVDA+ALT+Space: render note as markdown
```

Replace with:

```python
- NVDA+ALT+Space: render note as markdown (browses off-screen, nothing shown on screen)
```

- [ ] **Step 3: Update `readme.md`**

In `readme.md`, find the `NVDA+ALT+Space` gesture line located in Step 1 (its exact wording may differ slightly from `buildVars.py`) and update it to note the render browses off-screen with nothing shown on screen. Keep the surrounding list formatting identical.

- [ ] **Step 4: Final manual regression in NVDA**

Rebuild/reload (Task 3 Step 1) and confirm:
1. **Empty note:** create a blank `.txt` in a watched folder, navigate to it, `NVDA+ALT+Space` → announces "Empty note", no window.
2. **Normal render:** `NVDA+ALT+Space` on render-test.txt → off-screen browse doc, quick-nav works, Escape returns to host app (re-confirm Task 3 rows A-D).

- [ ] **Step 5: Commit**

```bash
git add buildVars.py readme.md
git commit -m "docs: note NVDA+ALT+Space renders off-screen"
```

---

## Notes carried forward (not part of this plan's commits)

- **Version bump 1.6 → 1.7** stays deferred to release time per the release checklist — do not bump `buildVars.py` here.
- The `tests/` directory is new to this repo and has no CI wiring. `python tests\test_window_select.py -v` is the run command. Wiring it into pre-commit/CI is out of scope here.
- If `git grep` in Task 5 Step 1 finds the gesture documented in additional locations (e.g. `addon/doc/`), update those too with the same wording.
