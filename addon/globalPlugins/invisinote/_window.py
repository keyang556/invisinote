"""Top-level window discovery and relocation for the off-screen markdown render.

No NVDA imports: only the standard library + user32.dll. The selection rule is
pure, and ctypes.windll is touched lazily, so this module imports and the rule
unit-tests off-NVDA on any platform.
"""

import ctypes
from ctypes import wintypes

_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_OFFSCREEN_X = -32000
_OFFSCREEN_Y = -32000
_SWP_FRAMECHANGED = 0x0020
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080

_user32 = None
_WNDENUMPROC = None


def _u32():
	"""Lazily resolve user32 with explicit 64-bit-safe prototypes.

	Deferred so merely importing this module (e.g. in off-NVDA unit tests on a
	non-Windows box) never touches ctypes.windll or ctypes.WINFUNCTYPE, both of
	which are Windows-only.
	"""
	global _user32, _WNDENUMPROC
	if _user32 is not None:
		return _user32
	_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
	u = ctypes.windll.user32
	u.EnumWindows.argtypes = (_WNDENUMPROC, wintypes.LPARAM)
	u.EnumWindows.restype = wintypes.BOOL
	u.IsWindowVisible.argtypes = (wintypes.HWND,)
	u.IsWindowVisible.restype = wintypes.BOOL
	u.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
	u.GetWindowTextLengthW.restype = ctypes.c_int
	u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
	u.GetWindowTextW.restype = ctypes.c_int
	u.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
	u.GetWindowThreadProcessId.restype = wintypes.DWORD
	u.SetWindowPos.argtypes = (
		wintypes.HWND,
		wintypes.HWND,
		ctypes.c_int,
		ctypes.c_int,
		ctypes.c_int,
		ctypes.c_int,
		wintypes.UINT,
	)
	u.SetWindowPos.restype = wintypes.BOOL
	u.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
	u.GetWindowRect.restype = wintypes.BOOL
	u.GetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int)
	u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
	u.SetWindowLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
	u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
	_user32 = u
	return _user32


def enum_top_level_windows():
	"""Return a list of all top-level window handles (ints)."""
	u = _u32()
	handles = []

	@_WNDENUMPROC
	def _cb(hwnd, _lparam):
		handles.append(int(hwnd))
		return True

	# EnumWindows is synchronous; _cb stays alive on the call stack for its full
	# duration, so no module-level keep-alive is needed.
	u.EnumWindows(_cb, 0)
	return handles


def is_window_visible(hwnd):
	"""Return True if the window's WS_VISIBLE style is set."""
	return bool(_u32().IsWindowVisible(hwnd))


def window_title(hwnd):
	u = _u32()
	length = u.GetWindowTextLengthW(hwnd)
	if length <= 0:
		return ""
	buf = ctypes.create_unicode_buffer(length + 1)
	u.GetWindowTextW(hwnd, buf, length + 1)
	return buf.value


def window_pid(hwnd):
	"""Return the process ID that owns hwnd."""
	pid = wintypes.DWORD()
	_u32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
	return pid.value


def move_window_offscreen(hwnd):
	"""Slide hwnd to (-32000, -32000) without hiding or activating it.

	SWP_NOACTIVATE is mandatory and the window must be moved, never hidden:
	hiding or deactivating it would remove focus from the document and break
	NVDA browse mode.
	"""
	_u32().SetWindowPos(
		hwnd, 0, _OFFSCREEN_X, _OFFSCREEN_Y, 0, 0, _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE
	)


def hide_from_taskbar(hwnd):
	"""Add WS_EX_TOOLWINDOW so the off-screen window drops its taskbar / Alt-Tab
	entry. The SWP_FRAMECHANGED nudge makes the ex-style change take effect."""
	u = _u32()
	ex = u.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
	u.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, ex | _WS_EX_TOOLWINDOW)
	u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED)


def window_rect(hwnd):
	"""Return (left, top, right, bottom) screen coordinates of hwnd.

	Diagnostic: lets the move be verified from the NVDA log without sight — an
	off-screen window reads back as roughly (-32000, -32000, ...).
	"""
	rect = wintypes.RECT()
	_u32().GetWindowRect(hwnd, ctypes.byref(rect))
	return (rect.left, rect.top, rect.right, rect.bottom)


def collect_candidate_metadata(handles, exclude, our_pid):
	"""Return {hwnd: (is_visible, title)} for handles not in `exclude` that
	belong to `our_pid`. Builds the `metadata` arg for select_render_window."""
	exclude_set = set(exclude)
	meta = {}
	for h in handles:
		if h in exclude_set:
			continue
		if window_pid(h) != our_pid:
			continue
		meta[h] = (is_window_visible(h), window_title(h))
	return meta


def select_render_window(before, after, metadata, expected_title):
	"""Pick the window opened by the render out of a before/after snapshot.

	`before`, `after`: iterables of top-level window handles (ints) captured
		immediately before and after rendering.
	`metadata`: dict mapping handle -> (is_visible: bool, title: str). It should
		contain only handles belonging to our own process; handles missing from
		it are ignored (treated as another process's windows).
	`expected_title`: the dialog title we asked NVDA to use (the note filename).

	Returns the chosen handle, or None when the choice is ambiguous or nothing
	new appeared (the caller then leaves the window visible as a safe fallback).

	Single untitled candidate: returned (handles a window that opened before
	setting its title). Multiple untitled candidates: None (ambiguous).
	"""
	# Re-filter against before even though collect_candidate_metadata already
	# excludes them, so this rule is correct for any before/after/metadata input.
	before_set = set(before)
	candidates = [h for h in after if h not in before_set and h in metadata and metadata[h][0]]
	titled = [h for h in candidates if metadata[h][1] == expected_title]
	if titled:
		return titled[0]
	if len(candidates) == 1:
		return candidates[0]
	return None
