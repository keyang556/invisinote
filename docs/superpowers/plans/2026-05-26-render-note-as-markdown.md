# Render Note As Markdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an NVDA+ALT+Space command that renders the current note's markdown to HTML and opens it in NVDA's browse-mode buffer for full quick-navigation.

**Architecture:** Vendor the pure-Python `markdown` library under `addon/globalPlugins/invisinote/_vendor/`, put that directory on `sys.path` at module load, and add one `@script` method that converts the current note (via `_get_current_note_content()`) and hands the HTML to `ui.browseableMessage(..., isHtml=True)`. No navigation state changes, no new settings, no build-script changes (the SCons bundler already zips the whole `addon/` tree).

**Tech Stack:** Python 3.11 (NVDA runtime), Python-Markdown (vendored, BSD), NVDA `ui.browseableMessage`, SCons build.

---

## Testing reality (read before starting)

This add-on has **no offline unit-test harness**, and `addon/globalPlugins/invisinote/__init__.py` imports NVDA-only modules (`ui`, `api`, `gui`, `globalVars`, `globalPluginHandler`, …) at the top, so the plugin module **cannot be imported on the host** to unit-test the script method. Classic per-function TDD is therefore not applicable to the script itself.

Verification is layered instead:
- **Host sanity check** of the *vendored* `markdown` conversion (Task 1) — this is genuinely runnable and is our automated check.
- **Build check** (Task 5) — `scons` succeeds and the produced `.nvda-addon` ZIP contains the vendored library.
- **Manual NVDA check** (Task 5) — the only way to verify the browse-mode behaviour; a concrete checklist is provided.

Do not claim the feature works until at least the host sanity check and the build check pass, and state plainly that the NVDA manual steps require a human in NVDA.

## File structure

- Create: `addon/globalPlugins/invisinote/_vendor/markdown/` — vendored Python-Markdown package (plus its `*.dist-info` for license/metadata).
- Modify: `addon/globalPlugins/invisinote/__init__.py` — add `import sys`, the `_vendor` `sys.path` insertion, the `_render_markdown` helper, the `script_render_markdown` method, and the gesture binding.
- Modify: `buildVars.py` — add the new gesture to `addon_description`.
- Modify: `readme.md` — add the new gesture to the list.
- Temporary (not committed): `scripts/_check_vendored_markdown.py` — host sanity check; delete before the final commit (or keep out of git).

---

## Task 1: Vendor the markdown library + host sanity check

**Files:**
- Create: `addon/globalPlugins/invisinote/_vendor/markdown/` (via pip)
- Create (temporary): `scripts/_check_vendored_markdown.py`

- [ ] **Step 1: Install Python-Markdown into the vendor directory**

Run (from repo root):

```bash
pip install markdown --target addon/globalPlugins/invisinote/_vendor
```

Expected: pip reports `Successfully installed Markdown-<version>` and creates
`addon/globalPlugins/invisinote/_vendor/markdown/` plus
`addon/globalPlugins/invisinote/_vendor/Markdown-<version>.dist-info/`.

- [ ] **Step 2: Remove any console-script directory pip created**

`pip install --target` may drop a `bin/` (or `Scripts/`) folder containing the
`markdown_py` launcher, which we do not ship. Remove it if present (leave
`markdown/` and the `*.dist-info` alone):

```powershell
Remove-Item -Recurse -Force addon/globalPlugins/invisinote/_vendor/bin -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force addon/globalPlugins/invisinote/_vendor/Scripts -ErrorAction SilentlyContinue
```

- [ ] **Step 3: Confirm the package landed and a license is present**

Run:

```powershell
Test-Path addon/globalPlugins/invisinote/_vendor/markdown/__init__.py
Get-ChildItem -Recurse addon/globalPlugins/invisinote/_vendor -Filter LICENSE* | Select-Object FullName
```

Expected: first command prints `True`; the second lists a `LICENSE.md` (it lives
under the `*.dist-info/licenses/` folder for modern pip). If no license file is
found anywhere under `_vendor`, download it from the Python-Markdown repo for the
installed version and save it as
`addon/globalPlugins/invisinote/_vendor/markdown/LICENSE.md` so attribution ships
with the package.

- [ ] **Step 4: Write the host sanity check**

Create `scripts/_check_vendored_markdown.py` with exactly this content:

```python
"""Host-only check that the vendored markdown renders the constructs we rely on.

Run from the repo root: python scripts/_check_vendored_markdown.py
Not shipped in the add-on; safe to delete after verifying.
"""

import os
import sys

VENDOR = os.path.join("addon", "globalPlugins", "invisinote", "_vendor")
# Put the vendored copy first so we test it, not any host-installed markdown.
sys.path.insert(0, os.path.abspath(VENDOR))

import markdown  # noqa: E402

assert os.path.abspath(VENDOR) in os.path.abspath(markdown.__file__), (
	f"Imported the wrong markdown: {markdown.__file__}"
)

SAMPLE = """# Title

Some **bold** text and a [link](https://www.nvaccess.org).

- one
- two

| a | b |
|---|---|
| 1 | 2 |

```python
print("hi")
```
"""

html = markdown.markdown(
	SAMPLE,
	extensions=[
		"markdown.extensions.fenced_code",
		"markdown.extensions.tables",
		"markdown.extensions.sane_lists",
	],
)

for needle in ("<h1>", "<strong>", '<a href="https://www.nvaccess.org">', "<ul>", "<table>", "<code"):
	assert needle in html, f"missing {needle!r} in:\n{html}"

print("OK: vendored markdown renders headings, bold, links, lists, tables, code")
print(f"markdown version: {markdown.__version__}  file: {markdown.__file__}")
```

- [ ] **Step 5: Run the sanity check and verify it passes**

Run:

```bash
python scripts/_check_vendored_markdown.py
```

Expected: prints `OK: vendored markdown renders ...` and the version/file line,
and the file path shown is inside `addon/globalPlugins/invisinote/_vendor`. Exit
code 0. If an `AssertionError` fires for the wrong-markdown check, the host's own
markdown shadowed the vendored copy — confirm `sys.path.insert(0, ...)` is using
the absolute `_vendor` path.

- [ ] **Step 6: Commit the vendored library**

The temporary check script is intentionally left out of this commit.

```bash
git add addon/globalPlugins/invisinote/_vendor
git commit -m "chore: vendor Python-Markdown for runtime note rendering"
```

---

## Task 2: Put the vendored library on sys.path

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py` (top of file, imports)

- [ ] **Step 1: Add `import sys` to the import block**

The current imports start at line 1 with `import re`. Add `import sys` alongside
them. After editing, the top of the file reads:

```python
import re
import os
import sys
import ui
import api
import wx
import gui
import subprocess
import globalVars
import globalPluginHandler
import characterProcessing
import languageHandler
import scriptHandler
from scriptHandler import script
```

- [ ] **Step 2: Insert the `_vendor` directory onto sys.path after the imports**

Immediately after the `from scriptHandler import script` line (before the
`class SettingsDialog` definition), add:

```python

# Make the vendored, pure-Python markdown library importable at runtime.
# NVDA's bundled interpreter does not ship markdown, so it travels with the add-on.
_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vendor")
if _VENDOR_DIR not in sys.path:
	sys.path.insert(0, _VENDOR_DIR)
```

- [ ] **Step 3: Verify the file still parses**

Run:

```bash
python -m py_compile addon/globalPlugins/invisinote/__init__.py
```

Expected: no output, exit code 0. (This only checks syntax — the NVDA imports
still cannot resolve on the host, which is expected; `py_compile` does not execute
imports.)

- [ ] **Step 4: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: make vendored markdown importable at runtime"
```

---

## Task 3: Add the render helper, script, and gesture

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py` (add helper + script near `script_read_note` ~line 295; add gesture in `__gestures` ~line 481)

- [ ] **Step 1: Add the `_render_markdown` helper method**

Place this method just before `script_read_note` (it is a plain helper, no
`@script` decorator). The lazy `import markdown` keeps NVDA startup fast and lets
us degrade gracefully if the vendored package is ever missing:

```python
	def _render_markdown(self, text):
		try:
			import markdown
		except ImportError:
			return None
		return markdown.markdown(
			text,
			extensions=[
				"markdown.extensions.fenced_code",
				"markdown.extensions.tables",
				"markdown.extensions.sane_lists",
			],
		)
```

- [ ] **Step 2: Add the `script_render_markdown` script method**

Place it immediately after `_render_markdown` (and before `script_read_note`).
It reuses `_get_current_note_content()`, which returns `None` for an empty note
or when no notes are loaded — so the early return also guards the
`self.notes[...]` indexing for the title:

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

- [ ] **Step 3: Bind the gesture**

In the `__gestures` dict at the bottom of the class, add this entry. Put it next
to `read_note` for readability:

```python
		"kb:NVDA+ALT+SHIFT+A": "read_note",
		"kb:NVDA+ALT+SPACE": "render_markdown",
```

(The first line above already exists — add only the second line directly beneath
it.)

- [ ] **Step 4: Verify the file still parses**

Run:

```bash
python -m py_compile addon/globalPlugins/invisinote/__init__.py
```

Expected: no output, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: render current note as markdown with NVDA+ALT+Space"
```

---

## Task 4: Update documentation

**Files:**
- Modify: `buildVars.py:43` (inside `addon_description`)
- Modify: `readme.md:21`

- [ ] **Step 1: Add the gesture to `buildVars.py` description**

In the `addon_description` string, the line `- NVDA+ALT+SHIFT+A: read note`
currently exists. Insert the new line directly after it:

```
- NVDA+ALT+SHIFT+A: read note
- NVDA+ALT+Space: render note as markdown
```

- [ ] **Step 2: Add the gesture to `readme.md`**

In `readme.md`, the line `- NVDA+ALT+SHIFT+A: read note` currently exists. Insert
the new line directly after it:

```
- NVDA+ALT+SHIFT+A: read note
- NVDA+ALT+Space: render note as markdown
```

- [ ] **Step 3: Commit**

```bash
git add buildVars.py readme.md
git commit -m "docs: document NVDA+ALT+Space render-as-markdown gesture"
```

---

## Task 5: Build verification + manual NVDA checklist

**Files:** none modified (verification only)

- [ ] **Step 1: Build the add-on**

Run (from repo root):

```bash
scons
```

Expected: build succeeds and produces `invisinote-1.6.nvda-addon` in the repo
root (version unchanged — the bump to 1.7 happens at release time per the
release checklist).

- [ ] **Step 2: Confirm the vendored library is inside the package**

The `.nvda-addon` is a ZIP. List its contents and confirm the markdown package
shipped:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::OpenRead((Resolve-Path "invisinote-1.6.nvda-addon")).Entries |
	Where-Object { $_.FullName -like "*_vendor/markdown/__init__.py*" } |
	Select-Object FullName
```

Expected: one entry like
`globalPlugins/invisinote/_vendor/markdown/__init__.py` is listed. If nothing is
listed, the vendored files were not packaged — re-check Task 1 paths.

- [ ] **Step 3: Remove the temporary host check script**

If `scripts/_check_vendored_markdown.py` was created and you do not want it in the
tree, delete it now. (It was never committed, so no commit is needed.)

```powershell
Remove-Item addon/../scripts/_check_vendored_markdown.py -ErrorAction SilentlyContinue
```

- [ ] **Step 4: Manual NVDA verification (requires a human in NVDA)**

Install the built `.nvda-addon` in NVDA and confirm:

  1. Put a `.md` (or `.txt`) note containing a `#` heading, a `##` heading, a
     bullet list, a `[link](https://www.nvaccess.org)`, a fenced code block, and
     a pipe table into a configured folder; load notes (NVDA+ALT+N) and navigate
     to it.
  2. Press **NVDA+ALT+Space**. Expected: a browse-mode dialog opens; NVDA first
     announces the **filename** (the dialog title), then the document content.
  3. In the buffer, `H` (and `1`/`2`) jumps between headings at the correct
     levels; `K` reaches the link; `L` reaches the list; the table is navigable.
  4. Press **Escape**. Expected: the buffer closes and focus returns to the app
     you were in; Invisinote's note/line position is unchanged (press
     NVDA+ALT+K/I to confirm you are where you left off).
  5. Navigate to an empty note and press NVDA+ALT+Space. Expected: NVDA speaks
     "Empty note" and **no** buffer opens.

- [ ] **Step 5: Report results honestly**

State which steps passed. The host sanity check (Task 1) and build/package check
(Steps 1–2) are machine-verifiable; explicitly note that the NVDA manual steps
(Step 4) require a human and report their outcome rather than assuming them.

---

## Self-review notes

- **Spec coverage:** trigger/scope → Task 3; announcements & edge cases (empty,
  import failure) → Task 3 script body + manual checklist Task 5; conversion with
  dotted-path extensions → Task 1 sanity check + Task 3 helper; vendoring & "no
  build change" → Tasks 1 & 5; license → Task 1 Step 3; docs/strings → Task 4;
  version-bump-at-release-time → noted in Task 5 Step 1. All spec sections map to
  a task.
- **Naming consistency:** `_render_markdown` and `script_render_markdown` /
  gesture target `render_markdown` are used consistently across Tasks 3–4.
- **No placeholders:** every code and command step contains literal content.
