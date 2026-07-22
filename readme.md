# Invisinote

Invisinote is an NVDA add-on for reading plain-text notes without leaving the
application you are working in. No window opens and focus never moves: the notes
are loaded into memory and you browse them entirely with keyboard gestures,
while the app you are in keeps the focus.

## Getting started

1. Open NVDA's Settings dialog and choose the **Invisinote**
   category, or press NVDA+ALT+SHIFT+P from anywhere.
2. Add one or more folders that contain your notes, and the file extensions to
   read (`txt` by default).
3. Press NVDA+ALT+N to load the notes in the current folder. NVDA announces how
   many notes were found.
4. Move between notes with NVDA+ALT+U and NVDA+ALT+O, then read line by line,
   word by word, or character by character with the gestures below.

Notes are read in sorted filename order. Loading again (NVDA+ALT+N) picks up
files you have added or changed since.

## Gestures

### Folders and notes

* NVDA+ALT+SHIFT+P: open the Invisinote settings
* NVDA+ALT+P: open the current folder in File Explorer
* NVDA+ALT+\[: previous folder
* NVDA+ALT+]: next folder
* NVDA+ALT+N: load the notes in the current folder
* NVDA+ALT+U: previous note
* NVDA+ALT+O: next note

### Reading

* NVDA+ALT+SHIFT+A: read the whole note
* NVDA+ALT+I: previous line
* NVDA+ALT+K: next line
* NVDA+ALT+J: previous word
* NVDA+ALT+L: next word
* NVDA+ALT+,: previous character
* NVDA+ALT+.: next character
* NVDA+ALT+H: start of line
* NVDA+ALT+': end of line
* NVDA+ALT+Space: render the note as Markdown and read it in a browse-mode
  window

### Copying

* NVDA+ALT+A: copy the whole note
* NVDA+ALT+;: copy the current line
* NVDA+ALT+F9: set the selection start at the current position
* NVDA+ALT+F10: set the selection end; press twice to copy the selection
* NVDA+ALT+BACKSPACE: clear the selection markers

### Encoding

* NVDA+ALT+E: switch to the next note encoding
* NVDA+ALT+SHIFT+E: switch to the previous note encoding

Moving to another note resets the line, word and character position. Moving
between lines resets the word and character position. Any movement that is not a
selection command clears the selection markers.

## Settings

Settings live in NVDA's Settings dialog under the **Invisinote**
category, and NVDA+ALT+SHIFT+P opens that category directly.

* **Folders** — the folders Invisinote reads notes from. Move between them with
  NVDA+ALT+\[ and NVDA+ALT+].
* **File types** — the extensions treated as notes, for example `txt` or `md`.
* **Cycle encodings** — the encodings NVDA+ALT+E and NVDA+ALT+SHIFT+E step
  through. Uncheck the ones you never use so cycling stays short. If the active
  encoding is unchecked, Invisinote falls back to the first one still enabled.

Available encodings are UTF-8, UTF-8 with BOM, Big5 (Traditional Chinese),
GB18030 (Simplified Chinese), Windows-1252 and Latin-1. If a note cannot be
decoded with the active encoding, it is re-read as Latin-1 so that reading never
fails outright.

## About this project

Invisinote is an open-source NVDA add-on, licensed under the GNU GPL v2.

* Repository: <https://github.com/ClippyCat/invisinote>
* Author: ClippyCat
* Issues and feature requests: <https://github.com/ClippyCat/invisinote/issues>

The add-on is built with SCons; see `CLAUDE.md` in the repository for build and
development notes. Contributions and translations are welcome — new languages go
in `addon/locale/<lang>/LC_MESSAGES/nvda.po`.
