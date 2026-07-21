# Note Encoding Setting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Note encoding" combo box to the Invisinote settings category so users can read notes saved in non-UTF-8 encodings (Big5, GB18030, etc.) correctly, applying the change to the current note immediately on OK.

**Architecture:** Add `self.encoding` state to `GlobalPlugin` (persisted in `encoding.txt`), use it in `_read_note_file` with a guaranteed `latin-1` fallback, extend `apply_settings` to persist it and re-read the current note when it changes, and add a labeled `wx.Choice` to `InvisinoteSettingsPanel`.

**Tech Stack:** Python 3.11, wxPython (NVDA's bundled `wx`), NVDA `gui.settingsDialogs` / `gui.guiHelper`.

## Global Constraints

- Code style: tabs for indentation, max line length 110 (ruff via `pyproject.toml`).
- Translation builtins `_`, `ngettext`, `pgettext`, `npgettext` are available — never import them, and never bind `_` as a throwaway variable. All user-visible strings wrapped in `_()`.
- Do not rewrite git history.
- Encoding list (label → codec), default `utf-8`, in this order: `UTF-8`→`utf-8`, `UTF-8 with BOM`→`utf-8-sig`, `Big5 (Traditional Chinese)`→`big5`, `GB18030 (Simplified Chinese)`→`gb18030`, `Windows-1252`→`cp1252`, `Latin-1`→`latin-1`. No UTF-16.
- Combo label verbatim: `Note encoding`. Placement: last control, after File types.
- `latin-1` remains the guaranteed read fallback.
- The entire add-on logic lives in `addon/globalPlugins/invisinote/__init__.py`.

## Note on testing

`__init__.py` imports NVDA runtime modules (`ui`, `api`, `gui`, `globalPluginHandler`, `wx`) that do not exist outside a running NVDA, so this change **cannot** be covered by the pytest/unittest suite (which only exercises the NVDA-free `_window` module). Do not add a unittest for the panel or reading logic. Automated gates are ruff and the existing pytest suite. Behaviour is verified manually in live NVDA (Task 2).

---

### Task 1: Add the Note encoding setting

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py` — import `guiHelper`; add encoding state + `_load_encoding`; update `_read_note_file`; extend `apply_settings`; add the combo to `InvisinoteSettingsPanel.makeSettings` and pass it from `onSave`.

**Interfaces:**
- Consumes: `GlobalPlugin` attrs `self.configFolder`, `self.notes`, and method `self._load_current_note_lines()` (re-reads the current note, resets to its start).
- Produces: `GlobalPlugin.encoding` (str codec), `GlobalPlugin.encodingFile` (str path), `GlobalPlugin._load_encoding()`, extended `apply_settings(self, paths, file_types, encoding)`, and `InvisinoteSettingsPanel._encoding_codecs` / `_encoding_choice`.

- [ ] **Step 1: Import guiHelper**

Replace the import line (line 8):

```python
from gui import settingsDialogs
```

with:

```python
from gui import guiHelper, settingsDialogs
```

- [ ] **Step 2: Add the encoding combo to `makeSettings`**

In `InvisinoteSettingsPanel.makeSettings`, the method currently ends with the four `Bind` calls (lines 63–66):

```python
		add_folder_btn.Bind(wx.EVT_BUTTON, self._on_add_folder)
		remove_folder_btn.Bind(wx.EVT_BUTTON, self._on_remove_folder)
		add_type_btn.Bind(wx.EVT_BUTTON, self._on_add_type)
		remove_type_btn.Bind(wx.EVT_BUTTON, self._on_remove_type)
```

Append, immediately after those four lines (still inside `makeSettings`):

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
		self._encoding_choice = enc_helper.addLabeledControl(
			_("Note encoding"), wx.Choice, choices=labels
		)
		current = plugin.encoding if plugin else "utf-8"
		self._encoding_choice.SetSelection(
			self._encoding_codecs.index(current) if current in self._encoding_codecs else 0
		)
```

Note `plugin` is the local already assigned at the top of `makeSettings` (`plugin = self.plugin`).

- [ ] **Step 3: Pass the selected encoding from `onSave`**

Replace `InvisinoteSettingsPanel.onSave` (lines 122–124):

```python
	def onSave(self):
		if self.plugin:
			self.plugin.apply_settings(self._paths, self._file_types)
```

with:

```python
	def onSave(self):
		if self.plugin:
			self.plugin.apply_settings(
				self._paths,
				self._file_types,
				self._encoding_codecs[self._encoding_choice.GetSelection()],
			)
```

- [ ] **Step 4: Initialise encoding state in `GlobalPlugin.__init__`**

In `GlobalPlugin.__init__`, the tail currently reads (lines 154–157):

```python
		self._load_paths()
		self._load_file_types()
		InvisinoteSettingsPanel.plugin = self
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(InvisinoteSettingsPanel)
```

Change it to add the encoding load between `_load_file_types()` and the panel registration:

```python
		self._load_paths()
		self._load_file_types()
		self.encoding = "utf-8"
		self.encodingFile = os.path.join(self.configFolder, "encoding.txt")
		self._load_encoding()
		InvisinoteSettingsPanel.plugin = self
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(InvisinoteSettingsPanel)
```

- [ ] **Step 5: Add the `_load_encoding` method**

Directly after the `_load_file_types` method (which currently ends at line 180 with the `self.fileTypes = ["txt"]` block), add:

```python
	def _load_encoding(self):
		if os.path.exists(self.encodingFile):
			with open(self.encodingFile, "r", encoding="utf-8") as f:
				value = f.read().strip()
			if value:
				self.encoding = value
```

- [ ] **Step 6: Use the encoding in `_read_note_file`**

Replace `_read_note_file` (lines 182–188):

```python
	def _read_note_file(self, path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				return f.read()
		except UnicodeDecodeError:
			with open(path, "r", encoding="latin-1") as f:
				return f.read()
```

with:

```python
	def _read_note_file(self, path):
		try:
			with open(path, "r", encoding=self.encoding) as f:
				return f.read()
		except (UnicodeDecodeError, LookupError):
			with open(path, "r", encoding="latin-1") as f:
				return f.read()
```

- [ ] **Step 7: Persist and apply the encoding in `apply_settings`**

Replace `apply_settings` (lines 271–279):

```python
	def apply_settings(self, paths, file_types):
		self.paths = list(paths) or [os.path.join(self.configFolder, "notes")]
		self.currentPathIndex = min(self.currentPathIndex, len(self.paths) - 1)
		self.notesPath = self.paths[self.currentPathIndex]
		with open(self.pathsFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.paths) + "\n")
		self.fileTypes = list(file_types) or ["txt"]
		with open(self.fileTypesFile, "w", encoding="utf-8") as f:
			f.write("\n".join(self.fileTypes) + "\n")
```

with:

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

- [ ] **Step 8: Lint**

Run: `ruff check addon/globalPlugins/invisinote/__init__.py && ruff format --check addon/globalPlugins/invisinote/__init__.py`
Expected: no errors. (If `ruff format --check` reports it would reformat, run `ruff format` on the file and re-check.) Confirm no accidental binding of `_` and no unused-import warnings.

- [ ] **Step 9: Run the existing test suite to confirm no regression**

Run: `python -m pytest tests/ -q`
Expected: PASS (7 passed) — the `_window` tests are unaffected; confirms the module still parses for the collector.

- [ ] **Step 10: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: add Note encoding setting for reading notes"
```

---

### Task 2: Manually verify in live NVDA

No code or docs change. The readme already states settings live in NVDA's Settings dialog under the Invisinote category, which covers this new control. This task is the live-NVDA verification, which requires a screen reader and cannot be automated.

**Interfaces:** depends on Task 1 being deployed.

- [ ] **Step 1: Deploy and reload**

Follow the `nvda-testing-setup` memory: build/deploy (`scons -c && scons`, or the scratchpad rig), then fully restart NVDA.

- [ ] **Step 2: Verify the control (screen reader)**

- `NVDA+CTRL+S` → Invisinote category → Tab to the end.
- Confirm the last control announces *"Note encoding, combo box, UTF-8"* and arrowing moves through the six entries (UTF-8, UTF-8 with BOM, Big5 (Traditional Chinese), GB18030 (Simplified Chinese), Windows-1252, Latin-1).

- [ ] **Step 3: Verify the Traditional-Chinese fix**

- Create a note saved as **Big5** containing Traditional Chinese text in a watched folder; load notes (`NVDA+ALT+N`) and read it — with UTF-8 it should read garbled.
- Open settings, set **Note encoding → Big5 (Traditional Chinese)**, press **OK**.
- Confirm the current note re-reads correctly from its start (reread-on-OK), and reading it (`NVDA+ALT+SHIFT+A`) is now correct.

- [ ] **Step 4: Verify the Simplified-Chinese fix and English safety**

- Repeat Step 3 with a **GB18030** Simplified-Chinese note.
- Confirm a plain **English/ASCII** note still reads correctly under the Big5/GB18030 setting (ASCII-compatible).

- [ ] **Step 5: Verify persistence**

- Set an encoding, OK, fully restart NVDA, reopen `NVDA+CTRL+S` → Invisinote; confirm the combo shows the saved encoding (i.e. `encoding.txt` persisted).

---

## Self-Review

**Spec coverage:**
- Combo `Note encoding` after File types via `guiHelper.addLabeledControl` → Task 1 Step 2. ✓
- Six-entry list (no UTF-16), default UTF-8, correct codecs/order → Task 1 Step 2 (verbatim). ✓
- Persistence in `encoding.txt`, load default utf-8 → Task 1 Steps 4 & 5. ✓
- `_read_note_file` uses `self.encoding` with `(UnicodeDecodeError, LookupError)` → `latin-1` fallback → Task 1 Step 6. ✓
- `apply_settings(paths, file_types, encoding)` persists encoding and re-reads current note only when changed → Task 1 Step 7; `onSave` passes selected codec → Step 3. ✓
- Reread-on-OK resets to note start → `_load_current_note_lines()` in Step 7, verified Task 2 Step 3. ✓
- No render change, no new dependency, config formats for paths/filetypes unchanged → nothing else touched. ✓

**Placeholder scan:** No TBD/TODO; all code verbatim. Line numbers are anchors accompanying exact old_string blocks.

**Type consistency:** `self.encoding` (str) set in `__init__` Step 4, read in `_read_note_file` (Step 6), `makeSettings` (Step 2, via `plugin.encoding`), and written in `apply_settings` (Step 7). `self.encodingFile` set in Step 4, used in Steps 5 & 7. `_encoding_codecs` / `_encoding_choice` defined in Step 2, used in `onSave` (Step 3). `apply_settings` 3-arg signature (Step 7) matches the `onSave` call (Step 3). `guiHelper` imported in Step 1, used in Step 2. No `_` rebinding (comprehensions use `e[0]`/`e[1]`). ✓
