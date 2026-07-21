# Design: Invisinote as an NVDA Settings category

**Date:** 2026-07-21
**Status:** Approved

## Goal

Move Invisinote's configuration out of a standalone dialog and into NVDA's
built-in Settings dialog as a category named **Invisinote** (reached via
Preferences → Settings…, or `NVDA+CTRL+S`). Remove the standalone Preferences
menu item and the `NVDA+ALT+SHIFT+P` shortcut.

This supersedes the previous change
(`2026-07-21-settings-in-nvda-menu-design.md`), which added a standalone
"Invisinote settings..." item to the Preferences menu. That menu item is
removed here.

## Decisions

- **Integration:** Convert the config UI into a `gui.settingsDialogs.SettingsPanel`
  subclass registered as a category in NVDA's Settings dialog. (Confirmed over
  keeping a standalone dialog.)
- **Category name:** `Invisinote` (the `title` attribute).
- **Old Preferences menu item:** removed — config is reached only via the
  Settings category.
- **Shortcut:** `NVDA+ALT+SHIFT+P` (Edit paths) removed. `NVDA+ALT+P` (open
  path, opens the folder in Explorer) is kept.
- **Panel tab order:** Folders (list, Add folder, Remove folder) then File
  types (list, Add type, Remove type) — unchanged from the current dialog.

## User-facing behaviour (accessibility)

- **Arrival:** `NVDA+CTRL+S` (or Preferences → Settings…) opens NVDA's Settings
  dialog. Focus lands in the category list (reopening on the last-used
  category). Arrowing onto **"Invisinote"** announces the category and shows its
  panel.
- **Tab order inside the panel:** Folders list box → Add folder → Remove folder
  → File types list box → Add type → Remove type. The StaticBox group names
  ("Folders", "File types") are announced on entry.
- **Save/cancel:** the Settings dialog's shared **OK / Apply / Cancel**. OK and
  Apply invoke every category's save handler (so Invisinote saves with them);
  Cancel discards. There is no Invisinote-specific OK button.

## Implementation

All changes are in `addon/globalPlugins/invisinote/__init__.py`.

### New: `InvisinoteSettingsPanel(gui.settingsDialogs.SettingsPanel)`

- `title = _("Invisinote")`.
- Holds a reference to the running `GlobalPlugin` instance (set by the plugin at
  registration time) so it can read current values and persist changes.
- `makeSettings(self, settingsSizer)`:
  - Working copies: `self._paths = list(plugin.paths)`,
    `self._file_types = list(plugin.fileTypes)`.
  - Build the two StaticBox groups (Folders, File types), each with a
    `wx.ListBox` and Add/Remove buttons, added to `settingsSizer`. Parent is the
    panel (`self`).
  - Bind the four buttons to the add/remove handlers.
- Add/Remove handlers (`_on_add_folder`, `_on_remove_folder`, `_on_add_type`,
  `_on_remove_type`): moved essentially verbatim from the old `SettingsDialog`;
  they mutate the working copies and the list boxes, with the same confirmation
  dialogs on removal.
- `onSave(self)`: calls `plugin.apply_settings(self._paths, self._file_types)`.
  Guarded if the plugin reference is missing.

### `GlobalPlugin` changes

- New method `apply_settings(self, paths, file_types)` — the persistence logic
  lifted from the old `_show_paths_dialog` OK branch, verbatim in effect:
  ```python
  self.paths = paths or [os.path.join(self.configFolder, "notes")]
  self.currentPathIndex = min(self.currentPathIndex, len(self.paths) - 1)
  self.notesPath = self.paths[self.currentPathIndex]
  # write self.pathsFile
  self.fileTypes = file_types or ["txt"]
  # write self.fileTypesFile
  ```
  This preserves current behaviour: the current folder position is kept if still
  valid; defaults are applied if a list is emptied.
- `__init__`: remove the Preferences menu-item registration (`Append` + `Bind`);
  instead set the panel's plugin reference and
  `gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(InvisinoteSettingsPanel)`.
- `terminate()`: remove the menu-item cleanup; instead remove the panel from
  `categoryClasses` (guarded by try/except) and clear the plugin reference, then
  `super().terminate()`. This prevents duplicate categories across plugin
  reloads.

### Removals

- Preferences menu item and the `on_settings` handler.
- `NVDA+ALT+SHIFT+P` entry in `__gestures` and the `script_edit_paths` method.
- The standalone `SettingsDialog` class and `_show_paths_dialog` (fully
  replaced; no dead code).

### Documentation

- `readme.md` (root, the tracked source; `addon/doc/en/` is gitignored build
  output): remove the `NVDA+ALT+SHIFT+P: open settings` line and add a note that
  settings live in NVDA's Settings dialog under the Invisinote category.

## Out of scope

- No change to navigation state, note loading, markdown rendering, or any other
  gesture.
- No change to the on-disk config format (`paths.txt`, `filetypes.txt`).

## Testing

`__init__.py` imports NVDA runtime modules and cannot be imported/unit-tested
outside NVDA; the pytest suite only covers the NVDA-free `_window` module.
Automated gates: `ruff check` / `ruff format --check`, and `python -m pytest
tests/`. Manual verification in live NVDA:

- `NVDA+CTRL+S` → category list contains **Invisinote**; arrowing onto it is
  announced; Tab order is Folders (list, add, remove) then File types (list,
  add, remove).
- Add/remove a folder and a file type, press OK, reopen Settings → changes
  persisted; live navigation (`NVDA+ALT+[` / `]`, `NVDA+ALT+N`) reflects the new
  folders/types.
- `NVDA+ALT+SHIFT+P` no longer does anything; `NVDA+ALT+P` still opens the
  folder.
- Preferences menu no longer has a standalone "Invisinote settings…" item.
- Reload plugins (`NVDA+CTRL+F3`); the Settings category list has exactly one
  Invisinote entry (no duplicate).
