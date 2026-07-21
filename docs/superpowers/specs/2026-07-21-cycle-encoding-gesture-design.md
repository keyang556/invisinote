# Design: NVDA+ALT+E — cycle note encoding

**Date:** 2026-07-21
**Status:** Approved

## Goal

Add a keyboard gesture, `NVDA+ALT+E`, that cycles the note encoding forward
through the same list offered by the settings combo box, applying and announcing
the change immediately — so a user can fix a garbled note without opening the
Settings dialog.

Builds on `2026-07-21-note-encoding-setting-design.md`.

## Decisions

- **Gesture:** `NVDA+ALT+E` (currently unbound). Forward-cycling with wrap-around.
- **Order:** the same six entries as the combo, in the same order: UTF-8 →
  UTF-8 with BOM → Big5 → GB18030 → Windows-1252 → Latin-1 → (wrap) UTF-8.
- **Apply timing:** persist to `encoding.txt` and re-read the current note
  immediately (position resets to the note's start), matching the settings
  dialog's reread-on-OK.
- **Announcement:** `"Note encoding: <name>"`, e.g.
  *"Note encoding: Big5 (Traditional Chinese)"*.
- **Unknown stored value:** if `self.encoding` is not in the list (e.g. a
  hand-edited `encoding.txt`), the first press selects the first entry (UTF-8).

## User-facing behaviour (accessibility)

- Pressing `NVDA+ALT+E` speaks *"Note encoding: <name>"* for the newly selected
  encoding. Repeated presses cycle through all six, announcing each.
- When the cycle reaches the encoding that matches the current note's on-disk
  encoding, the note (re-read on each press) reads correctly. The reread resets
  the reading position to the start of the current note and clears any selection.
- No new visual UI; this is a gesture only. The gesture is reassignable via
  NVDA's Input Gestures dialog (it carries the description "Cycle note
  encoding").

## Implementation

All changes in `addon/globalPlugins/invisinote/__init__.py`.

### Shared encoding list

- Extract the encoding table to a module-level function `_note_encodings()`
  returning a list of `(label, codec)` pairs in display/cycle order, with each
  label wrapped in `_()` at call time (so translation reflects the current
  language, as today):
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
  ```
- `InvisinoteSettingsPanel.makeSettings` uses `encodings = _note_encodings()`
  instead of the inline list. `labels` and `self._encoding_codecs` are derived
  from it exactly as now.

### Shared persistence helper

- Extract the one-line `encoding.txt` write to `GlobalPlugin._persist_encoding`:
  ```python
  def _persist_encoding(self):
  	with open(self.encodingFile, "w", encoding="utf-8") as f:
  		f.write(self.encoding + "\n")
  ```
- `apply_settings` calls `self._persist_encoding()` in place of its inline write
  (behaviour unchanged).

### New script

```python
@script(description=_("Cycle note encoding"))
def script_cycle_encoding(self, gesture):
	encodings = _note_encodings()
	codecs = [e[1] for e in encodings]
	idx = codecs.index(self.encoding) + 1 if self.encoding in codecs else 0
	idx %= len(encodings)
	label, codec = encodings[idx]
	self.encoding = codec
	self._persist_encoding()
	if self.notes:
		self._load_current_note_lines()
	ui.message(_("Note encoding: {}").format(label))
```

### Gesture binding

- Add to `__gestures`: `"kb:NVDA+ALT+E": "cycle_encoding"`.

### Documentation

- Add `- NVDA+ALT+E: cycle note encoding` to the gesture list in the root
  `readme.md` and to `buildVars.py`'s `addon_description` (both are user-facing
  surfaces; `addon/doc/en/` is gitignored build output regenerated from
  `readme.md`).

## Out of scope

- No reverse-cycle gesture (single forward key with wrap).
- No change to the combo box, `_read_note_file`, or config formats.

## Testing

`__init__.py` imports NVDA runtime modules and cannot be unit-tested outside
NVDA; the pytest suite only covers `_window`. Automated gates: `ruff check` /
`ruff format --check`, `python -m pytest tests/`. Manual verification in live
NVDA using the encoding-test folder:

- On `big5.txt` (garbled under UTF-8), press `NVDA+ALT+E` and confirm each press
  announces *"Note encoding: <name>"* through all six; on **Big5 (Traditional
  Chinese)** the note reads correctly.
- Confirm wrap-around returns to UTF-8 after Latin-1.
- Confirm the chosen encoding persists (visible in the settings combo, and
  across an NVDA restart via `encoding.txt`).
- Confirm the settings combo still works unchanged (shared `_note_encodings`).
