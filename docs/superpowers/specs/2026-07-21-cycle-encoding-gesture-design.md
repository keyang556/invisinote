# Design: Cycle-encoding checklist + NVDA+ALT+E

**Date:** 2026-07-21
**Status:** Approved

## Goal

Replace the single-select "Note encoding" combo box with a checkable list where
the user picks **which encodings to cycle between**, and add a gesture
`NVDA+ALT+E` that cycles the active reading encoding forward through the checked
ones, applying and announcing each change immediately.

Supersedes the combo-box interaction from
`2026-07-21-note-encoding-setting-design.md` (the combo is replaced) and the
earlier full-list cycling idea previously drafted in this file.

## Decisions

- **Control:** a `wx.CheckListBox` labelled **"Cycle encodings"**, replacing the
  combo box, in the same position (last control, after File types). Default: all
  six checked.
- **Two pieces of state:**
  - **Cycle set** — the checked encodings, persisted in a new
    `cycle_encodings.txt`. Edited only via the checklist.
  - **Active encoding** — the codec used by `_read_note_file`, persisted in
    `encoding.txt`. Chosen only by cycling with `NVDA+ALT+E`.
- **Invariant:** the active encoding is always a member of the (non-empty) cycle
  set.
- **Gesture:** `NVDA+ALT+E` cycles the active encoding forward through the
  checked codecs in canonical order, wrapping; persists it, re-reads the current
  note (position resets to its start), announces `"Note encoding: <name>"`.
- **Edge cases:**
  - Unchecking the currently-active encoding then pressing OK resets the active
    to the first checked codec and re-reads the current note. Unchecking other
    encodings leaves the active one and the reading position untouched.
  - Checking none falls back to a cycle set of `["utf-8"]` (and the active
    encoding becomes `utf-8`).
- **Encoding list / order** (unchanged, six entries, no UTF-16): UTF-8 →
  UTF-8 with BOM → Big5 (Traditional Chinese) → GB18030 (Simplified Chinese) →
  Windows-1252 → Latin-1.

## User-facing behaviour (accessibility)

- **Panel:** tab order is Folders (list, Add, Remove) → File types (list, Add,
  Remove) → **Cycle encodings**. The checklist announces
  *"Cycle encodings, <encoding>, check box, checked/not checked, N of 6"*; arrow
  keys move between rows, Space toggles.
- **Gesture:** `NVDA+ALT+E` speaks *"Note encoding: <name>"* for the newly
  selected encoding and re-reads the current note. Repeated presses cycle
  through the checked encodings; if only one is checked it re-announces and
  re-reads that one. Reassignable via NVDA's Input Gestures dialog
  (description "Cycle note encoding").

## Implementation

All changes in `addon/globalPlugins/invisinote/__init__.py`.

### Shared helpers (module level)

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

### Config state (`GlobalPlugin`)

- `__init__`: keep `self.encoding` / `self.encodingFile` / `self._load_encoding()`.
  Add `self.cycleEncodings = []`,
  `self.cycleEncodingsFile = os.path.join(self.configFolder, "cycle_encodings.txt")`,
  `self._load_cycle_encodings()`, then `self._clamp_active_encoding()`.
- `_load_cycle_encodings(self)`: known = codecs from `_note_encodings()` in
  canonical order. If the file exists, read the set of stored codec names and set
  `self.cycleEncodings = [c for c in known if c in stored] or list(known)`.
  Otherwise `self.cycleEncodings = list(known)` (all six).
- `_clamp_active_encoding(self)`: if `self.encoding not in self.cycleEncodings`,
  set `self.encoding = self.cycleEncodings[0] if self.cycleEncodings else "utf-8"`.
- `_persist_encoding(self)`: write `self.encoding` to `encoding.txt`.
- `_persist_cycle_encodings(self)`: write `self.cycleEncodings` (one codec per
  line) to `cycle_encodings.txt`.

### `apply_settings`

Signature becomes `apply_settings(self, paths, file_types, cycle_encodings)`.
After persisting paths and file types (unchanged):

```python
	self.cycleEncodings = list(cycle_encodings) or ["utf-8"]
	self._persist_cycle_encodings()
	previous = self.encoding
	self._clamp_active_encoding()
	if self.encoding != previous:
		self._persist_encoding()
		if self.notes:
			self._load_current_note_lines()
```

### `_read_note_file`

Unchanged from the note-encoding feature (reads with `self.encoding`, falls back
to `latin-1` on `UnicodeDecodeError` / `LookupError`).

### Panel (`InvisinoteSettingsPanel`)

- `makeSettings`: replace the combo block with a checklist:
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
- `onSave`: pass the checked codecs:
  ```python
  checked = [self._encoding_codecs[i] for i in self._cycle_list.GetCheckedItems()]
  self.plugin.apply_settings(self._paths, self._file_types, checked)
  ```

### New script

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

### Gesture binding

Add to `__gestures`: `"kb:NVDA+ALT+E": "cycle_encoding"`.

### Documentation

- Add `- NVDA+ALT+E: cycle note encoding` to the gesture list in root
  `readme.md` and to `buildVars.py`'s `addon_description`.

## Out of scope

- No reverse-cycle gesture.
- No direct "set active encoding" control (active is chosen only by cycling).
- No change to `_read_note_file`, the render path, or the paths/filetypes config.

## Testing

`__init__.py` imports NVDA runtime modules and cannot be unit-tested outside
NVDA. Automated gates: `ruff check` / `ruff format --check`,
`python -m pytest tests/`. Manual verification in live NVDA using the
encoding-test folder:

- Panel: the "Cycle encodings" checklist is the last control, all six checked by
  default, announces check state, Space toggles.
- `NVDA+ALT+E` on `big5.txt`: each press announces *"Note encoding: <name>"*
  through the checked encodings; on Big5 the note reads correctly; wrap-around
  returns to the first checked after the last.
- Uncheck all but UTF-8 and Big5, OK: `NVDA+ALT+E` now only alternates between
  those two.
- Cycle to Big5, reopen settings, uncheck Big5, OK: active resets to the first
  checked encoding and the note re-reads.
- Choices persist across an NVDA restart (`encoding.txt` +
  `cycle_encodings.txt`).
