# Render current note as markdown — design

**Date:** 2026-05-26
**Status:** Approved, ready for implementation planning

## Summary

Add a command to the Invisinote NVDA add-on that renders the current note's
markdown source to HTML and opens it in NVDA's browse-mode virtual buffer, so a
screen reader user can read the note with full quick-navigation (headings,
links, lists, tables) instead of the flat line-by-line model. The existing
in-app navigation is left untouched.

## Trigger & scope

- New script method `script_render_markdown` on `GlobalPlugin`.
- Bound to **NVDA+ALT+Space** (currently unbound — no conflict with existing
  gestures).
- Operates on the **current note** (`self.notes[self.currentNoteIndex]`) using
  the already-loaded `currentNoteLines`. Raw text obtained via the existing
  `_get_current_note_content()`.
- One-shot command. It does **not** mutate any navigation state
  (note/line/word/char index, selection anchors) and does **not** introduce a
  persistent setting or toggle.

## Interaction flow & what gets announced

- On press, the script calls
  `ui.browseableMessage(html, title=<note filename>, isHtml=True)`.
- NVDA opens a dialog containing a browse-mode virtual document.
  - **First announced on arrival:** the dialog title, which is the note's
    filename.
  - Browse mode is then active from the top of the document.
- **Top anchor:** title only. The document body begins directly with the note's
  own rendered content — **no synthetic heading is injected**. The note's own
  first `#` heading remains the top of the outline; heading levels are preserved
  exactly as written.
- Quick-navigation behaves as in any web document: `H` / `1`–`6` for headings,
  `K` for links, `L` for lists, arrows by line/element.
- **Escape** closes the buffer and returns focus to the application the user was
  in. (Standard NVDA browseableMessage behaviour; nothing custom required.)

### Edge cases

- **Empty note or no notes loaded:** announce `_("Empty note")` via
  `ui.message` and do **not** open an empty buffer. This mirrors the existing
  `script_read_note` behaviour (`_get_current_note_content()` returns `None`).
- **Defensive — markdown import failure:** if `import markdown` fails for any
  reason, announce `_("Markdown rendering unavailable")` rather than raising.
  (Should not occur given the library is vendored, but the command must never
  throw into NVDA.)

## Conversion

- Use the vendored Python-Markdown: `markdown.markdown(text, extensions=[...])`.
- Extensions are referenced by **full dotted module path**, not short names:
  - `"markdown.extensions.fenced_code"` — fenced code blocks (```` ``` ````).
  - `"markdown.extensions.tables"` — pipe tables, navigable in browse mode.
  - `"markdown.extensions.sane_lists"` — well-behaved ordered/unordered lists.
  - Rationale: Python-Markdown resolves short extension names
    (e.g. `"tables"`) via `importlib.metadata` entry points, which are not
    registered for a vendored copy lacking installed dist metadata. The dotted
    module path is imported directly and so works without entry points.
- Built-in (no-extension) behaviour already covers headings (`h1`–`h6`),
  paragraphs, lists, blockquotes, emphasis (`em`/`strong`), inline code,
  indented code blocks, horizontal rules, links, and images — i.e. all the
  quick-nav-relevant semantics.
- The rendered HTML fragment is passed directly to `browseableMessage`; NVDA
  supplies the surrounding document. No manual `<html>`/`<head>` wrapper.

## Vendoring & build

- Install Python-Markdown into `addon/globalPlugins/invisinote/_vendor/`
  (e.g. `pip install markdown --target addon/globalPlugins/invisinote/_vendor`),
  yielding the `markdown/` package directory. Pure-Python with no runtime
  dependencies on Python 3.11 (NVDA's interpreter).
- At module load time, prepend the `_vendor` directory to `sys.path` exactly
  once (guarded against duplicate insertion) so `import markdown` resolves to
  the vendored copy, then `import markdown`.
- **Packaging:** automatic. `createAddonBundleFromPath` in `sconstruct` walks
  the entire `addon/` tree and zips everything, so the vendored files ship with
  no `sconstruct` or `buildVars` build-logic change.
- `pythonSources = ["addon/globalPlugins/*.py"]` is used only for translation
  extraction and SCons dependency tracking — not packaging — so the vendored
  library is **not** scanned into the `.pot`.
- **License:** Python-Markdown is BSD-licensed (GPL-2 compatible). Keep its
  `LICENSE.md` inside the vendored `markdown/` directory.

## Docs, strings, version

- All new user-visible strings wrapped in `_()` (the `_` builtin is provided by
  NVDA; never imported).
- Add `NVDA+ALT+Space: render note as markdown` to:
  - the gesture list in `buildVars.py` (`addon_description`), and
  - `readme.md`.
- Translations: adding strings regenerates the `.pot`; existing locales
  (e.g. `zh_TW`) fall back to English for the new strings until translated.
- **Version bump** (`1.6` → `1.7`) is handled at **release time** per the
  existing release checklist, not as part of this change.

## Testing

- There is no offline NVDA unit-test harness in this repo; primary verification
  is **manual in NVDA**:
  - A note containing headings, lists, links, a fenced code block, and a pipe
    table renders with correct browse-mode quick-nav (H/K/L, heading levels).
  - An empty note announces "Empty note" and opens no buffer.
  - Escape closes the buffer and returns to the prior application.
- **Host-side sanity check:** confirm the vendored
  `markdown.markdown(text, extensions=[<dotted paths>])` imports and produces
  the expected HTML (correct heading tags, list/table structure) outside NVDA.
