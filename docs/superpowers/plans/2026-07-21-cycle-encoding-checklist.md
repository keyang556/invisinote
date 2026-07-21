# Cycle-encoding Checklist + NVDA+ALT+E — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "Note encoding" combo box with a checkable "Cycle encodings" list, and add an `NVDA+ALT+E` gesture that cycles the active encoding forward through the checked ones (persisting, re-reading the current note, and announcing each).

**Architecture:** Two pieces of state on `GlobalPlugin` — the active encoding (`encoding.txt`, used by `_read_note_file`) and the cycle set (`cycle_encodings.txt`, edited by the checklist). Module-level `_note_encodings()` / `_encoding_label()` are the single source of the list. `apply_settings` takes the checked set and enforces the invariant that the active encoding is always in the cycle set.

**Tech Stack:** Python 3.11, wxPython (`wx.CheckListBox`), NVDA `gui.guiHelper` / `gui.settingsDialogs`.

## Global Constraints

- Code style: tabs for indentation, max line length 110 (ruff via `pyproject.toml`).
- Translation builtins `_`, `ngettext`, `pgettext`, `npgettext` are available — never import them, and never bind `_` as a throwaway variable. All user-visible strings wrapped in `_()`.
- Do not rewrite git history.
- Encoding list (label → codec), canonical order, six entries, no UTF-16: `UTF-8`→`utf-8`, `UTF-8 with BOM`→`utf-8-sig`, `Big5 (Traditional Chinese)`→`big5`, `GB18030 (Simplified Chinese)`→`gb18030`, `Windows-1252`→`cp1252`, `Latin-1`→`latin-1`.
- Checklist label verbatim: `Cycle encodings`. Gesture announcement: `Note encoding: <name>`. Gesture: `NVDA+ALT+E`.
- Default cycle set: all six checked. Empty selection falls back to `["utf-8"]`.
- Invariant: the active encoding is always a member of the (non-empty) cycle set.
- The entire add-on logic lives in `addon/globalPlugins/invisinote/__init__.py`.

## Note on testing

`__init__.py` imports NVDA runtime modules (`ui`, `api`, `gui`, `globalPluginHandler`, `wx`) that do not exist outside a running NVDA, so this change **cannot** be covered by the pytest/unittest suite (which only exercises the NVDA-free `_window` module). Do not add a unittest. Automated gates are ruff and the existing pytest suite. Behaviour is verified manually in live NVDA (Task 2).

---

### Task 1: Checklist, cycle state, and gesture

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py`.

**Interfaces:**
- Consumes: `GlobalPlugin` attrs `self.configFolder`, `self.notes`, `self.encoding`, `self.encodingFile`, and `self._load_current_note_lines()`.
- Produces: module functions `_note_encodings()`, `_encoding_label(codec)`; `GlobalPlugin.cycleEncodings`, `cycleEncodingsFile`, `_load_cycle_encodings()`, `_clamp_active_encoding()`, `_persist_encoding()`, `_persist_cycle_encodings()`, `script_cycle_encoding`; extended `apply_settings(self, paths, file_types, cycle_encodings)`; panel `_cycle_list` / `_encoding_codecs`.

- [ ] **Step 1: Add module-level encoding helpers**

Between the render-timing constants and the `InvisinoteSettingsPanel` class, i.e. after line 29 (`_RENDER_HIDE_TIMEOUT_S = 1.0`) and before `class InvisinoteSettingsPanel...` (line 32), insert:

```python


def _note_encodings():
	return [
		(_("UTF-8"), "utf-8"),
		(_("UTF-8 with BOM"), "utf-8-sig"),
		(_("Big5 (Traditional Chinese)"), "big5"),
		(_("GB18030 (Simplified Chinese)"), "gb18030"),
		(_("Windows-1252"), "cp1252"),
		(_("Latin-1"), "latin-1"),
	]


def _encoding_label(codec):
	for label, c in _note_encodings():
		if c == codec:
			return label
	return codec
```

- [ ] **Step 2: Replace the combo with a checklist in `makeSettings`**

Replace the encoding combo block (lines 68–83, from `encodings = [` through the `SetSelection(...)` call):

```python
		encodings = [
			(_("UTF-8"), "utf-8"),
			(_("UTF-8 with BOM"), "utf-8-sig"),
			(_("Big5 (Traditional Chinese)"), "big5"),
			(_("GB18030 (Simplified Chinese)"), "gb18030"),
			(_("Windows-1252"), "cp1252"),
			(_("Latin-1"), "latin-1"),
		]
		labels = [e[0] for e in encodings]
		self._encoding_codecs = [e[1] for e in encodings]
		enc_helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._encoding_choice = enc_helper.addLabeledControl(_("Note encoding"), wx.Choice, choices=labels)
		current = plugin.encoding if plugin else "utf-8"
		self._encoding_choice.SetSelection(
			self._encoding_codecs.index(current) if current in self._encoding_codecs else 0
		)
```

with:

```python
		encodings = _note_encodings()
		labels = [e[0] for e in encodings]
		self._encoding_codecs = [e[1] for e in encodings]
		cycle_helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._cycle_list = cycle_helper.addLabeledControl(
			_("Cycle encodings"), wx.CheckListBox, choices=labels
		)
		enabled = plugin.cycleEncodings if plugin else self._encoding_codecs
		for i, codec in enumerate(self._encoding_codecs):
			self._cycle_list.Check(i, codec in enabled)
```

- [ ] **Step 3: Update `onSave` to pass the checked codecs**

Replace `InvisinoteSettingsPanel.onSave` (lines 139–145):

```python
	def onSave(self):
		if self.plugin:
			self.plugin.apply_settings(
				self._paths,
				self._file_types,
				self._encoding_codecs[self._encoding_choice.GetSelection()],
			)
```

with:

```python
	def onSave(self):
		if self.plugin:
			checked = [self._encoding_codecs[i] for i in self._cycle_list.GetCheckedItems()]
			self.plugin.apply_settings(self._paths, self._file_types, checked)
```

- [ ] **Step 4: Initialise cycle-set state in `__init__`**

Replace the encoding-load block (lines 177–179):

```python
		self.encoding = "utf-8"
		self.encodingFile = os.path.join(self.configFolder, "encoding.txt")
		self._load_encoding()
```

with:

```python
		self.encoding = "utf-8"
		self.encodingFile = os.path.join(self.configFolder, "encoding.txt")
		self._load_encoding()
		self.cycleEncodings = []
		self.cycleEncodingsFile = os.path.join(self.configFolder, "cycle_encodings.txt")
		self._load_cycle_encodings()
		self._clamp_active_encoding()
```

- [ ] **Step 5: Add the cycle-set load/clamp/persist helpers**

Directly after the `_load_encoding` method (which ends at line 211 with the `self.encoding = value` block), add:

```python
	def _load_cycle_encodings(self):
		known = [e[1] for e in _note_encodings()]
		if os.path.exists(self.cycleEncodingsFile):
			with open(self.cycleEncodingsFile, "r", encoding="utf-8") as f:
				stored = {line.strip() for line in f if line.strip()}
			self.cycleEncodings = [c for c in known if c in stored] or list(known)
		else:
			self.cycleEncodings = list(known)

	def _clamp_active_encoding(self):
		if self.encoding not in self.cycleEncodings:
			self.encoding = self.cycleEncodings[0] if self.cycleEncodings else "utf-8"

	def _persist_encoding(self):
		with open(self.encodingFile, "w", encoding="utf-8") as f:
			f.write(self.encoding + "\n")

	def _persist_cycle_encodings(self):
		with open(self.cycleEncodingsFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.cycleEncodings) + "\n")
```

- [ ] **Step 6: Rewrite `apply_settings` to take the cycle set**

Replace `apply_settings` (lines 302–316):

```python
	def apply_settings(self, paths, file_types, encoding):
		self.paths = list(paths) or [os.path.join(self.configFolder, "notes")]
		self.currentPathIndex = min(self.currentPathIndex, len(self.paths) - 1)
		self.notesPath = self.paths[self.currentPathIndex]
		with open(self.pathsFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.paths) + "\n")
		self.fileTypes = list(file_types) or ["txt"]
		with open(self.fileTypesFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.fileTypes) + "\n")
		encoding_changed = encoding != self.encoding
		self.encoding = encoding or "utf-8"
		with open(self.encodingFile, "w", encoding="utf-8") as f:
			f.write(self.encoding + "\n")
		if encoding_changed and self.notes:
			self._load_current_note_lines()
```

with:

```python
	def apply_settings(self, paths, file_types, cycle_encodings):
		self.paths = list(paths) or [os.path.join(self.configFolder, "notes")]
		self.currentPathIndex = min(self.currentPathIndex, len(self.paths) - 1)
		self.notesPath = self.paths[self.currentPathIndex]
		with open(self.pathsFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.paths) + "\n")
		self.fileTypes = list(file_types) or ["txt"]
		with open(self.fileTypesFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.fileTypes) + "\n")
		self.cycleEncodings = list(cycle_encodings) or ["utf-8"]
		self._persist_cycle_encodings()
		previous = self.encoding
		self._clamp_active_encoding()
		if self.encoding != previous:
			self._persist_encoding()
			if self.notes:
				self._load_current_note_lines()
```

- [ ] **Step 7: Add the cycle-encoding script**

Directly after `script_clear_markers` (which ends at line 590 with `ui.message(_("selection cleared"))`) and before the `__gestures = {` line, add:

```python
	@script(description=_("Cycle note encoding"))
	def script_cycle_encoding(self, gesture):
		cycle = self.cycleEncodings or ["utf-8"]
		idx = cycle.index(self.encoding) + 1 if self.encoding in cycle else 0
		idx %= len(cycle)
		self.encoding = cycle[idx]
		self._persist_encoding()
		if self.notes:
			self._load_current_note_lines()
		ui.message(_("Note encoding: {}").format(_encoding_label(self.encoding)))
```

- [ ] **Step 8: Bind the gesture**

In the `__gestures` dict, add after the `open_path` line (line 593):

```python
		"kb:NVDA+ALT+E": "cycle_encoding",
```

- [ ] **Step 9: Lint**

Run: `ruff check addon/globalPlugins/invisinote/__init__.py && ruff format --check addon/globalPlugins/invisinote/__init__.py`
Expected: no errors. (If `ruff format --check` reports it would reformat, run `ruff format` on the file and re-check.) Confirm no `_` rebinding and no leftover reference to `_encoding_choice`.

- [ ] **Step 10: Run the existing test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (7 passed).

- [ ] **Step 11: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: cycle-encoding checklist and NVDA+ALT+E gesture"
```

---

### Task 2: Docs and manual verification

**Files:**
- Modify: root `readme.md`; `buildVars.py` (`addon_description`). (`addon/doc/en/` is gitignored build output — do not edit.)

- [ ] **Step 1: Add the gesture to root readme.md**

In root `readme.md`, after the `- NVDA+ALT+P: open path` line, add:

```markdown
- NVDA+ALT+E: cycle note encoding
```

- [ ] **Step 2: Add the gesture to buildVars.py addon_description**

In `buildVars.py`, in the `addon_description` string, after the `- NVDA+ALT+P: open path` line, add the same bullet:

```
- NVDA+ALT+E: cycle note encoding
```

- [ ] **Step 3: Commit docs**

```bash
git add readme.md buildVars.py
git commit -m "docs: document NVDA+ALT+E cycle-encoding gesture"
```

- [ ] **Step 4: Deploy and reload**

Follow the `nvda-testing-setup` memory: build/deploy (`scons -c && scons`, or the scratchpad rig), then fully restart NVDA.

- [ ] **Step 5: Verify the checklist (screen reader)**

- `NVDA+CTRL+S` → Invisinote → Tab to the last control.
- Confirm it is a checkable list labelled "Cycle encodings"; all six checked by default; announces e.g. "Cycle encodings, Big5 (Traditional Chinese), check box, checked, 3 of 6"; arrows move, Space toggles.

- [ ] **Step 6: Verify the gesture cycles and applies**

- Load the encoding-test folder (`C:\Users\melody\Desktop\invisinote-encoding-test`); go to `big5.txt` (garbled under UTF-8).
- Press `NVDA+ALT+E` repeatedly; confirm each press announces "Note encoding: <name>" through the six; on Big5 the note reads correctly; after Latin-1 it wraps back to UTF-8.

- [ ] **Step 7: Verify the cycle set narrows the gesture**

- In settings, uncheck all but UTF-8 and Big5, OK.
- Confirm `NVDA+ALT+E` now only alternates between UTF-8 and Big5.

- [ ] **Step 8: Verify the uncheck-active edge case + persistence**

- Cycle to Big5, reopen settings, uncheck Big5, OK; confirm the active encoding resets (the note re-reads with the first checked encoding).
- Restart NVDA and confirm the checklist state and active encoding persisted (`cycle_encodings.txt`, `encoding.txt`).

---

## Self-Review

**Spec coverage:**
- `_note_encodings()` / `_encoding_label()` module helpers → Task 1 Step 1. ✓
- Combo replaced by `wx.CheckListBox` labelled `Cycle encodings`, last control, default all checked → Task 1 Step 2. ✓
- `onSave` passes checked codecs → Task 1 Step 3. ✓
- Cycle-set state, load (default all / fallback all), clamp, persist helpers → Task 1 Steps 4 & 5. ✓
- `apply_settings(paths, file_types, cycle_encodings)` persists set, enforces invariant, re-reads only when active changed → Task 1 Step 6. ✓
- `script_cycle_encoding` cycles checked set, wraps, persists, re-reads, announces `Note encoding: <name>` → Task 1 Step 7. ✓
- `NVDA+ALT+E` bound → Task 1 Step 8. ✓
- Docs on readme.md + buildVars.py → Task 2 Steps 1–2. ✓
- Empty-selection fallback to `["utf-8"]`, uncheck-active reset → Step 6 + Task 2 Step 8. ✓

**Placeholder scan:** No TBD/TODO; all code verbatim; line numbers are anchors with exact old_string blocks.

**Type consistency:** `_note_encodings()` returns `(label, codec)` pairs, consumed in Step 1 (`_encoding_label`), Step 2 (`labels`/`_encoding_codecs`), Steps 5 (`known`). `self.cycleEncodings` (list[str]) set in Steps 4/5/6, read in Steps 6/7 and panel Step 2. `_persist_encoding` / `_persist_cycle_encodings` defined Step 5, used Steps 6/7. `apply_settings` 3rd param renamed `encoding`→`cycle_encodings` (Step 6) matches the `onSave` call passing `checked` (Step 3). `_cycle_list` (`wx.CheckListBox`) defined Step 2, read Step 3 via `GetCheckedItems()`. No `_` rebinding (`for label, c in ...`, `e[0]`/`e[1]`). ✓
