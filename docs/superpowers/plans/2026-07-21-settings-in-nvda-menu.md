# Settings in the NVDA Menu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Invisinote settings..." item to NVDA's Preferences submenu that opens the existing settings dialog, while keeping the `NVDA+ALT+SHIFT+P` shortcut.

**Architecture:** In `GlobalPlugin`, register a menu item on `gui.mainFrame.sysTrayIcon.preferencesMenu` during `__init__`, bind it to a handler that reuses the existing `_show_paths_dialog`, and add a `terminate()` that removes the item so plugin reloads don't leave duplicates.

**Tech Stack:** Python 3.11, wxPython (NVDA's bundled `wx`), NVDA `gui` module.

## Global Constraints

- Code style: tabs for indentation, max line length 110 (ruff via `pyproject.toml`).
- Translation builtins `_`, `ngettext`, `pgettext`, `npgettext` are available — never import them. All user-visible strings wrapped in `_()`.
- Do not rewrite git history.
- WCAG 2.2 AAA / NVDA menu conventions: settings item lives in the **Preferences** submenu, labelled with a trailing ellipsis, with a help string.
- Menu label verbatim: `Invisinote settings...`
- Help/status string verbatim: `Configure Invisinote folders and file types`
- The entire add-on logic lives in `addon/globalPlugins/invisinote/__init__.py`.

## Note on testing

`__init__.py` imports NVDA runtime modules (`ui`, `api`, `gui`, `globalPluginHandler`, `wx`) that do not exist outside a running NVDA, so this change **cannot** be covered by the pytest/unittest suite (which only exercises the NVDA-free `_window` module). Verification is manual in the live NVDA rig described in the `nvda-testing-setup` memory. Do not add a unittest for the menu wiring — it would not import.

---

### Task 1: Add the Preferences menu item, handler, and cleanup

**Files:**
- Modify: `addon/globalPlugins/invisinote/__init__.py` — `GlobalPlugin.__init__` (ends line 158), add `on_settings` and `terminate` methods.

**Interfaces:**
- Consumes: existing `self._show_paths_dialog(self)` method (constructs and shows `SettingsDialog`, persists results) — unchanged.
- Consumes: `gui.mainFrame.sysTrayIcon.preferencesMenu` (a `wx.Menu`) and `gui.mainFrame.sysTrayIcon` (binds `wx.EVT_MENU`).
- Produces: `self.prefsMenu` (`wx.Menu`) and `self.settingsMenuItem` (`wx.MenuItem`) instance attributes; `on_settings(self, evt)` and `terminate(self)` methods.

- [ ] **Step 1: Register the menu item at the end of `__init__`**

In `addon/globalPlugins/invisinote/__init__.py`, immediately after the existing last two lines of `__init__`:

```python
		self._load_paths()
		self._load_file_types()
```

append:

```python
		self.prefsMenu = gui.mainFrame.sysTrayIcon.preferencesMenu
		self.settingsMenuItem = self.prefsMenu.Append(
			wx.ID_ANY,
			_("Invisinote settings..."),
			_("Configure Invisinote folders and file types"),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_settings, self.settingsMenuItem)
```

- [ ] **Step 2: Add the `on_settings` handler**

Add this method to `GlobalPlugin` (place it directly after `_show_paths_dialog`, which ends at line 287):

```python
	def on_settings(self, evt):
		wx.CallAfter(self._show_paths_dialog)
```

- [ ] **Step 3: Add `terminate` to remove the menu item on reload**

Add this method to `GlobalPlugin` (place it directly after `on_settings`):

```python
	def terminate(self):
		try:
			self.prefsMenu.Remove(self.settingsMenuItem)
		except (AttributeError, RuntimeError):
			pass
		super().terminate()
```

- [ ] **Step 4: Lint**

Run: `ruff check addon/globalPlugins/invisinote/__init__.py && ruff format --check addon/globalPlugins/invisinote/__init__.py`
Expected: no errors. (If `ruff format --check` reports the file would be reformatted, run `ruff format` on it and re-check.)

- [ ] **Step 5: Run the existing test suite to confirm no regression**

Run: `python -m pytest tests/ -q`
Expected: PASS (the `_window` tests are unaffected; this confirms the change did not break the build path).

- [ ] **Step 6: Commit**

```bash
git add addon/globalPlugins/invisinote/__init__.py
git commit -m "feat: add Invisinote settings to the NVDA Preferences menu"
```

---

### Task 2: Document the menu location and manually verify in live NVDA

**Files:**
- Modify: `addon/doc/en/readme.md` (or the equivalent user doc that describes the `NVDA+ALT+SHIFT+P` shortcut — confirm exact path first).

**Interfaces:**
- Consumes: nothing from Task 1's code; depends on Task 1 being deployed for the manual verification steps.

- [ ] **Step 1: Locate the doc line describing the settings shortcut**

Run: `grep -rn "ALT+SHIFT+P" addon/doc`
Expected: one or more matches naming the settings/paths shortcut. Note the file and line.

- [ ] **Step 2: Add a sentence noting the menu location**

Immediately after the sentence describing the `NVDA+ALT+SHIFT+P` shortcut, add (matching the surrounding markdown style):

```markdown
The settings can also be opened from the NVDA menu under Preferences → Invisinote settings.
```

- [ ] **Step 3: Deploy to live NVDA and reload**

Follow the `nvda-testing-setup` memory: build/deploy (`scons -c && scons`, or the scratchpad rig), then fully restart NVDA (or `NVDA+CTRL+F3` to reload plugins) so the new plugin code loads.

- [ ] **Step 4: Manually verify the menu item (screen reader)**

- Open the NVDA menu (`NVDA+N`), arrow to **Preferences**, arrow into the submenu.
- Confirm NVDA announces an item **"Invisinote settings…"** and its help text **"Configure Invisinote folders and file types"**.
- Press Enter and confirm the settings dialog opens (same dialog as the shortcut).

- [ ] **Step 5: Manually verify the shortcut still works**

- Press `NVDA+ALT+SHIFT+P` and confirm the same settings dialog opens.

- [ ] **Step 6: Manually verify no duplicate after reload**

- Press `NVDA+CTRL+F3` to reload plugins.
- Reopen NVDA menu → Preferences and confirm there is **exactly one** "Invisinote settings…" item (no duplicate).

- [ ] **Step 7: Commit**

```bash
git add addon/doc
git commit -m "docs: note NVDA Preferences menu entry for settings"
```

---

## Self-Review

**Spec coverage:**
- Preferences submenu placement → Task 1 Step 1. ✓
- Label `Invisinote settings...` + help string → Task 1 Step 1 (verbatim). ✓
- `on_settings` reuses `_show_paths_dialog` → Task 1 Step 2. ✓
- `terminate()` prevents duplicate on reload → Task 1 Step 3, verified Task 2 Step 6. ✓
- Keep `NVDA+ALT+SHIFT+P` (no change to `script_edit_paths`) → not touched; verified Task 2 Step 5. ✓
- `SettingsDialog`/config unchanged → not touched. ✓
- Docs get one added line → Task 2 Steps 1–2. ✓
- Announcement/focus verification → Task 2 Step 4. ✓

**Placeholder scan:** No TBD/TODO; all code and strings shown verbatim. The one "confirm exact path" (Task 2 Step 1) is a grep with expected output, not a placeholder.

**Type consistency:** `self.prefsMenu` / `self.settingsMenuItem` defined in Task 1 Step 1 and used in Task 1 Step 3; `_show_paths_dialog` name matches the existing method; `on_settings(self, evt)` signature consistent with its `wx.EVT_MENU` binding. ✓
