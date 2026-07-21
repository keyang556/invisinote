# Design: "Note encoding" setting

**Date:** 2026-07-21
**Status:** Approved

## Goal

Let the user choose the text encoding used to read note files, so notes saved
in non-UTF-8 encodings (notably Traditional Chinese / Big5 and Simplified
Chinese / GB18030) read correctly instead of appearing garbled. Adds a
"Note encoding" control to the existing Invisinote settings category.

Builds on `2026-07-21-invisinote-settings-category-design.md` (the
`InvisinoteSettingsPanel`).

## Problem being solved

`_read_note_file` currently reads UTF-8 and, on `UnicodeDecodeError`, falls back
to `latin-1`. `latin-1` decodes any byte sequence without error, so a Big5- or
GB18030-encoded note is silently turned into mojibake rather than read
correctly. A user-selectable primary encoding fixes this.

## Decisions

- **Control:** a combo box (`wx.Choice`) labelled **"Note encoding"**, added via
  `guiHelper.addLabeledControl` so NVDA announces the label with the control.
- **Placement / tab order:** after the File types group, i.e. Folders (list,
  Add, Remove) → File types (list, Add, Remove) → **Note encoding**.
- **Encoding list** (label → Python codec), default **UTF-8**:
  | Label | Codec |
  |---|---|
  | UTF-8 | `utf-8` |
  | UTF-8 with BOM | `utf-8-sig` |
  | UTF-16 | `utf-16` |
  | Big5 (Traditional Chinese) | `big5` |
  | GB18030 (Simplified Chinese) | `gb18030` |
  | Windows-1252 | `cp1252` |
  | Latin-1 | `latin-1` |
- **Apply timing:** on **OK/Apply**, if the encoding changed, re-read the
  currently open note immediately with the new encoding (position resets to the
  start of that note; selection cleared). Subsequent note loads use the new
  encoding automatically.
- **Fallback retained:** `latin-1` stays as a guaranteed fallback so an
  unreadable byte sequence or an unknown codec name never crashes reading.

## User-facing behaviour (accessibility)

- Entering the Invisinote category and tabbing to the end reaches **Note
  encoding**, announced as *"Note encoding, combo box, <current value>"* (e.g.
  "UTF-8"). Arrowing moves through the seven entries, each announced.
- After changing it and pressing OK: if the encoding changed, the current note
  is re-decoded and reading resumes from that note's first line. (No live-region
  announcement is added; navigating/reading the note surfaces the corrected
  text.)

## Implementation

All changes in `addon/globalPlugins/invisinote/__init__.py`.

### Config state (`GlobalPlugin`)

- `__init__`: add `self.encoding = "utf-8"`,
  `self.encodingFile = os.path.join(self.configFolder, "encoding.txt")`, and
  call a new `self._load_encoding()` (after the existing `_load_*` calls).
- `_load_encoding(self)`: if `encoding.txt` exists, read the stripped codec name
  and, if non-empty, store it in `self.encoding`. (No validation here; an
  invalid name is handled at read time by the fallback.)

### Reading (`_read_note_file`)

```python
def _read_note_file(self, path):
	try:
		with open(path, "r", encoding=self.encoding) as f:
			return f.read()
	except (UnicodeDecodeError, LookupError):
		with open(path, "r", encoding="latin-1") as f:
			return f.read()
```

### Persistence + apply (`apply_settings`)

- Extend the signature to `apply_settings(self, paths, file_types, encoding)`.
- After persisting paths and file types (unchanged), compute
  `encoding_changed = encoding != self.encoding`, set
  `self.encoding = encoding or "utf-8"`, write it to `encoding.txt` (`utf-8`
  file, codec name + newline).
- If `encoding_changed and self.notes`, call `self._load_current_note_lines()`
  to re-decode the current note (resets to its start).

### Panel (`InvisinoteSettingsPanel`)

- `makeSettings`: after building the Folders and File types groups, build the
  encoding combo via `guiHelper`:
  - Define parallel lists of labels and codecs (the table above).
  - `self._encoding_codecs = [codec, ...]`.
  - `self._encoding_choice = sHelper.addLabeledControl(_("Note encoding"), wx.Choice, choices=labels)`
    where `sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)`.
  - Select the index of `plugin.encoding` in the codec list; if not present,
    select index 0 (UTF-8).
- `onSave`: pass the selected codec —
  `plugin.apply_settings(self._paths, self._file_types, self._encoding_codecs[self._encoding_choice.GetSelection()])`.
  Guard as today when `plugin` is missing.

### Imports

- Add `from gui import guiHelper` (alongside `from gui import settingsDialogs`).

## Out of scope

- No change to markdown rendering (encoding affects only reading the file bytes).
- No new dependency; no true charset auto-detection.
- No change to the `paths.txt` / `filetypes.txt` formats.

## Testing

`__init__.py` imports NVDA runtime modules and cannot be unit-tested outside
NVDA; the pytest suite only covers `_window`. Automated gates: `ruff check` /
`ruff format --check`, `python -m pytest tests/`. Manual verification in live
NVDA:

- Create a note saved as Big5 with Traditional Chinese text; with encoding
  UTF-8 it reads garbled; set **Note encoding → Big5 (Traditional Chinese)**,
  OK; the current note re-reads correctly from its start.
- Repeat with a GB18030 Simplified-Chinese note.
- Confirm the combo announces "Note encoding, combo box, <value>" and is the
  last control in tab order.
- Confirm a normal UTF-8 note is unaffected (default UTF-8).
- Confirm the choice persists across an NVDA restart (`encoding.txt` written).
