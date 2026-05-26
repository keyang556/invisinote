import os
import sys
import unittest

_MOD_DIR = os.path.abspath(
	os.path.join(os.path.dirname(__file__), "..", "addon", "globalPlugins", "invisinote")
)
if _MOD_DIR not in sys.path:
	sys.path.insert(0, _MOD_DIR)

import _window  # noqa: E402


class SelectRenderWindowTests(unittest.TestCase):
	def test_single_new_visible_window_is_selected(self):
		before = {10, 20, 30}
		after = [10, 20, 30, 99]
		metadata = {99: (True, "note.txt")}
		self.assertEqual(_window.select_render_window(before, after, metadata, "note.txt"), 99)

	def test_title_match_wins_when_several_new_windows(self):
		before = {1}
		after = [1, 2, 3]
		metadata = {2: (True, "other"), 3: (True, "note.txt")}
		self.assertEqual(_window.select_render_window(before, after, metadata, "note.txt"), 3)

	def test_single_new_untitled_candidate_is_selected(self):
		"""Window opened before its title was set — single-candidate fallback fires."""
		before = {1}
		after = [1, 55]
		metadata = {55: (True, "")}  # empty title, not yet set
		self.assertEqual(_window.select_render_window(before, after, metadata, "note.txt"), 55)

	def test_no_title_match_and_multiple_candidates_returns_none(self):
		before = {1}
		after = [1, 2, 3]
		metadata = {2: (True, "a"), 3: (True, "b")}
		self.assertIsNone(_window.select_render_window(before, after, metadata, "note.txt"))

	def test_other_process_window_is_ignored(self):
		before = {1}
		after = [1, 42]
		metadata = {}  # 42 belongs to another process -> absent from metadata
		self.assertIsNone(_window.select_render_window(before, after, metadata, "note.txt"))

	def test_invisible_window_is_ignored(self):
		before = {1}
		after = [1, 7]
		metadata = {7: (False, "note.txt")}
		self.assertIsNone(_window.select_render_window(before, after, metadata, "note.txt"))

	def test_no_new_windows_returns_none(self):
		before = {1, 2}
		after = [1, 2]
		self.assertIsNone(_window.select_render_window(before, after, {}, "note.txt"))


if __name__ == "__main__":
	unittest.main()
