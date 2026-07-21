# Design: Invisinote settings in the NVDA menu

**Date:** 2026-07-21
**Status:** Approved

## Goal

Make the Invisinote settings dialog reachable from the NVDA menu, in addition to
the existing keyboard shortcut. Today the dialog is only reachable via the
`NVDA+ALT+SHIFT+P` gesture, which is not discoverable for a user browsing the
menu.

## Decisions

- **Menu location:** NVDA menu → **Preferences** submenu. Preferences is the
  conventional home for add-on configuration and where a screen reader user
  expects to find settings. (Tools is for actions/commands; top-level is
  discouraged.)
- **Keyboard shortcut:** `NVDA+ALT+SHIFT+P` is **kept**. Both the menu item and
  the gesture open the same dialog. The gesture remains reassignable via NVDA's
  Input Gestures dialog.

## User-facing behaviour (accessibility)

- A single menu item labelled **`Invisinote settings...`** is added to the
  Preferences submenu. The trailing ellipsis is the NVDA/Windows convention
  signalling that the item opens a dialog.
- The item carries a help/status string: **`Configure Invisinote folders and
  file types`**, which NVDA announces alongside the item.
- **Announcement / focus:** Arrowing into Preferences and onto the item, NVDA
  reads *"Invisinote settings…"* plus the help text. Pressing Enter opens the
  existing `SettingsDialog` with the same focus behaviour as the shortcut — no
  change to the dialog itself.

## Implementation

All changes are in `addon/globalPlugins/invisinote/__init__.py`,
in the `GlobalPlugin` class.

1. **`__init__`** — after config loads:
   - `prefsMenu = gui.mainFrame.sysTrayIcon.preferencesMenu`
   - `self.settingsMenuItem = prefsMenu.Append(wx.ID_ANY, _("Invisinote settings..."), _("Configure Invisinote folders and file types"))`
   - `gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_settings, self.settingsMenuItem)`
   - Store `self.prefsMenu = prefsMenu` for cleanup.

2. **`on_settings(self, evt)`** — new handler:
   - `wx.CallAfter(self._show_paths_dialog)` — reuses the existing method so there
     is a single code path for showing the dialog.

3. **`terminate(self)`** — new method (the class has none today):
   - Remove the menu item, guarded by `try/except`, so NVDA plugin reloads
     (`NVDA+CTRL+F3`) do not accumulate duplicate menu items.
   - Call `super().terminate()`.

4. **`_show_paths_dialog`** — unchanged; already the single method that
   constructs and shows `SettingsDialog` and persists results.

## Out of scope

- No change to `SettingsDialog`, the `script_edit_paths` gesture handler, config
  loading/saving, or navigation state.
- Documentation gets one added line noting the menu location; the existing
  description of the `NVDA+ALT+SHIFT+P` shortcut stays.

## Testing

- Manual (live NVDA per the testing rig): open NVDA menu → Preferences, confirm
  the item is announced with its help text, and Enter opens the dialog.
- Confirm the shortcut still opens the dialog.
- Reload plugins (`NVDA+CTRL+F3`) and confirm the Preferences submenu still has
  exactly one Invisinote item (no duplicate).
