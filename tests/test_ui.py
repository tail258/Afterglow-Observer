import base64
import struct
import tkinter as tk
import unittest
from types import SimpleNamespace

from app import App, THEMES
from app_icon import ICONS, ico_bytes
from widgets import RoundedScrollbar


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.app = App(cls.root, vault="", autoload=False)
        cls.root.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_remaining_themes_apply_to_all_scrollbars(self):
        self.assertEqual(len(THEMES), 3)
        self.assertNotIn("暗夜 · 绯红", THEMES)

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        bars = [w for w in descendants(self.root) if isinstance(w, RoundedScrollbar)]
        self.assertEqual(len(bars), 3)
        for name, colors in THEMES.items():
            self.app.theme.set(name)
            self.app.apply_theme()
            for bar in bars:
                self.assertEqual(bar.thumb_color, colors["heat"][0])
                self.assertEqual(bar.active_color, colors["accent"])

    def test_scrollbar_drag_reaches_end_even_with_minimum_thumb(self):
        for orientation in ("vertical", "horizontal"):
            commands = []
            bar = RoundedScrollbar(self.root, orient=orientation, command=lambda *args: commands.append(args))
            bar.winfo_height = lambda: 204
            bar.winfo_width = lambda: 204
            bar.set(0, 0.01)
            self.assertEqual(bar.geometry_values()[1], 28)
            bar.press(SimpleNamespace(x=10, y=10))
            bar.drag(SimpleNamespace(x=2000, y=2000))
            self.assertEqual(commands[-1], ("moveto", 0.99))
            bar.release(None)
            bar.set(0, 1)
            self.assertEqual(bar.find_all(), ())
            before = len(commands)
            bar.press(SimpleNamespace(x=10, y=10))
            self.assertEqual(len(commands), before)
            bar.destroy()

    def test_scrollbar_wheel_and_keyboard_commands(self):
        commands = []
        bar = RoundedScrollbar(self.root, command=lambda *args: commands.append(args))
        bar.set(0, 0.25)
        bar.wheel(SimpleNamespace(delta=-120))
        bar.wheel(SimpleNamespace(delta=240))
        bar.move(1)
        self.assertEqual(commands, [("scroll", 1, "units"), ("scroll", -2, "units"), ("moveto", 0.75)])
        bar.destroy()

    def test_icon_decodes_in_tk_and_ico_contains_multiple_sizes(self):
        content = ico_bytes()
        self.assertEqual(struct.unpack_from("<HHH", content), (0, 1, len(ICONS)))
        for index, (size, encoded) in enumerate(ICONS):
            image = tk.PhotoImage(master=self.root, data=encoded)
            self.assertEqual((image.width(), image.height()), (size, size))
            self.assertTrue(image.transparency_get(0, 0))
            self.assertTrue(image.transparency_get(size - 1, size - 1))
            self.assertFalse(image.transparency_get(size // 2, size // 2))
            length, offset = struct.unpack_from("<II", content, 6 + index * 16 + 8)
            self.assertEqual(content[offset:offset + length], base64.b64decode(encoded))


if __name__ == "__main__":
    unittest.main()
