# Invisinote Settings Category — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Invisinote's configuration into NVDA's built-in Settings dialog as a category named "Invisinote", removing the standalone Preferences menu item and the `NVDA+ALT+SHIFT+P` shortcut.

**Architecture:** Replace the standalone `SettingsDialog` (`wx.Dialog`) with an `InvisinoteSettingsPanel` (`gui.settingsDialogs.SettingsPanel`) registered in `NVDASettingsDialog.categoryClasses`. The panel reads/writes through a new `GlobalPlugin.apply_settings()` that carries the exact persistence logic from the old `_show_paths_dialog`. All menu-item wiring and the edit-paths gesture are removed.

**Tech Stack:** Python 3.11, wxPython (NVDA's bundled `wx`), NVDA `gui.settingsDialogs`.

## Global Constraints

- Code style: tabs for indentation, max line length 110 (ruff via `pyproject.toml`).
- Translation builtins `_`, `ngettext`, `pgettext`, `npgettext` are available — never import them. All user-visible strings wrapped in `_()`.
- Do not rewrite git history.
- Category title verbatim: `Invisinote`
- Group labels verbatim: `Folders`, `File types`. Button labels verbatim: `Add folder`, `Remove folder`, `Add type`, `Remove type`.
- Keep `NVDA+ALT+P` (open path). Remove `NVDA+ALT+SHIFT+P` (edit paths).
- On-disk config format (`paths.txt`, `filetypes.txt`) is unchanged.
- The entire add-on logic lives in `addon/globalPlugins/invisinote/__init__.py`.

## Note on testing

`__init__.py` imports NVDA runtime modules (`ui`, `api`, `gui`, `globalPluginHandler`, `wx`) that do not exist outside a running NVDA, so this change **cannot** be covered by the pytest/unittest suite (which only exercises the NVDA-free `_window` module). Do not add a unittest for the panel. Automated gates are ruff and the existing pytest suite. Behaviour is verified manually in live NVDA (Task 2).

---

### Task 1: Convert config UI to an NVDA Settings category

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py` — add `from gui import settingsDialogs`; replace `SettingsDialog` class with `InvisinoteSettingsPanel`; update `GlobalPlugin.__init__`, add `apply_settings`, rewrite `terminate`, remove `script_edit_paths` / `_show_paths_dialog` / `on_settings` and the `NVDA+ALT+SHIFT+P` gesture.

**Interfaces:**
- Consumes: existing `GlobalPlugin` attributes `self.paths` (list[str]), `self.fileTypes` (list[str]), `self.pathsFile` (str), `self.fileTypesFile` (str), `self.currentPathIndex` (int), `self.configFolder` (str).
- Produces: `InvisinoteSettingsPanel` (class attr `plugin`, methods `makeSettings`, `onSave`, the four add/remove handlers) and `GlobalPlugin.apply_settings(self, paths, file_types)`.

- [ ] **Step 1: Add the settingsDialogs import**

In the import block near the top of `addon/globalPlugins/invisinote/__init__.py`, after the line `import gui` (line 8), add:

```python
from gui import settingsDialogs
```

- [ ] **Step 2: Replace the `SettingsDialog` class with `InvisinoteSettingsPanel`**

Replace the ENTIRE `SettingsDialog` class (currently lines 32–127, from `class SettingsDialog(wx.Dialog):` through the end of `get_file_types`) with the panel below. Note: the add/remove handler bodies are unchanged from the old class except that `self` is now the panel; `makeSettings` adds groups to the passed `settingsSizer` instead of a local `main_sizer`, and there is no OK/Cancel sizer (the Settings dialog supplies those). `get_paths`/`get_file_types` are dropped (no external caller remains).

```python
class InvisinoteSettingsPanel(settingsDialogs.SettingsPanel):
	title = _("Invisinote")
	plugin = None

	def makeSettings(self, settingsSizer):
		plugin = self.plugin
		self._paths = list(plugin.paths) if plugin else []
		self._file_types = list(plugin.fileTypes) if plugin else []

		paths_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Folders")), wx.VERTICAL)
		self._paths_listbox = wx.ListBox(self, choices=self._paths)
		paths_box.Add(self._paths_listbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
		paths_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		add_folder_btn = wx.Button(self, label=_("Add folder"))
		remove_folder_btn = wx.Button(self, label=_("Remove folder"))
		paths_btn_sizer.Add(add_folder_btn, flag=wx.RIGHT, border=5)
		paths_btn_sizer.Add(remove_folder_btn)
		paths_box.Add(paths_btn_sizer, flag=wx.ALL, border=5)
		settingsSizer.Add(paths_box, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

		types_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("File types")), wx.VERTICAL)
		self._types_listbox = wx.ListBox(self, choices=self._file_types)
		types_box.Add(self._types_listbox, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
		types_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		add_type_btn = wx.Button(self, label=_("Add type"))
		remove_type_btn = wx.Button(self, label=_("Remove type"))
		types_btn_sizer.Add(add_type_btn, flag=wx.RIGHT, border=5)
		types_btn_sizer.Add(remove_type_btn)
		types_box.Add(types_btn_sizer, flag=wx.ALL, border=5)
		settingsSizer.Add(types_box, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

		add_folder_btn.Bind(wx.EVT_BUTTON, self._on_add_folder)
		remove_folder_btn.Bind(wx.EVT_BUTTON, self._on_remove_folder)
		add_type_btn.Bind(wx.EVT_BUTTON, self._on_add_type)
		remove_type_btn.Bind(wx.EVT_BUTTON, self._on_remove_type)

	def _on_add_folder(self, event):
		dlg = wx.DirDialog(self, _("Choose a folder"))
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			if path not in self._paths:
				self._paths.append(path)
				self._paths_listbox.Append(path)
				self._paths_listbox.SetSelection(len(self._paths) - 1)
		dlg.Destroy()

	def _on_remove_folder(self, event):
		idx = self._paths_listbox.GetSelection()
		if idx != wx.NOT_FOUND:
			path = self._paths[idx]
			dlg = wx.MessageDialog(
				self,
				_("Remove folder: {}?").format(path),
				_("Confirm removal"),
				wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
			)
			if dlg.ShowModal() == wx.ID_YES:
				self._paths.pop(idx)
				self._paths_listbox.Delete(idx)
				if self._paths:
					self._paths_listbox.SetSelection(min(idx, len(self._paths) - 1))
			dlg.Destroy()

	def _on_add_type(self, event):
		dlg = wx.TextEntryDialog(self, _("Enter file extension (e.g. md):"), _("Add file type"))
		if dlg.ShowModal() == wx.ID_OK:
			ext = dlg.GetValue().strip().lstrip(".")
			if ext and ext not in self._file_types:
				self._file_types.append(ext)
				self._types_listbox.Append(ext)
				self._types_listbox.SetSelection(len(self._file_types) - 1)
		dlg.Destroy()

	def _on_remove_type(self, event):
		idx = self._types_listbox.GetSelection()
		if idx != wx.NOT_FOUND:
			ext = self._file_types[idx]
			dlg = wx.MessageDialog(
				self,
				_("Remove file type: {}?").format(ext),
				_("Confirm removal"),
				wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
			)
			if dlg.ShowModal() == wx.ID_YES:
				self._file_types.pop(idx)
				self._types_listbox.Delete(idx)
				if self._file_types:
					self._types_listbox.SetSelection(min(idx, len(self._file_types) - 1))
			dlg.Destroy()

	def onSave(self):
		if self.plugin:
			self.plugin.apply_settings(self._paths, self._file_types)
```

- [ ] **Step 3: Register the panel in `GlobalPlugin.__init__`**

In `GlobalPlugin.__init__`, replace the menu-item block (currently lines 159–165):

```python
		self.prefsMenu = gui.mainFrame.sysTrayIcon.preferencesMenu
		self.settingsMenuItem = self.prefsMenu.Append(
			wx.ID_ANY,
			_("Invisinote settings..."),
			_("Configure Invisinote folders and file types"),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_settings, self.settingsMenuItem)
```

with:

```python
		InvisinoteSettingsPanel.plugin = self
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(InvisinoteSettingsPanel)
```

- [ ] **Step 4: Replace `_show_paths_dialog` and `on_settings` with `apply_settings`**

Replace this block (currently lines 283–297 — `_show_paths_dialog` and `on_settings`):

```python
	def _show_paths_dialog(self):
		dlg = SettingsDialog(gui.mainFrame, self.paths, self.fileTypes)
		if dlg.ShowModal() == wx.ID_OK:
			self.paths = dlg.get_paths() or [os.path.join(self.configFolder, "notes")]
			self.currentPathIndex = min(self.currentPathIndex, len(self.paths) - 1)
			self.notesPath = self.paths[self.currentPathIndex]
			with open(self.pathsFile, "w", encoding="utf-8") as f:
				f.write("\n".join(self.paths) + "\n")
			self.fileTypes = dlg.get_file_types() or ["txt"]
			with open(self.fileTypesFile, "w", encoding="utf-8") as f:
				f.write("\n".join(self.fileTypes) + "\n")
		dlg.Destroy()

	def on_settings(self, evt):
		wx.CallAfter(self._show_paths_dialog)
```

with:

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

- [ ] **Step 5: Rewrite `terminate` to deregister the panel**

Replace the current `terminate` (immediately after the block from Step 4, currently lines 299–307):

```python
	def terminate(self):
		try:
			gui.mainFrame.sysTrayIcon.Unbind(
				wx.EVT_MENU, source=self.settingsMenuItem, handler=self.on_settings
			)
			self.prefsMenu.Delete(self.settingsMenuItem)
		except (AttributeError, RuntimeError):
			pass
		super().terminate()
```

with:

```python
	def terminate(self):
		try:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(InvisinoteSettingsPanel)
		except (ValueError, AttributeError):
			pass
		InvisinoteSettingsPanel.plugin = None
		super().terminate()
```

- [ ] **Step 6: Remove the `script_edit_paths` script**

Delete this method (currently lines 279–281, between `script_open_path` and the block replaced in Step 4):

```python
	@script(description=_("Edit paths"))
	def script_edit_paths(self, gesture):
		wx.CallAfter(self._show_paths_dialog)
```

Leave `script_open_path` (above it) intact.

- [ ] **Step 7: Remove the `NVDA+ALT+SHIFT+P` gesture binding**

In the `__gestures` dict, delete this line (currently line 577):

```python
		"kb:NVDA+ALT+SHIFT+P": "edit_paths",
```

Leave `"kb:NVDA+ALT+P": "open_path",` intact.

- [ ] **Step 8: Lint**

Run: `ruff check addon/globalPlugins/invisinote/__init__.py && ruff format --check addon/globalPlugins/invisinote/__init__.py`
Expected: no errors. (If `ruff format --check` reports it would reformat, run `ruff format` on the file and re-check.) In particular, confirm there is no remaining reference to `SettingsDialog`, `_show_paths_dialog`, `on_settings`, `settingsMenuItem`, or `prefsMenu` (ruff F821 would flag undefined names).

- [ ] **Step 9: Run the existing test suite to confirm no regression**

Run: `python -m pytest tests/ -q`
Expected: PASS (7 passed) — the `_window` tests are unaffected; this confirms the module still parses/imports for the test collector.

- [ ] **Step 10: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: move settings into NVDA Settings dialog as Invisinote category"
```

---

### Task 2: Update docs and manually verify in live NVDA

**Files:**
- Modify: `readme.md` (root — the tracked doc source; `addon/doc/en/` is gitignored build output, do not edit it).

**Interfaces:**
- Depends on Task 1 being deployed for the manual verification steps.

- [ ] **Step 1: Remove the settings-shortcut line and add a Settings-dialog note**

In the root `readme.md`, delete this bullet from the gesture list (currently line 7):

```markdown
- NVDA+ALT+SHIFT+P: open settings (also available from the NVDA menu under Preferences > Invisinote settings)
```

Then, immediately after the closing bullet of the gesture list (after the `NVDA+ALT+BACKSPACE` line) and before the `[Update]` link, add a blank line and this sentence:

```markdown
Settings are configured in NVDA's Settings dialog (NVDA+CTRL+S) under the Invisinote category.
```

- [ ] **Step 2: Commit the doc change**

```bash
git add readme.md
git commit -m "docs: settings now live in NVDA Settings under the Invisinote category"
```

- [ ] **Step 3: Deploy to live NVDA and reload**

Follow the `nvda-testing-setup` memory: build/deploy (`scons -c && scons`, or the scratchpad rig), then fully restart NVDA (submodules are cached across `NVDA+CTRL+F3`, so a full restart is safest for a structural change like this).

- [ ] **Step 4: Manually verify the category (screen reader)**

- Press `NVDA+CTRL+S` to open NVDA's Settings dialog.
- Move through the category list; confirm an **"Invisinote"** category is announced.
- Tab into the panel; confirm tab order: Folders list → Add folder → Remove folder → File types list → Add type → Remove type, with the "Folders" and "File types" groups announced.

- [ ] **Step 5: Manually verify save + live pickup**

- Add a folder and a file type, press **OK**.
- Reopen `NVDA+CTRL+S` → Invisinote; confirm the additions persisted.
- Use `NVDA+ALT+[` / `NVDA+ALT+]` and `NVDA+ALT+N` and confirm the new folder/types are reflected in navigation.

- [ ] **Step 6: Manually verify removals**

- Press `NVDA+ALT+SHIFT+P`; confirm nothing happens (gesture removed).
- Press `NVDA+ALT+P`; confirm it still opens the current folder in Explorer.
- Open the NVDA menu (`NVDA+N`) → Preferences; confirm there is **no** standalone "Invisinote settings…" item.

- [ ] **Step 7: Manually verify no duplicate category on reload**

- Press `NVDA+CTRL+F3` to reload plugins.
- Open `NVDA+CTRL+S`; confirm the category list has **exactly one** Invisinote entry.

---

## Self-Review

**Spec coverage:**
- `InvisinoteSettingsPanel` with `title = "Invisinote"` → Task 1 Step 2. ✓
- Two groups + tab order (Folders list/add/remove, File types list/add/remove) → Task 1 Step 2 (verbatim labels). ✓
- `onSave` → `apply_settings` persisting + refreshing live state (preserves folder position, applies defaults) → Task 1 Steps 2 & 4. ✓
- Register in `__init__`, deregister + clear ref in `terminate` (no duplicate on reload) → Task 1 Steps 3 & 5, verified Task 2 Step 7. ✓
- Remove Preferences menu item + `on_settings` → Task 1 Steps 3 & 4. ✓
- Remove `NVDA+ALT+SHIFT+P` + `script_edit_paths`; keep `NVDA+ALT+P` → Task 1 Steps 6 & 7, verified Task 2 Step 6. ✓
- Delete `SettingsDialog` + `_show_paths_dialog` (no dead code) → Task 1 Steps 2 & 4. ✓
- Docs: drop shortcut line, add Settings-dialog note → Task 2 Step 1. ✓
- Config format unchanged → `apply_settings` writes the same files. ✓

**Placeholder scan:** No TBD/TODO; all code shown verbatim. Line-number references are anchors for the exact old_string blocks quoted alongside them.

**Type consistency:** `InvisinoteSettingsPanel.plugin` set in Task 1 Step 3, read in Step 2 (`makeSettings`, `onSave`) and cleared in Step 5. `apply_settings(self, paths, file_types)` defined in Step 4, called from `onSave` in Step 2 with `(self._paths, self._file_types)`. `settingsDialogs` imported in Step 1, used in Steps 2/3/5. Names `_paths`, `_file_types`, `_paths_listbox`, `_types_listbox` consistent across `makeSettings` and the handlers. ✓
